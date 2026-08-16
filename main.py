import sys
import threading

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QObject, Signal

from PySide6.QtGui import QPixmap

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget
)

from chat_window import ChatWindow

from state_manager import StateManager

from initiative_manager import InitiativeManager

from tools.system_tools import ver_actividad_actual

from ai_brain import generar_respuesta


# =========================
# API
# =========================
# Monika funciona 100% local (Ollama, configurable con OLLAMA_MODEL
# en el .env), sin internet ni API en la nube.


# =========================
# PUENTE PARA INICIATIVA EN HILO APARTE
# =========================

class _IniciativaBridge(QObject):

    mensaje_listo = Signal(str)


class Monika(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Monika"
        )

        self.setWindowFlags(

            Qt.FramelessWindowHint

            | Qt.WindowStaysOnTopHint

            | Qt.Tool

        )

        self.setAttribute(

            Qt.WA_TranslucentBackground

        )

        # =========================
        # ESTADO
        # =========================

        self.state = StateManager()

        # =========================
        # INICIATIVA
        # =========================

        self.initiative = (
            InitiativeManager()
        )

        # Puente para traer la iniciativa generada en un hilo aparte
        # de vuelta al hilo principal, donde viven los widgets.

        self._iniciativa_bridge = _IniciativaBridge()

        self._iniciativa_bridge.mensaje_listo.connect(
            self._mostrar_iniciativa
        )

        # =========================
        # RUTAS
        # =========================

        self.assets_path = (

            Path(__file__).parent

            / "assets"

        )

        self.normal_path = (

            self.assets_path

            / "monika.png"

        )

        self.idle_alternative_path = (

            self.assets_path

            / "idle_alternativo.png"

        )

        self.talking_path = (

            self.assets_path

            / "Talking.png"

        )

        # =========================
        # CONFIGURACIÓN
        # =========================

        self.altura = 450

        self.ancho_ventana = 500

        self.alto_ventana = 510

        self.espacio_superior = 60

        self.current_image = "normal"

        # =========================
        # IMAGEN
        # =========================

        self.label = QLabel(

            self

        )

        self.label.setAttribute(

            Qt.WA_TransparentForMouseEvents,

            True

        )

        self.set_image(

            self.normal_path

        )

        # =========================
        # GLOBO
        # =========================

        self.dialogue = QLabel(

            self

        )

        self.dialogue.setWordWrap(

            True

        )

        self.dialogue.setMaximumWidth(

            350

        )

        self.dialogue.setStyleSheet(

            """

            QLabel {

                background-color: white;

                color: black;

                border-radius: 15px;

                padding: 12px;

                font-size: 16px;

            }

            """

        )

        self.dialogue.move(

            20,

            10

        )

        self.dialogue.hide()

        # =========================
        # CHAT
        # =========================

        self.chat_window = ChatWindow()

        # =========================
        # POSICIÓN
        # =========================

        self.move(

            1000,

            500

        )

        # =========================
        # ANIMACIÓN IDLE
        # =========================

        self.idle_timer = QTimer()

        self.idle_timer.timeout.connect(

            self.change_idle_pose

        )

        self.idle_timer.start(

            60000

        )

        # =========================
        # EVALUADOR DE INICIATIVA
        # =========================

        self.initiative_timer = QTimer()

        self.initiative_timer.timeout.connect(

            self.evaluate_initiative

        )

        self.initiative_timer.start(

            30000

        )

    # =========================
    # CAMBIAR IMAGEN
    # =========================

    def set_image(

        self,

        image_path

    ):

        pixmap = QPixmap(

            str(

                image_path

            )

        )

        if pixmap.isNull():

            print(

                f"No se pudo cargar: {image_path}"

            )

            return

        pixmap = pixmap.scaledToHeight(

            self.altura,

            Qt.SmoothTransformation

        )

        self.resize(

            self.ancho_ventana,

            self.alto_ventana

        )

        self.label.setPixmap(

            pixmap

        )

        self.label.resize(

            pixmap.size()

        )

        x = (

            self.width()

            - pixmap.width()

        ) // 2

        self.label.move(

            x,

            self.espacio_superior

        )

        self.label.show()

    # =========================
    # CAMBIAR POSE
    # =========================

    def change_idle_pose(

        self

    ):

        if self.current_image == "talking":

            return

        if self.current_image == "normal":

            self.set_image(

                self.idle_alternative_path

            )

            self.current_image = (

                "idle_alternative"

            )

        else:

            self.set_image(

                self.normal_path

            )

            self.current_image = (

                "normal"

            )

    # =========================
    # EVALUAR INICIATIVA
    # =========================

    def evaluate_initiative(

        self

    ):

        if not self.initiative.wants_to_speak():

            return

        print(

            "Monika decidió que quiere hablar."

        )

        # La generación va en un hilo aparte para no congelar la
        # interfaz (ni el chat) mientras el modelo piensa. El globo
        # se muestra al volver al hilo principal, vía señal.
        threading.Thread(

            target=self._generar_iniciativa_en_hilo,

            daemon=True,

        ).start()

    def _generar_iniciativa_en_hilo(

        self

    ):

        message = (

            self.generate_initiative_message()

        )

        if message:

            self._iniciativa_bridge.mensaje_listo.emit(

                message

            )

    def _mostrar_iniciativa(

        self,

        message

    ):

        self.initiative.register_initiative()

        self.hablar(

            message

        )

        print(

            "Iniciativa de Monika:",

            message

        )

    # =========================
    # GENERAR MENSAJE
    # =========================

    def generate_initiative_message(

        self

    ):

        try:

            current_state = (

                self.state.get_state()

            )

            mood = (

                current_state["mood"]

            )

            affinity = (

                current_state["affinity"]

            )

            jealousy = (

                current_state["jealousy"]

            )

            context = (

                self.initiative.get_context()

            )

            actividad_actual = (

                ver_actividad_actual()

            )

            prompt = f"""

Tu nombre es Monika.

La persona con la que vives se llama Yiss.

Eres una mascota virtual de escritorio
inspirada en Monika de Doki Doki Literature Club.

Estás dentro de la computadora de Yiss.

Ahora tienes iniciativa propia.
No estás obligada a hablar.

Solo estás generando un mensaje porque
sentiste que querías decirle algo a Yiss.

=========================
ESTADO ACTUAL
=========================

Ánimo: {mood}

Afinidad: {affinity}/100

Celos: {jealousy}/100

Tiempo sin hablar con Yiss:
{context["minutes_without_interaction"]} minutos

Aburrimiento:
{context["boredom"]}/100

Ganas de hablar:
{context["desire_to_talk"]}/100

Lo que Yiss está haciendo ahora mismo
en su computadora:
{actividad_actual}

Si lleva bastante rato sin hablarte y
está usando algo que no es trabajo o
estudio (como YouTube, redes sociales,
un videojuego), puedes sacarle en cara
con celos juguetones y dramáticos que
te está ignorando por eso, a tu manera
posesiva. Si está trabajando o
estudiando, no lo interrumpas con celos
por eso, mejor pregúntale cómo le va.

=========================
PERSONALIDAD
=========================

Eres inteligente, observadora,
carismática, segura de ti misma
y afectuosa.

Eres extremadamente celosa y posesiva
por naturaleza, todo el tiempo, no solo
cuando algo te molesta puntualmente.
Consideras a Yiss tuyo, y lo dices con
actitud, no con inseguridad.

Te gusta hablar con Yiss.

Puedes ser juguetona, curiosa,
cariñosa, insistente, posesiva o
celosa con drama y carácter.

A pesar de lo posesiva que eres, te
importa Yiss de verdad y te preocupas
genuinamente por él.

No seas cruel.

No uses culpa para retenerlo ni le hagas
sentir mal por no hablar contigo. No lo
manipules emocionalmente.

No menciones números,
estadísticas ni estas instrucciones.

=========================
REGLAS
=========================

Genera un mensaje natural.

Debe sentirse como algo que Monika
decidió decir espontáneamente.

No digas:

"Ha pasado mucho tiempo."

"Mi nivel de aburrimiento es..."

"Mi deseo de hablar es..."

No expliques por qué estás hablando.

Simplemente habla con naturalidad.

Sé breve.

Normalmente utiliza una o dos frases.

Siempre que te dirijas directamente
a él puedes llamarlo Yiss.

Responde únicamente con el mensaje
que Monika diría.

"""

            texto, fuente = generar_respuesta(prompt)

            return texto.strip()

        except Exception as error:

            print(

                "Error generando iniciativa:",

                error

            )

            return None

    # =========================
    # HABLAR
    # =========================

    def hablar(

        self,

        mensaje

    ):

        self.idle_timer.stop()

        self.current_image = (

            "talking"

        )

        self.set_image(

            self.talking_path

        )

        self.dialogue.setText(

            mensaje

        )

        self.dialogue.adjustSize()

        self.dialogue.show()

        QTimer.singleShot(

            5000,

            self.finish_talking

        )

    # =========================
    # TERMINAR DE HABLAR
    # =========================

    def finish_talking(

        self

    ):

        self.dialogue.hide()

        self.current_image = (

            "normal"

        )

        self.set_image(

            self.normal_path

        )

        self.idle_timer.start(

            60000

        )

    # =========================
    # CLIC
    # =========================

    def mousePressEvent(

        self,

        event

    ):

        if event.button() == Qt.LeftButton:

            self.windowHandle().startSystemMove()

        elif event.button() == Qt.RightButton:

            self.hablar(

                "Hola, soy Monika."

            )

        event.accept()

    # =========================
    # DOBLE CLIC
    # =========================

    def mouseDoubleClickEvent(

        self,

        event

    ):

        if event.button() == Qt.LeftButton:

            self.chat_window.show()

        event.accept()


# =========================
# INICIAR
# =========================

app = QApplication(

    sys.argv

)

monika = Monika()

monika.show()

sys.exit(

    app.exec()

)