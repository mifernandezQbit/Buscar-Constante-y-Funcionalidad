
from zipfile import ZipFile, BadZipFile
from datetime import datetime
import re
import csv
import os


# ============================================================
# CONFIGURACION
# ============================================================

RUTA_ZIP = (
    r"A:\Oficina\Qbit\Seaboard\Python\Buscar_AC"
    r"\vbstudioseaboard-seaboardoci-gru_portal_1381_441-1.0.zip"
)

CADENA_BUSCAR = "buscar_constante"

CARPETA_CSV = (
    r"A:\Oficina\Qbit\Seaboard\Python\Buscar_AC\Archivos"
)

FECHA_HORA = datetime.now().strftime("%Y%m%d_%H%M%S")

RUTA_CSV = os.path.join(
    CARPETA_CSV,
    f"resultado_{CADENA_BUSCAR}_{FECHA_HORA}.csv"
)


# ============================================================
# ENCONTRAR CIERRE DE BLOQUE O PARENTESIS
# ============================================================

def encontrar_cierre(
    texto,
    apertura,
    caracter_abre="{",
    caracter_cierra="}"
):
    nivel = 0
    i = apertura
    estado = "normal"

    while i < len(texto):
        c = texto[i]
        siguiente = texto[i + 1] if i + 1 < len(texto) else ""

        if estado == "normal":
            if c == "'":
                estado = "simple"
            elif c == '"':
                estado = "doble"
            elif c == "`":
                estado = "template"
            elif c == "/" and siguiente == "/":
                estado = "comentario_linea"
                i += 1
            elif c == "/" and siguiente == "*":
                estado = "comentario_bloque"
                i += 1
            elif c == caracter_abre:
                nivel += 1
            elif c == caracter_cierra:
                nivel -= 1
                if nivel == 0:
                    return i

        elif estado in ("simple", "doble", "template"):
            if c == "\\":
                i += 1
            elif (
                estado == "simple" and c == "'"
                or estado == "doble" and c == '"'
                or estado == "template" and c == "`"
            ):
                estado = "normal"

        elif estado == "comentario_linea":
            if c == "\n":
                estado = "normal"

        elif estado == "comentario_bloque":
            if c == "*" and siguiente == "/":
                estado = "normal"
                i += 1

        i += 1

    return None


# ============================================================
# EXTRAER EL PRIMER PARAMETRO Y SU LINEA COMPLETA
# ============================================================

def extraer_primer_parametro(bloque):
    # Busca el bloque params: {
    match_params = re.search(r"\bparams\s*:\s*\{", bloque)

    if not match_params:
        return "", ""

    # Encuentra la llave de apertura y cierre de params.
    apertura = bloque.find("{", match_params.start())
    cierre = encontrar_cierre(bloque, apertura)

    if cierre is None:
        return "", ""

    contenido_params = bloque[apertura + 1:cierre]

    # Busca la primera propiedad dentro de params.
    # Contempla tanto "nombre: valor" como la forma abreviada "nombre".
    patron_parametro = re.compile(
        r"""(?m)^[ \t]*(['"]?[\w$-]+['"]?)[ \t]*"""
        r"""(?::[ \t]*(.*?))?[ \t]*,?[ \t]*(?://.*)?$"""
    )

    coincidencia = patron_parametro.search(contenido_params)

    if not coincidencia:
        return "", ""

    # Conserva la línea original del parámetro.
    linea_completa = coincidencia.group(0).strip()

    # Extrae el valor explícito o utiliza el nombre si es abreviado.
    valor = coincidencia.group(2)

    if valor is None:
        valor = coincidencia.group(1).strip("'\"")
    else:
        # Elimina comentarios // al final de la línea.
        valor = re.split(r"//", valor, maxsplit=1)[0].strip()

        # Elimina coma final y comillas exteriores.
        valor = valor.rstrip(",").strip()
        valor = valor.strip("'\"").strip()

    return valor, linea_completa

# ============================================================
# BUSCAR LA ACTION CHAIN EXACTA EN EL ZIP
# ============================================================

def buscar_en_zip(ruta_zip, cadena):
    resultados = []

    # El prefijo application: es opcional para la comparación.
    nombre_buscado = cadena.strip()

    if nombre_buscado.startswith("application:"):
        nombre_buscado = nombre_buscado[len("application:"):]

    with ZipFile(ruta_zip, "r") as archivo_zip:
        for info in archivo_zip.infolist():

            if info.is_dir():
                continue

            try:
                contenido = archivo_zip.read(info).decode("utf-8-sig")
            except (UnicodeDecodeError, OSError, RuntimeError):
                continue

            lineas = contenido.splitlines()

            patron_llamada = re.compile(
                r"Actions\.callChain\s*\("
            )

            for llamada in patron_llamada.finditer(contenido):
                inicio_llamada = llamada.start()
                apertura = contenido.find("(", inicio_llamada)

                if apertura == -1:
                    continue

                cierre = encontrar_cierre(
                    contenido,
                    apertura,
                    "(",
                    ")"
                )

                if cierre is None:
                    continue

                bloque = contenido[apertura:cierre + 1]

                patron_chain = re.compile(
                    r"""chain\s*:\s*(['"])(.*?)\1""",
                    re.DOTALL
                )

                match_chain = patron_chain.search(bloque)

                if not match_chain:
                    continue

                nombre_chain = match_chain.group(2).strip()

                if nombre_chain.startswith("application:"):
                    nombre_chain = nombre_chain[len("application:"):]

                # Comparación exacta: no acepta sufijos como _obj.
                if nombre_chain != nombre_buscado:
                    continue

                # Línea donde está declarada la chain.
                posicion_chain = apertura + match_chain.start(2)

                numero_linea = (
                    contenido.count("\n", 0, posicion_chain) + 1
                )

                linea = lineas[numero_linea - 1]

                valor, linea_completa = extraer_primer_parametro(
                    bloque
                )

                resultados.append({
                    "ARCHIVO": info.filename,
                    "LINEA": numero_linea,
                    "RENGLON COINCIDENCIA": linea.strip(),
                    "VALOR": valor,
                    "RENGLON VALOR": linea_completa
                })

    return resultados


# ============================================================
# EXPORTAR CSV
# ============================================================

def exportar_csv(resultados, ruta_csv):
    columnas = [
        "ARCHIVO",
        "LINEA",
        "RENGLON COINCIDENCIA",
        "VALOR",
        "RENGLON VALOR"
    ]

    os.makedirs(os.path.dirname(ruta_csv), exist_ok=True)

    with open(
        ruta_csv,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as archivo:

        escritor = csv.DictWriter(
            archivo,
            fieldnames=columnas,
            delimiter=";"
        )

        escritor.writeheader()
        escritor.writerows(resultados)


# ============================================================
# EJECUCION PRINCIPAL
# ============================================================

if __name__ == "__main__":

    try:
        resultados = buscar_en_zip(
            RUTA_ZIP,
            CADENA_BUSCAR
        )

        exportar_csv(
            resultados,
            RUTA_CSV
        )

        print(f"Cadena buscada: {CADENA_BUSCAR}")
        print(f"Coincidencias encontradas: {len(resultados)}")
        print(f"CSV generado correctamente:\n{RUTA_CSV}")

    except FileNotFoundError:
        print(f"No se encontró el ZIP:\n{RUTA_ZIP}")

    except BadZipFile:
        print("El archivo ZIP no es válido.")

    except PermissionError:
        print(
            "No se pudo escribir el CSV. "
            "Cerrá el archivo si está abierto en Excel."
        )
