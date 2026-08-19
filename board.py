from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ..advances import (
    advance_record_type,
    delete_advances,
    delete_candidates_preserving_latest_records,
    effective_task_status,
    latest_status_by_task,
)
from ..config import COMMENT_DISPLAY_LIMIT, STATE_ACTIONS, STATE_ROW_STYLES
from ..data import ot_text, raw_value, task_title
from ..export import advances_export, hide_kks_for_tasks, strip_kks_if_distribution
from ..advances import combined_comment
from ..textutils import effective_company, effective_sector
from ..timeutil import advance_date, advance_time, format_date, local_today


def task_dataframe(tasks: list[dict[str, Any]], latest: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for task in tasks:
        advance = latest.get(task["id"], {})
        status = effective_task_status(task, latest)
        display_start = format_date(task.get("fecha_inicio"))
        if status == "EN CURSO" and advance.get("created_at"):
            display_start = advance_date(advance.get("created_at"))
        rows.append(
            {
                "Seleccionar": False,
                "Estado": status,
                "Titulo tarea": task_title(task),
                "Fecha inicio": display_start,
                "Duracion": f"{task.get('duracion') or 1} dia(s)",
                "Cuadrilla": task.get("cuadrilla") or "",
                "OT": ot_text(task.get("nro_ot")),
                "Ubicacion tecnica": task.get("ubicacion_tecnica") or "",
                "PTE": raw_value(task, ["PTE", "pte"]),
                "KKS/TAG": task.get("kks_tag") or "",
                "_task_id": task["id"],
                "_estado_original": status,
            }
        )
    return pd.DataFrame(rows)


def task_status_style(row: pd.Series) -> list[str]:
    status = str(row.get("Estado") or "").strip().upper()
    row_style = STATE_ROW_STYLES.get(status, "")
    return [row_style for _ in row]


def record_status_style(row: pd.Series) -> list[str]:
    state_column = "Estado final" if "Estado final" in row.index else "Estado"
    status = str(row.get(state_column) or "").strip().upper()
    return [STATE_ROW_STYLES.get(status, "") for _ in row]


def task_table_column_config() -> dict[str, Any]:
    return {
        "Seleccionar": st.column_config.CheckboxColumn("Sel.", width=56),
        "Estado": st.column_config.SelectboxColumn("Estado", options=STATE_ACTIONS, required=True, width=108),
        "Titulo tarea": st.column_config.TextColumn("Titulo tarea", width=390),
        "Fecha inicio": st.column_config.TextColumn("Fecha inicio", width=104),
        "Duracion": st.column_config.TextColumn("Duracion", width=82),
        "Cuadrilla": st.column_config.TextColumn("Cuadrilla", width=82),
        "OT": st.column_config.TextColumn("OT", width=92),
        "Ubicacion tecnica": st.column_config.TextColumn("Ubicacion tecnica", width=290),
        "PTE": st.column_config.TextColumn("PTE", width=105),
        "KKS/TAG": st.column_config.TextColumn("KKS/TAG", width=110),
    }


def records_table_column_config(state_column: str = "Estado") -> dict[str, Any]:
    return {
        "Titulo tarea": st.column_config.TextColumn("Titulo tarea", width=330),
        "Cuadrilla": st.column_config.TextColumn("Cuadrilla", width=92),
        "OT": st.column_config.TextColumn("OT", width=92),
        "Ubicacion tecnica": st.column_config.TextColumn("Ubicacion tecnica", width=230),
        "KKS/TAG": st.column_config.TextColumn("KKS/TAG", width=105),
        "Tipo registro": st.column_config.TextColumn("Tipo registro", width=130),
        state_column: st.column_config.TextColumn(state_column, width=116),
        "Comentario": st.column_config.TextColumn("Comentario", width=250),
        "Fecha modificacion": st.column_config.TextColumn("Fecha modificacion", width=118),
        "Hora modificacion": st.column_config.TextColumn("Hora modificacion", width=104),
        "Informado por": st.column_config.TextColumn("Informado por", width=150),
        "Empresa": st.column_config.TextColumn("Empresa", width=150),
        "Sector": st.column_config.TextColumn("Sector", width=160),
    }


def delete_records_column_config(state_column: str = "Estado") -> dict[str, Any]:
    config = records_table_column_config(state_column)
    config.update(
        {
            "_advance_id": None,
            "Eliminar": st.column_config.CheckboxColumn("Eliminar", width=76),
        }
    )
    return config


def truncate_display_text(value: Any, limit: int = COMMENT_DISPLAY_LIMIT) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def order_records_by_area(
    rows: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    state_column: str,
) -> list[dict[str, Any]]:
    if hide_kks_for_tasks(tasks):
        columns = [
            "_advance_id",
            "Titulo tarea",
            "Cuadrilla",
            "OT",
            "Ubicacion tecnica",
            "Tipo registro",
            state_column,
            "Comentario",
            "Fecha modificacion",
            "Hora modificacion",
            "Informado por",
            "Empresa",
            "Sector",
        ]
    else:
        columns = [
            "_advance_id",
            "Titulo tarea",
            "Tipo registro",
            state_column,
            "OT",
            "Cuadrilla",
            "Ubicacion tecnica",
            "KKS/TAG",
            "Comentario",
            "Fecha modificacion",
            "Hora modificacion",
            "Informado por",
            "Empresa",
            "Sector",
        ]
    return [{column: row.get(column, "") for column in columns if column in row} for row in rows]


def render_records_section(
    tasks: list[dict[str, Any]],
    advances: list[dict[str, Any]],
    filtered_base: list[dict[str, Any]],
    filtered_advances: list[dict[str, Any]],
    records_key_suffix: str = "",
) -> None:
    key_suffix = f"_{records_key_suffix}" if records_key_suffix else ""
    title_col, view_col = st.columns([2, 1])
    title_col.subheader("Avances / registros")
    records_view = view_col.selectbox(
        "Vista",
        ["Log completo", "Estado final por OT"],
        key=f"records_view{key_suffix}",
    )
    tasks_by_id = {task["id"]: task for task in tasks}
    source_advances = filtered_advances
    if records_view == "Estado final por OT":
        source_advances = list(latest_status_by_task(filtered_advances).values())
    state_column = "Estado final" if records_view == "Estado final por OT" else "Estado"
    log_rows = [
        {
            "_advance_id": advance.get("id", ""),
            "OT": ot_text(task.get("nro_ot")),
            "Titulo tarea": task_title(task),
            "Fecha modificacion": advance_date(advance.get("created_at")),
            "Hora modificacion": advance_time(advance.get("created_at")),
            "Tipo registro": advance_record_type(advance),
            state_column: advance.get("action"),
            "Comentario": combined_comment(advance),
            "Informado por": advance.get("reporter_name"),
            "Empresa": effective_company(task),
            "Sector": effective_sector(task),
            "Cuadrilla": task.get("cuadrilla", ""),
            "Ubicacion tecnica": task.get("ubicacion_tecnica", ""),
            "KKS/TAG": task.get("kks_tag", ""),
        }
        for advance in source_advances
        for task in [tasks_by_id.get(advance["task_id"], {})]
    ]
    display_log_rows = order_records_by_area(
        strip_kks_if_distribution(log_rows, filtered_base),
        filtered_base,
        state_column,
    )
    log = pd.DataFrame([{key: value for key, value in row.items() if key != "_advance_id"} for row in display_log_rows])
    display_log = log.copy()
    if "Comentario" in display_log.columns:
        display_log["Comentario"] = display_log["Comentario"].map(truncate_display_text)
    if display_log.empty:
        st.dataframe(display_log, hide_index=True, use_container_width=False, column_config=records_table_column_config(state_column))
    else:
        st.dataframe(
            display_log.style.apply(record_status_style, axis=1),
            hide_index=True,
            use_container_width=False,
            column_config=records_table_column_config(state_column),
        )

    if st.session_state.role == "admin" and advances:
        with st.expander("Administracion de registros", expanded=False):
            st.caption(
                "La limpieza trabaja sobre los registros seleccionados. Puede conservar el ultimo cambio "
                "de estado y/o el ultimo comentario independiente de cada tarea segun la opcion elegida."
            )
            if display_log_rows:
                # Si cambia el conjunto de registros visibles, se destilda el
                # check maestro y se limpia la seleccion del editor de borrado.
                visible_advance_ids = tuple(str(row.get("_advance_id", "")) for row in display_log_rows)
                snapshot_key = f"advances_visible_snapshot{key_suffix}_{records_view}"
                delete_editor_key = f"delete_advances_editor_{records_view}{key_suffix}"
                if st.session_state.get(snapshot_key) != visible_advance_ids:
                    st.session_state.pop(f"select_all_visible_advances{key_suffix}", None)
                    st.session_state.pop(delete_editor_key, None)
                    st.session_state[snapshot_key] = visible_advance_ids
                select_all_visible = st.checkbox(
                    "Seleccionar todo visible",
                    key=f"select_all_visible_advances{key_suffix}",
                )
                delete_df = pd.DataFrame([{**{"Eliminar": False}, **row} for row in display_log_rows])
                if select_all_visible:
                    delete_df["Eliminar"] = True
                edited_delete = st.data_editor(
                    delete_df,
                    hide_index=True,
                    use_container_width=False,
                    disabled=[column for column in delete_df.columns if column != "Eliminar"],
                    column_config=delete_records_column_config(state_column),
                    key=f"delete_advances_editor_{records_view}{key_suffix}",
                )
                selected_delete_ids = (
                    edited_delete.loc[edited_delete["Eliminar"] == True, "_advance_id"].tolist()
                    if not edited_delete.empty
                    else []
                )
            else:
                st.info("No hay registros visibles con los filtros actuales.")
                selected_delete_ids = []

            def run_selected_cleanup(label: str, delete_status: bool, delete_comments: bool) -> None:
                delete_ids, keep_ids = delete_candidates_preserving_latest_records(
                    advances,
                    selected_delete_ids,
                    delete_status=delete_status,
                    delete_comments=delete_comments,
                )
                delete_advances(delete_ids)
                st.session_state.pop(f"delete_advances_editor_{records_view}{key_suffix}", None)
                st.session_state.pop(f"select_all_visible_advances{key_suffix}", None)
                if delete_ids:
                    st.success(
                        f"{label}: {len(delete_ids)} registro(s) eliminado(s). "
                        f"Se conservaron {len(keep_ids)} ultimo(s) registro(s) protegido(s)."
                    )
                else:
                    st.info(f"{label}: no habia registros antiguos para eliminar con esta seleccion.")
                st.rerun()

            d1, d2, d3 = st.columns(3)
            if d1.button(
                "Borrar estados y comentarios antiguos",
                disabled=not selected_delete_ids,
                key=f"clean_status_comments{key_suffix}",
            ):
                run_selected_cleanup("Estados y comentarios", delete_status=True, delete_comments=True)
            if d2.button(
                "Borrar cambios de estado antiguos",
                disabled=not selected_delete_ids,
                key=f"clean_status_only{key_suffix}",
            ):
                run_selected_cleanup("Cambios de estado", delete_status=True, delete_comments=False)
            if d3.button(
                "Borrar comentarios antiguos",
                disabled=not selected_delete_ids,
                key=f"clean_comments_only{key_suffix}",
            ):
                run_selected_cleanup("Comentarios", delete_status=False, delete_comments=True)
            confirm_all = st.checkbox(
                "Confirmo resetear avances del programa activo al estado original del Excel",
                key=f"confirm_reset_advances{key_suffix}",
            )
            if st.button("Resetear al Excel original", disabled=not confirm_all, key=f"reset_advances{key_suffix}"):
                delete_advances([advance["id"] for advance in advances])
                st.session_state.pop(f"delete_advances_editor_{records_view}{key_suffix}", None)
                st.session_state.pop(f"select_all_visible_advances{key_suffix}", None)
                st.success("Registros del programa eliminados.")
                st.rerun()

    e1, e2 = st.columns(2)
    e1.download_button(
        "Exportar log Excel",
        data=advances_export(filtered_base, filtered_advances, final_only=False),
        file_name=f"avances_{local_today().isoformat()}.xlsx",
        key=f"export_log{key_suffix}",
    )
    e2.download_button(
        "Exportar estado final Excel",
        data=advances_export(filtered_base, filtered_advances, final_only=True),
        file_name=f"estado_final_{local_today().isoformat()}.xlsx",
        key=f"export_final{key_suffix}",
    )
