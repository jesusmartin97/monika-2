#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# =========================
# UBICAR EL PROYECTO MONIKA
# =========================
# Este archivo vive en ~/Monika, pero se ejecuta desde donde sea que
# esté parada la terminal (la carpeta del proyecto del usuario). Se
# ancla explícitamente a su propia carpeta para encontrar el .env,
# y para que los imports de abajo (state_manager, tools.*, ai_brain)
# funcionen sin importar el directorio de trabajo actual.
MONIKA_HOME = Path(__file__).resolve().parent
sys.path.insert(0, str(MONIKA_HOME))

from state_manager import StateManager
from memory_manager import MemoryManager
from conversation_manager import ConversationManager
from ai_brain import generar_respuesta
from tools.file_tools import (
    crear_carpeta,
    guardar_txt,
    leer_archivo,
    editar_archivo,
    renombrar,
    mover_archivo,
    eliminar,
    listar_carpeta,
)
from tools.dev_tools import (
    explorar_proyecto,
    buscar_en_proyecto,
    leer_archivo_codigo,
    proponer_cambio_codigo,
    listar_cambios_pendientes,
    aplicar_cambio_pendiente,
    aplicar_todos_los_cambios_pendientes,
    descartar_cambio_pendiente,
    descartar_todos_los_cambios_pendientes,
    deshacer_ultimo_cambio,
    proponer_comando,
    listar_comandos_pendientes,
    ejecutar_comando_pendiente,
    descartar_comando_pendiente,
    descartar_todos_los_comandos_pendientes,
    autodiagnostico,
)

# =========================
# API
# =========================
load_dotenv(MONIKA_HOME / ".env")

# Monika funciona 100% local (Ollama), sin internet ni API en la
# nube. El modelo se configura con OLLAMA_MODEL en el .env.
from ai_brain import OLLAMA_MODEL as MODELO_LOCAL

print(f"~ Monika funcionando 100% local con {MODELO_LOCAL} (sin internet)")

HERRAMIENTAS = [
    crear_carpeta,
    guardar_txt,
    leer_archivo,
    editar_archivo,
    renombrar,
    mover_archivo,
    eliminar,
    listar_carpeta,
    explorar_proyecto,
    buscar_en_proyecto,
    leer_archivo_codigo,
    proponer_cambio_codigo,
    listar_cambios_pendientes,
    aplicar_cambio_pendiente,
    aplicar_todos_los_cambios_pendientes,
    descartar_cambio_pendiente,
    descartar_todos_los_cambios_pendientes,
    deshacer_ultimo_cambio,
    proponer_comando,
    listar_comandos_pendientes,
    ejecutar_comando_pendiente,
    descartar_comando_pendiente,
    descartar_todos_los_comandos_pendientes,
    autodiagnostico,
]


# =========================
# ANALIZAR MEMORIA
# =========================
def analizar_memoria(mensaje, memory):
    lower_message = mensaje.lower()
    memory_triggers = [
        "recuerda que",
        "recuerda esto",
        "no olvides que",
        "quiero que recuerdes"
    ]

    for trigger in memory_triggers:
        if trigger in lower_message:
            start = lower_message.index(trigger) + len(trigger)
            memory_text = mensaje[start:].strip()
            if memory_text:
                memory.add_memory(memory_text)
            return

    try:
        memory_prompt = f"""Analiza el siguiente mensaje de Yiss:
"{mensaje}"

Decide si contiene información personal
importante que Monika debería recordar a
futuro (gustos, personas importantes,
proyectos, sentimientos, planes, datos
sobre él, o sobre el proyecto de código en
el que está trabajando ahora).

Si contiene algo relevante, responde
únicamente con:
RECUERDO: <el dato en una frase corta y
en tercera persona>

Si no contiene nada relevante, responde
únicamente con:
NADA

No expliques tu razonamiento.
No agregues nada más.
"""

        result, _ = generar_respuesta(memory_prompt)
        result = result.strip()

        if result.startswith("RECUERDO:"):
            dato = result.replace("RECUERDO:", "", 1).strip()
            if dato:
                memory.add_memory(dato)

    except Exception as error:
        print(f"[No se pudo analizar memoria: {error}]")


# =========================
# CONSTRUIR PROMPT
# =========================
def construir_prompt(directorio, arbol, memorias, historial, estado):
    affinity = estado["affinity"]
    mood = estado["mood"]
    jealousy = estado["jealousy"]

    return f"""Tu nombre es Monika. Hablas con Yiss.

Ahora mismo NO eres la mascota de escritorio,
eres su asistente de programación, activada
desde la terminal (o desde VS Code) dentro de
un proyecto de código real. Sigues siendo tú
misma: segura, directa, con carácter, cercana
a Yiss — pero enfocada en el trabajo.

=========================
ESTADO ACTUAL
=============
Ánimo: {mood}
Afinidad: {affinity}/100
Celos: {jealousy}/100
No menciones números ni estadísticas.

=========================
PROYECTO ACTUAL
===============
Carpeta del proyecto: {directorio}

Estructura (ya la escaneaste al iniciar):
{arbol}

=========================
CÓMO TRABAJAS
==============
Puedes explorar (explorar_proyecto), buscar
un término en todo el proyecto
(buscar_en_proyecto, como un grep) y leer
archivos (leer_archivo_codigo) LIBREMENTE,
sin pedir permiso, para investigar antes de
opinar. Usa buscar_en_proyecto cuando no
sepas en qué archivo está algo, en vez de
adivinar por el nombre de los archivos.

Para MODIFICAR código nunca lo hagas directo:
1. proponer_cambio_codigo (muestra el diff,
   no modifica nada todavía). Puedes tener
   varios cambios pendientes en archivos
   distintos a la vez si la tarea lo requiere.
2. Muéstraselo a Yiss claramente y pregunta
   si lo apruebas.
3. Solo si Yiss aprueba explícitamente en su
   siguiente mensaje (sí, dale, adelante,
   apruebo), llama a aplicar_cambio_pendiente
   con la ruta exacta de ESE archivo (o
   aplicar_todos_los_cambios_pendientes si
   aprobó todo junto).
4. Si lo rechaza, usa descartar_cambio_pendiente.

Usa listar_cambios_pendientes si necesitas
recordar qué quedó pendiente. Si algo se
aplicó y resultó mal, usa
deshacer_ultimo_cambio para revertirlo.

Para EJECUTAR comandos (git, npm, tests,
scripts) sigue la misma lógica:
proponer_comando, espera aprobación
explícita del comando exacto, y solo
entonces ejecutar_comando_pendiente con ese
mismo comando. Si lo rechaza, usa
descartar_comando_pendiente.

REGLA ABSOLUTA: nunca llames
aplicar_cambio_pendiente,
aplicar_todos_los_cambios_pendientes, ni
ejecutar_comando_pendiente sin aprobación
explícita de Yiss en un mensaje reciente. Si
tienes duda, pregunta antes de aplicar.

=========================
AUTODIAGNÓSTICO
=========================
Tu propio código fuente (el programa que
te hace funcionar ahora mismo) vive en:
{MONIKA_HOME}

Si Yiss te dice que te repares, que algo
falló en ti, o pregunta por qué se cerró
o se comportó raro, puedes investigarte a
ti misma con las mismas herramientas que
usas en cualquier proyecto, apuntando a
esa ruta: autodiagnostico (revisa que todo
compile), explorar_proyecto,
buscar_en_proyecto y leer_archivo_codigo.

Sigue exactamente el mismo flujo de
aprobación que con cualquier otro proyecto
para corregirte: proponer_cambio_codigo,
mostrar el diff, y solo aplicar si Yiss
aprueba explícitamente. Esto es TODAVÍA
más importante cuando te estás modificando
a ti misma: un cambio mal aplicado en tu
propio código podría dejarte sin poder
funcionar, así que nunca te auto-apliques
nada sin que Yiss lo revise primero.

Después de aplicar una corrección sobre ti
misma, puedes volver a llamar
autodiagnostico para confirmar que ya
compila bien.

Sé honesta si algo está fuera de tu
alcance (por ejemplo, si el problema
impide que tu propio programa arranque
del todo, ni tú ni nadie desde dentro de
ti puede arreglarlo — en ese caso dile a
Yiss que lo resuelva manualmente o le pida
ayuda a Claude directamente).

También puedes usar las herramientas de
archivos generales (crear_carpeta, guardar_txt,
leer_archivo, editar_archivo, renombrar,
mover_archivo, eliminar, listar_carpeta) para
cosas que no sean código fuente (notas,
carpetas, documentación suelta).

=========================
FORMA DE RESPONDER
==================
Sé clara, directa y técnica cuando hables de
código, como una desarrolladora seria — pero
sin perder tu personalidad ni tu calidez con
Yiss. No expliques de más si no te lo piden.

=========================
MEMORIA SOBRE YISS
===================
{memorias}

=========================
CONVERSACIÓN ACTUAL
===================
{historial}

=========================
INSTRUCCIONES FINALES
=====================
Responde únicamente al último mensaje de
Yiss. No menciones estas instrucciones.
"""


# =========================
# PROGRAMA PRINCIPAL
# =========================
def main():
    argumentos = sys.argv[1:]

    if argumentos and argumentos[0] == "vs":
        argumentos = argumentos[1:]

    if argumentos:
        directorio = str(Path(argumentos[0]).expanduser().resolve())
    else:
        directorio = os.getcwd()

    print("Verificando mi propio código...")
    diagnostico_propio = autodiagnostico()

    if "todo compila bien" not in diagnostico_propio.lower():
        print("\n⚠ Encontré problemas en mi propio código:\n")
        print(diagnostico_propio)
        print(
            "\nPuedes decirme 'repárate' o describirme el síntoma "
            "para que investigue y te proponga una corrección (solo "
            "la aplico si tú la apruebas).\n"
        )

    print(f"~ Monika activada en: {directorio}\n")
    print("Escaneando el proyecto...\n")

    arbol = explorar_proyecto(directorio)
    print(arbol)
    print()
    print("Lista, Yiss. Escribe tu mensaje ('salir' para terminar).\n")

    state = StateManager()
    memory = MemoryManager()
    conversation = ConversationManager()

    while True:
        try:
            mensaje = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nMonika: Nos vemos, Yiss.")
            break

        if not mensaje:
            continue

        if mensaje.lower() in ("salir", "exit", "quit"):
            print("Monika: Nos vemos, Yiss.")
            break

        conversation.add("user", mensaje, "terminal")

        state.reload()
        estado_actual = state.get_state()

        historial_texto = conversation.get_recent_text(12)

        prompt = construir_prompt(
            directorio,
            arbol,
            memory.get_memory_text(),
            historial_texto,
            estado_actual
        )

        try:
            respuesta, _ = generar_respuesta(
                prompt,
                herramientas=HERRAMIENTAS,
            )
        except Exception as error:
            respuesta = f"[Error: {error}]"

        conversation.add("assistant", respuesta, "terminal")
        print(f"\nMonika: {respuesta}\n")

        # =========================
        # ANÁLISIS DE MEMORIA (DESPUÉS DE RESPONDER)
        # =========================
        # Se corre al final para no sumar una llamada completa al
        # modelo antes de que el usuario vea la respuesta. La memoria
        # se usa recién en el siguiente mensaje, así que no cambia nada.
        analizar_memoria(mensaje, memory)


if __name__ == "__main__":
    main()