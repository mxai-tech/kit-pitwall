"""WORKSHOP: personaliza el prompt; conserva el contrato JSON y el respaldo."""
import json

RITMOS = ("ATAQUE", "CARRERA", "CONSERVAR")
ENERGIAS = ("BOOST", "EQUILIBRIO", "RECARGA")
COMPUESTOS = ("BLANDO", "MEDIO", "DURO", "INTER", "LLUVIA")

# PERSONALIZA tu estrategia aquí: objetivos, prioridades y tolerancia al riesgo.
INSTRUCCIONES = """Eres el ingeniero de estrategia de un equipo en una carrera simulada.
Decide con la telemetría y los informes de llantas, pista y estrategia.
Responde exclusivamente con un objeto JSON.
Radio: máximo 20 palabras. Razonamiento: breve explicación, sin texto fuera del JSON.
"""


def prompt(mensaje, agentes, ficha):
    tipo = mensaje["tipo"]
    if tipo == "ventana":
        formato = {"ritmo": "CARRERA", "energia": "EQUILIBRIO",
                   "pits": {"compuesto": "NINGUNO"}, "radio": "...", "razonamiento": "..."}
        regla = ("ritmo: ATAQUE/CARRERA/CONSERVAR; energia: BOOST/EQUILIBRIO/RECARGA. "
                 "pits.compuesto: NINGUNO/BLANDO/MEDIO/DURO/INTER/LLUVIA. "
                 "Si paras, añade pits.vuelta: entero 1..6, relativo a esta ventana.")
    elif tipo == "pre_carrera":
        formato = {"llanta_salida": "MEDIO", "aleron": "ALTA_CARGA", "ritmo": "CARRERA",
                   "energia": "EQUILIBRIO", "radio": "...", "razonamiento": "..."}
        regla = "Elige opciones permitidas en el mensaje. Alerón: ALTA_CARGA o MEDIA_CARGA."
    else:
        formato = {"respuesta": mensaje.get("formato", {}), "razon": "..."}
        regla = "Responde la pregunta del Momento usando su formato y opciones."
    sistema = INSTRUCCIONES + "\nPERSONALIDAD: " + json.dumps(ficha, ensure_ascii=False)
    usuario = json.dumps({"solicitud": mensaje, "agentes": agentes,
                          "ejemplo_formato": formato, "instruccion": regla}, ensure_ascii=False)
    return sistema, usuario


def validar(mensaje, datos):
    """Normaliza la salida LLM y evita enviar órdenes inválidas al servidor."""
    if not isinstance(datos, dict):
        raise ValueError("La respuesta debe ser un objeto JSON")
    tipo = mensaje["tipo"]
    if tipo == "momento":
        r = datos.get("respuesta")
        if not isinstance(r, dict):
            raise ValueError("Falta respuesta del Momento")
        i = mensaje["id"]
        if i == 1:
            if type(r.get("vuelta_parada")) is not int or not 5 <= r["vuelta_parada"] <= 65:
                raise ValueError("Vuelta de parada inválida")
            if r.get("compuesto") not in COMPUESTOS[:3]:
                raise ValueError("Compuesto inválido")
        elif i == 2 and r.get("decision") not in ("ATACAR", "SEGUIR", "CUIDAR"):
            raise ValueError("Decisión de Momento inválida")
        elif i == 3 and r.get("energia") not in ENERGIAS:
            raise ValueError("Energía de Momento inválida")
        return {"tipo": "respuesta_momento", "id": i, "respuesta": r,
                "razon": str(datos.get("razon", ""))[:300]}
    ritmo = str(datos.get("ritmo", "CARRERA")).upper()
    energia = str(datos.get("energia", "EQUILIBRIO")).upper()
    if ritmo not in RITMOS or energia not in ENERGIAS:
        raise ValueError("Ritmo o energía inválidos")
    salida = {"ventana": mensaje["ventana"], "ritmo": ritmo, "energia": energia,
              "radio": " ".join(str(datos.get("radio", "")).split()[:20]),
              "razonamiento": str(datos.get("razonamiento", ""))[:600]}
    if tipo == "pre_carrera":
        permitidas = mensaje.get("opciones", {}).get("llanta_salida", list(COMPUESTOS[:3]))
        llanta = str(datos.get("llanta_salida", "MEDIO")).upper()
        aleron = str(datos.get("aleron", "ALTA_CARGA")).upper()
        if llanta not in permitidas or aleron not in ("ALTA_CARGA", "MEDIA_CARGA"):
            raise ValueError("Setup no permitido")
        return {**salida, "tipo": "setup", "llanta_salida": llanta, "aleron": aleron}
    pits = datos.get("pits") or {"compuesto": "NINGUNO"}
    if isinstance(pits, str):
        pits = {"compuesto": pits}
    comp = str(pits.get("compuesto", "NINGUNO")).upper()
    if comp not in ("NINGUNO",) + COMPUESTOS:
        raise ValueError("Compuesto no permitido")
    parada = {"compuesto": comp}
    if comp != "NINGUNO":
        vuelta = pits.get("vuelta", 1)
        if type(vuelta) is not int or not 1 <= vuelta <= 6:
            raise ValueError("pits.vuelta debe estar entre 1 y 6")
        parada["vuelta"] = vuelta
    return {**salida, "tipo": "orden", "pits": parada}


def respaldo(mensaje):
    """Respaldo mínimo de continuidad; no hay un motor alternativo de estrategia."""
    tipo = mensaje["tipo"]
    if tipo == "momento":
        ejemplos = {1: {"vuelta_parada": 25, "compuesto": "MEDIO"},
                    2: {"decision": "SEGUIR"}, 3: {"energia": "EQUILIBRIO"}}
        return validar(mensaje, {"respuesta": ejemplos.get(mensaje["id"], {}),
                                 "razon": "Respaldo: el LLM no respondió con una respuesta válida a tiempo."})
    datos = {"ritmo": "CARRERA", "energia": "EQUILIBRIO", "radio": "",
             "razonamiento": "Respaldo: se mantiene la orden vigente; LLM no disponible o inválido."}
    if tipo == "pre_carrera":
        permitidas = mensaje.get("opciones", {}).get("llanta_salida", list(COMPUESTOS[:3]))
        datos.update(llanta_salida="MEDIO" if "MEDIO" in permitidas else permitidas[0], aleron="ALTA_CARGA")
    else:
        coche = mensaje.get("coche", {})
        datos.update(ritmo=coche.get("ritmo", "CARRERA"), energia=coche.get("energia", "EQUILIBRIO"),
                     pits={"compuesto": "NINGUNO"})
        parada = coche.get("pit_programado")
        if parada:
            datos["pits"] = {"compuesto": parada["compuesto"],
                             "vuelta": max(1, min(6, parada["vuelta"] - mensaje["vuelta"]))}
    return validar(mensaje, datos)
