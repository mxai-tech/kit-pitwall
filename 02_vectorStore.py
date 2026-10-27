"""Segundo ejercicio: carga un documento y busca en un vector store existente de OCI."""
import argparse
import os
from pathlib import Path
import re
import sys
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI


def esperar_indexacion(client, vector_store_id, file_id, segundos):
    fin = time.monotonic() + segundos
    anterior = None
    while True:
        archivo = client.vector_stores.files.retrieve(vector_store_id=vector_store_id, file_id=file_id)
        if archivo.status != anterior:
            print(f"Indexación: {archivo.status}", flush=True)
            anterior = archivo.status
        if archivo.status == "completed":
            return
        if archivo.status in ("failed", "cancelled"):
            codigo = getattr(archivo.last_error, "code", "sin_codigo")
            raise ValueError(f"La indexación terminó en {archivo.status} ({codigo}).")
        if time.monotonic() >= fin:
            raise ValueError(f"La indexación sigue pendiente. Reutiliza --file-id {file_id} para continuar.")
        time.sleep(min(2, max(0, fin - time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", nargs="?", help="Ruta a un documento ya preparado, por ejemplo TXT o PDF")
    parser.add_argument("--file-id", help="Reutiliza un archivo ya cargado, sin volver a subirlo")
    parser.add_argument("--pregunta", default="Which team does Lando Norris drive for?")
    parser.add_argument("--espera", type=int, default=180, help="Segundos para esperar la indexación")
    args = parser.parse_args()
    if bool(args.archivo) == bool(args.file_id):
        parser.error("Indica una ruta de archivo o --file-id, pero no ambos.")
    if args.espera <= 0:
        parser.error("--espera debe ser mayor que cero.")
    for nombre in ("OCI_GENAI_API_KEY", "OCI_GENAI_PROJECT_ID", "OCI_GENAI_VECTOR_STORE_ID"):
        if not os.getenv(nombre, "").strip():
            raise ValueError(f"Configura la variable {nombre} antes de ejecutar el ejemplo.")
    region = os.getenv("OCI_GENAI_REGION", "us-chicago-1")
    if not re.fullmatch(r"[a-z]{2}-[a-z0-9]+-[0-9]+", region):
        raise ValueError("OCI_GENAI_REGION debe ser una región OCI válida.")
    if not os.environ["OCI_GENAI_PROJECT_ID"].startswith("ocid1.generativeaiproject."):
        raise ValueError("OCI_GENAI_PROJECT_ID debe contener el OCID de un proyecto Generative AI.")
    vector_store_id = os.environ["OCI_GENAI_VECTOR_STORE_ID"]
    with OpenAI(
        base_url=f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1",
        api_key=os.environ["OCI_GENAI_API_KEY"],
        project=os.environ["OCI_GENAI_PROJECT_ID"],
        timeout=30,
        max_retries=0,
    ) as client:
        file_id = args.file_id
        if args.archivo:
            ruta = Path(args.archivo)
            with ruta.open("rb") as archivo:
                subido = client.files.create(file=archivo, purpose="assistants")
            file_id = subido.id
            print(f"Archivo cargado: {ruta.name}", flush=True)
        print(f"file_id: {file_id}\nvector_store_id: {vector_store_id}", flush=True)
        # Reutilizar un file_id no vuelve a asociarlo si ya está en este vector store.
        try:
            client.vector_stores.files.retrieve(vector_store_id=vector_store_id, file_id=file_id)
        except APIStatusError as exc:
            if exc.status_code != 404:
                raise
            client.vector_stores.files.create(vector_store_id=vector_store_id, file_id=file_id)
        esperar_indexacion(client, vector_store_id, file_id, args.espera)
        resultados = client.vector_stores.search(
            vector_store_id=vector_store_id, query=args.pregunta,
            max_num_results=3, rewrite_query=False,
        )
        print(f"\nConsulta: {args.pregunta}")
        if not resultados.data:
            print("No se encontraron fragmentos para esta consulta.")
        for numero, resultado in enumerate(resultados.data, 1):
            print(f"\nResultado {numero}: {resultado.filename} | file_id={resultado.file_id} | score={resultado.score:.3f}")
            for bloque in resultado.content:
                if bloque.type == "text":
                    print(bloque.text)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        # ValueError tiene mensajes propios; OSError puede contener rutas privadas.
        sys.exit(str(exc) if isinstance(exc, ValueError) else "No se pudo leer el documento. Revisa ruta, permisos y formato.")
    except APITimeoutError:
        sys.exit("OCI no respondió dentro del tiempo de la solicitud. Reintenta con --file-id si ya se mostró uno.")
    except APIConnectionError:
        sys.exit("No fue posible conectar con OCI. Revisa la red y la región.")
    except APIStatusError as exc:
        sys.exit(f"OCI respondió HTTP {exc.status_code}. Revisa permisos, proyecto, vector store y formato del documento.")
