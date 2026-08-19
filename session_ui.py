from __future__ import annotations

from typing import Any

import streamlit as st

from .filters import restore_filter_state
from .textutils import canonical_area


def editor_has_status_changes(editor_state: Any) -> bool:
    """True solo si el editor tiene cambios de Estado. Marcar/desmarcar la
    columna Seleccionar NO se considera un cambio pendiente."""
    if not isinstance(editor_state, dict):
        return False
    for changes in editor_state.get("edited_rows", {}).values():
        if isinstance(changes, dict) and any(key != "Seleccionar" for key in changes):
            return True
    return False


def mark_comment_dirty() -> None:
    """Marca el comentario como pendiente solo cuando el usuario modifica su texto."""
    st.session_state["comment_dirty"] = bool(
        str(st.session_state.get("common_comment_text") or "").strip()
    )


def has_pending_work() -> bool:
    pending = st.session_state.get("pending_state_changes", {})
    comment = str(st.session_state.get("common_comment_text") or "").strip()
    comment_pending = bool(st.session_state.get("comment_dirty", False)) and bool(comment)
    editor_state = st.session_state.get("task_editor", {})
    # La seleccion de tareas (selected_task_ids / check maestro) no cuenta como
    # trabajo pendiente. Un comentario solo cuenta si fue modificado y aun no se guardo.
    return bool(pending) or comment_pending or editor_has_status_changes(editor_state)


def clear_task_selection() -> None:
    """Limpia toda la seleccion de tareas y destilda el check maestro.

    El check maestro se fuerza a False por asignacion explicita (no pop):
    en Streamlit, hacer pop de la key de un widget NO destilda el checkbox
    porque conserva su estado interno; asignarle False si lo destilda."""
    st.session_state.pop("selected_task_ids", None)
    st.session_state["select_all_visible_tasks_filter"] = False
    st.session_state["select_all_visible_tasks_prev"] = False
    st.session_state.pop("task_editor", None)


def clear_pending_work() -> None:
    st.session_state.pop("pending_state_changes", None)
    st.session_state.pop("pending_program_id", None)
    st.session_state.pop("selected_task_ids", None)
    st.session_state["select_all_visible_tasks_filter"] = False
    st.session_state["select_all_visible_tasks_prev"] = False
    st.session_state.pop("task_editor", None)
    st.session_state["comment_dirty"] = False
    st.session_state.clear_comment_text_next = True
    st.session_state.pop("confirm_refresh", None)
    st.session_state.pop("pending_navigation", None)
    st.session_state.pop("filter_change_guard", None)


def request_navigation(action: str) -> None:
    if has_pending_work():
        st.session_state.pending_navigation = action
    elif action == "profile":
        clear_task_selection()
        st.session_state.pop("profile", None)
        st.rerun()
    elif action == "logout":
        st.session_state.clear()
        st.rerun()


def apply_navigation(action: str) -> None:
    if action == "profile":
        clear_pending_work()
        st.session_state.pop("profile", None)
        st.rerun()
    if action == "logout":
        st.session_state.clear()
        st.rerun()


def undo_last_change() -> None:
    if st.session_state.get("confirm_refresh") or st.session_state.get("pending_navigation") or st.session_state.get("filter_change_guard"):
        st.session_state.pop("confirm_refresh", None)
        st.session_state.pop("pending_navigation", None)
        st.session_state.pop("filter_change_guard", None)
        clear_task_selection()
        st.rerun()
    if has_pending_work():
        clear_pending_work()
        st.rerun()
    if st.session_state.get("selected_task_ids") or st.session_state.get("select_all_visible_tasks_filter"):
        clear_task_selection()
        st.rerun()
    previous = st.session_state.get("previous_filter_state")
    if previous:
        restore_filter_state(previous)
        st.session_state.last_filter_state = previous
        st.session_state.pop("previous_filter_state", None)
        clear_task_selection()
        st.rerun()


def logout_controls() -> None:
    col1, col2, col3, col4, col5 = st.columns([3.0, 0.9, 0.9, 1, 1])
    profile = st.session_state.profile
    role = "Administrador" if st.session_state.role == "admin" else "Usuario"
    area = canonical_area(profile.get("area") or "GENERACION")
    profile_name = profile.get("name") or role
    col1.caption(
        f"{role}: {profile_name} - {area} - {profile.get('company') or 'Todas'} / {profile.get('sector') or 'Todos'}"
    )
    if col2.button("Deshacer"):
        undo_last_change()
    if col3.button("Actualizar datos"):
        st.session_state.request_refresh = True
    if col4.button("Volver al inicio"):
        request_navigation("profile")
    if col5.button("Cerrar sesion"):
        request_navigation("logout")
