from __future__ import annotations

from typing import Any

import streamlit as st

from .config import HIDE_AFTER_SAVE_ACTIONS, REASON_ACTIONS, STATE_ACTIONS
from .supabase_client import sb_delete, sb_insert


def is_status_advance(advance: dict[str, Any]) -> bool:
    action = str(advance.get("action") or "").strip().upper()
    return bool(action) and action != "COMENTARIO"


def advance_has_comment(advance: dict[str, Any]) -> bool:
    reason = str(advance.get("reason") or "").strip()
    observation = str(advance.get("observation") or "").strip()
    return bool(reason or observation)


def advance_record_type(advance: dict[str, Any]) -> str:
    if not is_status_advance(advance):
        return "Comentario"
    if advance_has_comment(advance):
        return "Cambio de estado + comentario"
    return "Cambio de estado"


def delete_candidates_preserving_latest_status(
    advances: list[dict[str, Any]],
    candidate_ids: list[str],
) -> tuple[list[str], set[str]]:
    candidate_set = {str(item) for item in candidate_ids if item}
    keep_ids: set[str] = set()
    seen_tasks: set[str] = set()
    for advance in sorted(advances, key=lambda item: item.get("created_at", ""), reverse=True):
        task_id = str(advance.get("task_id") or "")
        advance_id = str(advance.get("id") or "")
        if not task_id or task_id in seen_tasks or not is_status_advance(advance):
            continue
        seen_tasks.add(task_id)
        if advance_id in candidate_set:
            keep_ids.add(advance_id)
    delete_ids = [str(item) for item in candidate_ids if item and str(item) not in keep_ids]
    return delete_ids, keep_ids


def delete_candidates_preserving_latest_records(
    advances: list[dict[str, Any]],
    candidate_ids: list[str],
    delete_status: bool,
    delete_comments: bool,
) -> tuple[list[str], set[str]]:
    candidate_set = {str(item) for item in candidate_ids if item}
    keep_ids: set[str] = set()
    seen_status_tasks: set[str] = set()
    seen_comment_tasks: set[str] = set()
    for advance in sorted(advances, key=lambda item: item.get("created_at", ""), reverse=True):
        task_id = str(advance.get("task_id") or "")
        advance_id = str(advance.get("id") or "")
        if not task_id or not advance_id:
            continue
        if is_status_advance(advance):
            if task_id in seen_status_tasks:
                continue
            seen_status_tasks.add(task_id)
            if advance_id in candidate_set and delete_status:
                keep_ids.add(advance_id)
        else:
            if task_id in seen_comment_tasks:
                continue
            seen_comment_tasks.add(task_id)
            if advance_id in candidate_set and delete_comments:
                keep_ids.add(advance_id)

    delete_ids: list[str] = []
    for advance in advances:
        advance_id = str(advance.get("id") or "")
        if advance_id not in candidate_set or advance_id in keep_ids:
            continue
        if is_status_advance(advance) and delete_status:
            delete_ids.append(advance_id)
        elif not is_status_advance(advance) and delete_comments:
            delete_ids.append(advance_id)
    return delete_ids, keep_ids


def delete_advances(advance_ids: list[str]) -> None:
    clean_ids = [item for item in advance_ids if item]
    for start in range(0, len(clean_ids), 100):
        chunk = ",".join(clean_ids[start : start + 100])
        sb_delete("advances", {"id": f"in.({chunk})"})


def save_advances(program_id: str, task_ids: list[str], action: str, reason: str, observation: str) -> None:
    profile = st.session_state.profile
    rows = [
        {
            "program_id": program_id,
            "task_id": task_id,
            "action": action,
            "reason": reason,
            "observation": observation,
            "reporter_name": profile["name"],
            "reporter_company": profile.get("company") or "",
            "reporter_sector": profile.get("sector") or "",
        }
        for task_id in task_ids
    ]
    sb_insert("advances", rows)


def save_advance_entries(program_id: str, entries: list[dict[str, str]], reason: str, observation: str) -> None:
    profile = st.session_state.profile
    rows = [
        {
            "program_id": program_id,
            "task_id": entry["task_id"],
            "action": entry["action"],
            "reason": reason if entry["action"] in REASON_ACTIONS else "",
            "observation": observation,
            "reporter_name": profile["name"],
            "reporter_company": profile.get("company") or "",
            "reporter_sector": profile.get("sector") or "",
        }
        for entry in entries
    ]
    sb_insert("advances", rows)


def combined_comment(advance: dict[str, Any]) -> str:
    reason = str(advance.get("reason") or "").strip()
    observation = str(advance.get("observation") or "").strip()
    if reason and observation:
        return f"{reason} / {observation}"
    return reason or observation


def latest_status_by_task(advances: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for advance in sorted(advances, key=lambda item: item.get("created_at", ""), reverse=True):
        if advance["task_id"] not in latest and advance.get("action") != "COMENTARIO":
            latest[advance["task_id"]] = advance
    return latest


def effective_task_status(task: dict[str, Any], latest: dict[str, dict[str, Any]]) -> str:
    """Estado efectivo de la tarea: prioriza el ultimo avance guardado en la app
    y, si no hay, usa el estado que trae el programa (Excel). Normaliza a
    mayusculas para tolerar distinto formato en el Excel."""
    advance = latest.get(task["id"], {})
    status = str(advance.get("action") or task.get("estado_programa") or "SIN AVANCE").strip().upper()
    if status not in STATE_ACTIONS:
        status = "SIN AVANCE"
    return status


def hide_task_after_saved(task: dict[str, Any], latest: dict[str, dict[str, Any]]) -> bool:
    return effective_task_status(task, latest) in HIDE_AFTER_SAVE_ACTIONS
