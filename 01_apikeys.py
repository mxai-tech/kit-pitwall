"""Primer ejercicio: una pregunta a OCI Enterprise AI usando una API key."""
import argparse
import os
import re
import sys

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pregunta", nargs="?",
                        default="Explica en español qué hace el muro de estrategia de un equipo de Fórmula 1.")
    args = parser.parse_args()
    if not os.getenv("OCI_GENAI_API_KEY", "").strip():
        raise ValueError("Configura la variable OCI_GENAI_API_KEY antes de ejecutar el ejemplo.")
    region = os.getenv("OCI_GENAI_REGION", "us-chicago-1")
    modelo = os.getenv("OCI_GENAI_MODEL", "openai.gpt-oss-120b")
    if not re.fullmatch(r"[a-z]{2}-[a-z0-9]+-[0-9]+", region):
        raise ValueError("OCI_GENAI_REGION debe ser una región OCI válida, por ejemplo us-chicago-1.")

    # El SDK es de OpenAI, pero endpoint, credenciales y ejecución pertenecen a OCI.
    with OpenAI(
        base_url=f"https://inference.generativeai.{region}.oci.oraclecloud.com/20231130/actions/v1",
        api_key=os.environ["OCI_GENAI_API_KEY"],
        timeout=60,
        max_retries=0,
    ) as client:
        response = client.responses.create(model=modelo, input=args.pregunta)
        if not response.output_text:
            raise ValueError("El modelo no devolvió texto. Revisa el modelo y la solicitud.")
        print(response.output_text)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(str(exc))
    except APITimeoutError:
        sys.exit("OCI no respondió dentro de 60 segundos. Intenta nuevamente.")
    except APIConnectionError:
        sys.exit("No fue posible conectar con OCI. Revisa la red y la región.")
    except APIStatusError as exc:
        # No imprimir la excepción completa: puede contener datos de la petición.
        sys.exit(f"OCI respondió HTTP {exc.status_code}. Revisa permisos, región y compatibilidad del modelo.")
