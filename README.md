# Director Workshop OCI

Cada proceso ejecuta un Director para un equipo. El servidor de carrera,
los tres auxiliares, la UI y el torneo continúan juntos en el servidor.

## Archivos

| Archivo | Responsabilidad |
|---|---|
| `01_apikeys.py` | Primer ejercicio: una pregunta a Enterprise AI con API key y Responses API |
| `estrategia.py` | Prompt editable, validación de órdenes y respaldo mínimo |
| `agente.py` | Ficha, variables de entorno, cliente OCI, auxiliares y conexión a carrera |
| `main.py` | Arranque y endpoints HTTP de alojamiento |
| `requirements.txt` | Cinco dependencias directas, sin SDK de Claude ni YAML |
| `.env.example` | Plantilla pública de variables de ejecución |
| `README.md` | Instrucciones del workshop |

## 0. Tu primera llamada a Enterprise AI con API key

Antes de construir tu Director, ejecuta `01_apikeys.py` para comprobar tu acceso al
modelo. Este ejercicio es independiente: no requiere equipo, token ni servidor
de carrera. Sólo envía una pregunta a OCI e imprime la respuesta.

Necesitas Python 3.11 o posterior, acceso a Internet y los siguientes datos del
organizador: una API key de **OCI Generative AI** y un modelo
compatible con **Responses API** en la región elegida. La clave no es una API key
de OpenAI ni una clave privada IAM.

Desde esta carpeta, crea un entorno e instala las dependencias existentes:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Configura las variables en esa misma terminal, reemplazando los valores de ejemplo:

```bash
export OCI_GENAI_REGION=us-chicago-1
export OCI_GENAI_MODEL=openai.gpt-oss-20b
export OCI_GENAI_API_KEY='REEMPLAZAR_API_KEY_DE_OCI_GENERATIVE_AI'
```

El ejemplo comparte las variables de región, modelo y API key con el Director.
Ambos utilizan el endpoint de inferencia con API key y **no requieren un Project ID**.
Las variables se leen del entorno de la terminal: **no carga `.env` automáticamente**.
Estos comandos seleccionan `openai.gpt-oss-20b`, el mismo modelo del Director.
Si no defines `OCI_GENAI_MODEL`, el script utiliza `openai.gpt-oss-120b`.
El modelo debe estar disponible en tu región y ser compatible con Responses API.
No compartas tu clave ni la escribas en el código.

Ejecuta la pregunta incluida y luego prueba con una propia:

```bash
python 01_apikeys.py
python 01_apikeys.py "¿Cómo influye el desgaste de llantas en la estrategia de carrera?"
```

La salida esperada es una explicación en texto generada por el modelo; su contenido
puede variar entre ejecuciones. Un error termina con código distinto de cero y un
mensaje breve. HTTP 401/403 orienta a revisar credenciales y permisos; 400/404, a
revisar región y modelo; 429, a revisar límites o capacidad del servicio.

Observa los elementos principales de `01_apikeys.py`:

| Elemento | Para qué sirve |
|---|---|
| `base_url` | Dirige la llamada al endpoint regional de OCI |
| `api_key` | Autentica la solicitud con tu API key de OCI Generative AI |
| `model` | Selecciona el modelo que responderá |
| `input` | Contiene la pregunta o instrucción del participante |
| `response.output_text` | Obtiene el texto generado |

Aunque se importa `OpenAI`, la inferencia ocurre en OCI. Tanto este ejercicio
como el Director utilizan `client.responses.create()`. El ejercicio imprime
texto libre; el Director exige una respuesta JSON con órdenes de carrera.
Los dos utilizan el endpoint de inferencia sin proyecto.

Cuando obtengas una respuesta, continúa con la personalización del Director.
El ejemplo es un archivo de aprendizaje independiente del proceso del Director.

## 1. Diseña tu Director

Edita `FICHA` al inicio de `agente.py`: ingeniero, piloto ficticio, número, estilo,
riesgo, relación con estrategia, regla de oro y frase de radio. El número debe
estar entre 1 y 99, salvo 3 y 6. Opcionalmente puedes inyectar el objeto completo
mediante `DIRECTOR_FICHA_JSON` antes de iniciar el proceso.

El archivo `agente.py` está organizado en cuatro pasos para recorrerlo durante el
workshop: personalidad (`FICHA`), validación (`validar_entorno()`), llamada al modelo
(`ModeloOCI`) y comunicación de carrera (`Agente`). El cliente construye la variable
local `url_oci` a partir de la región configurada. No necesitas un archivo separado
de configuración ni una clase intermedia: `Agente()` lee directamente el equipo,
token y servidor del entorno, y `ModeloOCI()` lee las variables de OCI. La función
`validar_entorno()` conserva las validaciones y carga la ficha opcional de
`DIRECTOR_FICHA_JSON`. Las variables que configura el participante no cambian.

Edita `INSTRUCCIONES` en `estrategia.py` para definir cómo compara las lecturas de
llantas, pista y estrategia. No elimines los formatos de mensajes ni su validación.
No hay políticas seleccionables ni proveedores alternativos: siempre se consulta
un modelo de OCI. El SDK OpenAI sólo se usa como cliente compatible, no como
destino de inferencia.

## 2. Configura tus variables

Configura las variables en la misma terminal donde iniciarás el Director.
Reemplaza los valores de ejemplo por los datos proporcionados por el organizador:

```bash
export EQUIPO=MI_EQUIPO
export TOKEN='MI_TOKEN'
export SERVIDOR='ws://IP_DEL_SERVIDOR:8000'
export OCI_GENAI_REGION=us-chicago-1
export OCI_GENAI_MODEL=openai.gpt-oss-20b
export OCI_GENAI_API_KEY='MI_API_KEY_DE_OCI_GENERATIVE_AI'
```

Usa un modelo disponible en tu región que soporte Responses API de OCI.
La API key debe ser de **OCI Generative AI**, de la misma región, y tener los
permisos correspondientes. No es una API key de OpenAI ni una clave privada IAM.
El código construye internamente el endpoint regional de OCI; no hay variable
para sustituirlo por un servicio externo o local. El modelo se ejecuta en OCI;
no se descarga en tu equipo.

El Director usa la URL base
`https://inference.generativeai.<region>.oci.oraclecloud.com/20231130/actions/v1`
y no requiere `OCI_GENAI_PROJECT_ID`. El ejemplo introductorio `01_apikeys.py`
utiliza la misma URL base y tampoco necesita un proyecto.

Estas variables **sustituyen** `LLM_PROVEEDOR`, `DIRECTOR_POLITICA` y las variables
`OPENAI_*` de la versión 0.2. No se aceptan como configuración del nuevo template.
Python no carga `.env` automáticamente: para ejecutar localmente, utiliza los
comandos `export` anteriores. `.env.example` sirve como referencia de las
variables disponibles. Mantén tus credenciales fuera del repositorio y del
material compartido.

## 3. Ejecuta localmente

Desde la raíz del repositorio, crea o activa el entorno Python e instala las
dependencias. Si ya completaste el ejercicio 0, puedes reutilizar ese entorno:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Con las variables del paso 2 configuradas en esta misma terminal, inicia el
Director:

```bash
python -m uvicorn main:app \
  --host 127.0.0.1 \
  --port 8080 \
  --workers 1 \
  --no-access-log
```

Los logs aparecen en la terminal. El mensaje `Director conectado y autenticado`
confirma que la conexión con el Servidor de Carrera se estableció correctamente.

En otra terminal:

```bash
curl -i http://localhost:8080/health
curl -i http://localhost:8080/ready
curl -fsS http://localhost:8080/status
curl -N -H 'Accept: text/event-stream' http://localhost:8080/status
```

`/health`: 200 mientras vive la tarea del Director. `/ready`: 200 después de
autenticarse en carrera; no requiere una carrera iniciada. `/status` devuelve JSON
o una fotografía SSE según Accept. Las sondas devuelven sólo código HTTP y un
cuerpo vacío con Content-Type application/json.

El Director inicia la conexión saliente a `SERVIDOR/ws/agente` con su equipo y
token. Recibe pre-carrera, ventanas y Momentos; consulta los auxiliares en
`http(s)://SERVIDOR/api/agentes/{nombre}` y devuelve órdenes por el mismo WebSocket.
No requiere que el servidor llame al puerto 8080 del Director.

Sólo puede haber un Director conectado por equipo. Detén el proceso anterior
antes de conectar el tuyo. Si otro toma el control, la instancia se
detiene para evitar que ambos reconecten en bucle.

Para detener el Director, presiona **Ctrl+C** en la terminal donde se ejecuta.

Referencias:
[Responses API](https://docs.oracle.com/en-us/iaas/Content/generative-ai/responses-api.htm),
[API keys](https://docs.oracle.com/en-us/iaas/Content/generative-ai/api-keys.htm).
