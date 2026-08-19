from __future__ import annotations

import io
from typing import Any

import pandas as pd

from .advances import combined_comment, latest_status_by_task
from .config import END_DATE_COLUMNS, OT_COLUMNS, START_DATE_COLUMNS, STATUS_COLUMNS
from .data import ot_text, parse_date, raw_column_name, task_title
from .textutils import effective_company, effective_sector, normalize, task_area
from .timeutil import advance_date, advance_time, format_date


def hide_kks_for_tasks(tasks: list[dict[str, Any]]) -> bool:
    return bool(tasks) and all(task_area(task) == "DISTRIBUCION" for task in tasks)


def strip_kks_if_distribution(rows: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not hide_kks_for_tasks(tasks):
        return rows
    return [{key: value for key, value in row.items() if key != "KKS/TAG"} for row in rows]


def advances_export(tasks: list[dict[str, Any]], advances: list[dict[str, Any]], final_only: bool = False) -> bytes:
    tasks_by_id = {task["id"]: task for task in tasks}
    rows = []
    source = advances
    if final_only:
        seen = set()
        filtered = []
        for advance in sorted(advances, key=lambda item: item.get("created_at", ""), reverse=True):
            if advance["task_id"] in seen or advance.get("action") == "COMENTARIO":
                continue
            seen.add(advance["task_id"])
            filtered.append(advance)
        source = filtered
    for advance in source:
        task = tasks_by_id.get(advance["task_id"], {})
        action = advance.get("action", "")
        start_date = format_date(task.get("fecha_inicio"))
        end_date = format_date(task.get("fecha_fin"))
        program_change = ""
        display_status = action
        if final_only:
            start_date, end_date, program_change = wrike_dates_for_advance(task, advance)
            display_status = status_usuario_for_wrike(action)
        rows.append(
            {
                "OT": ot_text(task.get("nro_ot")),
                "Titulo tarea": task_title(task),
                "Empresa": effective_company(task),
                "Sector": effective_sector(task),
                "Cuadrilla": task.get("cuadrilla", ""),
                "KKS/TAG": task.get("kks_tag", ""),
                "Ubicacion tecnica": task.get("ubicacion_tecnica", ""),
                "Fecha inicio": start_date,
                "Fecha fin": end_date,
                "Duracion": task.get("duracion", ""),
                "Estado": display_status,
                **(
                    {
                        "Modificaciones programa": program_change,
                    }
                    if final_only
                    else {}
                ),
                "Comentario": combined_comment(advance),
                "Fecha avance": advance_date(advance.get("created_at")),
                "Hora avance": advance_time(advance.get("created_at")),
                "Informado por": advance.get("reporter_name", ""),
                "Empresa informante": advance.get("reporter_company", ""),
            }
        )
    rows = strip_kks_if_distribution(rows, tasks)
    return write_excel(rows, sheet_name="Avances")


def status_usuario_for_wrike(action: str) -> str:
    mapping = {
        "EN CURSO": "EN CURSO",
        "COMPLETADO": "COMPLETADO",
        "REPLANIFICAR": "ON HOLD",
        "EN ESPERA": "ON HOLD",
        "SIN AVANCE": "SIN AVANCE",
    }
    return mapping.get(str(action or "").strip().upper(), str(action or "").strip())


def _date_changed(original: Any, updated: str) -> bool:
    if not updated:
        return False
    original_iso = parse_date(original)
    updated_iso = parse_date(updated)
    if not original_iso:
        return bool(updated_iso)
    return bool(updated_iso and original_iso != updated_iso)


def wrike_dates_for_advance(task: dict[str, Any], advance: dict[str, Any]) -> tuple[str, str, str]:
    action = str(advance.get("action") or "").strip().upper()
    start_date = format_date(task.get("fecha_inicio"))
    end_date = format_date(task.get("fecha_fin"))
    change_date = advance_date(advance.get("created_at"))
    changed = False

    if action == "EN CURSO" and change_date:
        changed = _date_changed(task.get("fecha_inicio"), change_date)
        start_date = change_date
    elif action == "COMPLETADO" and change_date:
        changed = _date_changed(task.get("fecha_fin"), change_date)
        end_date = change_date
        if not start_date:
            start_date = change_date
            changed = True

    program_change = "Cambia fecha de tarea" if changed else ""
    return start_date, end_date, program_change


def wrike_advances_export(tasks: list[dict[str, Any]], advances: list[dict[str, Any]]) -> bytes:
    tasks_by_id = {task["id"]: task for task in tasks}
    latest = latest_status_by_task(advances)
    rows = []
    for task_id, advance in latest.items():
        task = tasks_by_id.get(task_id)
        if not task:
            continue
        order = ot_text(task.get("nro_ot"))
        if not order:
            continue
        action = str(advance.get("action") or "").strip()
        if not action or action == "COMENTARIO":
            continue
        start_date, end_date, program_change = wrike_dates_for_advance(task, advance)
        wrike_status = status_usuario_for_wrike(action)
        rows.append(
            {
                "Orden": order,
                "Estado": wrike_status,
                "Modificaciones programa": program_change,
                "Comentario": combined_comment(advance),
                "Fecha avance": advance_date(advance.get("created_at")),
                "Hora avance": advance_time(advance.get("created_at")),
                "Fecha inicio": start_date,
                "Fecha fin": end_date,
                "Texto breve": task_title(task),
                "Ubicacion tecnica": task.get("ubicacion_tecnica", ""),
                "Cuadrilla": task.get("cuadrilla", ""),
                "KKS/TAG": task.get("kks_tag", ""),
                "Informado por": advance.get("reporter_name", ""),
                "Empresa informante": advance.get("reporter_company", ""),
            }
        )
    columns = [
        "Orden",
        "Estado",
        "Modificaciones programa",
        "Comentario",
        "Fecha avance",
        "Hora avance",
        "Fecha inicio",
        "Fecha fin",
        "Texto breve",
        "Ubicacion tecnica",
        "Cuadrilla",
        "KKS/TAG",
        "Informado por",
        "Empresa informante",
    ]
    return write_excel(rows, columns=columns, sheet_name="Wrike avances")


def looks_like_date_column(column: str) -> bool:
    normalized = normalize(column)
    return any(part in normalized for part in ["fecha", "vencimiento", "inicio", "fin", "start", "due"])


def export_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = parse_date(text)
    if parsed:
        return format_date(parsed)
    return text


def write_excel(rows: list[dict[str, Any]], columns: list[str] | None = None, sheet_name: str = "Datos") -> bytes:
    buffer = io.BytesIO()
    df = pd.DataFrame(rows, columns=columns)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        worksheet = writer.sheets[sheet_name]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_cells in worksheet.columns:
            header = str(column_cells[0].value or "")
            max_length = max(len(str(cell.value or "")) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, len(header) + 2), 45)
    return buffer.getvalue()


def program_updated_export(tasks: list[dict[str, Any]], advances: list[dict[str, Any]]) -> bytes:
    latest = latest_status_by_task(advances)
    rows: list[dict[str, Any]] = []
    columns: list[str] = []

    for task in tasks:
        raw = task.get("raw") or {}
        if isinstance(raw, dict) and raw:
            row = dict(raw)
        else:
            row = {
                "OT": ot_text(task.get("nro_ot")),
                "Titulo tarea": task_title(task),
                "Trabajo": task.get("tarea", ""),
                "Fecha inicio": format_date(task.get("fecha_inicio")),
                "Fecha fin": format_date(task.get("fecha_fin")),
                "Estado": task.get("estado_programa") or "",
                "Cuadrilla": task.get("cuadrilla") or "",
                "Ubicacion tecnica": task.get("ubicacion_tecnica") or "",
                "KKS/TAG": task.get("kks_tag") or "",
            }

        advance = latest.get(task["id"])
        if advance:
            state_col = raw_column_name(row, STATUS_COLUMNS) or "Estado"
            row[state_col] = advance.get("action", "")

            changed_on = advance_date(advance.get("created_at"))
            if advance.get("action") == "EN CURSO" and changed_on:
                start_col = raw_column_name(row, START_DATE_COLUMNS) or "Fecha inicio"
                row[start_col] = changed_on
            elif advance.get("action") == "COMPLETADO" and changed_on:
                end_col = raw_column_name(row, END_DATE_COLUMNS) or "Fecha fin"
                row[end_col] = changed_on
                start_col = raw_column_name(row, START_DATE_COLUMNS) or "Fecha inicio"
                if not str(row.get(start_col) or "").strip():
                    row[start_col] = changed_on

        if "OT" in row:
            row["OT"] = ot_text(row.get("OT"))
        else:
            nro_col = raw_column_name(row, OT_COLUMNS)
            if nro_col:
                row[nro_col] = ot_text(row.get(nro_col))

        for column in list(row.keys()):
            if looks_like_date_column(column):
                row[column] = export_date(row.get(column))

        for column in row.keys():
            if column not in columns:
                columns.append(column)
        rows.append(row)

    return write_excel(rows, columns=columns, sheet_name="Programa actualizado")
