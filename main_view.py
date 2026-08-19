from __future__ import annotations

import streamlit as st

from ..advances import (
    hide_task_after_saved,
    latest_status_by_task,
    save_advance_entries,
)
from ..config import REASON_ACTIONS, REASONS, SEARCH_FIELD_OPTIONS, STATE_ACTIONS
from ..data import list_programs, load_advances, load_tasks
from ..filters import (
    add_search_filter_from_state,
    apply_filters,
    current_filter_state,
    remove_search_filter,
    restore_filter_state,
)
from ..session_ui import (
    apply_navigation,
    clear_pending_work,
    clear_task_selection,
    has_pending_work,
    logout_controls,
    mark_comment_dirty,
)
from ..textutils import canonical_area, effective_sector, normalize, option_label, program_area, scope_value
from ..timeutil import local_today
from .admin import admin_panel
from .board import render_records_section, task_dataframe, task_status_style, task_table_column_config
from .dashboard import render_dashboard
from .auth import require_session
from .styles import app_header


def main() -> None:
    require_session()

    if st.session_state.pop("clear_comment_text_next", False):
        st.session_state.pop("common_comment_text", None)
        st.session_state.pop("common_reason_select", None)
        st.session_state.pop("state_select_for_selected", None)
        st.session_state["comment_dirty"] = False
    app_header()
    logout_controls()
    admin_panel()

    profile = st.session_state.profile
    area = canonical_area(profile.get("area") or "GENERACION")
    programs = [program for program in list_programs(active_only=True) if program_area(program) == area]
    if not programs:
        st.info(f"No hay programas activos para {area}. Ingresar como administrador y cargar un Excel.")
        return

    program_col, _program_spacer = st.columns([2.1, 2.9])
    program = program_col.selectbox(
        "Programa",
        programs,
        format_func=lambda item: item["name"],
        key="program_filter",
    )
    tasks = load_tasks(program["id"])
    advances = load_advances(program["id"])
    latest = latest_status_by_task(advances)

    company = scope_value(profile.get("company"))
    sector = scope_value(profile.get("sector"))
    scoped_tasks = apply_filters(tasks, company, sector, "", None, None, "")
    if st.session_state.role == "admin" and profile.get("admin_view") == "Avances / registros":
        scoped_task_ids = {task["id"] for task in scoped_tasks}
        scoped_advances = [advance for advance in advances if advance.get("task_id") in scoped_task_ids]
        st.caption(
            f"Vista de administrador: {area} - {profile.get('company') or 'Todas'} / "
            f"{profile.get('sector') or 'Todos'}. Los registros se mantienen separados por area."
        )
        render_records_section(tasks, advances, scoped_tasks, scoped_advances, records_key_suffix="admin_direct")
        return

    render_dashboard(scoped_tasks, latest)

    inner_sector_options = [""] + sorted(
        {effective_sector(task) for task in scoped_tasks if effective_sector(task)},
        key=lambda item: normalize(item),
    )
    f1, f2, f3, f4, f5 = st.columns([0.95, 1.25, 0.62, 0.62, 1.95])
    inner_sector = f1.selectbox(
        "Sector",
        inner_sector_options,
        format_func=lambda item: option_label(item, "Todos"),
        key="sector_filter",
    )
    tasks_for_crews = apply_filters(scoped_tasks, "", inner_sector, "", None, None, "")
    crew_options = sorted({task.get("cuadrilla") or "" for task in tasks_for_crews if task.get("cuadrilla")})
    if "crew_filter" in st.session_state and not isinstance(st.session_state.get("crew_filter"), list):
        st.session_state.pop("crew_filter", None)
    crew = f2.multiselect("Cuadrilla", crew_options, placeholder="Todas", key="crew_filter")
    start = f3.date_input("Fecha inicio", value=None, format="DD/MM/YYYY", key="start_filter")
    end = f4.date_input("Fecha fin", value=None, format="DD/MM/YYYY", key="end_filter")
    active_search_terms = st.session_state.setdefault("search_terms_filter", [])
    search_field_col, search_value_col = f5.columns([0.9, 1.25])
    search_field_col.selectbox("Buscar por", list(SEARCH_FIELD_OPTIONS.keys()), key="search_field_input")
    search_value_col.text_input(
        "Buscar",
        placeholder="Escribir y presionar Enter",
        key="search_value_input",
        on_change=add_search_filter_from_state,
    )
    active_search_terms = st.session_state.get("search_terms_filter", [])
    if active_search_terms:
        tag_cols = st.columns(4)
        for index, label in enumerate(active_search_terms):
            if tag_cols[index % 4].button(f"x {label}", key=f"remove_search_filter_{index}_{normalize(label)}"):
                remove_search_filter(label)
                st.rerun()
    show_all_tasks = bool(st.session_state.get("show_all_tasks_filter", False))

    filters_now = current_filter_state(program["id"])

    filters_before = st.session_state.get("last_filter_state")
    if filters_before is None:
        st.session_state.last_filter_state = filters_now
    elif filters_now != filters_before:
        if has_pending_work():
            st.session_state.filter_change_guard = {
                "previous": filters_before,
                "current": filters_now,
            }
        else:
            st.session_state.previous_filter_state = filters_before
            st.session_state.last_filter_state = filters_now
            # Cambio el conjunto visible: se limpia la seleccion y se destilda
            # el check maestro (no queda ninguna tarea seleccionada).
            clear_task_selection()

    base_sector = inner_sector or sector
    filtered_base = apply_filters(tasks, company, base_sector, crew, start, end, active_search_terms)
    loaded_for_scope = apply_filters(tasks, company, base_sector, "", None, None, "")
    if show_all_tasks:
        filtered = filtered_base
    else:
        filtered = [task for task in filtered_base if not hide_task_after_saved(task, latest)]
    hidden_count = len(filtered_base) - len(filtered)
    caption = f"{len(filtered)} tarea(s) visibles de {len(loaded_for_scope)} cargadas para empresa/sector."
    if hidden_count:
        caption += f" {hidden_count} completada(s) o a replanificar ocultas."
    visible_task_ids = {task["id"] for task in filtered}
    filtered_base_task_ids = {task["id"] for task in filtered_base}
    # Los avances/registros siguen los MISMOS filtros que el tablero (empresa,
    # sector, cuadrilla, fechas, busqueda). Se incluyen las tareas completadas o
    # a replanificar que se ocultan del tablero, para no perder sus registros.
    filtered_advances = [advance for advance in advances if advance.get("task_id") in filtered_base_task_ids]
    scoped_task_ids = {task["id"] for task in scoped_tasks}
    scoped_advances = [advance for advance in advances if advance.get("task_id") in scoped_task_ids]

    pending_changes = st.session_state.setdefault("pending_state_changes", {})
    selected_task_state = set(st.session_state.setdefault("selected_task_ids", []))

    # Manejo del check maestro "Seleccionar tareas visibles". Solo actua en la
    # TRANSICION (cuando se tilda o se destilda), no en cada rerun, para que las
    # tareas que el usuario destilde individualmente queden respetadas y no se
    # vuelvan a marcar solas.
    master_now = bool(st.session_state.get("select_all_visible_tasks_filter", False))
    master_prev = bool(st.session_state.get("select_all_visible_tasks_prev", False))
    if master_now and not master_prev:
        # Recien tildado: seleccionar todas las visibles (una sola vez). Se
        # descartan ediciones de "Seleccionar" previas del editor; los cambios
        # de estado ya viven en pending_changes y se reaplican mas abajo.
        selected_task_state.update(visible_task_ids)
        st.session_state.pop("task_editor", None)
    elif master_prev and not master_now:
        # Recien destildado: limpiar toda la seleccion.
        selected_task_state.clear()
        st.session_state.pop("task_editor", None)
    elif master_now and visible_task_ids and not visible_task_ids.issubset(selected_task_state):
        # Sigue tildado pero el usuario destildo alguna: destildar el maestro
        # (ya no estan todas las visibles) sin tocar la seleccion restante.
        st.session_state["select_all_visible_tasks_filter"] = False
        master_now = False
    st.session_state.select_all_visible_tasks_prev = master_now
    st.session_state.selected_task_ids = sorted(selected_task_state)

    df = task_dataframe(filtered, latest)
    for index, row in df.iterrows():
        task_id = str(row["_task_id"])
        if task_id in selected_task_state:
            df.at[index, "Seleccionar"] = True
        if task_id in pending_changes:
            df.at[index, "Estado"] = pending_changes[task_id]
            df.at[index, "Seleccionar"] = True
            if pending_changes[task_id] == "EN CURSO" and not str(df.at[index, "Fecha inicio"] or "").strip():
                df.at[index, "Fecha inicio"] = local_today().strftime("%d/%m/%Y")

    editor_state = st.session_state.get("task_editor", {})
    if isinstance(editor_state, dict):
        for row_index, changes in editor_state.get("edited_rows", {}).items():
            try:
                index = int(row_index)
            except Exception:
                continue
            if 0 <= index < len(df):
                if "Seleccionar" in changes:
                    df.at[index, "Seleccionar"] = bool(changes["Seleccionar"])
                if "Estado" in changes:
                    new_status = str(changes["Estado"] or "")
                    original_status = str(df.at[index, "_estado_original"] or "")
                    df.at[index, "Estado"] = new_status
                    if new_status and new_status != original_status:
                        df.at[index, "Seleccionar"] = True
                        task_id = str(df.at[index, "_task_id"])
                        pending_changes[task_id] = new_status
                        st.session_state.pending_program_id = program["id"]
                        if new_status == "EN CURSO" and not str(df.at[index, "Fecha inicio"] or "").strip():
                            df.at[index, "Fecha inicio"] = local_today().strftime("%d/%m/%Y")

    selected_task_ids = [
        str(row["_task_id"])
        for _, row in df.iterrows()
        if bool(row.get("Seleccionar"))
    ]
    pending_visible_ids = sorted(task_id for task_id in pending_changes if task_id in visible_task_ids)
    pending_all_ids = sorted(pending_changes)

    entries = [{"task_id": task_id, "action": pending_changes[task_id]} for task_id in pending_all_ids]
    selected_actions = [entry["action"] for entry in entries]
    pending_needs_reason = any(item in REASON_ACTIONS for item in selected_actions)

    st.markdown("#### Cambiar estado / comentar")
    # Los campos aparecen solo cuando hay tareas seleccionadas (o cambios ya
    # pendientes). El estado y el comentario elegidos aca NO se aplican hasta
    # tocar "Guardar cambios".
    if selected_task_ids or pending_all_ids:
        # Valor previo del desplegable, para decidir si mostrar el motivo antes
        # de instanciar el widget de estado.
        action_prev = str(st.session_state.get("state_select_for_selected", "") or "")
        show_reason = pending_needs_reason or action_prev in REASON_ACTIONS

        if show_reason:
            estado_col, motivo_col, detalle_col = st.columns([1.0, 1.0, 1.8])
        else:
            estado_col, detalle_col = st.columns([1.0, 2.0])
            motivo_col = None

        action = estado_col.selectbox(
            "Estado para seleccionadas",
            [""] + STATE_ACTIONS,
            format_func=lambda item: option_label(item, "Elegir estado"),
            key="state_select_for_selected",
            help="Se aplica a las tareas tildadas al tocar 'Guardar cambios'. Tambien podes cambiar el estado directamente en la columna Estado de cada fila.",
        )
        if motivo_col is not None:
            reason = motivo_col.selectbox(
                "Motivo (obligatorio)",
                REASONS,
                format_func=lambda item: option_label(item, "Elegir motivo"),
                key="common_reason_select",
            )
        else:
            reason = ""

        # El motivo/detalle obligatorio depende de lo que se va a guardar:
        # pendientes con EN ESPERA/REPLANIFICAR, o el estado elegido ahora.
        will_need_reason = pending_needs_reason or action in REASON_ACTIONS
        detail_required = will_need_reason and reason == "Otros"
        detail_label = "Detalle (obligatorio)" if detail_required else "Detalle (opcional)"
        observation = detalle_col.text_input(
            detail_label,
            placeholder="Detalle libre. Obligatorio si el motivo es 'Otros'. Tambien sirve como comentario de las tareas seleccionadas.",
            key="common_comment_text",
            on_change=mark_comment_dirty,
        )
    else:
        action = ""
        reason = ""
        observation = ""
        st.caption("Selecciona una o mas tareas para cambiar su estado o dejar un comentario.")

    def save_current_pending_work() -> bool:
        save_program_id = st.session_state.get("pending_program_id") or program["id"]
        # Aplicar el estado elegido en el desplegable a las tareas seleccionadas.
        if action and selected_task_ids:
            for task_id in selected_task_ids:
                pending_changes[task_id] = action
            save_program_id = program["id"]
        current_pending_ids = sorted(pending_changes)
        current_entries = [{"task_id": tid, "action": pending_changes[tid]} for tid in current_pending_ids]
        current_actions = [item["action"] for item in current_entries]
        needs_reason = any(item in REASON_ACTIONS for item in current_actions)
        if current_pending_ids:
            if needs_reason and not reason:
                st.warning("Elegi un motivo para EN ESPERA o REPLANIFICAR.")
                return False
            if needs_reason and reason == "Otros" and not observation.strip():
                st.warning("Escribi el detalle cuando el motivo es 'Otros'.")
                return False
            save_advance_entries(save_program_id, current_entries, reason, observation.strip())
            clear_pending_work()
            return True
        if observation.strip() and selected_task_ids:
            comment_entries = [{"task_id": task_id, "action": "COMENTARIO"} for task_id in selected_task_ids]
            save_advance_entries(program["id"], comment_entries, "", observation.strip())
            clear_pending_work()
            return True
        st.warning("No hay cambios ni comentarios para guardar.")
        return False

    # Hay algo para guardar si hay pendientes, un estado elegido para las
    # seleccionadas, o un comentario para las seleccionadas.
    has_savable_changes = (
        bool(pending_all_ids)
        or bool(action and selected_task_ids)
        or bool(observation.strip() and selected_task_ids)
    )

    if st.session_state.pop("request_refresh", False):
        if pending_all_ids:
            st.session_state.confirm_refresh = True
        else:
            clear_task_selection()
            st.rerun()

    if st.session_state.get("confirm_refresh"):
        st.warning("Hay avances pendientes sin guardar. Elegi como continuar antes de actualizar datos.")
        r1, r2, r3 = st.columns(3)
        if r1.button("Guardar avances y actualizar", type="primary"):
            if save_current_pending_work():
                st.rerun()
        if r2.button("Actualizar sin guardar"):
            clear_pending_work()
            st.rerun()
        if r3.button("Cancelar"):
            st.session_state.pop("confirm_refresh", None)
            st.rerun()

    filter_guard = st.session_state.get("filter_change_guard")
    if filter_guard:
        st.warning("Cambiaste un filtro y hay avances o comentarios pendientes sin guardar.")
        f1, f2, f3 = st.columns(3)

        if f1.button("Guardar y aplicar filtro", type="primary"):
            previous = filter_guard.get("previous")
            current = filter_guard.get("current")
            if save_current_pending_work():
                st.session_state.previous_filter_state = previous
                st.session_state.last_filter_state = current
                st.session_state.pop("filter_change_guard", None)
                st.rerun()

        def apply_filter_without_saving() -> None:
            guard = st.session_state.get("filter_change_guard") or {}
            previous = guard.get("previous")
            current = guard.get("current")
            # El usuario confirma el filtro nuevo y descarta todo avance/comentario
            # pendiente. Como esto corre en callback, ocurre antes del nuevo render.
            clear_pending_work()
            st.session_state.previous_filter_state = previous
            st.session_state.last_filter_state = current
            st.session_state.pop("filter_change_guard", None)

        def cancel_filter_change() -> None:
            guard = st.session_state.get("filter_change_guard") or {}
            previous = guard.get("previous")
            if previous:
                # Callback de Streamlit: se ejecuta antes del siguiente render,
                # por lo que es seguro restaurar las keys de los widgets acá.
                restore_filter_state(previous)
                st.session_state.last_filter_state = previous
            st.session_state.pop("filter_change_guard", None)
            st.session_state.pop("previous_filter_state", None)
            clear_task_selection()

        f2.button(
            "Aplicar filtro sin guardar",
            on_click=apply_filter_without_saving,
        )
        f3.button(
            "Cancelar cambio de filtro",
            on_click=cancel_filter_change,
        )

    pending_navigation = st.session_state.get("pending_navigation")
    if pending_navigation:
        label = "volver al inicio" if pending_navigation == "profile" else "cerrar sesion"
        st.warning(f"Hay avances o comentarios pendientes sin guardar antes de {label}.")
        n1, n2, n3 = st.columns(3)
        if n1.button("Guardar y continuar", type="primary"):
            if save_current_pending_work():
                apply_navigation(pending_navigation)
        if n2.button("Continuar sin guardar"):
            clear_pending_work()
            apply_navigation(pending_navigation)
        if n3.button("Cancelar salida"):
            st.session_state.pop("pending_navigation", None)
            st.rerun()

    guard_active = bool(
        st.session_state.get("confirm_refresh")
        or st.session_state.get("filter_change_guard")
        or st.session_state.get("pending_navigation")
    )

    save_col, discard_col, pending_col, select_all_col, show_col = st.columns([1.1, 1.15, 1.05, 1.25, 1.2])
    if not guard_active:
        if save_col.button("Guardar cambios", type="primary", disabled=not has_savable_changes, use_container_width=True):
            # Contar lo que se va a guardar antes de aplicar/limpiar.
            affected = set(pending_all_ids)
            if action and selected_task_ids:
                affected.update(selected_task_ids)
            comment_only = not affected and bool(observation.strip()) and bool(selected_task_ids)
            if save_current_pending_work():
                if affected:
                    st.success(f"{len(affected)} tarea(s) actualizada(s).")
                elif comment_only:
                    st.success(f"{len(selected_task_ids)} comentario(s) guardado(s).")
                else:
                    st.success("Cambios guardados.")
                st.rerun()

        # "No guardar cambios": descarta los cambios de estado y/o comentarios
        # pendientes y vuelve al estado previo. Se habilita cuando hay algo que
        # descartar (cambio de estado pendiente, estado elegido o comentario).
        if discard_col.button("No guardar cambios", disabled=not (has_pending_work() or has_savable_changes), use_container_width=True):
            clear_pending_work()
            st.rerun()

        if pending_all_ids:
            pending_col.caption(f"{len(pending_all_ids)} avance(s) pendiente(s) de guardar.")
    else:
        # Hay un aviso activo arriba: resolverlo con sus propios botones.
        save_col.caption("Resolve el aviso de arriba para continuar.")
    select_all_col.checkbox(
        "Seleccionar tareas visibles",
        key="select_all_visible_tasks_filter",
    )
    show_col.checkbox("Mostrar todas las tareas", value=show_all_tasks, key="show_all_tasks_filter")
    st.caption(caption)

    visible_df = df.drop(columns=["_task_id", "_estado_original"], errors="ignore")
    edited = st.data_editor(
        visible_df.style.apply(task_status_style, axis=1),
        hide_index=True,
        use_container_width=False,
        disabled=[column for column in visible_df.columns if column not in {"Seleccionar", "Estado"}],
        column_config=task_table_column_config(),
        key="task_editor",
    )
    if not edited.empty:
        previous_visible_selection = selected_task_state.intersection(visible_task_ids)
        selected_task_state.difference_update(visible_task_ids)
        current_visible_selection = {
            str(df.at[index, "_task_id"])
            for index in edited.index[edited["Seleccionar"] == True].tolist()
            if index in df.index
        }
        selected_task_state.update(current_visible_selection)
        for index, row in edited.iterrows():
            if index not in df.index:
                continue
            task_id = str(df.at[index, "_task_id"])
            status = str(row["Estado"] or "")
            original_status = str(df.at[index, "_estado_original"] or "")
            if status and status != original_status:
                pending_changes[task_id] = status
                st.session_state.pending_program_id = program["id"]
            elif task_id in pending_changes:
                pending_changes.pop(task_id, None)
        st.session_state.selected_task_ids = sorted(selected_task_state)
        if current_visible_selection != previous_visible_selection:
            st.rerun()

    render_records_section(tasks, advances, filtered_base, filtered_advances)
