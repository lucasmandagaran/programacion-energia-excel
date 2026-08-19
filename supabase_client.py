from __future__ import annotations

import json
from typing import Any

import requests
import streamlit as st

from .config import SUPABASE_KEY, SUPABASE_URL


def supabase_headers(prefer: str | None = None) -> dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Falta configurar SUPABASE_URL y SUPABASE_KEY en Streamlit Secrets.")
        st.stop()
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def api_url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


def stop_supabase_error(response: requests.Response, action: str) -> None:
    message = response.text.strip()
    try:
        payload = response.json()
        message = json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        pass
    st.error(f"Error de Supabase al {action}. Codigo HTTP: {response.status_code}")
    if response.status_code in {401, 403}:
        st.warning("Revisar SUPABASE_KEY y los permisos/grants del SQL.")
    elif response.status_code == 404:
        st.warning("Revisar que existan las tablas public.programs, public.tasks y public.advances.")
    st.code(message[:2000] or "Sin detalle devuelto por Supabase.")
    st.stop()


def sb_get(table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    try:
        response = requests.get(api_url(table), headers=supabase_headers(), params=params or {}, timeout=30)
    except requests.RequestException as exc:
        st.error("No se pudo conectar con Supabase.")
        st.code(str(exc))
        st.stop()
    if not response.ok:
        stop_supabase_error(response, f"leer {table}")
    return response.json()


def sb_insert(table: str, rows: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    try:
        response = requests.post(
            api_url(table),
            headers=supabase_headers("return=representation"),
            data=json.dumps(rows, default=str),
            timeout=60,
        )
    except requests.RequestException as exc:
        st.error("No se pudo conectar con Supabase.")
        st.code(str(exc))
        st.stop()
    if not response.ok:
        stop_supabase_error(response, f"guardar en {table}")
    return response.json()


def sb_patch(table: str, params: dict[str, str], values: dict[str, Any]) -> None:
    try:
        response = requests.patch(
            api_url(table),
            headers=supabase_headers(),
            params=params,
            data=json.dumps(values, default=str),
            timeout=30,
        )
    except requests.RequestException as exc:
        st.error("No se pudo conectar con Supabase.")
        st.code(str(exc))
        st.stop()
    if not response.ok:
        stop_supabase_error(response, f"actualizar {table}")


def sb_delete(table: str, params: dict[str, str]) -> None:
    try:
        response = requests.delete(api_url(table), headers=supabase_headers(), params=params, timeout=30)
    except requests.RequestException as exc:
        st.error("No se pudo conectar con Supabase.")
        st.code(str(exc))
        st.stop()
    if not response.ok:
        stop_supabase_error(response, f"eliminar de {table}")
