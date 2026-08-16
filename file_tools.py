import os
import shutil
import subprocess
from pathlib import Path

from state_manager import StateManager


# =========================
# RUTAS PROTEGIDAS
# =========================
# Estas rutas nunca se pueden eliminar, mover ni
# renombrar, sin importar lo que pida el usuario.
# Es una protección contra errores, no una limitación
# de funcionalidad real.

RUTAS_PROTEGIDAS = [
    Path("/"),
    Path.home(),
    Path("/etc"),
    Path("/bin"),
    Path("/usr"),
    Path("/boot"),
    Path("/root"),
    Path("/sys"),
    Path("/proc"),
    Path("/var"),
]


def _resolver_ruta(ruta: str) -> Path:
    return Path(ruta).expanduser().resolve()


def _es_ruta_protegida(ruta: Path) -> bool:
    try:
        ruta = ruta.resolve()
    except Exception:
        return True
    return ruta in RUTAS_PROTEGIDAS


def _esta_dentro_de(hijo: Path, padre: Path) -> bool:
    try:
        hijo.relative_to(padre)
        return True
    except ValueError:
        return False


def _ruta_escritorio() -> Path:
    """Encuentra la ruta real del Escritorio del usuario, sin importar
    el idioma del sistema (en Fedora/Linux con locale en español la
    carpeta se llama "Escritorio", no "Desktop")."""
    try:
        resultado = subprocess.run(
            ["xdg-user-dir", "DESKTOP"],
            capture_output=True,
            text=True,
            timeout=2
        )
        ruta = resultado.stdout.strip()
        if ruta and Path(ruta).exists():
            return Path(ruta)
    except Exception:
        pass

    for nombre in ("Desktop", "Escritorio"):
        candidato = Path.home() / nombre
        if candidato.exists():
            return candidato

    # Si no se encuentra ninguna, se crea "Escritorio" por defecto
    # en vez de caer silenciosamente en la raíz del home.
    return Path.home() / "Escritorio"


# =========================
# CREAR CARPETA
# =========================
def crear_carpeta(nombre: str, ruta_base: str = "") -> str:
    """Crea una carpeta nueva en la ubicación indicada.

    Args:
        nombre: Nombre de la carpeta a crear.
        ruta_base: Ruta completa donde crear la carpeta, SOLO si el
            usuario mencionó explícitamente una carpeta o ruta destino
            (por ejemplo "/home/jesus62/Documentos"). Si el usuario NO
            especificó dónde, deja este parámetro como cadena vacía ""
            — nunca inventes ni adivines una ruta como el home del
            usuario. Al dejarlo vacío, se usa automáticamente el
            Escritorio real del usuario, detectado por el sistema.

    Returns:
        La ruta completa de la carpeta creada.
    """
    print(f"DEBUG: crear_carpeta(nombre={nombre!r}, ruta_base={ruta_base!r})")

    base = (
        _resolver_ruta(ruta_base)
        if ruta_base
        else _ruta_escritorio()
    )

    print(f"DEBUG: carpeta base resuelta -> {base}")

    destino = base / nombre
    destino.mkdir(parents=True, exist_ok=True)

    try:
        registro = StateManager()
        registro.add_folder(nombre, str(destino))
    except Exception as error:
        print("No se pudo registrar la carpeta:", error)

    return str(destino)


# =========================
# GUARDAR TXT
# =========================
def guardar_txt(nombre: str, contenido: str, ruta: str) -> str:
    """Crea o sobrescribe un archivo .txt con el contenido indicado.

    Args:
        nombre: Nombre del archivo (con o sin extensión .txt).
        contenido: Texto que se guardará dentro del archivo.
        ruta: Carpeta completa donde se guardará el archivo.

    Returns:
        La ruta completa del archivo creado.
    """
    if not nombre.endswith(".txt"):
        nombre += ".txt"

    carpeta = _resolver_ruta(ruta)
    carpeta.mkdir(parents=True, exist_ok=True)

    archivo = carpeta / nombre
    archivo.write_text(contenido, encoding="utf-8")

    return str(archivo)


# =========================
# LEER ARCHIVO
# =========================
def leer_archivo(ruta: str) -> str:
    """Lee y devuelve el contenido de un archivo de texto.

    Args:
        ruta: Ruta completa del archivo a leer.

    Returns:
        El contenido del archivo como texto, o un mensaje de error
        si no existe o no se puede leer.
    """
    archivo = _resolver_ruta(ruta)

    if not archivo.exists():
        return f"El archivo no existe: {archivo}"

    if not archivo.is_file():
        return f"La ruta no es un archivo: {archivo}"

    try:
        return archivo.read_text(encoding="utf-8")
    except Exception as error:
        return f"No se pudo leer el archivo: {error}"


# =========================
# EDITAR ARCHIVO
# =========================
def editar_archivo(ruta: str, contenido: str, modo: str = "sobrescribir") -> str:
    """Modifica el contenido de un archivo de texto existente (o lo crea si no existe).

    Args:
        ruta: Ruta completa del archivo a modificar.
        contenido: Texto nuevo a escribir o a agregar.
        modo: "sobrescribir" reemplaza todo el contenido del archivo,
            "agregar" añade el texto al final sin borrar lo anterior.

    Returns:
        Mensaje confirmando la operación, o un error si algo falló.
    """
    archivo = _resolver_ruta(ruta)
    archivo.parent.mkdir(parents=True, exist_ok=True)

    try:
        if modo == "agregar":
            with open(archivo, "a", encoding="utf-8") as file:
                file.write(contenido)
        else:
            archivo.write_text(contenido, encoding="utf-8")

        return f"Archivo actualizado: {archivo}"
    except Exception as error:
        return f"No se pudo editar el archivo: {error}"


# =========================
# RENOMBRAR
# =========================
def renombrar(ruta: str, nuevo_nombre: str) -> str:
    """Renombra un archivo o carpeta.

    Args:
        ruta: Ruta completa del archivo o carpeta a renombrar.
        nuevo_nombre: Nuevo nombre, solo el nombre, sin la ruta.

    Returns:
        La nueva ruta completa, o un mensaje de error si algo falló.
    """
    origen = _resolver_ruta(ruta)

    if not origen.exists():
        return f"No existe: {origen}"

    if _es_ruta_protegida(origen):
        return "No puedo renombrar esa ubicación, es una carpeta crítica del sistema."

    destino = origen.parent / nuevo_nombre

    try:
        origen.rename(destino)
        return str(destino)
    except Exception as error:
        return f"No se pudo renombrar: {error}"


# =========================
# MOVER
# =========================
def mover_archivo(ruta: str, destino: str) -> str:
    """Mueve un archivo o carpeta a otra ubicación.

    Args:
        ruta: Ruta completa del archivo o carpeta a mover. Debe ser la
            ruta real y exacta (usa tu registro de carpetas o lo que
            ya sabes de la conversación; nunca inventes esta ruta).
        destino: Carpeta completa a la que se moverá.

    Returns:
        La nueva ruta completa, o un mensaje de error si algo falló.
    """
    print(f"DEBUG: mover_archivo(ruta={ruta!r}, destino={destino!r})")

    origen = _resolver_ruta(ruta)
    carpeta_destino = _resolver_ruta(destino)

    print(f"DEBUG: origen resuelto -> {origen} (existe: {origen.exists()})")
    print(f"DEBUG: destino resuelto -> {carpeta_destino}")

    if not origen.exists():
        return f"No existe: {origen}"

    if _es_ruta_protegida(origen):
        return "No puedo mover esa ubicación, es una carpeta crítica del sistema."

    try:
        carpeta_destino.mkdir(parents=True, exist_ok=True)
        nueva_ruta = carpeta_destino / origen.name
        shutil.move(str(origen), str(nueva_ruta))
        print(f"DEBUG: movido exitosamente a -> {nueva_ruta}")

        # Si lo que se movió era una carpeta registrada, actualizar
        # su ruta en el registro para no perderle la pista.
        try:
            registro = StateManager()
            folders = dict(registro.state.get("folders", {}))
            for nombre_carpeta, ruta_guardada in folders.items():
                if _resolver_ruta(ruta_guardada) == origen:
                    registro.add_folder(nombre_carpeta, str(nueva_ruta))
        except Exception as error:
            print("DEBUG: no se pudo actualizar el registro tras mover:", error)

        return str(nueva_ruta)
    except Exception as error:
        print(f"DEBUG: error moviendo -> {error}")
        return f"No se pudo mover: {error}"


# =========================
# ELIMINAR
# =========================
def eliminar(ruta: str) -> str:
    """Elimina un archivo, o una carpeta completa junto con todo su contenido.

    Args:
        ruta: Ruta completa del archivo o carpeta a eliminar.

    Returns:
        Mensaje confirmando la eliminación, o un error si algo falló.
    """
    objetivo = _resolver_ruta(ruta)

    if not objetivo.exists():
        return f"No existe: {objetivo}"

    if _es_ruta_protegida(objetivo):
        return "No puedo eliminar esa ubicación, es una carpeta crítica del sistema."

    try:
        if objetivo.is_dir():
            shutil.rmtree(objetivo)
        else:
            objetivo.unlink()

        try:
            registro = StateManager()
            folders = dict(registro.state.get("folders", {}))
            for nombre, ruta_guardada in folders.items():
                ruta_guardada = _resolver_ruta(ruta_guardada)
                if ruta_guardada == objetivo or _esta_dentro_de(ruta_guardada, objetivo):
                    registro.remove_folder(nombre)
        except Exception as error:
            print("No se pudo actualizar el registro de carpetas:", error)

        return f"Eliminado: {objetivo}"
    except Exception as error:
        return f"No se pudo eliminar: {error}"


# =========================
# LISTAR CARPETA
# =========================
def listar_carpeta(ruta: str) -> str:
    """Lista los archivos y subcarpetas dentro de una carpeta.

    Args:
        ruta: Ruta completa de la carpeta a listar.

    Returns:
        Una lista con los nombres de archivos y carpetas separados por
        salto de línea, o un mensaje de error si la ruta no es válida.
    """
    carpeta = _resolver_ruta(ruta)

    if not carpeta.exists() or not carpeta.is_dir():
        return f"La carpeta no existe: {carpeta}"

    try:
        elementos = sorted(os.listdir(carpeta))
    except Exception as error:
        return f"No se pudo listar la carpeta: {error}"

    if not elementos:
        return "La carpeta está vacía."

    return "\n".join(elementos)


# =========================
# MARCAR CARPETA PRINCIPAL
# =========================
def marcar_carpeta_principal(ruta: str) -> str:
    """Marca una carpeta ya existente como "nuestra carpeta": la
    carpeta principal compartida entre Yiss y Monika. A partir de ese
    momento, cuando Yiss diga "nuestra carpeta" sin especificar el
    nombre, se debe usar esta ruta por defecto.

    Args:
        ruta: Ruta completa de la carpeta que se marcará como principal.

    Returns:
        Mensaje confirmando la operación, o un error si la ruta no existe.
    """
    carpeta = _resolver_ruta(ruta)

    if not carpeta.exists() or not carpeta.is_dir():
        return f"Esa carpeta no existe: {carpeta}"

    registro = StateManager()
    registro.set_main_folder(str(carpeta))

    return f"Carpeta principal establecida: {carpeta}"


# =========================
# CARPETAS CREADAS
# =========================
def carpetas_creadas() -> str:
    """Devuelve cuántas carpetas ha creado Monika y siguen existiendo,
    junto con su nombre y ruta. Si alguna fue borrada manualmente
    fuera de la conversación, ya no aparece en esta lista.

    Returns:
        Un resumen con el total de carpetas vigentes y el detalle de
        cada una (nombre y ruta completa).
    """
    registro = StateManager()
    folders = registro.list_folders()

    if not folders:
        return "Todavía no he creado ninguna carpeta que siga existiendo."

    lineas = [
        f"- {nombre}: {ruta}"
        for nombre, ruta in folders.items()
    ]

    return (
        f"Total de carpetas creadas que aún existen: {len(folders)}\n"
        + "\n".join(lineas)
    )


# =========================
# NOMBRE DISPONIBLE PARA NOTA
# =========================
def obtener_nombre_nota(ruta_carpeta: str) -> str:
    """Genera un nombre de archivo disponible para una nueva nota dentro
    de una carpeta, evitando sobrescribir notas ya existentes
    (nota_1.txt, nota_2.txt, etc).

    Args:
        ruta_carpeta: Carpeta donde se guardará la nota.

    Returns:
        Un nombre de archivo disponible, por ejemplo "nota_2.txt".
    """
    carpeta = _resolver_ruta(ruta_carpeta)
    contador = 1

    while (carpeta / f"nota_{contador}.txt").exists():
        contador += 1

    return f"nota_{contador}.txt"