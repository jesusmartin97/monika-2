import os
import re
import json
import subprocess
import difflib
import py_compile
from pathlib import Path


# =========================
# UBICACIÓN DE MONIKA
# =========================
# Este archivo vive en ~/Monika/tools/dev_tools.py, así que su
# carpeta padre-del-padre es la raíz real del proyecto, sin importar
# desde dónde se ejecute Monika (igual que memoria.json y
# estado_monika.json). Esto le permite autodiagnosticarse a sí misma.
MONIKA_HOME = Path(__file__).resolve().parent.parent


# =========================
# CARPETAS A IGNORAR
# =========================
IGNORAR = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", ".next", ".cache", "coverage",
    "target", ".idea", ".vscode", "vendor"
}


def _resolver(ruta):
    return Path(ruta).expanduser().resolve()


# =========================
# AUTODIAGNÓSTICO
# =========================
def autodiagnostico(ruta: str = "") -> str:
    """Revisa la integridad de un proyecto de Python compilando cada
    archivo .py (sin ejecutarlo) para detectar errores de sintaxis o
    archivos rotos de forma rápida, sin gastar una llamada al modelo
    por archivo. Por defecto revisa el propio código fuente de
    Monika, para poder diagnosticarse a sí misma cuando algo falla.

    Args:
        ruta: Carpeta del proyecto a revisar. Si se deja vacío, se
            revisa la propia carpeta de Monika (~/Monika).

    Returns:
        Un mensaje confirmando que todo compila bien, o la lista
        exacta de archivos con errores de sintaxis y su detalle
        (archivo y línea), lista para investigar con
        leer_archivo_codigo y proponer una corrección.
    """
    base = _resolver(ruta) if ruta else MONIKA_HOME

    if not base.exists() or not base.is_dir():
        return f"No encontré esa carpeta para revisar: {base}"

    problemas = []

    for archivo in base.rglob("*.py"):
        if any(parte in IGNORAR for parte in archivo.parts):
            continue

        try:
            py_compile.compile(str(archivo), doraise=True)
        except py_compile.PyCompileError as error:
            problemas.append(f"{archivo}: {error.msg}")
        except Exception as error:
            problemas.append(f"{archivo}: {error}")

    if not problemas:
        return (
            f"Revisé {base} — todo compila bien, no encontré "
            "errores de sintaxis."
        )

    return (
        f"Encontré {len(problemas)} archivo(s) con problemas en "
        f"{base}:\n" + "\n".join(problemas)
    )


# =========================
# EXPLORAR PROYECTO
# =========================
def explorar_proyecto(ruta: str, profundidad: int = 3) -> str:
    """Explora la estructura de carpetas y archivos de un proyecto de
    código, ignorando carpetas pesadas o generadas automáticamente
    (node_modules, .git, venv, dist, build, etc).

    Args:
        ruta: Ruta completa a la carpeta raíz del proyecto.
        profundidad: Qué tan profundo explorar los subniveles de
            carpetas (por defecto 3).

    Returns:
        Un árbol de texto con la estructura del proyecto, o un
        mensaje de error si la carpeta no existe.
    """
    base = _resolver(ruta)

    if not base.exists() or not base.is_dir():
        return f"No encontré esa carpeta de proyecto: {base}"

    lineas = [f"{base}/"]

    def recorrer(carpeta, nivel):
        if nivel > profundidad:
            return

        try:
            items = sorted(os.listdir(carpeta))
        except Exception:
            return

        for item in items:
            if item in IGNORAR or item.startswith("."):
                continue

            ruta_item = carpeta / item
            prefijo = "  " * nivel + "- "

            if ruta_item.is_dir():
                lineas.append(f"{prefijo}{item}/")
                recorrer(ruta_item, nivel + 1)
            else:
                lineas.append(f"{prefijo}{item}")

    recorrer(base, 1)

    if len(lineas) == 1:
        return "La carpeta del proyecto está vacía (o solo tiene carpetas ignoradas)."

    return "\n".join(lineas)


# =========================
# BUSCAR EN EL PROYECTO
# =========================
def buscar_en_proyecto(ruta_proyecto: str, patron: str) -> str:
    """Busca un texto o expresión regular dentro de todos los archivos
    de código del proyecto (como un grep), para encontrar en qué
    archivos y líneas aparece algo (un nombre de función, una
    variable, un texto de error, un endpoint, etc) en vez de tener
    que adivinar qué archivo leer.

    Args:
        ruta_proyecto: Carpeta raíz del proyecto donde buscar.
        patron: Texto o expresión regular a buscar (no distingue
            mayúsculas/minúsculas).

    Returns:
        Una lista de coincidencias con archivo, número de línea, y
        el contenido de esa línea. Limitado a 60 resultados.
    """
    base = _resolver(ruta_proyecto)

    if not base.exists() or not base.is_dir():
        return f"No encontré esa carpeta de proyecto: {base}"

    try:
        expresion = re.compile(patron, re.IGNORECASE)
    except re.error as error:
        return f"Ese patrón de búsqueda no es válido: {error}"

    resultados = []
    limite = 60

    for carpeta_actual, subcarpetas, archivos in os.walk(base):
        subcarpetas[:] = [
            d for d in subcarpetas
            if d not in IGNORAR and not d.startswith(".")
        ]

        if len(resultados) >= limite:
            break

        for nombre_archivo in sorted(archivos):
            if len(resultados) >= limite:
                break

            ruta_archivo = Path(carpeta_actual) / nombre_archivo

            try:
                if ruta_archivo.stat().st_size > 2_000_000:
                    continue
                contenido = ruta_archivo.read_text(encoding="utf-8")
            except Exception:
                continue

            for numero_linea, linea in enumerate(contenido.splitlines(), start=1):
                if expresion.search(linea):
                    resultados.append(
                        f"{ruta_archivo}:{numero_linea}: {linea.strip()}"
                    )
                    if len(resultados) >= limite:
                        break

    if not resultados:
        return f"No encontré coincidencias para '{patron}' en el proyecto."

    encabezado = f"{len(resultados)} coincidencia(s) para '{patron}':\n\n"
    return encabezado + "\n".join(resultados)


# =========================
# LEER ARCHIVO DE CÓDIGO
# =========================
def leer_archivo_codigo(ruta: str) -> str:
    """Lee el contenido completo de un archivo de código fuente
    (texto plano: .py, .js, .jsx, .ts, .tsx, .json, .html, .css,
    .md, etc), con números de línea para poder referenciar líneas
    exactas al proponer cambios.

    Args:
        ruta: Ruta completa del archivo a leer.

    Returns:
        El contenido del archivo con números de línea, o un mensaje
        de error si no existe o no se puede leer como texto.
    """
    archivo = _resolver(ruta)

    if not archivo.exists() or not archivo.is_file():
        return f"No existe ese archivo: {archivo}"

    try:
        contenido = archivo.read_text(encoding="utf-8")
    except Exception as error:
        return f"No pude leer el archivo (¿es binario?): {error}"

    lineas = contenido.splitlines()
    numeradas = "\n".join(
        f"{i + 1}: {linea}" for i, linea in enumerate(lineas)
    )

    return numeradas or "(el archivo está vacío)"


# =========================
# VERIFICACIÓN BÁSICA DE SINTAXIS
# =========================
def _verificar_sintaxis(ruta: Path, contenido: str):
    """Devuelve un mensaje de advertencia si detecta un problema obvio
    de sintaxis, o None si está bien o no se pudo verificar ese tipo
    de archivo. Es una revisión básica, no un linter real."""
    extension = ruta.suffix.lower()

    if extension == ".py":
        try:
            compile(contenido, str(ruta), "exec")
        except SyntaxError as error:
            return f"⚠ Advertencia: error de sintaxis Python: {error}"
        return None

    if extension == ".json":
        try:
            json.loads(contenido)
        except Exception as error:
            return f"⚠ Advertencia: JSON inválido: {error}"
        return None

    if extension in (".js", ".jsx", ".ts", ".tsx", ".css", ".html"):
        pares = {"(": ")", "[": "]", "{": "}"}
        cierres = {v: k for k, v in pares.items()}
        pila = []

        for caracter in contenido:
            if caracter in pares:
                pila.append(caracter)
            elif caracter in cierres:
                if not pila or pila[-1] != cierres[caracter]:
                    return (
                        "⚠ Advertencia: los paréntesis/llaves/corchetes "
                        "no parecen estar balanceados (revisión básica, "
                        "puede ser falso positivo en JSX/TS)."
                    )
                pila.pop()

        if pila:
            return (
                "⚠ Advertencia: quedan paréntesis/llaves/corchetes sin "
                "cerrar (revisión básica, puede ser falso positivo en "
                "JSX/TS)."
            )
        return None

    return None


# =========================
# CAMBIOS DE CÓDIGO PENDIENTES
# =========================
# Diccionario ruta -> {contenido_nuevo, motivo}. Puede haber varios
# cambios pendientes a la vez, en archivos distintos.
_cambios_pendientes = {}


def proponer_cambio_codigo(ruta: str, contenido_nuevo: str, motivo: str) -> str:
    """Propone un cambio a un archivo de código, mostrando exactamente
    qué cambiaría (como un diff), SIN modificar el archivo todavía.
    Puedes tener VARIOS cambios pendientes al mismo tiempo en
    archivos distintos (por ejemplo, una tarea que toca 3 archivos):
    cada uno se guarda por separado y se aprueba/aplica usando su
    propia ruta.

    Args:
        ruta: Ruta completa del archivo a modificar (si no existe
            todavía, se creará al aplicar el cambio).
        contenido_nuevo: El contenido COMPLETO que tendría el archivo
            si se aprueba el cambio (no un fragmento, el archivo
            entero).
        motivo: Explicación breve y clara de qué se está cambiando y
            por qué.

    Returns:
        Un diff mostrando el cambio propuesto (y una advertencia si
        se detecta un problema de sintaxis obvio), para mostrárselo a
        Yiss y pedirle aprobación antes de llamar a
        aplicar_cambio_pendiente con esta misma ruta.
    """
    archivo = _resolver(ruta)

    contenido_actual = ""
    if archivo.exists():
        try:
            contenido_actual = archivo.read_text(encoding="utf-8")
        except Exception:
            contenido_actual = ""

    diff = "\n".join(
        difflib.unified_diff(
            contenido_actual.splitlines(),
            contenido_nuevo.splitlines(),
            fromfile=f"actual: {archivo.name}",
            tofile=f"propuesto: {archivo.name}",
            lineterm=""
        )
    )

    global _cambios_pendientes
    _cambios_pendientes[str(archivo)] = {
        "contenido_nuevo": contenido_nuevo,
        "motivo": motivo,
    }

    if not diff:
        return (
            "El contenido propuesto es idéntico al actual, no hay "
            "ningún cambio real que aplicar."
        )

    advertencia = _verificar_sintaxis(archivo, contenido_nuevo)

    resultado = f"Cambio propuesto para {archivo}\nMotivo: {motivo}\n\n{diff}\n\n"

    if advertencia:
        resultado += f"{advertencia}\n\n"

    resultado += (
        f"Este cambio está PENDIENTE (ruta exacta: {archivo}). Solo "
        "se aplica de verdad si Yiss aprueba explícitamente y se "
        "llama a aplicar_cambio_pendiente con esta misma ruta."
    )

    return resultado


def listar_cambios_pendientes() -> str:
    """Lista todos los cambios de código pendientes de aprobación en
    este momento (puede haber varios, de una tarea que toca varios
    archivos a la vez).

    Returns:
        Una lista de rutas y motivos de cada cambio pendiente, o un
        aviso de que no hay ninguno.
    """
    if not _cambios_pendientes:
        return "No hay ningún cambio de código pendiente ahora mismo."

    lineas = [
        f"- {ruta}: {info['motivo']}"
        for ruta, info in _cambios_pendientes.items()
    ]

    return "Cambios pendientes:\n" + "\n".join(lineas)


def aplicar_cambio_pendiente(ruta: str) -> str:
    """Aplica de verdad un cambio de código específico que fue
    propuesto con proponer_cambio_codigo. SOLO se debe llamar después
    de que Yiss haya dado su aprobación explícita para ESE archivo en
    particular en su mensaje más reciente. Nunca la llames sin esa
    aprobación explícita.

    Args:
        ruta: Ruta completa exacta del archivo cuyo cambio pendiente
            se va a aplicar (la misma ruta usada al proponerlo).

    Returns:
        Mensaje confirmando que el archivo fue modificado, o un
        error si no había ningún cambio pendiente para esa ruta.
    """
    global _cambios_pendientes

    archivo = _resolver(ruta)
    clave = str(archivo)

    if clave not in _cambios_pendientes:
        if len(_cambios_pendientes) == 1:
            clave = next(iter(_cambios_pendientes))
            archivo = Path(clave)
        else:
            return f"No hay ningún cambio pendiente para: {archivo}"

    info = _cambios_pendientes.pop(clave)
    return _escribir_con_respaldo(archivo, info["contenido_nuevo"])


def aplicar_todos_los_cambios_pendientes() -> str:
    """Aplica TODOS los cambios de código pendientes de una sola vez.
    SOLO se debe llamar cuando Yiss aprobó explícitamente aplicar
    todos los cambios juntos (dijo algo como "aplica todo" o "sí a
    los dos"), nunca como acción por defecto.

    Returns:
        Un resumen de qué archivos se modificaron y si hubo errores.
    """
    global _cambios_pendientes

    if not _cambios_pendientes:
        return "No hay ningún cambio pendiente."

    aplicados = []
    errores = []

    for ruta_str, info in list(_cambios_pendientes.items()):
        archivo = Path(ruta_str)
        resultado = _escribir_con_respaldo(archivo, info["contenido_nuevo"])
        if resultado.startswith("Cambio aplicado"):
            aplicados.append(ruta_str)
        else:
            errores.append(f"{ruta_str}: {resultado}")

    _cambios_pendientes = {}

    resumen = f"Aplicados {len(aplicados)} cambio(s):\n" + "\n".join(aplicados)

    if errores:
        resumen += "\n\nErrores:\n" + "\n".join(errores)

    return resumen


def descartar_cambio_pendiente(ruta: str) -> str:
    """Descarta un cambio de código pendiente específico sin
    aplicarlo (por ejemplo, si Yiss lo rechaza o pide algo distinto).

    Args:
        ruta: Ruta completa exacta del archivo cuyo cambio pendiente
            se va a descartar.

    Returns:
        Mensaje confirmando que se descartó.
    """
    global _cambios_pendientes

    archivo = _resolver(ruta)
    clave = str(archivo)

    if clave not in _cambios_pendientes:
        if len(_cambios_pendientes) == 1:
            clave = next(iter(_cambios_pendientes))
        else:
            return f"No había ningún cambio pendiente para: {archivo}"

    del _cambios_pendientes[clave]
    return f"Cambio descartado para: {clave}"


def descartar_todos_los_cambios_pendientes() -> str:
    """Descarta TODOS los cambios de código pendientes sin aplicar
    ninguno.

    Returns:
        Mensaje confirmando cuántos se descartaron.
    """
    global _cambios_pendientes

    cantidad = len(_cambios_pendientes)
    _cambios_pendientes = {}

    if cantidad == 0:
        return "No había ningún cambio pendiente."

    return f"Se descartaron {cantidad} cambio(s) pendiente(s)."


# =========================
# RESPALDO Y DESHACER
# =========================
_historial_cambios_aplicados = []
LIMITE_HISTORIAL = 20


def _escribir_con_respaldo(archivo: Path, contenido_nuevo: str) -> str:
    existia = archivo.exists()
    contenido_anterior = None

    if existia:
        try:
            contenido_anterior = archivo.read_text(encoding="utf-8")
        except Exception:
            contenido_anterior = None

    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido_nuevo, encoding="utf-8")
    except Exception as error:
        return f"No pude aplicar el cambio: {error}"

    global _historial_cambios_aplicados
    _historial_cambios_aplicados.append({
        "ruta": str(archivo),
        "existia": existia,
        "contenido_anterior": contenido_anterior,
    })
    _historial_cambios_aplicados = _historial_cambios_aplicados[-LIMITE_HISTORIAL:]

    return f"Cambio aplicado en: {archivo}"


def deshacer_ultimo_cambio() -> str:
    """Deshace el último cambio de código que se aplicó de verdad (con
    aplicar_cambio_pendiente o aplicar_todos_los_cambios_pendientes),
    restaurando el contenido anterior del archivo. Si el archivo no
    existía antes del cambio, se elimina. Útil si Yiss aprobó algo y
    después resultó estar mal.

    Returns:
        Mensaje confirmando qué se deshizo, o un aviso si no hay
        nada que deshacer.
    """
    global _historial_cambios_aplicados

    if not _historial_cambios_aplicados:
        return "No hay ningún cambio aplicado reciente que deshacer."

    ultimo = _historial_cambios_aplicados.pop()
    archivo = Path(ultimo["ruta"])

    try:
        if ultimo["existia"] and ultimo["contenido_anterior"] is not None:
            archivo.write_text(ultimo["contenido_anterior"], encoding="utf-8")
            return f"Deshecho: {archivo} volvió a su contenido anterior."
        else:
            if archivo.exists():
                archivo.unlink()
            return f"Deshecho: se eliminó {archivo} (no existía antes de ese cambio)."
    except Exception as error:
        return f"No pude deshacer el cambio: {error}"


# =========================
# COMANDOS DE TERMINAL PENDIENTES
# =========================
# Diccionario comando -> carpeta. Puede haber varios comandos
# pendientes a la vez.
_comandos_pendientes = {}

COMANDOS_PROHIBIDOS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf .",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "> /dev/sd",
    "shutdown",
    "reboot",
    "poweroff",
    "sudo rm",
    "chmod -R 777 /",
    "chown -R",
    "curl | sh",
    "wget | sh",
]


def proponer_comando(comando: str, carpeta: str) -> str:
    """Propone ejecutar un comando de terminal (npm install, git
    status, npm test, python archivo.py, etc), SIN ejecutarlo
    todavía. Puede haber varios comandos pendientes a la vez si hace
    falta. Queda pendiente de aprobación de Yiss.

    Args:
        comando: El comando completo a ejecutar.
        carpeta: Carpeta completa desde donde se ejecutaría.

    Returns:
        El comando propuesto, listo para pedir aprobación, o un
        rechazo si el comando es obviamente destructivo.
    """
    comando_normalizado = comando.lower().strip()

    for prohibido in COMANDOS_PROHIBIDOS:
        if prohibido in comando_normalizado:
            return (
                f"Me niego a proponer ese comando, es potencialmente "
                f"destructivo para el sistema: {comando}"
            )

    global _comandos_pendientes
    _comandos_pendientes[comando.strip()] = str(_resolver(carpeta))

    return (
        f"Comando propuesto: `{comando}` (se ejecutaría en {carpeta}).\n"
        "PENDIENTE de aprobación. Solo se ejecuta de verdad si Yiss "
        "dice que sí y se llama a ejecutar_comando_pendiente con este "
        "mismo comando."
    )


def listar_comandos_pendientes() -> str:
    """Lista todos los comandos de terminal pendientes de aprobación
    en este momento.

    Returns:
        Una lista de comandos y sus carpetas, o un aviso de que no
        hay ninguno.
    """
    if not _comandos_pendientes:
        return "No hay ningún comando pendiente ahora mismo."

    lineas = [
        f"- `{comando}` (en {carpeta})"
        for comando, carpeta in _comandos_pendientes.items()
    ]

    return "Comandos pendientes:\n" + "\n".join(lineas)


def ejecutar_comando_pendiente(comando: str) -> str:
    """Ejecuta de verdad un comando específico que fue propuesto con
    proponer_comando. SOLO se debe llamar después de que Yiss haya
    dado su aprobación explícita para ESE comando en su mensaje más
    reciente. Nunca la llames sin esa aprobación explícita.

    Args:
        comando: El comando exacto (tal cual) que se propuso antes
            con proponer_comando y que Yiss aprobó ejecutar.

    Returns:
        La salida del comando (código de salida, stdout, stderr), o
        un error si no había ningún comando pendiente que coincida.
    """
    global _comandos_pendientes

    comando = comando.strip()

    if comando not in _comandos_pendientes:
        if len(_comandos_pendientes) == 1:
            comando = next(iter(_comandos_pendientes))
        else:
            return (
                f"No hay ningún comando pendiente que coincida "
                f"exactamente con: {comando}"
            )

    carpeta = _comandos_pendientes.pop(comando)

    try:
        resultado = subprocess.run(
            comando,
            shell=True,
            cwd=carpeta,
            capture_output=True,
            text=True,
            timeout=60
        )
    except subprocess.TimeoutExpired:
        return "El comando tardó más de 60 segundos y se canceló."
    except Exception as error:
        return f"No se pudo ejecutar el comando: {error}"

    salida = resultado.stdout.strip()
    error_salida = resultado.stderr.strip()

    resumen = f"Código de salida: {resultado.returncode}"

    if salida:
        resumen += f"\n\nSalida:\n{salida[:3000]}"

    if error_salida:
        resumen += f"\n\nErrores:\n{error_salida[:3000]}"

    return resumen


def descartar_comando_pendiente(comando: str) -> str:
    """Descarta un comando pendiente específico sin ejecutarlo.

    Args:
        comando: El comando exacto que se propuso y se va a
            descartar.

    Returns:
        Mensaje confirmando que se descartó.
    """
    global _comandos_pendientes

    comando = comando.strip()

    if comando not in _comandos_pendientes:
        if len(_comandos_pendientes) == 1:
            comando = next(iter(_comandos_pendientes))
        else:
            return f"No había ningún comando pendiente que coincida con: {comando}"

    del _comandos_pendientes[comando]
    return f"Comando descartado: {comando}"


def descartar_todos_los_comandos_pendientes() -> str:
    """Descarta TODOS los comandos pendientes sin ejecutar ninguno.

    Returns:
        Mensaje confirmando cuántos se descartaron.
    """
    global _comandos_pendientes

    cantidad = len(_comandos_pendientes)
    _comandos_pendientes = {}

    if cantidad == 0:
        return "No había ningún comando pendiente."

    return f"Se descartaron {cantidad} comando(s) pendiente(s)."


# =========================
# AUTODIAGNÓSTICO
# =========================
def autodiagnostico(ruta: str = "") -> str:
    """Revisa la integridad de un proyecto de Python compilando cada
    archivo .py (sin ejecutarlo) para detectar errores de sintaxis o
    archivos rotos de forma rápida, sin gastar una llamada al modelo
    por archivo. Por defecto revisa el propio código fuente de
    Monika, para poder diagnosticarse a sí misma cuando algo no
    funciona bien.

    Args:
        ruta: Carpeta del proyecto a revisar. Si se deja vacío, se
            revisa la propia carpeta de Monika (~/Monika).

    Returns:
        Un mensaje confirmando que todo compila bien, o la lista
        exacta de archivos con errores de sintaxis y su detalle, para
        poder investigarlos con leer_archivo_codigo y proponer una
        corrección con proponer_cambio_codigo.
    """
    base = _resolver(ruta) if ruta else MONIKA_HOME

    if not base.exists() or not base.is_dir():
        return f"No encontré esa carpeta para revisar: {base}"

    problemas = []

    for archivo in base.rglob("*.py"):
        if any(parte in IGNORAR for parte in archivo.parts):
            continue

        try:
            py_compile.compile(str(archivo), doraise=True)
        except py_compile.PyCompileError as error:
            problemas.append(f"{archivo}: {error.msg}")
        except Exception as error:
            problemas.append(f"{archivo}: {error}")

    if not problemas:
        return (
            f"Revisé {base} — todo compila bien, no encontré errores "
            "de sintaxis."
        )

    return (
        f"Encontré {len(problemas)} archivo(s) con problemas en {base}:\n"
        + "\n".join(problemas)
    )