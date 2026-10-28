"""Punto de entrada para Docker y OCI Hosted Deployments, puerto 8080."""
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from agente import Agente
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def vida(app):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    for nombre in ("httpx", "httpx2", "openai", "websockets.client"):
        logging.getLogger(nombre).setLevel(logging.WARNING)
    app.state.agente = Agente()
    app.state.agente.iniciar()
    try:
        yield
    finally:
        await app.state.agente.cerrar()


app = FastAPI(title="Director Workshop OCI · 0.4", lifespan=vida,
              docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health():
    return Response(status_code=200 if app.state.agente.saludable() else 503,
                    media_type="application/json", headers={"Cache-Control": "no-store"})


@app.get("/ready")
async def ready():
    return Response(status_code=200 if app.state.agente.listo() else 503,
                    media_type="application/json", headers={"Cache-Control": "no-store"})


@app.get("/")
@app.get("/status")
async def status(request: Request):
    datos = app.state.agente.estado()
    if "text/event-stream" in request.headers.get("accept", "").lower():
        async def evento():
            yield f"event: status\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"
        return StreamingResponse(evento(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})
    return JSONResponse(datos, headers={"Cache-Control": "no-store"})
