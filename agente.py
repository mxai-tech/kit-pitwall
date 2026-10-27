"""Director del workshop: personalidad, configuración, cliente OCI y conexión a carrera."""
import asyncio
import copy
import json
import logging
import os
import re
import time
from contextvars import ContextVar
from uuid import uuid4
from urllib.parse import urlencode, urlsplit

import httpx
import websockets
from openai import AsyncOpenAI

from estrategia import prompt, respaldo, validar

LOG = logging.getLogger("director")
CONTEXTO_LOG = ContextVar("contexto_log", default={})


def registrar(evento, **campos):
    """Una línea JSON por evento, sin credenciales incluso si el modelo las repite."""
    datos = {"evento": evento, **CONTEXTO_LOG.get(), **campos}
    def limpiar(valor):
        if isinstance(valor, dict):
            return {k: "[OCULTO]" if any(s in k.lower() for s in ("token", "api_key", "password", "authorization"))
                    else limpiar(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [limpiar(v) for v in valor]
        if isinstance(valor, str):
            for nombre in ("TOKEN", "OCI_GENAI_API_KEY", "OPENAI_API_KEY"):
                secreto = os.getenv(nombre)
                if secreto:
                    valor = valor.replace(secreto, "[OCULTO]")
        return valor
    LOG.info("%s", json.dumps(limpiar(datos), ensure_ascii=False))

# 1. Define la personalidad de tu equipo.
# PERSONALIZA esta ficha. También puedes sustituirla mediante DIRECTOR_FICHA_JSON.
FICHA = {
    "ingeniero": "Mi ingeniero", "piloto": "Mi piloto", "numero": 27,
    "estilo": "calculador", "riesgo": 3, "relacion": "cuestiona",
    "regla_de_oro": "Cuidar las llantas", "frase_radio": "Vamos equipo",
    "descripcion_avatar": "Piloto ficticio con casco",
}


# 2. Carga y valida las variables de entorno.
def validar_entorno():
    """Valida las variables del workshop y devuelve la ficha de personalidad."""
    e = os.environ
    nombres = ("EQUIPO", "TOKEN", "SERVIDOR", "OCI_GENAI_API_KEY", "OCI_GENAI_PROJECT_ID")
    for nombre in nombres:
        if not e.get(nombre, "").strip():
            raise ValueError(f"Falta la variable {nombre}")
    url = urlsplit(e["SERVIDOR"])
    if (url.scheme not in ("ws", "wss") or not url.hostname or url.username
            or url.password or url.query or url.fragment or url.path not in ("", "/")):
        raise ValueError("SERVIDOR debe ser ws://host:puerto o wss://host, sin ruta ni credenciales")
    try:
        url.port
    except ValueError:
        raise ValueError("Puerto de SERVIDOR inválido") from None
    region = e.get("OCI_GENAI_REGION", "us-chicago-1")
    modelo = e.get("OCI_GENAI_MODEL", "openai.gpt-oss-20b")
    if not re.fullmatch(r"[a-z]{2}-[a-z0-9]+-[0-9]+", region):
        raise ValueError("Región OCI inválida")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]+", modelo):
        raise ValueError("Identificador de modelo inválido")
    if not e["OCI_GENAI_PROJECT_ID"].startswith("ocid1.generativeaiproject."):
        raise ValueError("OCI_GENAI_PROJECT_ID debe identificar un proyecto Generative AI")
    try:
        ficha = json.loads(e["DIRECTOR_FICHA_JSON"]) if e.get("DIRECTOR_FICHA_JSON") else copy.deepcopy(FICHA)
    except ValueError:
        raise ValueError("DIRECTOR_FICHA_JSON debe ser JSON válido") from None
    if not isinstance(ficha, dict):
        raise ValueError("La ficha debe ser un objeto JSON")
    for nombre in ("ingeniero", "piloto", "regla_de_oro", "frase_radio"):
        if not isinstance(ficha.get(nombre), str) or not ficha[nombre].strip():
            raise ValueError(f"La ficha requiere {nombre} como texto")
    if ficha.get("estilo") not in ("agresivo", "calculador", "conservador"):
        raise ValueError("Estilo de ficha inválido")
    if ficha.get("relacion") not in ("sigue", "cuestiona", "solo"):
        raise ValueError("Relación de ficha inválida")
    for nombre, minimo, maximo in (("numero", 1, 99), ("riesgo", 1, 5)):
        if type(ficha.get(nombre)) is not int or not minimo <= ficha[nombre] <= maximo:
            raise ValueError(f"Valor inválido de {nombre} en ficha")
    if ficha["numero"] in (3, 6):
        raise ValueError("El número del piloto no puede ser 3 ni 6")
    return ficha


# 3. Consulta OCI con API key.
class ModeloOCI:
    """Única conexión LLM: OCI Generative AI por API key y Chat Completions."""
    def __init__(self):
        self.nombre = os.getenv("OCI_GENAI_MODEL", "openai.gpt-oss-20b")
        region = os.getenv("OCI_GENAI_REGION", "us-chicago-1")
        url_oci = f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"
        self.cliente = AsyncOpenAI(api_key=os.environ["OCI_GENAI_API_KEY"],
                                  project=os.environ["OCI_GENAI_PROJECT_ID"],
                                  base_url=url_oci, timeout=7, max_retries=0)

    async def consultar(self, sistema, usuario):
        inicio = time.monotonic()
        r = await self.cliente.chat.completions.create(
            model=self.nombre,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        )
        texto = r.choices[0].message.content or ""
        registrar("LLM_RESPUESTA", modelo=self.nombre, respuesta=texto,
                  duracion_s=round(time.monotonic() - inicio, 3))
        decoder = json.JSONDecoder()
        for inicio, caracter in enumerate(texto):
            if caracter == "{":
                try:
                    datos, _ = decoder.raw_decode(texto[inicio:])
                    if isinstance(datos, dict):
                        return datos
                except ValueError:
                    pass
        raise ValueError("El modelo no devolvió un objeto JSON")

    async def cerrar(self):
        await self.cliente.close()


# 4. Conecta al servidor de carrera y responde a sus solicitudes.
class Agente:
    def __init__(self):
        self.ficha = validar_entorno()
        self.equipo = os.environ["EQUIPO"].strip()
        self.token = os.environ["TOKEN"]
        self.servidor = os.environ["SERVIDOR"].rstrip("/")
        self.modelo = ModeloOCI()
        self.ws = None
        self.tarea = None
        self.pendientes = set()
        self.activo = True
        self.autenticado = False
        self.error = None
        self.reconexiones = 0
        self.errores_respuesta = 0

    def iniciar(self):
        self.tarea = asyncio.create_task(self.correr(), name="director")

    def saludable(self):
        return self.tarea is not None and not self.tarea.done() and self.error is None

    def listo(self):
        return self.saludable() and self.autenticado

    def estado(self):
        return {"version": "0.4", "equipo": self.equipo, "modelo": self.modelo.nombre,
                "saludable": self.saludable(), "listo": self.listo(), "error": self.error,
                "autenticado": self.autenticado, "reconexiones": self.reconexiones,
                "respuestas_pendientes": len(self.pendientes), "errores_respuesta": self.errores_respuesta}

    async def consultar_auxiliar(self, http, nombre):
        base = self.servidor.replace("ws://", "http://").replace("wss://", "https://")
        try:
            r = await http.get(f"{base}/api/agentes/{nombre}",
                               params={"equipo": self.equipo, "token": self.token}, timeout=4)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}"}
        except (httpx.RequestError, ValueError):
            return {"error": "Auxiliar no disponible"}

    async def decidir(self, mensaje, http):
        inicio = time.monotonic()
        nombres = ("llantas", "pista", "estrategia")
        agentes = {}
        if mensaje["tipo"] == "ventana":
            resultados = await asyncio.gather(*(self.consultar_auxiliar(http, n) for n in nombres))
            agentes = dict(zip(nombres, resultados))
        sistema, usuario = prompt(mensaje, agentes, self.ficha)
        # Conserva el presupuesto total de 6.5 s para auxiliares + LLM en carrera.
        presupuesto = 6.5 if mensaje["tipo"] == "ventana" else 20
        restante = max(.01, presupuesto - (time.monotonic() - inicio))
        datos = await asyncio.wait_for(self.modelo.consultar(sistema, usuario), restante)
        return validar(mensaje, datos)

    async def responder(self, mensaje, http):
        contexto = CONTEXTO_LOG.set({"equipo": self.equipo, "correlacion": uuid4().hex,
                                    "solicitud": mensaje["tipo"], "ventana": mensaje.get("ventana"),
                                    "vuelta": mensaje.get("vuelta"), "momento": mensaje.get("id")})
        try:
            await self._responder(mensaje, http)
        finally:
            CONTEXTO_LOG.reset(contexto)

    async def _responder(self, mensaje, http):
        inicio = time.monotonic()
        limite = max(.1, mensaje.get("limite_ms", 10000) / 1000 - 2)
        fuente = "llm"
        try:
            orden = await asyncio.wait_for(self.decidir(mensaje, http), limite)
        except Exception as e:
            # Nunca registrar la excepción completa: puede contener URLs o credenciales.
            LOG.warning("LLM %s: uso respaldo", "timeout" if isinstance(e, asyncio.TimeoutError) else type(e).__name__)
            orden, fuente = respaldo(mensaje), "respaldo"
        if self.ws is not None:
            contenido = json.dumps(orden, ensure_ascii=False)
            await self.ws.send(contenido)
            registrar("SERVIDOR_RESPUESTA_ENVIADA", fuente=fuente, respuesta=json.loads(contenido))
        else:
            registrar("SERVIDOR_RESPUESTA_NO_ENVIADA", fuente=fuente, motivo="sin_conexion")
        LOG.info("tipo=%s vuelta=%s fuente=%s duracion_s=%.2f", mensaje["tipo"],
                 mensaje.get("vuelta", "-"), fuente, time.monotonic() - inicio)

    def terminada(self, tarea):
        self.pendientes.discard(tarea)
        if not tarea.cancelled() and tarea.exception() is not None:
            self.errores_respuesta += 1
            LOG.error("No se pudo enviar una respuesta (%s)", type(tarea.exception()).__name__)

    async def cancelar_pendientes(self):
        tareas = list(self.pendientes)
        for tarea in tareas:
            tarea.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
        self.pendientes.clear()

    async def correr(self):
        url = f"{self.servidor}/ws/agente?{urlencode({'equipo': self.equipo, 'token': self.token})}"
        espera = 1
        try:
            async with httpx.AsyncClient() as http:
                while self.activo and self.error is None:
                    try:
                        async with websockets.connect(url, open_timeout=10, ping_interval=20,
                                                      ping_timeout=20, max_size=2 ** 22) as ws:
                            self.ws = ws
                            await ws.send(json.dumps({"tipo": "hola", "ficha": self.ficha}))
                            saludo = json.loads(await asyncio.wait_for(ws.recv(), 15))
                            if saludo.get("tipo") == "error":
                                self.error = "autenticacion_rechazada"
                                continue
                            if saludo.get("tipo") != "bienvenida":
                                raise ValueError("Bienvenida no válida")
                            self.autenticado = True
                            espera = 1
                            LOG.info("Director conectado y autenticado")
                            async for crudo in ws:
                                mensaje = json.loads(crudo)
                                if mensaje.get("tipo") in ("pre_carrera", "ventana", "momento"):
                                    tarea = asyncio.create_task(self.responder(mensaje, http))
                                    self.pendientes.add(tarea)
                                    tarea.add_done_callback(self.terminada)
                                elif mensaje.get("tipo") in ("setup_error", "orden_error", "momento_error"):
                                    LOG.warning("Servidor rechazó respuesta: %s", mensaje["tipo"])
                    except websockets.exceptions.ConnectionClosed as e:
                        codigo = getattr(getattr(e, "rcvd", None), "code", None)
                        if codigo in (4000, 4401):
                            self.error = "otro_director_tomo_control" if codigo == 4000 else "autenticacion_rechazada"
                    except (OSError, websockets.exceptions.WebSocketException, asyncio.TimeoutError, ValueError):
                        LOG.warning("Conexión interrumpida; se reintentará")
                    finally:
                        self.ws = None
                        self.autenticado = False
                        await self.cancelar_pendientes()
                    if self.activo and self.error is None:
                        self.reconexiones += 1
                        await asyncio.sleep(espera)
                        espera = min(10, espera * 2)
        finally:
            self.autenticado = False
            await self.cancelar_pendientes()

    async def cerrar(self):
        self.activo = False
        if self.ws is not None:
            await self.ws.close()
        if self.tarea is not None:
            self.tarea.cancel()
            await asyncio.gather(self.tarea, return_exceptions=True)
        await self.cancelar_pendientes()
        await self.modelo.cerrar()
