from __future__ import annotations

import os

import streamlit as st
from zoneinfo import ZoneInfo


APP_TITLE = "Programacion Energia"
LOCAL_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
AREAS = ["GENERACION", "DISTRIBUCION"]
COMPANIES_BY_AREA = {
    "GENERACION": ["", "MANPETROL", "SAN&FRAN", "OTRA"],
    "DISTRIBUCION": ["", "MANPETROL", "ELECTRO PATAGONIA", "OTRA"],
}
SECTORS_BY_AREA = {
    "GENERACION": ["", "Electricidad", "Mecanica", "Instrumentacion", "Otros"],
    "DISTRIBUCION": [
        "",
        "Estaciones Transformadoras",
        "Telemando",
        "Trabajos con tension",
        "Trabajos sin tension",
        "Guardia 24hs",
        "Otros",
    ],
}
COMPANIES = COMPANIES_BY_AREA["GENERACION"]
SECTORS = SECTORS_BY_AREA["GENERACION"]
GENERATION_SECTORS = {"electricidad", "mecanica", "instrumentacion"}
DISTRIBUTION_SECTORS = {
    "estaciones transformadoras",
    "telemando",
    "trabajos con tension",
    "trabajos sin tension",
    "guardia 24hs",
}
STATE_ACTIONS = ["EN CURSO", "EN ESPERA", "COMPLETADO", "REPLANIFICAR", "SIN AVANCE"]
REASON_ACTIONS = {"EN ESPERA", "REPLANIFICAR"}
HIDE_AFTER_SAVE_ACTIONS = {"COMPLETADO", "REPLANIFICAR"}
SEARCH_FIELD_OPTIONS = {
    "Titulo tarea": ["tarea"],
    "OT": ["nro_ot"],
    "Ubicacion tecnica": ["ubicacion_tecnica"],
    "KKS/TAG": ["kks_tag"],
    "Cuadrilla": ["cuadrilla"],
}
STATE_ROW_STYLES = {
    "COMPLETADO": "background-color: rgba(36, 161, 72, 0.30); color: #f2fff5; font-weight: 700;",
    "EN CURSO": "background-color: rgba(31, 111, 235, 0.28); color: #f2f7ff; font-weight: 700;",
    "EN ESPERA": "background-color: rgba(214, 158, 46, 0.30); color: #fff8e5; font-weight: 700;",
    "REPLANIFICAR": "background-color: rgba(248, 81, 73, 0.30); color: #fff0ef; font-weight: 700;",
    "COMENTARIO": "background-color: rgba(137, 87, 229, 0.22); color: #f6efff; font-weight: 700;",
    "SIN AVANCE": "background-color: rgba(139, 148, 158, 0.14); color: #f0f3f6;",
}
COMMENT_DISPLAY_LIMIT = 95
REASONS = [
    "",
    "Pedido Sup PAE",
    "Por factor climatico",
    "Por falta de equipo/recursos/materiales",
    "Cuadrilla no operativa",
    "Otros",
]
OT_COLUMNS = ["ot", "ots", "orden", "ordenes", "orden de trabajo", "nro ot", "nro de ot", "nro. de ot", "numero ot", "numero de ot", "nrodeot", "nroot"]
TITLE_COLUMNS = ["title", "titulo", "titulo tarea", "titulo de tarea", "trabajo", "tarea", "descripcion", "description", "texto breve", "textobreve", "nombre", "nombre tarea"]
COMPANY_COLUMNS = ["empresa", "contratista", "compania", "cia"]
SECTOR_COLUMNS = ["sector", "especialidad", "disciplina", "puesto de trabajo"]
CREW_COLUMNS = ["cuadrilla", "cuadrillas", "cuadrilla gen", "cuadrillagen", "crew", "recurso", "recursos"]
START_DATE_COLUMNS = ["fecha inicio", "fecha inic", "fecha ini", "inicio", "start", "fecha programada", "fechaprogramada"]
END_DATE_COLUMNS = ["fecha fin", "fecha vencimiento", "vencimiento", "fin", "due", "fecha cierre", "cierre"]
STATUS_COLUMNS = ["estado", "status", "estado actual", "status de usuario", "avance"]
LOCATION_COLUMNS = ["ubicacion tecnica", "ubicacion", "ubic tecnica", "ubic. tecnica", "ubictecnica", "objeto ubicacion", "objetoubicacion"]
KKS_COLUMNS = ["kks tag", "kks-tag", "kks/tag", "kks", "tag", "kkstag", "kks tag ubicacion", "kkstagubicacion"]


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, "") or os.getenv(name, "") or default)
    except Exception:
        return str(os.getenv(name, "") or default)


def required_secret(name: str) -> str:
    value = secret(name)
    if not value:
        st.error(f"Falta configurar {name} en Streamlit Secrets.")
        st.stop()
    return value


SUPABASE_URL = secret("SUPABASE_URL").rstrip("/")
if SUPABASE_URL.endswith("/rest/v1"):
    SUPABASE_URL = SUPABASE_URL[: -len("/rest/v1")]
SUPABASE_KEY = secret("SUPABASE_KEY")
ACCESS_PASSWORD = required_secret("ACCESS_PASSWORD")
ADMIN_PASSWORD = required_secret("ADMIN_PASSWORD")


st.set_page_config(page_title=APP_TITLE, page_icon="PE", layout="wide")
