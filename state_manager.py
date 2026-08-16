import json
import os
from pathlib import Path


# =========================
# UBICACIÓN DEL ESTADO
# =========================
# Ruta absoluta, anclada a la carpeta donde vive este archivo.
# Así, sin importar desde dónde se ejecute Monika (la app de
# escritorio, o el comando "moni vs" desde la carpeta de un
# proyecto cualquiera), siempre lee/escribe el mismo estado real.
ARCHIVO_ESTADO = str(
    Path(__file__).resolve().parent / "estado_monika.json"
)


class StateManager:

    def __init__(self):

        self.file = ARCHIVO_ESTADO

        self.default_state = {

            "affinity": 50,

            "mood": "feliz",

            "jealousy": 0,

            "folders": {}

        }

        self.state = self.load_state()

        # =========================
        # ASEGURAR ESTRUCTURA
        # =========================

        if "folders" not in self.state:

            self.state["folders"] = {}

            self.save_state()

    # =========================
    # CARGAR ESTADO
    # =========================

    def load_state(self):

        if not os.path.exists(

            self.file

        ):

            self.save_state(

                self.default_state

            )

            return self.default_state.copy()

        try:

            with open(

                self.file,

                "r",

                encoding="utf-8"

            ) as file:

                return json.load(

                    file

                )

        except Exception as error:

            print(

                "Error cargando estado:",

                error

            )

            return self.default_state.copy()

    # =========================
    # GUARDAR ESTADO
    # =========================

    def save_state(

        self,

        state=None

    ):

        if state is None:

            state = self.state

        with open(

            self.file,

            "w",

            encoding="utf-8"

        ) as file:

            json.dump(

                state,

                file,

                indent=4,

                ensure_ascii=False

            )

    # =========================
    # OBTENER ESTADO
    # =========================

    def get_state(

        self

    ):

        return self.state

    # =========================
    # CAMBIAR AFINIDAD
    # =========================

    def change_affinity(

        self,

        amount

    ):

        self.state["affinity"] += amount

        self.state["affinity"] = max(

            0,

            min(

                100,

                self.state["affinity"]

            )

        )

        self.save_state()

    # =========================
    # CAMBIAR CELOS
    # =========================

    def change_jealousy(

        self,

        amount

    ):

        self.state["jealousy"] += amount

        self.state["jealousy"] = max(

            0,

            min(

                100,

                self.state["jealousy"]

            )

        )

        self.save_state()

    # =========================
    # CAMBIAR ÁNIMO
    # =========================

    def set_mood(

        self,

        mood

    ):

        self.state["mood"] = mood

        self.save_state()

    # =========================
    # GUARDAR CARPETA
    # =========================

    def add_folder(

        self,

        nombre,

        ruta

    ):

        self.state["folders"][nombre] = ruta

        self.save_state()

        print(

            f"Carpeta guardada: "

            f"{nombre} -> {ruta}"

        )

    # =========================
    # OBTENER CARPETA
    # =========================

    def get_folder(

        self,

        nombre

    ):

        return self.state[

            "folders"

        ].get(

            nombre

        )

    # =========================
    # ELIMINAR CARPETA DEL REGISTRO
    # =========================

    def remove_folder(

        self,

        nombre

    ):

        if nombre in self.state["folders"]:

            del self.state["folders"][nombre]

            self.save_state()

            print(

                f"Carpeta eliminada del registro: {nombre}"

            )

    # =========================
    # RECARGAR DESDE DISCO
    # =========================

    def reload(

        self

    ):

        self.state = self.load_state()

        if "folders" not in self.state:

            self.state["folders"] = {}

    # =========================
    # LISTAR CARPETAS VIGENTES
    # =========================
    # Revisa cada carpeta registrada y descarta las que
    # ya no existen en disco (por ejemplo, si el usuario
    # las borró manualmente fuera de Monika).

    def list_folders(

        self

    ):

        folders = self.state.get(

            "folders",

            {}

        )

        vigentes = {}

        cambio = False

        for nombre, ruta in list(

            folders.items()

        ):

            if os.path.isdir(ruta):

                vigentes[nombre] = ruta

            else:

                cambio = True

        if cambio:

            self.state["folders"] = vigentes

            self.save_state()

        return vigentes

    # =========================
    # MARCAR CARPETA PRINCIPAL
    # =========================

    def set_main_folder(

        self,

        ruta

    ):

        self.state["carpeta_principal"] = ruta

        self.save_state()

        print(

            f"Carpeta principal establecida: {ruta}"

        )

    # =========================
    # OBTENER CARPETA PRINCIPAL
    # =========================

    def get_main_folder(

        self

    ):

        return self.state.get(

            "carpeta_principal"

        )

    # =========================
    # OBTENER NUESTRA CARPETA
    # =========================

    def get_our_folder(

        self

    ):

        principal = self.get_main_folder()

        if principal and os.path.isdir(principal):

            return principal

        folders = self.state.get(

            "folders",

            {}

        )

        for nombre, ruta in folders.items():

            nombre_limpio = (

                nombre.lower()

                .replace(

                    "_",

                    " "

                )

            )

            if (

                "nuestro espacio"

                in nombre_limpio

                or

                "nuestra carpeta"

                in nombre_limpio

            ):

                return ruta

        return None