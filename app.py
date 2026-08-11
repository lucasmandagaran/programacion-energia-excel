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
ACTIONS = ["EN CURSO", "EN ESPERA", "COMPLETADO", "REPLANIFICAR", "SIN AVANCE", "COMENTARIO"]
WAIT_REASONS = [
    "Pedido Sup PAE",
    "Por factor climatico",
    "Por falta de equipo/recursos/materiales",
    "Cuadrilla no operativa",
    "Otros",
]


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
        company = st.selectbox("Empresa", COMPANIES, index=0)
        sector = st.selectbox("Sector", SECTORS, index=0)
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
        nro_ot = row_text(row, mapping["nro_ot"])
        if not tarea and not nro_ot:
            continue
        start = parse_date(row.get(mapping["fecha_inicio"])) if mapping["fecha_inicio"] else None
        end = parse_date(row.get(mapping["fecha_fin"])) if mapping["fecha_fin"] else None
        raw = {str(col): (None if pd.isna(row.get(col)) else str(row.get(col))) for col in columns}
        digest = hashlib.sha1(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        tasks.append(
            {
                "row_hash": digest,
                "nro_ot": nro_ot,
                "tarea": tarea,
                "empresa": row_text(row, mapping["empresa"]),
                "sector": row_text(row, mapping["sector"]),
                "cuadrilla": row_text(row, mapping["cuadrilla"]),
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
    start_iso = start.isoformat() if start else ""
    end_iso = end.isoformat() if end else ""
    text_norm = normalize(text)
    for task in tasks:
        if company and normalize(task.get("empresa")) != normalize(company):
            continue
        if sector and normalize(task.get("sector")) != normalize(sector):
            continue
        if crew and task.get("cuadrilla") != crew:
            continue
        task_start = task.get("fecha_inicio") or ""
        if start_iso and task_start and task_start < start_iso:
            continue
        if end_iso and task_start and task_start > end_iso:
            continue
        haystack = normalize(" ".join(str(task.get(key) or "") for key in ["nro_ot", "tarea", "cuadrilla", "ubicacion_tecnica", "kks_tag"]))
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
        rows.append(
            {
                "Seleccionar": False,
                "Trabajo": task.get("tarea") or "",
                "Fecha inicio": format_date(task.get("fecha_inicio")),
                "Duracion": f"{task.get('duracion') or 1} dia(s)",
                "Estado": advance.get("action") or task.get("estado_programa") or "SIN AVANCE",
                "Cuadrilla": task.get("cuadrilla") or "",
                "OT": task.get("nro_ot") or "",
                "Ubicacion tecnica": task.get("ubicacion_tecnica") or "",
                "KKS/TAG": task.get("kks_tag") or "",
                "_task_id": task["id"],
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
                "OT": task.get("nro_ot", ""),
                "Trabajo": task.get("tarea", ""),
                "Empresa": task.get("empresa", ""),
                "Sector": task.get("sector", ""),
                "Cuadrilla": task.get("cuadrilla", ""),
                "KKS/TAG": task.get("kks_tag", ""),
                "Fecha inicio": format_date(task.get("fecha_inicio")),
                "Duracion": task.get("duracion", ""),
                "Avance": advance.get("action", ""),
                "Motivo": advance.get("reason", ""),
                "Comentarios": advance.get("observation", ""),
                "Fecha avance": format_datetime(advance.get("created_at")),
                "Informado por": advance.get("reporter_name", ""),
                "Empresa informante": advance.get("reporter_company", ""),
            }
        )
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    return buffer.getvalue()


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

    program = st.selectbox("Programa", programs, format_func=lambda item: item["name"])
    tasks = load_tasks(program["id"])
    advances = load_advances(program["id"])
    latest = latest_status_by_task(advances)

    profile = st.session_state.profile
    companies = [""] + sorted({task.get("empresa") or "" for task in tasks if task.get("empresa")})
    sectors = [""] + sorted({task.get("sector") or "" for task in tasks if task.get("sector")})
    crews = [""] + sorted({task.get("cuadrilla") or "" for task in tasks if task.get("cuadrilla")})

    col1, col2, col3, col4, col5 = st.columns(5)
    company = col1.selectbox("Empresa", companies, index=companies.index(profile.get("company")) if profile.get("company") in companies else 0)
    sector = col2.selectbox("Sector", sectors, index=sectors.index(profile.get("sector")) if profile.get("sector") in sectors else 0)
    crew = col3.selectbox("Cuadrilla", crews)
    start = col4.date_input("Fecha inicio", value=None, format="DD/MM/YYYY")
    end = col5.date_input("Fecha fin", value=None, format="DD/MM/YYYY")
    text = st.text_input("Buscar", placeholder="OT, trabajo, ubicacion, KKS/TAG")

    filtered = apply_filters(tasks, company, sector, crew, start, end, text)
    st.caption(f"{len(filtered)} tarea(s) visibles de {len(tasks)} cargadas.")

    df = task_dataframe(filtered, latest)
    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        disabled=[column for column in df.columns if column != "Seleccionar"],
        column_config={"_task_id": None, "Seleccionar": st.column_config.CheckboxColumn("Sel.")},
        key="task_editor",
    )
    selected_ids = edited.loc[edited["Seleccionar"] == True, "_task_id"].tolist() if not edited.empty else []

    st.subheader("Informar seleccionadas")
    c1, c2, c3 = st.columns([1, 1, 2])
    action = c1.selectbox("Avance", ACTIONS)
    reason = ""
    if action == "EN ESPERA":
        reason = c2.selectbox("Motivo", WAIT_REASONS)
    observation_required = action in {"REPLANIFICAR", "COMENTARIO"} or action == "EN ESPERA"
    observation = c3.text_input(
        "Comentario comun" if observation_required else "Comentario opcional",
        placeholder="Se aplicara a todas las tareas seleccionadas",
    )
    if st.button("Guardar avance para seleccionadas", type="primary", disabled=not selected_ids):
        if action == "EN ESPERA" and not reason:
            st.warning("Elegir motivo para EN ESPERA.")
        elif observation_required and not observation.strip():
            st.warning("Escribir el comentario comun para las tareas seleccionadas.")
        else:
            save_advances(program["id"], selected_ids, action, reason, observation.strip())
            st.success(f"{len(selected_ids)} avance(s) guardado(s).")
            st.rerun()

    st.subheader("Avances / registros")
    log = pd.DataFrame(
        [
            {
                "Fecha": format_datetime(advance.get("created_at")),
                "Avance": advance.get("action"),
                "Motivo": advance.get("reason"),
                "Comentario": advance.get("observation"),
                "Informado por": advance.get("reporter_name"),
                "OT": next((task.get("nro_ot") for task in tasks if task["id"] == advance["task_id"]), ""),
                "Trabajo": next((task.get("tarea") for task in tasks if task["id"] == advance["task_id"]), ""),
            }
            for advance in advances
        ]
    )
    st.dataframe(log, hide_index=True, use_container_width=True)

    e1, e2 = st.columns(2)
    e1.download_button(
        "Exportar log Excel",
        data=advances_export(tasks, advances, final_only=False),
        file_name=f"avances_{date.today().isoformat()}.xlsx",
    )
    e2.download_button(
        "Exportar estado final Excel",
        data=advances_export(tasks, advances, final_only=True),
        file_name=f"estado_final_{date.today().isoformat()}.xlsx",
    )


if __name__ == "__main__":
    main()
