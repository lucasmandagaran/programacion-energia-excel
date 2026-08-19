from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ..advances import effective_task_status
from ..config import STATE_ACTIONS
from ..textutils import effective_company, effective_sector
from ..timeutil import local_today

STATE_LABELS = {
    "EN CURSO": "En curso",
    "EN ESPERA": "En espera",
    "COMPLETADO": "Completado",
    "REPLANIFICAR": "A replanificar",
    "SIN AVANCE": "Sin avance",
}


def _is_overdue(task: dict[str, Any], status: str) -> bool:
    if status in {"COMPLETADO"}:
        return False
    end = str(task.get("fecha_fin") or "").strip()
    if not end:
        return False
    try:
        return end[:10] < local_today().isoformat()
    except Exception:
        return False


def render_dashboard(tasks: list[dict[str, Any]], latest: dict[str, dict[str, Any]]) -> None:
    if not tasks:
        return

    statuses = {task["id"]: effective_task_status(task, latest) for task in tasks}
    total = len(tasks)
    counts = {action: 0 for action in STATE_ACTIONS}
    for status in statuses.values():
        counts[status] = counts.get(status, 0) + 1
    completed = counts.get("COMPLETADO", 0)
    overdue = sum(1 for task in tasks if _is_overdue(task, statuses[task["id"]]))
    pct_completed = round((completed / total) * 100) if total else 0

    with st.expander("Resumen del programa", expanded=True):
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Tareas", total)
        m2.metric("Completadas", f"{completed} ({pct_completed}%)")
        m3.metric("En curso", counts.get("EN CURSO", 0))
        m4.metric("En espera / replanificar", counts.get("EN ESPERA", 0) + counts.get("REPLANIFICAR", 0))
        m5.metric("Vencidas sin completar", overdue)
        if overdue:
            m5.caption(":red[Requieren atencion]")

        chart_col, table_col = st.columns([1.1, 1.4])

        state_df = pd.DataFrame(
            {
                "Estado": [STATE_LABELS.get(action, action) for action in STATE_ACTIONS],
                "Tareas": [counts.get(action, 0) for action in STATE_ACTIONS],
            }
        ).set_index("Estado")
        chart_col.caption("Tareas por estado")
        chart_col.bar_chart(state_df, use_container_width=True)

        breakdown_rows: dict[tuple[str, str], dict[str, int]] = {}
        for task in tasks:
            key = (effective_company(task) or "Sin empresa", effective_sector(task) or "Sin sector")
            entry = breakdown_rows.setdefault(key, {"Tareas": 0, "Completadas": 0})
            entry["Tareas"] += 1
            if statuses[task["id"]] == "COMPLETADO":
                entry["Completadas"] += 1

        table_col.caption("Avance por empresa / sector")
        breakdown_df = pd.DataFrame(
            [
                {
                    "Empresa": company,
                    "Sector": sector,
                    "Tareas": data["Tareas"],
                    "Completadas": data["Completadas"],
                    "% Completado": round((data["Completadas"] / data["Tareas"]) * 100) if data["Tareas"] else 0,
                }
                for (company, sector), data in sorted(breakdown_rows.items())
            ]
        )
        table_col.dataframe(breakdown_df, hide_index=True, use_container_width=True)
