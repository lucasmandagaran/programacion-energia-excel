from __future__ import annotations

import hashlib
import io
import json
import os
import re
import unicodedata
from datetime import date, datetime
from typing import Any

import pandas as pd
import requests
import streamlit as st


APP_TITLE = "Programacion Energia"
COMPANIES = ["", "MANPETROL", "SAN&FRAN", "OTRA"]
SECTORS = ["", "Electricidad", "Mecanica", "Instrumentacion", "Otros"]
GENERATION_SECTORS = {"electricidad", "mecanica", "instrumentacion"}
STATE_ACTIONS = ["EN CURSO", "EN ESPERA", "COMPLETADO", "REPLANIFICAR", "SIN AVANCE"]
REASON_ACTIONS = {"EN ESPERA", "REPLANIFICAR"}
REASONS = [
    "",
    "Pedido Sup PAE",
    "Por factor climatico",
    "Por falta de equipo/recursos/materiales",
    "Cuadrilla no operativa",
    "Otros",
]


def option_label(value: str, empty_label: str) -> str:
    return value or empty_label


def scope_value(value: Any) -> str:
    text = str(value or "").strip()
    if normalize(text) in {"todas", "todos", "all"}:
        return ""
    return text


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, "") or os.getenv(name, "") or default)
    except Exception:
        return str(os.getenv(name, "") or default)


SUPABASE_URL = secret("SUPABASE_URL").rstrip("/")
if SUPABASE_URL.endswith("/rest/v1"):
    SUPABASE_URL = SUPABASE_URL[: -len("/rest/v1")]
SUPABASE_KEY = secret("SUPABASE_KEY")
ACCESS_PASSWORD = secret("ACCESS_PASSWORD", "Energia2026")
ADMIN_PASSWORD = secret("ADMIN_PASSWORD", "36719317")


st.set_page_config(page_title=APP_TITLE, page_icon="PE", layout="wide")


def normalize(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_crew(value: Any) -> str:
    text = normalize(value).upper().replace(" ", "")
    text = re.sub(r"(MP|SF|SANFRAN|MANPETROL)$", "", text)
    return text


def infer_company_sector(cuadrilla: Any) -> tuple[str, str]:
    crew = normalize_crew(cuadrilla)
    if crew in {"555", "555A"}:
        return "MANPETROL", "Electricidad"
    if crew in {"556A", "556B", "556C"}:
        return "MANPETROL", "Instrumentacion"
    if crew in {"720", "721", "722", "723", "724"}:
        return "SAN&FRAN", "Mecanica"
    return "", "Otros"


def effective_company(task: dict[str, Any]) -> str:
    value = str(task.get("empresa") or "").strip()
    inferred, _ = infer_company_sector(task.get("cuadrilla"))
    return value or inferred


def effective_sector(task: dict[str, Any]) -> str:
    value = str(task.get("sector") or "").strip()
    _, inferred = infer_company_sector(task.get("cuadrilla"))
    return value or inferred


def is_other_company_scope(task: dict[str, Any]) -> bool:
    inferred_company, _ = infer_company_sector(task.get("cuadrilla"))
    return not inferred_company


def is_other_sector_scope(task: dict[str, Any]) -> bool:
    _, inferred_sector = infer_company_sector(task.get("cuadrilla"))
    if inferred_sector == "Otros":
        return True
    return normalize(effective_sector(task)) not in GENERATION_SECTORS


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


def delete_advances(advance_ids: list[str]) -> None:
    clean_ids = [item for item in advance_ids if item]
    for start in range(0, len(clean_ids), 100):
        chunk = ",".join(clean_ids[start : start + 100])
        sb_delete("advances", {"id": f"in.({chunk})"})


def login_screen() -> None:
    st.title(APP_TITLE)
    st.subheader("Trabajos programados")
    mode = st.radio("Modo de ingreso", ["Cuadrilla / contratista", "Administrador"], horizontal=True)
    password = st.text_input("Contrasena", type="password")
    if st.button("Ingresar", type="primary"):
        if mode.startswith("Administrador"):
            if password == ADMIN_PASSWORD:
                st.session_state.role = "admin"
                st.rerun()
            st.error("Clave administradora incorrecta.")
        else:
            if password == ACCESS_PASSWORD:
                st.session_state.role = "user"
                st.rerun()
            st.error("Contrasena incorrecta.")
    st.stop()


def profile_screen() -> None:
    st.title(APP_TITLE)
    st.subheader("Ingreso al programa")
    with st.form("profile_form"):
        company = st.selectbox("Empresa", COMPANIES, index=0, format_func=lambda item: option_label(item, "Todas"))
        sector = st.selectbox("Sector", SECTORS, index=0, format_func=lambda item: option_label(item, "Todos"))
        name = st.text_input("Nombre", placeholder="Nombre y apellido / rol")
        if st.form_submit_button("Ingresar", type="primary"):
            if not name.strip():
                st.warning("Ingresar nombre de usuario.")
                st.stop()
            st.session_state.profile = {"company": company, "sector": sector, "name": name.strip()}
            st.rerun()
    st.stop()


def require_session() -> None:
    if "role" not in st.session_state:
        login_screen()
    if "profile" not in st.session_state:
        profile_screen()


def logout_controls() -> None:
    col1, col2, col3 = st.columns([3, 1, 1])
    profile = st.session_state.profile
    role = "Administrador" if st.session_state.role == "admin" else "Usuario"
    col1.caption(f"{role}: {profile['name']} - {profile.get('company') or 'Todas'} / {profile.get('sector') or 'Todos'}")
    if col2.button("Cambiar perfil"):
        st.session_state.pop("profile", None)
        st.rerun()
    if col3.button("Cerrar sesion"):
        st.session_state.clear()
        st.rerun()


def find_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized = {normalize(column): column for column in columns}
    for candidate in candidates:
        wanted = normalize(candidate)
        if wanted in normalized:
            return normalized[wanted]
    for norm, original in normalized.items():
        if any(normalize(candidate) in norm for candidate in candidates):
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
    for candidate in candidates:
        value = normalized.get(normalize(candidate))
        if value not in (None, ""):
            return str(value).strip()
    for key, value in normalized.items():
        if value in (None, ""):
            continue
        if any(normalize(candidate) in key for candidate in candidates):
            return str(value).strip()
    return ""


def raw_column_name(raw: dict[str, Any], candidates: list[str]) -> str | None:
    normalized = {normalize(column): column for column in raw.keys()}
    for candidate in candidates:
        wanted = normalize(candidate)
        if wanted in normalized:
            return normalized[wanted]
    for norm, original in normalized.items():
        if any(normalize(candidate) in norm for candidate in candidates):
            return original
    return None


def task_title(task: dict[str, Any]) -> str:
    title = raw_value(
        task,
        [
            "title",
            "titulo",
            "titulo tarea",
            "titulo de tarea",
            "descripcion",
            "descripcion tarea",
            "description",
            "task title",
            "nombre tarea",
        ],
    )
    if title:
        return title
    return str(task.get("tarea") or "").strip()


def map_excel(df: pd.DataFrame) -> list[dict[str, Any]]:
    columns = list(df.columns)
    mapping = {
        "nro_ot": find_column(columns, ["nro ot", "nro de ot", "numero ot", "ot", "orden"]),
        "tarea": find_column(columns, ["trabajo", "tarea", "descripcion", "nombre", "titulo"]),
        "empresa": find_column(columns, ["empresa", "contratista"]),
        "sector": find_column(columns, ["sector", "especialidad", "disciplina"]),
        "cuadrilla": find_column(columns, ["cuadrilla", "crew", "recurso"]),
        "fecha_inicio": find_column(columns, ["fecha inicio", "inicio", "start"]),
        "fecha_fin": find_column(columns, ["fecha fin", "fecha vencimiento", "vencimiento", "fin", "due"]),
        "estado_programa": find_column(columns, ["estado", "status", "estado actual"]),
        "ubicacion_tecnica": find_column(columns, ["ubicacion tecnica", "ubicacion", "ubic tecnica"]),
        "kks_tag": find_column(columns, ["kks tag", "kks-tag", "kks", "tag"]),
    }
    tasks: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        tarea = row_text(row, mapping["tarea"])
        nro_ot = ot_text(row_text(row, mapping["nro_ot"]))
        if not tarea and not nro_ot:
            continue
        start = parse_date(row.get(mapping["fecha_inicio"])) if mapping["fecha_inicio"] else None
        end = parse_date(row.get(mapping["fecha_fin"])) if mapping["fecha_fin"] else None
        cuadrilla = row_text(row, mapping["cuadrilla"])
        inferred_company, inferred_sector = infer_company_sector(cuadrilla)
        empresa = row_text(row, mapping["empresa"]) or inferred_company
        sector = row_text(row, mapping["sector"]) or inferred_sector
        raw = {str(col): (None if pd.isna(row.get(col)) else str(row.get(col))) for col in columns}
        digest = hashlib.sha1(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        tasks.append(
            {
                "row_hash": digest,
                "nro_ot": nro_ot,
                "tarea": tarea,
                "empresa": empresa,
                "sector": sector,
                "cuadrilla": cuadrilla,
                "fecha_inicio": start,
                "fecha_fin": end,
                "duracion": duration_days(start, end),
                "estado_programa": row_text(row, mapping["estado_programa"]),
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
    return sb_get("tasks", {"select": "*", "program_id": f"eq.{program_id}", "order": "fecha_inicio.asc,nro_ot.asc"})


def load_advances(program_id: str) -> list[dict[str, Any]]:
    return sb_get("advances", {"select": "*", "program_id": f"eq.{program_id}", "order": "created_at.desc"})


def admin_panel() -> None:
    if st.session_state.role != "admin":
        return
    with st.expander("Administracion - cargar programa Excel", expanded=False):
        uploaded = st.file_uploader("Excel del programa", type=["xlsx", "xls"])
        program_name = st.text_input("Nombre del programa", value=f"Programa {date.today().isoformat()}")
        replace_active = st.checkbox("Dejar este como unico programa activo", value=True)
        if st.button("Publicar programa", type="primary", disabled=uploaded is None):
            with st.spinner("Importando Excel..."):
                df = pd.read_excel(uploaded)
                tasks = map_excel(df)
                if not tasks:
                    st.error("No encontre tareas validas en el Excel.")
                    return
                if replace_active:
                    for program in list_programs(active_only=True):
                        sb_patch("programs", {"id": f"eq.{program['id']}"}, {"active": False})
                program = sb_insert(
                    "programs",
                    {
                        "name": program_name.strip() or uploaded.name,
                        "source_filename": uploaded.name,
                        "uploaded_by": st.session_state.profile["name"],
                        "active": True,
                    },
                )[0]
                for task in tasks:
                    task["program_id"] = program["id"]
                for start in range(0, len(tasks), 500):
                    sb_insert("tasks", tasks[start : start + 500])
            st.success(f"Programa publicado con {len(tasks)} tarea(s).")
            st.rerun()

        programs = list_programs(active_only=False)
        if programs:
            st.divider()
            selected = st.selectbox("Programa para administrar", programs, format_func=lambda item: item["name"])
            col1, col2 = st.columns(2)
            if col1.button("Activar / mostrar a cuadrillas"):
                sb_patch("programs", {"id": f"eq.{selected['id']}"}, {"active": True})
                st.success("Programa activado.")
                st.rerun()
            if col2.button("Ocultar programa"):
                sb_patch("programs", {"id": f"eq.{selected['id']}"}, {"active": False})
                st.success("Programa ocultado.")
                st.rerun()


def apply_filters(tasks: list[dict[str, Any]], company: str, sector: str, crew: str, start: Any, end: Any, text: str) -> list[dict[str, Any]]:
    output = []
    company = scope_value(company)
    sector = scope_value(sector)
    crew = scope_value(crew)
    start_iso = start.isoformat() if start else ""
    end_iso = end.isoformat() if end else ""
    text_norm = normalize(text)
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
        if crew and normalize_crew(task.get("cuadrilla")) != normalize_crew(crew):
            continue
        task_start = task.get("fecha_inicio") or ""
        if start_iso and task_start and task_start < start_iso:
            continue
        if end_iso and task_start and task_start > end_iso:
            continue
        haystack = normalize(" ".join(str(task.get(key) or "") for key in ["nro_ot", "tarea", "cuadrilla", "ubicacion_tecnica", "kks_tag"]))
        haystack = normalize(f"{haystack} {task_title(task)}")
        if text_norm and text_norm not in haystack:
            continue
        output.append(task)
    return output


def latest_status_by_task(advances: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for advance in sorted(advances, key=lambda item: item.get("created_at", ""), reverse=True):
        if advance["task_id"] not in latest and advance.get("action") != "COMENTARIO":
            latest[advance["task_id"]] = advance
    return latest


def task_dataframe(tasks: list[dict[str, Any]], latest: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for task in tasks:
        advance = latest.get(task["id"], {})
        status = advance.get("action") or task.get("estado_programa") or "SIN AVANCE"
        if status not in STATE_ACTIONS:
            status = "SIN AVANCE"
        display_start = format_date(task.get("fecha_inicio"))
        if status == "EN CURSO" and advance.get("created_at"):
            display_start = advance_date(advance.get("created_at"))
        rows.append(
            {
                "Seleccionar": False,
                "Titulo tarea": task_title(task),
                "Estado": status,
                "Fecha inicio": display_start,
                "Duracion": f"{task.get('duracion') or 1} dia(s)",
                "Cuadrilla": task.get("cuadrilla") or "",
                "OT": ot_text(task.get("nro_ot")),
                "Ubicacion tecnica": task.get("ubicacion_tecnica") or "",
                "KKS/TAG": task.get("kks_tag") or "",
                "_task_id": task["id"],
                "_estado_original": status,
            }
        )
    return pd.DataFrame(rows)


def format_date(value: Any) -> str:
    if not value:
        return ""
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


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
        rows.append(
            {
                "OT": ot_text(task.get("nro_ot")),
                "Titulo tarea": task_title(task),
                "Trabajo": task.get("tarea", ""),
                "Empresa": effective_company(task),
                "Sector": effective_sector(task),
                "Cuadrilla": task.get("cuadrilla", ""),
                "KKS/TAG": task.get("kks_tag", ""),
                "Fecha inicio": format_date(task.get("fecha_inicio")),
                "Duracion": task.get("duracion", ""),
                "Avance": advance.get("action", ""),
                "Motivo": advance.get("reason", ""),
                "Comentarios": advance.get("observation", ""),
                "Fecha avance": advance_date(advance.get("created_at")),
                "Hora avance": advance_time(advance.get("created_at")),
                "Informado por": advance.get("reporter_name", ""),
                "Empresa informante": advance.get("reporter_company", ""),
            }
        )
    return write_excel(rows, sheet_name="Avances")


def advance_date(value: Any) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return str(value)[:10]


def advance_time(value: Any) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%H:%M")
    except Exception:
        return ""


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
            state_col = raw_column_name(row, ["estado", "status", "estado actual"]) or "Estado"
            row[state_col] = advance.get("action", "")

            changed_on = advance_date(advance.get("created_at"))
            if advance.get("action") == "EN CURSO" and changed_on:
                start_col = raw_column_name(row, ["fecha inicio", "inicio", "start"]) or "Fecha inicio"
                row[start_col] = changed_on
            elif advance.get("action") == "COMPLETADO" and changed_on:
                end_col = raw_column_name(row, ["fecha fin", "fecha vencimiento", "vencimiento", "fin", "due"]) or "Fecha fin"
                row[end_col] = changed_on
                start_col = raw_column_name(row, ["fecha inicio", "inicio", "start"]) or "Fecha inicio"
                if not str(row.get(start_col) or "").strip():
                    row[start_col] = changed_on

        if "OT" in row:
            row["OT"] = ot_text(row.get("OT"))
        else:
            nro_col = raw_column_name(row, ["nro ot", "nro de ot", "numero ot", "ot", "orden"])
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


def format_datetime(value: Any) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def main() -> None:
    require_session()
    st.title(APP_TITLE)
    logout_controls()
    admin_panel()

    programs = list_programs(active_only=True)
    if not programs:
        st.info("No hay programas activos. Ingresar como administrador y cargar un Excel.")
        return

    program = st.selectbox("Programa", programs, format_func=lambda item: item["name"], key="program_filter")
    tasks = load_tasks(program["id"])
    advances = load_advances(program["id"])
    latest = latest_status_by_task(advances)

    profile = st.session_state.profile
    company = scope_value(profile.get("company"))
    sector = scope_value(profile.get("sector"))
    scoped_tasks = apply_filters(tasks, company, sector, "", None, None, "")
    crews = [""] + sorted({task.get("cuadrilla") or "" for task in scoped_tasks if task.get("cuadrilla")})

    col1, col2, col3 = st.columns(3)
    crew = col1.selectbox("Cuadrilla", crews, format_func=lambda item: option_label(item, "Todas"), key="crew_filter")
    start = col2.date_input("Fecha inicio", value=None, format="DD/MM/YYYY", key="start_filter")
    end = col3.date_input("Fecha fin", value=None, format="DD/MM/YYYY", key="end_filter")
    text = st.text_input("Buscar", placeholder="OT, trabajo, ubicacion, KKS/TAG", key="text_filter")

    filtered = apply_filters(tasks, company, sector, crew, start, end, text)
    st.caption(f"{len(filtered)} tarea(s) visibles de {len(scoped_tasks)} cargadas para el perfil seleccionado.")
    visible_task_ids = {task["id"] for task in filtered}
    filtered_advances = [advance for advance in advances if advance.get("task_id") in visible_task_ids]

    pending_changes = st.session_state.setdefault("pending_state_changes", {})
    df = task_dataframe(filtered, latest)
    for index, row in df.iterrows():
        task_id = str(row["_task_id"])
        if task_id in pending_changes:
            df.at[index, "Estado"] = pending_changes[task_id]
            df.at[index, "Seleccionar"] = True
            if pending_changes[task_id] == "EN CURSO" and not str(df.at[index, "Fecha inicio"] or "").strip():
                df.at[index, "Fecha inicio"] = date.today().strftime("%d/%m/%Y")

    editor_state = st.session_state.get("task_editor", {})
    if isinstance(editor_state, dict):
        for row_index, changes in editor_state.get("edited_rows", {}).items():
            if "Estado" in changes:
                try:
                    index = int(row_index)
                except Exception:
                    continue
                if 0 <= index < len(df):
                    new_status = str(changes["Estado"] or "")
                    original_status = str(df.at[index, "_estado_original"] or "")
                    df.at[index, "Estado"] = new_status
                    if new_status and new_status != original_status:
                        df.at[index, "Seleccionar"] = True
                        task_id = str(df.at[index, "_task_id"])
                        pending_changes[task_id] = new_status
                        if new_status == "EN CURSO" and not str(df.at[index, "Fecha inicio"] or "").strip():
                            df.at[index, "Fecha inicio"] = date.today().strftime("%d/%m/%Y")
    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        disabled=[column for column in df.columns if column not in {"Seleccionar", "Estado"}],
        column_config={
            "_task_id": None,
            "_estado_original": None,
            "Seleccionar": st.column_config.CheckboxColumn("Sel."),
            "Estado": st.column_config.SelectboxColumn("Estado", options=STATE_ACTIONS, required=True),
        },
        key="task_editor",
    )
    if edited.empty:
        selected_task_ids: list[str] = []
    else:
        for _, row in edited.iterrows():
            task_id = str(row["_task_id"])
            status = str(row["Estado"] or "")
            original_status = str(row["_estado_original"] or "")
            if status and status != original_status:
                pending_changes[task_id] = status
            elif task_id in pending_changes:
                pending_changes.pop(task_id, None)
        selected_task_ids = [str(item) for item in edited.loc[edited["Seleccionar"] == True, "_task_id"].tolist()]
    pending_visible_ids = sorted(task_id for task_id in pending_changes if task_id in visible_task_ids)

    st.subheader("Cambiar estado")
    c1, c2, c3 = st.columns([1, 1, 2])
    action = c1.selectbox("Estado para seleccionadas", STATE_ACTIONS)
    if c2.button("Cambiar estado", disabled=not selected_task_ids, use_container_width=True):
        for task_id in selected_task_ids:
            pending_changes[task_id] = action
        st.session_state.pop("task_editor", None)
        st.rerun()
    entries = [{"task_id": task_id, "action": pending_changes[task_id]} for task_id in pending_visible_ids]
    selected_actions = [entry["action"] for entry in entries]
    reason = ""
    if any(item in REASON_ACTIONS for item in selected_actions):
        reason = c3.selectbox("Motivo", REASONS, format_func=lambda item: option_label(item, "Seleccionar motivo"))
    observation_required = any(item in REASON_ACTIONS for item in selected_actions) and reason == "Otros"
    comment_label = "Comentario comun"
    if observation_required:
        comment_label = "Comentario comun obligatorio"
    observation = st.text_input(
        comment_label,
        placeholder="Opcional. Obligatorio solo si el motivo es Otros. Tambien sirve para agregar comentario a tareas seleccionadas.",
        key="common_comment_text",
    )

    def pending_is_valid() -> bool:
        if any(item in REASON_ACTIONS for item in selected_actions) and not reason:
            st.warning("Elegir motivo para EN ESPERA o REPLANIFICAR.")
            return False
        if observation_required and not observation.strip():
            st.warning("Escribir comentario cuando el motivo es Otros.")
            return False
        return True

    update_col, pending_col = st.columns([1, 4])
    if update_col.button("Actualizar datos", use_container_width=True):
        if pending_visible_ids:
            st.session_state.confirm_refresh = True
        else:
            st.session_state.pop("task_editor", None)
            st.rerun()
    if pending_visible_ids:
        pending_col.caption(f"{len(pending_visible_ids)} avance(s) pendiente(s) de guardar.")

    if st.session_state.get("confirm_refresh"):
        st.warning("Hay avances pendientes sin guardar. Elegi como continuar antes de actualizar datos.")
        r1, r2, r3 = st.columns(3)
        if r1.button("Guardar avances y actualizar", type="primary"):
            if pending_is_valid():
                save_advance_entries(program["id"], entries, reason, observation.strip())
                for task_id in pending_visible_ids:
                    pending_changes.pop(task_id, None)
                st.session_state.pop("task_editor", None)
                st.session_state.pop("confirm_refresh", None)
                st.rerun()
        if r2.button("Actualizar sin guardar"):
            for task_id in pending_visible_ids:
                pending_changes.pop(task_id, None)
            st.session_state.pop("task_editor", None)
            st.session_state.pop("confirm_refresh", None)
            st.rerun()
        if r3.button("Cancelar"):
            st.session_state.pop("confirm_refresh", None)
            st.rerun()

    save_col, comment_col = st.columns([1, 1])
    if save_col.button("Guardar avances", type="primary", disabled=not pending_visible_ids):
        if pending_is_valid():
            save_advance_entries(program["id"], entries, reason, observation.strip())
            for task_id in pending_visible_ids:
                pending_changes.pop(task_id, None)
            st.session_state.pop("task_editor", None)
            st.session_state.pop("confirm_refresh", None)
            st.success(f"{len(pending_visible_ids)} avance(s) guardado(s).")
            st.rerun()

    if comment_col.button("Guardar comentario", disabled=not selected_task_ids or not observation.strip()):
        comment_entries = [{"task_id": task_id, "action": "COMENTARIO"} for task_id in selected_task_ids]
        save_advance_entries(program["id"], comment_entries, "", observation.strip())
        st.session_state.pop("task_editor", None)
        st.success(f"{len(selected_task_ids)} comentario(s) guardado(s).")
        st.rerun()

    st.subheader("Avances / registros")
    tasks_by_id = {task["id"]: task for task in tasks}
    log_rows = [
        {
            "_advance_id": advance.get("id", ""),
            "OT": ot_text(task.get("nro_ot")),
            "Titulo tarea": task_title(task),
            "Fecha modificacion": advance_date(advance.get("created_at")),
            "Hora modificacion": advance_time(advance.get("created_at")),
            "Avance": advance.get("action"),
            "Motivo": advance.get("reason"),
            "Comentario": advance.get("observation"),
            "Informado por": advance.get("reporter_name"),
            "Empresa": effective_company(task),
            "Sector": effective_sector(task),
            "Cuadrilla": task.get("cuadrilla", ""),
            "Ubicacion tecnica": task.get("ubicacion_tecnica", ""),
            "KKS/TAG": task.get("kks_tag", ""),
            "Trabajo": task.get("tarea", ""),
        }
        for advance in filtered_advances
        for task in [tasks_by_id.get(advance["task_id"], {})]
    ]
    log = pd.DataFrame([{key: value for key, value in row.items() if key != "_advance_id"} for row in log_rows])
    st.dataframe(log, hide_index=True, use_container_width=True)

    if st.session_state.role == "admin" and advances:
        with st.expander("Administracion de registros", expanded=False):
            if log_rows:
                delete_df = pd.DataFrame([{**{"Eliminar": False}, **row} for row in log_rows])
                edited_delete = st.data_editor(
                    delete_df,
                    hide_index=True,
                    use_container_width=True,
                    disabled=[column for column in delete_df.columns if column != "Eliminar"],
                    column_config={
                        "_advance_id": None,
                        "Eliminar": st.column_config.CheckboxColumn("Eliminar"),
                    },
                    key="delete_advances_editor",
                )
                selected_delete_ids = (
                    edited_delete.loc[edited_delete["Eliminar"] == True, "_advance_id"].tolist()
                    if not edited_delete.empty
                    else []
                )
            else:
                st.info("No hay registros visibles con los filtros actuales.")
                selected_delete_ids = []
            d1, d2, d3 = st.columns(3)
            if d1.button("Eliminar seleccionados", disabled=not selected_delete_ids):
                delete_advances(selected_delete_ids)
                st.session_state.pop("delete_advances_editor", None)
                st.success(f"{len(selected_delete_ids)} registro(s) eliminado(s).")
                st.rerun()
            if d2.button("Eliminar visibles por filtros", disabled=not filtered_advances):
                delete_advances([advance["id"] for advance in filtered_advances])
                st.session_state.pop("delete_advances_editor", None)
                st.success("Registros visibles eliminados.")
                st.rerun()
            confirm_all = st.checkbox("Confirmo eliminar todos los registros de avances del programa activo")
            if d3.button("Eliminar todo el programa", disabled=not confirm_all):
                delete_advances([advance["id"] for advance in advances])
                st.session_state.pop("delete_advances_editor", None)
                st.success("Registros del programa eliminados.")
                st.rerun()

    e1, e2, e3 = st.columns(3)
    e1.download_button(
        "Exportar log Excel",
        data=advances_export(filtered, filtered_advances, final_only=False),
        file_name=f"avances_{date.today().isoformat()}.xlsx",
    )
    e2.download_button(
        "Exportar estado final Excel",
        data=advances_export(filtered, filtered_advances, final_only=True),
        file_name=f"estado_final_{date.today().isoformat()}.xlsx",
    )
    e3.download_button(
        "Exportar programa actualizado Excel",
        data=program_updated_export(filtered, filtered_advances),
        file_name=f"programa_actualizado_{date.today().isoformat()}.xlsx",
    )


if __name__ == "__main__":
    main()
