from __future__ import annotations

import re
import unicodedata
from typing import Any

import streamlit as st


def option_label(value: str, empty_label: str) -> str:
    return value or empty_label


def scope_value(value: Any) -> str:
    text = str(value or "").strip()
    if normalize(text) in {"todas", "todos", "all"}:
        return ""
    return text


def normalize(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_key(value: Any) -> str:
    return normalize(value).replace(" ", "")


def normalize_crew(value: Any) -> str:
    text = normalize(value).upper().replace(" ", "")
    text = re.sub(r"(MP|SF|SANFRAN|MANPETROL)$", "", text)
    return text


def canonical_area(value: Any) -> str:
    norm = compact_key(value)
    if "distrib" in norm or norm in {"td", "tyd", "tandd"}:
        return "DISTRIBUCION"
    return "GENERACION"


def current_area() -> str:
    profile = st.session_state.get("profile", {})
    return canonical_area(profile.get("area") or "GENERACION")


def program_area(program: dict[str, Any]) -> str:
    return canonical_area(program.get("area") or "GENERACION")


def task_area(task: dict[str, Any]) -> str:
    return canonical_area(task.get("area") or "GENERACION")


def canonical_company(value: Any) -> str:
    norm = compact_key(value)
    if not norm:
        return ""
    if "manpetrol" in norm or norm in {"mp", "manpet"}:
        return "MANPETROL"
    if "sanfran" in norm or "sanyfran" in norm or norm in {"sf", "sanf"}:
        return "SAN&FRAN"
    if "electropatagonia" in norm or norm in {"ep", "elepatagonia"}:
        return "ELECTRO PATAGONIA"
    if norm in {"otra", "otro", "otros", "otras"}:
        return "OTRA"
    return str(value or "").strip()


def canonical_sector(value: Any) -> str:
    norm = compact_key(value)
    if not norm:
        return ""
    company, distribution_sector = distribution_company_sector(value)
    if distribution_sector:
        return distribution_sector
    if "elect" in norm or norm in {"elec", "pdgelec", "pdegelec", "pdgelect", "pdgelectrico"}:
        return "Electricidad"
    if "inst" in norm or norm in {"pdginst", "pdeginst", "pdginstrumentacion"}:
        return "Instrumentacion"
    if "mec" in norm or "mecan" in norm or norm in {"pdgmec", "pdegmeca", "pdgmecanica"}:
        return "Mecanica"
    if norm in {"otro", "otros", "otras"}:
        return "Otros"
    return str(value or "").strip()


def distribution_company_sector(value: Any) -> tuple[str, str]:
    norm = compact_key(value)
    if not norm:
        return "", ""
    if "tareasrelevantes" in norm:
        return "", ""
    if "pdedeett" in norm or "estacionestransformadoras" in norm:
        return "MANPETROL", "Estaciones Transformadoras"
    if "pdedstel" in norm or "telemando" in norm:
        return "ELECTRO PATAGONIA", "Telemando"
    if "pdedetct" in norm or norm.startswith("tct") or "trabajoscontension" in norm:
        return "MANPETROL", "Trabajos con tension"
    if "pdedstop" in norm or norm.startswith("tst") or "trabajossintension" in norm:
        return "ELECTRO PATAGONIA", "Trabajos sin tension"
    if "guardia24" in norm:
        return "MANPETROL", "Guardia 24hs"
    return "", ""


def infer_company_sector(cuadrilla: Any, area: Any = "GENERACION", sector_value: Any = "") -> tuple[str, str]:
    if canonical_area(area) == "DISTRIBUCION":
        return distribution_company_sector(sector_value)
    crew = normalize_crew(cuadrilla)
    if crew in {"555", "555A", "A555"}:
        return "MANPETROL", "Electricidad"
    if crew in {"556A", "556B", "556C"}:
        return "MANPETROL", "Instrumentacion"
    if crew in {"720", "721", "722", "723", "724"}:
        return "SAN&FRAN", "Mecanica"
    return "", "Otros"


def effective_company(task: dict[str, Any]) -> str:
    area = task_area(task)
    value = canonical_company(task.get("empresa"))
    inferred, _ = infer_company_sector(task.get("cuadrilla"), area, task.get("sector"))
    crew_company = canonical_company(task.get("cuadrilla"))
    return value or inferred or crew_company


def effective_sector(task: dict[str, Any]) -> str:
    area = task_area(task)
    value = canonical_sector(task.get("sector"))
    _, inferred = infer_company_sector(task.get("cuadrilla"), area, task.get("sector"))
    return value or inferred


def is_other_company_scope(task: dict[str, Any]) -> bool:
    area = task_area(task)
    inferred_company, _ = infer_company_sector(task.get("cuadrilla"), area, task.get("sector"))
    return not inferred_company


def is_other_sector_scope(task: dict[str, Any]) -> bool:
    from .config import DISTRIBUTION_SECTORS, GENERATION_SECTORS

    area = task_area(task)
    _, inferred_sector = infer_company_sector(task.get("cuadrilla"), area, task.get("sector"))
    if inferred_sector == "Otros":
        return True
    known = GENERATION_SECTORS if area == "GENERACION" else DISTRIBUTION_SECTORS
    return normalize(effective_sector(task)) not in known
