import os
import subprocess
import threading
import shutil


class TTSManager:
    """Convierte texto a voz usando Piper y lo reproduce con aplay,
    en un hilo aparte para no congelar la interfaz mientras habla.

    Requiere tener instalado Piper y aplay (parte de alsa-utils),
    y configurar en el .env:
        PIPER_BINARY=/ruta/a/piper
        PIPER_MODEL=/ruta/a/tu_voz.onnx
    """

    def __init__(self, piper_binario="piper", modelo_voz="", sample_rate=22050):
        self.piper_binario = piper_binario
        self.modelo_voz = modelo_voz
        self.sample_rate = sample_rate
        self.activado = False

    # =========================
    # DISPONIBILIDAD
    # =========================
    def esta_disponible(self):
        if not self.modelo_voz:
            return False

        if self.piper_binario.startswith("/"):
            return os.path.isfile(self.piper_binario)

        return bool(shutil.which(self.piper_binario))

    # =========================
    # ALTERNAR ON/OFF
    # =========================
    def alternar(self):
        self.activado = not self.activado
        return self.activado

    # =========================
    # HABLAR
    # =========================
    def hablar(self, texto):
        if not self.activado:
            return

        if not texto or not texto.strip():
            return

        if not self.esta_disponible():
            print(
                "TTS activado pero Piper no está configurado "
                "correctamente (revisa PIPER_BINARY y PIPER_MODEL "
                "en el .env, o que las rutas existan de verdad)."
            )
            return

        threading.Thread(
            target=self._reproducir,
            args=(texto,),
            daemon=True
        ).start()

    # =========================
    # REPRODUCIR (EN HILO APARTE)
    # =========================
    def _reproducir(self, texto):
        try:
            # =========================
            # ENTORNO (LD_LIBRARY_PATH)
            # =========================
            # Los binarios de Piper descargados como .tar.gz suelen
            # traer sus propias librerías (libpiper_phonemize.so) en
            # la misma carpeta del ejecutable. Si no se apunta ahí,
            # Piper falla al arrancar sin avisar en pantalla.
            entorno = os.environ.copy()
            carpeta_piper = os.path.dirname(self.piper_binario)

            if carpeta_piper:
                ld_actual = entorno.get("LD_LIBRARY_PATH", "")
                entorno["LD_LIBRARY_PATH"] = (
                    f"{carpeta_piper}:{ld_actual}"
                    if ld_actual
                    else carpeta_piper
                )

            # =========================
            # LANZAR PIPER
            # =========================
            piper = subprocess.Popen(
                [
                    self.piper_binario,
                    "--model", self.modelo_voz,
                    "--output-raw"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=entorno
            )

            # =========================
            # LANZAR REPRODUCTOR
            # =========================
            reproductor = subprocess.Popen(
                [
                    "aplay",
                    "-q",
                    "-r", str(self.sample_rate),
                    "-f", "S16_LE",
                    "-t", "raw",
                    "-"
                ],
                stdin=piper.stdout,
                stderr=subprocess.PIPE
            )

            # Importante: cerrar la copia del pipe en este proceso
            # para que aplay reciba el fin de la señal cuando Piper
            # termine, en vez de quedarse esperando para siempre.
            piper.stdout.close()

            piper.stdin.write(texto.encode("utf-8"))
            piper.stdin.close()

            error_piper = piper.stderr.read()
            piper.wait()

            error_aplay = reproductor.stderr.read()
            reproductor.wait()

            if piper.returncode != 0 and error_piper:
                print(
                    "Piper falló:",
                    error_piper.decode(errors="ignore").strip()
                )

            if reproductor.returncode != 0 and error_aplay:
                print(
                    "aplay falló:",
                    error_aplay.decode(errors="ignore").strip()
                )

        except Exception as error:
            print("Error reproduciendo voz:", error)