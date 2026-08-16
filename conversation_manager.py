import json
from pathlib import Path


# =========================
# UBICACIÓN DE LA CONVERSACIÓN
# =========================
# Ruta absoluta, igual que memoria.json y estado_monika.json: así la
# app de escritorio y el comando "moni vs" leen y escriben siempre el
# mismo archivo, sin importar desde dónde se ejecuten.
ARCHIVO_CONVERSACION = str(
    Path(__file__).resolve().parent / "conversacion.json"
)

# Cuántos mensajes se conservan como máximo en el archivo. No hace
# falta guardar el historial completo de toda la vida del proyecto.
LIMITE_GUARDADO = 200


class ConversationManager:
    """Historial de conversación compartido entre la app de escritorio
    y el CLI (moni vs), para que Monika sea la misma en ambos lugares,
    no dos versiones con memorias separadas.

    Antes de cada lectura/escritura recarga desde disco, para reducir
    (no eliminar del todo) el riesgo de que dos sesiones abiertas al
    mismo tiempo se pisen la una a la otra.
    """

    def __init__(self):
        self.mensajes = self._cargar()

    # =========================
    # CARGAR
    # =========================
    def _cargar(self):
        archivo = Path(ARCHIVO_CONVERSACION)

        if not archivo.exists():
            return []

        try:
            with open(archivo, "r", encoding="utf-8") as file:
                datos = json.load(file)
                if isinstance(datos, list):
                    return datos
        except Exception as error:
            print("Error cargando conversación compartida:", error)

        return []

    # =========================
    # GUARDAR
    # =========================
    def _guardar(self):
        try:
            with open(ARCHIVO_CONVERSACION, "w", encoding="utf-8") as file:
                json.dump(
                    self.mensajes[-LIMITE_GUARDADO:],
                    file,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as error:
            print("Error guardando conversación compartida:", error)

    # =========================
    # AGREGAR MENSAJE
    # =========================
    def add(self, role, content, origen):
        # Recarga primero, para no pisar lo que la otra instancia
        # (app o terminal) haya guardado mientras tanto.
        self.mensajes = self._cargar()

        self.mensajes.append({
            "role": role,
            "content": content,
            "origen": origen,
        })

        self.mensajes = self.mensajes[-LIMITE_GUARDADO:]
        self._guardar()

    # =========================
    # OBTENER TEXTO RECIENTE
    # =========================
    def get_recent_text(self, n=12):
        self.mensajes = self._cargar()
        recientes = self.mensajes[-n:]

        texto = ""
        for item in recientes:
            etiqueta = "app" if item.get("origen") == "app" else "terminal"
            texto += f"[{etiqueta}] {item['role']}: {item['content']}\n"

        return texto
