import os
import subprocess
import json
import shutil
import urllib.request


# =========================
# NAVEGADORES CON SOPORTE CDP
# =========================
# Fragmento de la clase de ventana (en minúsculas) -> puerto de
# depuración remota. Funciona con cualquier navegador basado en
# Chromium (Brave, Chrome, Chromium, Edge) si se lanza con la bandera
# --remote-debugging-port=9222 (ver instrucciones aparte).
NAVEGADORES_CDP = {
    "brave": 9222,
    "chrome": 9222,
    "chromium": 9222,
    "edge": 9222,
}


# =========================
# EJECUTAR COMANDO
# =========================
def _ejecutar(comando):
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=5
        )
        return resultado.stdout.strip(), resultado.stderr.strip()
    except Exception as error:
        return "", str(error)


# =========================
# DETECTAR ENTORNO DE ESCRITORIO
# =========================
def _usar_hyprland():
    return (
        bool(shutil.which("hyprctl"))
        and bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
    )


def _usar_kde():
    return bool(shutil.which("kdotool"))


# =========================
# OBTENER PESTAÑA ACTIVA (CDP)
# =========================
def _obtener_pestana_navegador(puerto):
    """Consulta el protocolo de depuración remota del navegador
    (si está habilitado) para saber en qué página está Yiss de verdad,
    no solo el título de la ventana."""
    try:
        with urllib.request.urlopen(
            f"http://localhost:{puerto}/json",
            timeout=1
        ) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except Exception:
        return None

    pestanas = [
        pestana for pestana in datos
        if pestana.get("type") == "page"
        and not pestana.get("url", "").startswith("chrome-extension://")
    ]

    if not pestanas:
        return None

    activa = pestanas[0]
    return activa.get("url"), activa.get("title")


def _agregar_url_si_es_navegador(aplicacion, resultado):
    clase_normalizada = aplicacion.lower()

    for fragmento, puerto in NAVEGADORES_CDP.items():
        if fragmento in clase_normalizada:
            pestana = _obtener_pestana_navegador(puerto)

            if pestana:
                url, _ = pestana
                resultado += f" Está navegando en: {url}"
            else:
                resultado += (
                    " (No se pudo leer la URL exacta: la depuración "
                    "remota del navegador no está activada.)"
                )

            break

    return resultado


# =========================
# ACTIVIDAD ACTUAL (HYPRLAND)
# =========================
def _actividad_hyprland():
    salida, error = _ejecutar(["hyprctl", "activewindow", "-j"])

    if not salida:
        return "No parece haber ninguna ventana activa en este momento."

    try:
        datos = json.loads(salida)
    except Exception:
        return "No pude interpretar la ventana activa."

    aplicacion = (
        datos.get("class")
        or datos.get("initialClass")
        or "una aplicación desconocida"
    )
    titulo = datos.get("title", "")

    resultado = f"Aplicación activa: {aplicacion}."
    if titulo:
        resultado += f" Título de la ventana: {titulo}."

    return _agregar_url_si_es_navegador(aplicacion, resultado)


# =========================
# ACTIVIDAD ACTUAL (KDE / KWIN)
# =========================
def _actividad_kde():
    ventana_id, error = _ejecutar(["kdotool", "getactivewindow"])

    if not ventana_id:
        return "No parece haber ninguna ventana activa en este momento."

    ventana_id = ventana_id.splitlines()[0].strip()

    clase, _ = _ejecutar(
        ["kdotool", "getwindowclassname", ventana_id]
    )
    titulo, _ = _ejecutar(
        ["kdotool", "getwindowname", ventana_id]
    )

    aplicacion = clase or "una aplicación desconocida"

    resultado = f"Aplicación activa: {aplicacion}."
    if titulo:
        resultado += f" Título de la ventana: {titulo}."

    return _agregar_url_si_es_navegador(aplicacion, resultado)


# =========================
# VER ACTIVIDAD ACTUAL
# =========================
def ver_actividad_actual() -> str:
    """Consulta qué aplicación y ventana está usando Yiss en este momento.
    Si es un navegador basado en Chromium (Brave, Chrome) con la
    depuración remota habilitada, también obtiene la página exacta
    en la que está, no solo el título de la ventana.

    Funciona tanto en Hyprland como en KDE Plasma (X11 o Wayland).

    Returns:
        Una descripción de la aplicación activa, el título de su
        ventana, y si aplica, la URL exacta que está viendo.
    """
    if _usar_hyprland():
        return _actividad_hyprland()

    if _usar_kde():
        return _actividad_kde()

    return (
        "No pude detectar tu actividad actual: no encontré ni "
        "hyprctl (Hyprland) ni kdotool (KDE Plasma) instalados."
    )


# =========================
# LISTAR VENTANAS (HYPRLAND)
# =========================
def _listar_hyprland():
    salida, error = _ejecutar(["hyprctl", "clients", "-j"])

    if not salida:
        return "No parece haber ventanas abiertas en este momento."

    try:
        ventanas = json.loads(salida)
    except Exception:
        return "No pude interpretar la lista de ventanas."

    if not ventanas:
        return "No hay ventanas abiertas en este momento."

    lineas = []
    for ventana in ventanas:
        clase = ventana.get("class", "desconocida")
        titulo = ventana.get("title", "")

        if titulo:
            lineas.append(f"- {clase}: {titulo}")
        else:
            lineas.append(f"- {clase}")

    return "\n".join(lineas)


# =========================
# LISTAR VENTANAS (KDE / KWIN)
# =========================
def _listar_kde():
    salida, error = _ejecutar(["kdotool", "search", "."])

    if not salida:
        return "No hay ventanas abiertas en este momento."

    ids = [linea.strip() for linea in salida.splitlines() if linea.strip()]

    lineas = []
    for ventana_id in ids:
        clase, _ = _ejecutar(
            ["kdotool", "getwindowclassname", ventana_id]
        )
        titulo, _ = _ejecutar(
            ["kdotool", "getwindowname", ventana_id]
        )

        clase = clase or "desconocida"

        if titulo:
            lineas.append(f"- {clase}: {titulo}")
        else:
            lineas.append(f"- {clase}")

    if not lineas:
        return "No hay ventanas abiertas en este momento."

    return "\n".join(lineas)


# =========================
# LISTAR VENTANAS ABIERTAS
# =========================
def listar_ventanas_abiertas() -> str:
    """Lista todas las ventanas/aplicaciones que Yiss tiene abiertas
    actualmente en su escritorio. Funciona tanto en Hyprland como en
    KDE Plasma (X11 o Wayland).

    Returns:
        Una lista con el nombre de cada aplicación abierta y el título
        de su ventana, o un mensaje de error si no se pudo obtener.
    """
    if _usar_hyprland():
        return _listar_hyprland()

    if _usar_kde():
        return _listar_kde()

    return (
        "No pude listar tus ventanas: no encontré ni hyprctl "
        "(Hyprland) ni kdotool (KDE Plasma) instalados."
    )


# =========================
# ABRIR APLICACIÓN
# =========================
def abrir_aplicacion(comando: str) -> str:
    """Abre una aplicación en la computadora de Yiss. Funciona en
    cualquier entorno de escritorio, no depende de Hyprland ni KDE.

    Args:
        comando: El comando o nombre del ejecutable a abrir (por ejemplo
            "firefox", "code", "brave", "kitty").

    Returns:
        Mensaje confirmando que se lanzó la aplicación, o un error si
        no se pudo ejecutar.
    """
    try:
        subprocess.Popen(
            comando.split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return f"Abrí '{comando}'."
    except Exception as error:
        return f"No pude abrir '{comando}': {error}"


# =========================
# CONTROL DE VOLUMEN
# =========================
def controlar_volumen(accion: str, cantidad: int = 5) -> str:
    """Controla el volumen del sistema (usa PipeWire/wpctl, funciona
    igual en Hyprland y en KDE Plasma con PipeWire).

    Args:
        accion: Una de "subir", "bajar", "silenciar", "activar" (para
            quitar el silencio).
        cantidad: Porcentaje a subir o bajar cuando la acción es "subir"
            o "bajar". Se ignora en las demás acciones.

    Returns:
        Mensaje confirmando la acción realizada, o un error si algo
        falló.
    """
    if not shutil.which("wpctl"):
        return "No puedo controlar el volumen (wpctl no está disponible)."

    if accion == "subir":
        comando = [
            "wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{cantidad}%+"
        ]
    elif accion == "bajar":
        comando = [
            "wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{cantidad}%-"
        ]
    elif accion == "silenciar":
        comando = [
            "wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"
        ]
    elif accion == "activar":
        comando = [
            "wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"
        ]
    else:
        return f"No reconozco esa acción de volumen: {accion}"

    _, error = _ejecutar(comando)

    if error:
        return f"No pude ajustar el volumen: {error}"

    return f"Listo, volumen: {accion}."