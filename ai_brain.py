import os
import json
import re
import inspect
import urllib.request
import urllib.error
from pathlib import Path
from typing import get_type_hints

from dotenv import load_dotenv

# =========================
# UBICACIÓN Y CONFIGURACIÓN
# =========================
MONIKA_HOME = Path(__file__).resolve().parent
load_dotenv(MONIKA_HOME / ".env")

# =========================
# MODELO LOCAL (OLLAMA)
# =========================
# Monika funciona 100% local, sin internet ni API en la nube. El
# modelo por defecto es qwen3:4b (ligero, ~2.5GB, buen español y
# buen uso de herramientas, cabe en una laptop de 8GB cuando Monika
# corre casi sola). Si la laptop se siente pesada, cambia
# OLLAMA_MODEL en el .env a "qwen3:1.7b" (más ligero, piensa peor)
# sin tocar código. Instálalo con: ollama pull qwen3:4b
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.9"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
MAX_RONDAS_HERRAMIENTAS = 5


# =========================
# QUITAR EL "PENSAMIENTO" DE QWEN3
# =========================
# qwen3 trae un modo de razonamiento ("thinking") que va lento y
# desperdicia tokens. Se desactiva pidiendo "think": false en la
# petición, y por si alguna versión no lo respeta, estas funciones
# descartan cualquier bloque <think>...</think> del texto, aunque
# esté partido entre varios fragmentos del streaming.

def _limpiar_pensamiento(texto):
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


class _FiltroPensamiento:
    """Filtro para streaming: deja pasar solo el texto visible y se
    traga los bloques <think>...</think> aunque lleguen partidos."""

    def __init__(self):
        self._buffer = ""
        self._apertura = "<think>"
        self._cierre = "</think>"

    def recibir(self, fragmento):
        self._buffer += fragmento
        salida = []

        while True:
            apertura = self._buffer.find(self._apertura)

            if apertura == -1:
                # Sin apertura completa: ¿hay una a medias al final?
                # (p. ej. "<th" esperando el resto) — se retiene para
                # no mostrarla por error.
                inicio_sospechoso = self._buffer.rfind("<")
                if inicio_sospechoso != -1 and self._apertura.startswith(
                    self._buffer[inicio_sospechoso:]
                ):
                    salida.append(self._buffer[:inicio_sospechoso])
                    self._buffer = self._buffer[inicio_sospechoso:]
                    break

                salida.append(self._buffer)
                self._buffer = ""
                break

            # Lo de antes de la apertura es visible; lo que siga hasta
            # el cierre es razonamiento y se descarta.
            salida.append(self._buffer[:apertura])
            resto = self._buffer[apertura:]
            cierre = resto.find(self._cierre)

            if cierre == -1:
                self._buffer = ""
                break

            self._buffer = resto[cierre + len(self._cierre):]

        return "".join(salida)


# =========================
# GENERAR ESQUEMA DE HERRAMIENTA
# =========================
# Ollama necesita un JSON Schema explícito por herramienta. Este
# generador lo construye automáticamente a partir de
# los type hints y el docstring "Args:" que ya usan todas las
# herramientas de Monika, así no hay que mantener dos copias.
def _esquema_desde_funcion(funcion):
    firma = inspect.signature(funcion)

    try:
        pistas = get_type_hints(funcion)
    except Exception:
        pistas = {}

    doc = inspect.getdoc(funcion) or ""
    descripciones = {}

    if "Args:" in doc:
        bloque_args = doc.split("Args:", 1)[1]
        if "Returns:" in bloque_args:
            bloque_args = bloque_args.split("Returns:", 1)[0]

        nombre_actual = None
        texto_actual = []

        for linea in bloque_args.splitlines():
            linea = linea.strip()
            if not linea:
                continue

            partes = linea.split(":", 1)
            if len(partes) == 2 and partes[0].strip().replace("_", "").isalnum():
                if nombre_actual:
                    descripciones[nombre_actual] = " ".join(texto_actual).strip()
                nombre_actual = partes[0].strip()
                texto_actual = [partes[1].strip()]
            else:
                texto_actual.append(linea)

        if nombre_actual:
            descripciones[nombre_actual] = " ".join(texto_actual).strip()

    tipos_json = {str: "string", int: "integer", float: "number", bool: "boolean"}
    propiedades = {}
    requeridos = []

    for nombre_param, parametro in firma.parameters.items():
        tipo_python = pistas.get(nombre_param, str)
        propiedades[nombre_param] = {
            "type": tipos_json.get(tipo_python, "string"),
            "description": descripciones.get(nombre_param, ""),
        }
        if parametro.default is inspect.Parameter.empty:
            requeridos.append(nombre_param)

    descripcion_funcion = doc.split("Args:")[0].strip().split("\n\n")[0]

    return {
        "type": "function",
        "function": {
            "name": funcion.__name__,
            "description": descripcion_funcion,
            "parameters": {
                "type": "object",
                "properties": propiedades,
                "required": requeridos,
            },
        },
    }


# =========================
# LLAMAR A OLLAMA (CON HERRAMIENTAS)
# =========================
def _llamar_ollama(prompt, herramientas_python, on_chunk=None):
    """Hace el bucle de herramientas contra Ollama. Si se pasa
    on_chunk, usa streaming y va avisando con cada fragmento de texto
    a medida que llega; si no, se comporta igual que siempre."""
    mapa_funciones = {f.__name__: f for f in (herramientas_python or [])}
    esquemas = [_esquema_desde_funcion(f) for f in (herramientas_python or [])]

    mensajes = [{"role": "user", "content": prompt}]

    # Parámetros pensados para una laptop de 8GB: contexto moderado
    # (la plática + memoria + instrucciones caben con holgura y se
    # gasta menos RAM), respuesta breve (Monika es breve por diseño)
    # y "think": false para que qwen3 responda directo y rápido.
    opciones = {
        "num_ctx": OLLAMA_NUM_CTX,
        "num_predict": OLLAMA_NUM_PREDICT,
        "temperature": OLLAMA_TEMPERATURE,
    }

    for _ in range(MAX_RONDAS_HERRAMIENTAS):
        cuerpo = {
            "model": OLLAMA_MODEL,
            "messages": mensajes,
            "stream": on_chunk is not None,
            "think": False,
            "options": opciones,
        }
        if esquemas:
            cuerpo["tools"] = esquemas

        peticion = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(peticion, timeout=OLLAMA_TIMEOUT) as respuesta:
                if on_chunk is None:
                    datos = json.loads(respuesta.read().decode("utf-8"))
                    mensaje = datos.get("message", {})
                    llamadas = mensaje.get("tool_calls")

                    if not llamadas:
                        return _limpiar_pensamiento(
                            mensaje.get("content", "")
                        ).strip()

                    mensajes.append(mensaje)
                else:
                    contenido_total = ""
                    filtro = _FiltroPensamiento()
                    llamadas = []

                    for linea in respuesta:
                        linea = linea.decode("utf-8").strip()
                        if not linea:
                            continue
                        datos = json.loads(linea)
                        mensaje = datos.get("message", {})
                        fragmento = mensaje.get("content", "")
                        if fragmento:
                            contenido_total += fragmento
                            visible = filtro.recibir(fragmento)
                            if visible:
                                on_chunk(visible)
                        llamadas_parciales = mensaje.get("tool_calls")
                        if llamadas_parciales:
                            llamadas.extend(llamadas_parciales)

                    if not llamadas:
                        return _limpiar_pensamiento(contenido_total).strip()

                    mensajes.append({
                        "role": "assistant",
                        "content": contenido_total,
                        "tool_calls": llamadas,
                    })
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise RuntimeError(
                    f"El modelo {OLLAMA_MODEL} no está descargado. "
                    f"Ejecuta: ollama pull {OLLAMA_MODEL}"
                ) from error
            raise RuntimeError(
                f"Ollama respondió con error {error.code}."
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                "No pude contactar a Ollama local "
                f"({OLLAMA_URL}): {error}. "
                "¿Está corriendo el servicio ollama?"
            ) from error

        for llamada in llamadas:
            nombre_funcion = llamada.get("function", {}).get("name", "")
            argumentos = llamada.get("function", {}).get("arguments", {})

            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos)
                except Exception:
                    argumentos = {}

            funcion = mapa_funciones.get(nombre_funcion)

            if funcion:
                try:
                    resultado = funcion(**argumentos)
                except Exception as error:
                    resultado = f"Error ejecutando {nombre_funcion}: {error}"
            else:
                resultado = f"Herramienta desconocida: {nombre_funcion}"

            mensajes.append({
                "role": "tool",
                "content": str(resultado),
            })

    return (
        "Se me enredaron las herramientas con esto — "
        "¿me lo repites de forma más simple?"
    )


# =========================
# GENERAR RESPUESTA (PUNTO DE ENTRADA)
# =========================
def generar_respuesta_stream(prompt, on_chunk, herramientas=None):
    """Genera una respuesta con el modelo local y va llamando a
    on_chunk(texto) con cada fragmento a medida que el modelo lo
    genera, para mostrarlo en vivo en la interfaz sin esperar a que
    termine.

    Returns:
        Una tupla (texto_respuesta, fuente). fuente siempre es
        "ollama", se conserva para no romper a quien llame.
    """
    texto = _llamar_ollama(prompt, herramientas, on_chunk=on_chunk)
    return texto, "ollama"


def generar_respuesta(prompt, herramientas=None):
    """Genera una respuesta de texto con el modelo local (Ollama).

    Returns:
        Una tupla (texto_respuesta, fuente), donde fuente es "ollama".
    """
    return generar_respuesta_stream(
        prompt,
        lambda _fragmento: None,
        herramientas,
    )
