import time


class InitiativeManager:

    def __init__(self):

        self.last_interaction = time.time()

        self.last_initiative = 0

        self.minimum_wait = 5 * 60

        self.maximum_wait = 15 * 60

        self.desire_to_talk = 20

        self.boredom = 0

    # =========================
    # REGISTRAR INTERACCIÓN
    # =========================

    def register_interaction(self):

        self.last_interaction = time.time()

        self.last_initiative = time.time()

        self.desire_to_talk = 10

        self.boredom = 0

    # =========================
    # ACTUALIZAR ESTADO
    # =========================

    def update(self):

        current_time = time.time()

        minutes_without_interaction = (
            current_time - self.last_interaction
        ) / 60

        self.boredom = min(
            100,
            int(minutes_without_interaction * 2)
        )

        self.desire_to_talk = min(
            100,
            int(20 + minutes_without_interaction * 3)
        )

    # =========================
    # ¿PUEDE HABLAR?
    # =========================

    def can_speak(self):

        current_time = time.time()

        time_since_last_initiative = (
            current_time - self.last_initiative
        )

        return (
            time_since_last_initiative
            >= self.minimum_wait
        )

    # =========================
    # ¿QUIERE HABLAR?
    # =========================

    def wants_to_speak(self):

        self.update()

        if not self.can_speak():

            return False

        if self.desire_to_talk < 45:

            return False

        return True

    # =========================
    # REGISTRAR INICIATIVA
    # =========================

    def register_initiative(self):

        self.last_initiative = time.time()

        self.desire_to_talk = 10

        self.boredom = 0

    # =========================
    # OBTENER CONTEXTO
    # =========================

    def get_context(self):

        self.update()

        return {

            "minutes_without_interaction": round(
                (
                    time.time()
                    - self.last_interaction
                ) / 60,
                1
            ),

            "desire_to_talk": self.desire_to_talk,

            "boredom": self.boredom

        }
