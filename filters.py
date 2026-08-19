from __future__ import annotations

from typing import Any

import streamlit as st

from .config import SEARCH_FIELD_OPTIONS
from .data import task_title
from .textutils import (
    effective_company,
    effective_sector,
    is_other_company_scope,
    is_other_sector_scope,
    normalize,
    normalize_crew,
    scope_value,
)


FILTER_KEYS = [
    "program_filter",
    "sector_filter",
    "crew_filter",
    "start_filter",
    "end_filter",
    "search_terms_filter",
]


def selected_crews(value: Any) -> set[str]:
    if not value:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {normalize_crew(item) for item in value if str(item or "").strip()}
    return {normalize_crew(value)}


def search_terms(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_terms = [str(item or "").strip() for item in value]
    else:
        raw_terms = [str(value or "").strip()]
    terms = []
    seen = set()
    for item in raw_terms:
        normalized = normalize(item)
        if normalized and normalized not in seen:
            terms.append(normalized)
            seen.add(normalized)
    return terms


def make_search_filter_label(field: str, value: str) -> str:
    return f"{field}: {value.strip()}"


def parse_search_filter_label(label: Any) -> tuple[str, str]:
    text = str(label or "").strip()
    if ":" not in text:
        return "Todos los campos", text
    field, value = text.split(":", 1)
    field = field.strip()
    value = value.strip()
    if field not in SEARCH_FIELD_OPTIONS:
        return "Todos los campos", value or text
    return field, value


def task_search_text(task: dict[str, Any], field: str) -> str:
    if field in SEARCH_FIELD_OPTIONS:
        keys = SEARCH_FIELD_OPTIONS[field]
    else:
        keys = ["nro_ot", "tarea", "cuadrilla", "ubicacion_tecnica", "kks_tag"]
    text = " ".join(str(task.get(key) or "") for key in keys)
    if field in {"Todos los campos", "Titulo tarea"}:
        text = f"{text} {task_title(task)}"
    return normalize(text)


def apply_filters(
    tasks: list[dict[str, Any]],
    company: str,
    sector: str,
    crew: Any,
    start: Any,
    end: Any,
    text: Any,
) -> list[dict[str, Any]]:
    output = []
    company = scope_value(company)
    sector = scope_value(sector)
    crew_values = selected_crews(crew)
    start_iso = start.isoformat() if start else ""
    end_iso = end.isoformat() if end else ""
    if start_iso and not end_iso:
        end_iso = start_iso
    elif end_iso and not start_iso:
        start_iso = end_iso
    search_filters = [parse_search_filter_label(item) for item in (text or [])] if isinstance(text, (list, tuple, set)) else []
    if not search_filters and text:
        search_filters = [("Todos los campos", str(text))]
    search_filters = [(field, value) for field, value in search_filters if normalize(value)]
    for task in tasks:
        if company:
            if normalize(company) == "otra":
                if not is_other_company_scope(task):
                    continue
            elif normalize(effective_company(task)) != normalize(company):
                continue
        if sector:
            if normalize(sector) == "otros":
                if not is_other_sector_scope(task):
                    continue
            elif normalize(effective_sector(task)) != normalize(sector):
                continue
        if crew_values and normalize_crew(task.get("cuadrilla")) not in crew_values:
            continue
        if start_iso or end_iso:
            task_start = str(task.get("fecha_inicio") or "").strip()
            task_end = str(task.get("fecha_fin") or "").strip()
            if task_start and not task_end:
                task_end = task_start
            elif task_end and not task_start:
                task_start = task_end
            if not task_start and not task_end:
                continue
            if task_start > end_iso or task_end < start_iso:
                continue
        if search_filters:
            filters_by_field: dict[str, list[str]] = {}
            for field, value in search_filters:
                filters_by_field.setdefault(field, []).append(value)
            if not all(
                any(normalize(value) in task_search_text(task, field) for value in values)
                for field, values in filters_by_field.items()
            ):
                continue
        output.append(task)
    return output


def current_filter_state(program_id: str) -> dict[str, Any]:
    return {
        "program_id": program_id,
        "program_filter": st.session_state.get("program_filter"),
        "sector_filter": st.session_state.get("sector_filter", ""),
        "crew_filter": st.session_state.get("crew_filter", ""),
        "start_filter": st.session_state.get("start_filter"),
        "end_filter": st.session_state.get("end_filter"),
        "search_terms_filter": tuple(st.session_state.get("search_terms_filter", [])),
    }


def restore_filter_state(state: dict[str, Any] | None) -> None:
    if not state:
        return
    for key in FILTER_KEYS:
        if key in state:
            value = state[key]
            if key == "search_terms_filter" and isinstance(value, tuple):
                value = list(value)
            st.session_state[key] = value


def add_search_filter_from_state() -> None:
    field = str(st.session_state.get("search_field_input") or "Titulo tarea")
    value = str(st.session_state.get("search_value_input") or "").strip()
    if not value:
        return
    label = make_search_filter_label(field, value)
    active = list(st.session_state.get("search_terms_filter", []))
    if normalize(label) not in {normalize(item) for item in active}:
        active.append(label)
    st.session_state.search_terms_filter = active
    st.session_state.search_value_input = ""


def remove_search_filter(label: str) -> None:
    st.session_state.search_terms_filter = [
        item for item in st.session_state.get("search_terms_filter", []) if item != label
    ]
