import json
import threading
from pathlib import Path


# =========================
# UBICACIÓN DE LA MEMORIA
# =========================

MEMORY_FILE = (
    Path(__file__).parent
    / "memoria.json"
)


class MemoryManager:

    def __init__(self):

        # Lock reentrante: la memoria se escribe desde varios hilos
        # (el hilo de análisis de memoria y el principal), y queremos
        # que las escrituras no se pisen unas a otras.

        self._lock = threading.RLock()

        self.memory = {

            "user": {

                "name": "Yiss"

            },

            "memories": []

        }

        self.load_memory()

    # =========================
    # CARGAR MEMORIA
    # =========================

    def load_memory(self):

        if not MEMORY_FILE.exists():

            self.save_memory()

            return

        try:

            with open(

                MEMORY_FILE,

                "r",

                encoding="utf-8"

            ) as file:

                data = json.load(file)

                # Verificar que el formato
                # sea correcto

                if not isinstance(
                    data,
                    dict
                ):

                    return

                if "memories" not in data:

                    data["memories"] = []

                self.memory = data

        except Exception as error:

            print(
                "Error cargando memoria:",
                error
            )

    # =========================
    # GUARDAR MEMORIA
    # =========================

    def save_memory(self):

        with self._lock:

            try:

                with open(

                    MEMORY_FILE,

                    "w",

                    encoding="utf-8"

                ) as file:

                    json.dump(

                        self.memory,

                        file,

                        ensure_ascii=False,

                        indent=4

                    )

                print(

                    "Memoria guardada correctamente"

                )

            except Exception as error:

                print(

                    "Error guardando memoria:",

                    error

                )

    # =========================
    # AGREGAR RECUERDO
    # =========================

    def add_memory(

        self,

        memory

    ):

        with self._lock:

            memory = memory.strip()

            if not memory:

                return

            if memory not in self.memory[
                "memories"
            ]:

                self.memory[
                    "memories"
                ].append(

                    memory

                )

                self.save_memory()

                print(

                    "Nuevo recuerdo:",

                    memory

                )

    # =========================
    # OBTENER RECUERDOS
    # =========================

    def get_memories(self):

        return self.memory[
            "memories"
        ]

    # =========================
    # TEXTO DE LA MEMORIA
    # =========================

    def get_memory_text(self):

        memories = self.get_memories()

        if not memories:

            return (

                "Monika todavía no tiene "

                "recuerdos importantes."

            )

        return "\n".join(

            f"- {memory}"

            for memory in memories

        )
