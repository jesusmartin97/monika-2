from tools.file_tools import (
    crear_carpeta,
    guardar_txt,
    leer_archivo
)


# Crear carpeta

ruta = crear_carpeta(

    "Nuestro_Rincon"

)

print(

    "Carpeta creada en:",

    ruta

)


# Crear archivo

archivo = guardar_txt(

    "poema.txt",

    "Este es nuestro primer poema.",

    ruta

)

print(

    "Archivo creado en:",

    archivo

)


# Leer archivo

contenido = leer_archivo(

    archivo

)

print(

    "Contenido:"


)

print(

    contenido

)
