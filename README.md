# Director Workshop OCI · 0.7

Template funcional de **12 archivos**, sin carpeta de tests ni credenciales.
Cada contenedor ejecuta un Director para un equipo. El servidor de carrera,
los tres auxiliares, la UI y el torneo continúan juntos en el servidor original.

## Archivos

| Archivo | Responsabilidad |
|---|---|
| `01_apikeys.py` | Primer ejercicio: una pregunta a Enterprise AI con API key y Responses API |
| `02_vectorStore.py` | Segundo ejercicio: cargar documentos, indexarlos y buscar con API key |
| `datos/Formula1_2025Season_Drivers.txt` | Datos de muestra ya preparados para cargar y buscar |
| `estrategia.py` | Prompt editable, validación de órdenes y respaldo mínimo |
| `agente.py` | Ficha, variables de entorno, cliente OCI, auxiliares y conexión a carrera |
| `main.py` | Arranque y endpoints HTTP de alojamiento |
| `requirements.txt` | Cinco dependencias directas, sin SDK de Claude ni YAML |
| `Dockerfile` | Python 3.11, usuario no root y un worker en 0.0.0.0:8080 |
| `.env.example` | Plantilla pública de variables de ejecución |
| `.dockerignore` | Sólo permite los tres módulos del Director y dependencias en la imagen |
| `.gitignore` | Excluye credenciales y archivos locales |
| `README.md` | Instrucciones del workshop |

## 0. Tu primera llamada a Enterprise AI con API key

Antes de construir tu Director, ejecuta `01_apikeys.py` para comprobar tu acceso al
modelo. Este ejercicio es independiente: no requiere equipo, token, servidor de
carrera ni Docker. Sólo envía una pregunta a OCI e imprime la respuesta.

Necesitas Python 3.11 o posterior, acceso a Internet y los siguientes datos del
organizador: una API key de **OCI Generative AI**, el OCID del proyecto y un modelo
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
export OCI_GENAI_MODEL=openai.gpt-oss-120b
export OCI_GENAI_API_KEY='REEMPLAZAR_API_KEY_DE_OCI_GENERATIVE_AI'
export OCI_GENAI_PROJECT_ID='ocid1.generativeaiproject.REEMPLAZAR'
```

El ejemplo utiliza las mismas variables `OCI_GENAI_*` del Director, pero las toma
del entorno de la terminal: **no carga `.env` automáticamente**. Para este primer
ejercicio usamos `openai.gpt-oss-120b`; más adelante, el `.env.example` del Director
propone `openai.gpt-oss-20b` para Chat Completions. El modelo debe estar habilitado
para tu proyecto, región y API. No compartas tu clave ni la escribas en el código.

Ejecuta la pregunta incluida y luego prueba con una propia:

```bash
python 01_apikeys.py
python 01_apikeys.py "¿Cómo influye el desgaste de llantas en la estrategia de carrera?"
```

La salida esperada es una explicación en texto generada por el modelo; su contenido
puede variar entre ejecuciones. Un error termina con código distinto de cero y un
mensaje breve. HTTP 401/403 orienta a revisar credenciales y permisos; 400/404, a
revisar proyecto, región y modelo; 429, a revisar límites o capacidad del servicio.

Observa los elementos principales de `01_apikeys.py`:

| Elemento | Para qué sirve |
|---|---|
| `base_url` | Dirige la llamada al endpoint regional de OCI |
| `api_key` | Autentica la solicitud con tu API key de OCI Generative AI |
| `project` | Identifica el proyecto Generative AI de la solicitud |
| `model` | Selecciona el modelo que responderá |
| `input` | Contiene la pregunta o instrucción del participante |
| `response.output_text` | Obtiene el texto generado |

Aunque se importa `OpenAI`, la inferencia ocurre en OCI. Este ejercicio utiliza
`client.responses.create()`. El Director actual utiliza
`client.chat.completions.create()` y exige una respuesta JSON con órdenes de
carrera. Son dos interfaces diferentes; este ejercicio no cambia la del Director.

Cuando obtengas una respuesta, continúa con el segundo ejercicio. Los dos ejemplos
son archivos locales de aprendizaje: no se incluyen en la imagen Docker del agente.

## 0.1. Busca documentos con un vector store

`02_vectorStore.py` muestra el siguiente paso: subir un documento, obtener su
`file_id`, asociarlo a un vector store y recuperar fragmentos mediante una consulta.
Utiliza **API key** y el SDK ya instalado; no requiere IAM, wallet ni dependencias
adicionales. Tampoco conecta al servidor de carrera ni modifica al Director.

Conserva `OCI_GENAI_API_KEY`, `OCI_GENAI_PROJECT_ID` y `OCI_GENAI_REGION` del primer
ejercicio. El organizador debe proporcionar un **vector store existente para datos
no estructurados**, accesible desde ese proyecto en la misma región. Configúralo:

```bash
export OCI_GENAI_VECTOR_STORE_ID='REEMPLAZAR_ID_DEL_VECTOR_STORE'
```

Esta variable sólo la utiliza el segundo ejemplo. `OCI_GENAI_MODEL` no se utiliza:
la búsqueda devuelve fragmentos y no llama a un modelo para redactar una respuesta.
La API key necesita permisos para subir archivos, asociarlos y consultar el store.

El ejemplo reutiliza un store existente: no crea uno nuevo ni consume otro cupo de
vector stores del tenant. El identificador suele tener formato `vs_...`; debe ser el
ID real asignado por OCI, sin inventarlo ni reemplazarlo por el nombre del recurso.

### Carga, indexación y búsqueda

Desde la raíz de esta carpeta, con el entorno Python del primer ejercicio activo:

```bash
python 02_vectorStore.py datos/Formula1_2025Season_Drivers.txt
```

El archivo de muestra ya está preparado en TXT con los 21 registros, columnas y
valores del CSV proporcionado. El script lo sube directamente, sin transformar su
contenido. Los valores no se verifican contra datos externos. Para otros archivos,
prepara previamente un formato que OCI admita; la indexación directa de CSV fue
rechazada por el servicio durante la validación del workshop.

El programa muestra:

1. El `file_id` devuelto al subir el TXT.
2. El `vector_store_id` utilizado.
3. El estado de indexación, hasta `completed`.
4. Los fragmentos recuperados, su archivo de origen y `score` de relevancia.

La pregunta predeterminada es `Which team does Lando Norris drive for?`. En el
documento de muestra, el fragmento correspondiente contiene `Team: McLaren`.
El texto y orden de resultados pueden variar; el score no representa una
probabilidad de que la información sea verdadera.

### Reutiliza el archivo y cambia la pregunta

Cada ejecución con una ruta sube un archivo nuevo. Para hacer más consultas sin
duplicar cargas, copia el `file_id` que imprimió el programa y reutilízalo:

```bash
python 02_vectorStore.py --file-id 'REEMPLAZAR_FILE_ID' \
  --pregunta 'Which team does Charles Leclerc drive for?'
```

No necesitas escribir un `file_id` antes de la primera carga: OCI lo genera.
`file_ids` sería una lista de IDs obtenidos al subir varios documentos, para
asociarlos mediante la API de lotes; este ejercicio comienza con un solo archivo.
Para un TXT o PDF propio puedes pasar su ruta directamente.
Su procesamiento queda sujeto a los formatos y límites que admita OCI.

La espera de indexación es de hasta 180 segundos. Si termina antes de completarse,
el script imprime el ID para continuar con `--file-id`; opcionalmente aumenta la
espera con `--espera 300`. Las solicitudes individuales tienen timeout de 30 s.
No se busca hasta que el archivo esté en estado `completed`.

Los recursos quedan en OCI después de ejecutar el ejemplo; el script no borra
documentos ni modifica la expiración del store. Si el store contiene otros
documentos, también pueden aparecer entre los resultados: revisa `file_id` y
nombre del archivo. Coordina la limpieza o expiración con el organizador.

Después de completar ambos ejercicios, continúa con la personalización del Director.

## 1. Diseña tu Director

Edita `FICHA` al inicio de `agente.py`: ingeniero, piloto ficticio, número, estilo,
riesgo, relación con estrategia, regla de oro y frase de radio. El número debe
estar entre 1 y 99, salvo 3 y 6. Opcionalmente puedes inyectar el objeto completo
mediante `DIRECTOR_FICHA_JSON` sin reconstruir la imagen.

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

```bash
cp .env.example .env
chmod 600 .env
```

Completa `.env` con los datos proporcionados por el organizador:

```dotenv
EQUIPO=MI_EQUIPO
TOKEN=MI_TOKEN
SERVIDOR=ws://IP_DEL_SERVIDOR:8000
OCI_GENAI_REGION=us-chicago-1
OCI_GENAI_MODEL=openai.gpt-oss-20b
OCI_GENAI_API_KEY=MI_API_KEY_DE_OCI_GENERATIVE_AI
OCI_GENAI_PROJECT_ID=OCID_DE_MI_PROYECTO_GENERATIVE_AI
```

Usa un modelo disponible en tu región que soporte Chat Completions de OCI.
La API key debe ser de **OCI Generative AI**, de la misma región, y tener los
permisos correspondientes. No es una API key de OpenAI ni una clave privada IAM.
El código construye internamente el endpoint regional de OCI; no hay variable
para sustituirlo por un servicio externo o local. El modelo se ejecuta en OCI;
no se descarga en el contenedor.

Estas variables **sustituyen** `LLM_PROVEEDOR`, `DIRECTOR_POLITICA` y las variables
`OPENAI_*` de la versión 0.2. No se aceptan como configuración del nuevo template.
No se carga `.env` desde Python: Docker u OCI deben inyectar las variables.
Mantén `.env` fuera del material que compartas con los participantes.

## 3. Construye tu imagen

Desde esta carpeta, con Docker y Buildx disponibles:

```bash
docker buildx build --platform linux/amd64 --load -t techweek26-director:0.7 .
```

> **OCI Cloud Shell:** selecciona la arquitectura **X86_64** antes de construir
> la imagen, para trabajar con la plataforma `linux/amd64` que utiliza este
> workshop. En Cloud Shell, abre **Actions > Architecture**, elige **X86_64**
> y confirma el reinicio de la sesión. Consulta la
> [documentación de arquitectura de Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cloudshellintro.htm#Cloud_Shell_Architecture).

Si Docker de Rancher Desktop no está en PATH en macOS:

```bash
export PATH="$HOME/.rd/bin:$PATH"
```

## 4. Ejecuta localmente

```bash
docker run -d --name director-workshop \
  --platform linux/amd64 --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m,mode=1777 \
  --env-file .env -p 127.0.0.1:8080:8080 \
  techweek26-director:0.7

docker logs -f director-workshop
```

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

Sólo puede haber un Director conectado por equipo. Detén el bot o contenedor
anterior antes de conectar el tuyo. Si otro toma el control, la instancia se
detiene para evitar que ambos reconecten en bucle.

Para detener y eliminar tu contenedor local:

```bash
docker stop --timeout 30 director-workshop
docker rm director-workshop
```

## 5. Publica en OCIR

El repositorio del organizador utiliza el tag `0.7`:

```bash
docker tag techweek26-director:0.7 ord.ocir.io/idajmumkp9ca/techweek26-director:0.7
docker login ord.ocir.io
docker push ord.ocir.io/idajmumkp9ca/techweek26-director:0.7
```

> **Namespace del tenant:** `idajmumkp9ca` es el namespace de Object Storage del
> tenant del organizador y forma parte de la ruta del repositorio en OCIR.
> Para publicar en tu propio tenant, reemplázalo en los comandos `docker tag`
> y `docker push` por tu namespace.
>
> Para consultarlo en la consola de OCI, abre el menú de perfil en la esquina
> superior derecha y haz clic en `Tenancy: <nombre-tenant>`. En la página
> **Tenancy details**, busca **Object Storage Settings** y copia el valor de
> **Object Storage Namespace**. Consulta la
> [documentación de namespaces de Object Storage](https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/understandingnamespaces.htm).

Para imágenes personalizadas de participantes usa tu repositorio/tag asignado;
no sobrescribas el tag compartido del organizador.

## 6. Despliega en OCI Hosted Deployments

Selecciona la imagen de OCIR y configura las variables anteriores en la aplicación.
Usa **una aplicación por equipo, con mínimo=1 y máximo=1 réplicas**, sin múltiples
workers. No hace falta almacenamiento administrado ni volúmenes. Configura también
autenticación entrante y conectividad de salida hacia carrera y OCI Generative AI.
Una IP privada local requiere una ruta desde OCI, por ejemplo VCN y VPN.

No definas variables reservadas como PORT, K_SERVICE, K_CONFIGURATION, K_REVISION,
OCI_RESOURCE_PRINCIPAL_* o KUBERNETES_*. Este template sólo usa API key para inferencia.
El deployment real debe validarse en tu tenancy, incluida la actividad del Director
durante periodos sin peticiones HTTP entrantes y los reemplazos de instancia.

La etiqueta de imagen de esta entrega es `0.7`. El campo `version` de `/status`
y el título interno de FastAPI conservan el valor `0.4` del código incluido.

## Tiempo de decisión y respaldo

Se conserva un presupuesto de **6.5 s para auxiliares + LLM** en las ventanas de
carrera, con margen adicional antes del límite enviado por el servidor. Si hay
timeout, error de OCI o JSON inválido, se registra el motivo y se mantiene el
ritmo/energía vigentes y la parada programada. Para pre-carrera y Momentos existe
una respuesta mínima válida. No se incluye el motor completo de estrategias por
reglas ni el modo azar de las versiones anteriores.

Si falta configuración obligatoria, la aplicación no arranca. El estado y los logs
no muestran tokens, claves ni excepciones completas que puedan contenerlos.

Los logs del logger `director` incluyen eventos JSON en una sola línea:

- `LLM_RESPUESTA`: contenido devuelto por el modelo antes de validar el JSON,
  modelo utilizado y duración de la consulta en segundos.
- `SERVIDOR_RESPUESTA_ENVIADA`: respuesta final después de completar el envío
  WebSocket, con fuente `llm` o `respaldo`. Confirma el envío, no la aceptación
  del servidor.
- `SERVIDOR_RESPUESTA_NO_ENVIADA`: no había conexión disponible para enviarla.

Los eventos de una misma solicitud comparten `correlacion`, `equipo`, tipo de
`solicitud`, `ventana`, `vuelta` e ID de `momento`, cuando corresponden. También se
registra el texto del modelo si no contiene JSON válido; en un timeout sin
respuesta no existe un evento `LLM_RESPUESTA`. Los valores de las credenciales
configuradas y los campos sensibles se ocultan en estos eventos. Consulta la
salida con `docker logs -f director-workshop`.

Referencias:
[Responses API](https://docs.oracle.com/en-us/iaas/Content/generative-ai/responses-api.htm),
[Files API](https://docs.oracle.com/en-us/iaas/Content/generative-ai/files.htm),
[Vector Store Files](https://docs.oracle.com/en-us/iaas/Content/generative-ai/vector-store-files.htm),
[contenedores OCI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/prepare-artifacts.htm),
[API keys](https://docs.oracle.com/en-us/iaas/Content/generative-ai/api-keys.htm),
[Chat Completions](https://docs.oracle.com/en-us/iaas/Content/generative-ai/chat-completions-api.htm).
