from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

import pandas as pd

from .config import (
    COMPANY_COLUMNS,
    CREW_COLUMNS,
    END_DATE_COLUMNS,
    KKS_COLUMNS,
    LOCATION_COLUMNS,
    OT_COLUMNS,
    SECTOR_COLUMNS,
    START_DATE_COLUMNS,
    STATUS_COLUMNS,
    TITLE_COLUMNS,
)
from .supabase_client import sb_get
from .textutils import (
    canonical_area,
    canonical_company,
    canonical_sector,
    compact_key,
    distribution_company_sector,
    infer_company_sector,
    normalize,
)


def find_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {normalize(column): column for column in columns}
    compact = {compact_key(column): column for column in columns}
    for candidate in candidates:
        wanted = normalize(candidate)
        if wanted in normalized:
            return normalized[wanted]
        compact_wanted = compact_key(candidate)
        if compact_wanted in compact:
            return compact[compact_wanted]
    for norm, original in normalized.items():
        if any(normalize(candidate) in norm for candidate in candidates):
            return original
    for norm, original in compact.items():
        if any(compact_key(candidate) in norm for candidate in candidates):
            return original
    return None


def parse_date(value: Any) -> str | None:
    if pd.isna(value) or value == "":
        return None
    try:
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date().isoformat()
    except Exception:
        return None


def duration_days(start: str | None, end: str | None) -> int:
    try:
        start_date = date.fromisoformat(start or end or "")
        end_date = date.fromisoformat(end or start or "")
        return max((end_date - start_date).days + 1, 1)
    except Exception:
        return 1


def row_text(row: pd.Series, column: str | None) -> str:
    if not column:
        return ""
    value = row.get(column, "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def ot_text(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except Exception:
        pass
    return text


def raw_value(task: dict[str, Any], candidates: list[str]) -> str:
    raw = task.get("raw") or {}
    if not isinstance(raw, dict):
        return ""
    normalized = {normalize(key): value for key, value in raw.items()}
    compact = {compact_key(key): value for key, value in raw.items()}
    for candidate in candidates:
        value = normalized.get(normalize(candidate))
        if value not in (None, ""):
            return str(value).strip()
        value = compact.get(compact_key(candidate))
        if value not in (None, ""):
            return str(value).strip()
    for key, value in normalized.items():
        if value in (None, ""):
            continue
        if any(normalize(candidate) in key for candidate in candidates):
            return str(value).strip()
    for key, value in compact.items():
        if value in (None, ""):
            continue
        if any(compact_key(candidate) in key for candidate in candidates):
            return str(value).strip()
    return ""


def raw_column_name(raw: dict[str, Any], candidates: list[str]) -> str | None:
    normalized = {normalize(column): column for column in raw.keys()}
    compact = {compact_key(column): column for column in raw.keys()}
    for candidate in candidates:
        wanted = normalize(candidate)
        if wanted in normalized:
            return normalized[wanted]
        compact_wanted = compact_key(candidate)
        if compact_wanted in compact:
            return compact[compact_wanted]
    for norm, original in normalized.items():
        if any(normalize(candidate) in norm for candidate in candidates):
            return original
    for norm, original in compact.items():
        if any(compact_key(candidate) in norm for candidate in candidates):
            return original
    return None


def task_title(task: dict[str, Any]) -> str:
    title = raw_value(task, TITLE_COLUMNS)
    if title:
        return title
    return str(task.get("tarea") or "").strip()


def is_distribution_skip_section(value: Any) -> bool:
    return "tareasrelevantes" in compact_key(value)


def section_text(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("/") and text.endswith("/"):
        text = text.strip("/").strip()
    return text


def map_excel(df: pd.DataFrame, area: str = "GENERACION") -> list[dict[str, Any]]:
    area = canonical_area(area)
    columns = list(df.columns)
    mapping = {
        "nro_ot": find_column(columns, OT_COLUMNS),
        "tarea": find_column(columns, TITLE_COLUMNS),
        "empresa": find_column(columns, COMPANY_COLUMNS),
        "sector": find_column(columns, SECTOR_COLUMNS),
        "cuadrilla": find_column(columns, CREW_COLUMNS),
        "fecha_inicio": find_column(columns, START_DATE_COLUMNS),
        "fecha_fin": find_column(columns, END_DATE_COLUMNS),
        "estado_programa": find_column(columns, STATUS_COLUMNS),
        "ubicacion_tecnica": find_column(columns, LOCATION_COLUMNS),
        "kks_tag": find_column(columns, KKS_COLUMNS),
    }
    tasks: list[dict[str, Any]] = []
    current_section = ""
    skip_section = False
    for _, row in df.iterrows():
        tarea = row_text(row, mapping["tarea"])
        nro_ot = ot_text(row_text(row, mapping["nro_ot"]))
        cuadrilla = row_text(row, mapping["cuadrilla"])
        estado_programa = row_text(row, mapping["estado_programa"])
        section_candidate = section_text(tarea)
        if area == "DISTRIBUCION":
            section_company, section_sector = distribution_company_sector(section_candidate)
            if is_distribution_skip_section(section_candidate):
                current_section = section_candidate
                skip_section = True
                continue
            is_section_row = bool(section_sector) and not nro_ot and not cuadrilla
            if is_section_row:
                current_section = section_candidate
                skip_section = False
                continue
            if skip_section or not current_section:
                continue
            if not cuadrilla:
                continue
        elif tarea.startswith("/") and tarea.endswith("/") and not nro_ot:
            continue
        if not tarea and not nro_ot:
            continue
        start = parse_date(row.get(mapping["fecha_inicio"])) if mapping["fecha_inicio"] else None
        end = parse_date(row.get(mapping["fecha_fin"])) if mapping["fecha_fin"] else None
        if area == "DISTRIBUCION":
            inferred_company, inferred_sector = distribution_company_sector(current_section)
        else:
            inferred_company, inferred_sector = infer_company_sector(cuadrilla, area)
        empresa = canonical_company(row_text(row, mapping["empresa"])) or inferred_company or canonical_company(cuadrilla)
        sector = canonical_sector(row_text(row, mapping["sector"])) or inferred_sector
        raw = {str(col): (None if pd.isna(row.get(col)) else str(row.get(col))) for col in columns}
        # Guardar la posicion original de la fila dentro del JSON raw para no
        # necesitar una columna adicional en Supabase. "Orden" sigue quedando
        # disponible como alias del numero de OT del Excel.
        raw["_posicion_excel"] = len(tasks)
        digest = hashlib.sha1(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        tasks.append(
            {
                "area": area,
                "row_hash": digest,
                "nro_ot": nro_ot,
                "tarea": tarea,
                "empresa": empresa,
                "sector": sector,
                "cuadrilla": cuadrilla,
                "fecha_inicio": start,
                "fecha_fin": end,
                "duracion": duration_days(start, end),
                "estado_programa": estado_programa,
                "ubicacion_tecnica": row_text(row, mapping["ubicacion_tecnica"]),
                "kks_tag": row_text(row, mapping["kks_tag"]),
                "raw": raw,
            }
        )
    return tasks


def list_programs(active_only: bool = True) -> list[dict[str, Any]]:
    params = {"select": "*", "order": "uploaded_at.desc"}
    if active_only:
        params["active"] = "eq.true"
    return sb_get("programs", params)


def load_tasks(program_id: str) -> list[dict[str, Any]]:
    tasks = sb_get("tasks", {"select": "*", "program_id": f"eq.{program_id}"})

    def excel_position(task: dict[str, Any]) -> int:
        raw = task.get("raw") or {}
        if not isinstance(raw, dict):
            return 10**9
        try:
            return int(raw.get("_posicion_excel", 10**9))
        except (TypeError, ValueError):
            return 10**9

    # Los programas nuevos respetan la posicion original del Excel guardada
    # dentro de raw. Los programas anteriores, que no tienen _posicion_excel,
    # siguen funcionando y se ordenan como respaldo por fecha de inicio y OT.
    tasks.sort(
        key=lambda t: (
            excel_position(t),
            str(t.get("fecha_inicio") or ""),
            str(t.get("nro_ot") or ""),
        )
    )
    return tasks


def load_advances(program_id: str) -> list[dict[str, Any]]:
    return sb_get("advances", {"select": "*", "program_id": f"eq.{program_id}", "order": "created_at.desc"})
