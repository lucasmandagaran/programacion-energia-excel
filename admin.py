from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from ..config import AREAS
from ..data import duration_days, list_programs, load_tasks, map_excel, ot_text, task_title
from ..supabase_client import sb_insert, sb_patch
from ..textutils import canonical_company, canonical_sector, current_area, infer_company_sector, normalize, option_label, program_area
from ..timeutil import local_today


def admin_panel() -> None:
    if st.session_state.role != "admin":
        return
    with st.expander("Administracion - cargar programa Excel", expanded=False):
        default_area = current_area()
        upload_area = st.selectbox("Area del programa", AREAS, index=AREAS.index(default_area))
        uploaded = st.file_uploader("Excel del programa", type=["xlsx", "xls"])
        program_name = st.text_input("Nombre del programa", value=f"Programa {local_today().isoformat()}")
        replace_active = st.checkbox("Dejar este como unico programa activo", value=True)
        if st.button("Publicar programa", type="primary", disabled=uploaded is None):
            with st.spinner("Importando Excel..."):
                df = pd.read_excel(uploaded)
                tasks = map_excel(df, upload_area)
                if not tasks:
                    st.error("No encontre tareas validas en el Excel.")
                    return
                if replace_active:
                    for program in list_programs(active_only=True):
                        if program_area(program) == upload_area:
                            sb_patch("programs", {"id": f"eq.{program['id']}"}, {"active": False})
                program = sb_insert(
                    "programs",
                    {
                        "name": program_name.strip() or uploaded.name,
                        "area": upload_area,
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
            selected = st.selectbox(
                "Programa para administrar",
                programs,
                format_func=lambda item: f"{program_area(item)} - {item['name']}",
            )
            col1, col2 = st.columns(2)
            if col1.button("Activar / mostrar a cuadrillas"):
                sb_patch("programs", {"id": f"eq.{selected['id']}"}, {"active": True})
                st.success("Programa activado.")
                st.rerun()
            if col2.button("Ocultar programa"):
                sb_patch("programs", {"id": f"eq.{selected['id']}"}, {"active": False})
                st.success("Programa ocultado.")
                st.rerun()

            st.divider()
            st.subheader("Agregar tarea manual al programa")
            st.caption(
                "Permite incorporar una tarea nueva sin volver a importar el Excel. "
                "La tarea queda vinculada al programa activo que elijas."
            )

            active_manual_programs = [
                program
                for program in list_programs(active_only=True)
                if program_area(program) == current_area()
            ]

            if not active_manual_programs:
                st.info("No hay programas activos disponibles para agregar una tarea manual.")
            else:
                current_program_id = ""
                current_program_value = st.session_state.get("program_filter")
                if isinstance(current_program_value, dict):
                    current_program_id = str(current_program_value.get("id") or "")

                manual_program_index = next(
                    (
                        idx
                        for idx, item in enumerate(active_manual_programs)
                        if str(item.get("id") or "") == current_program_id
                    ),
                    0,
                )

                manual_program = st.selectbox(
                    "Programa activo donde se agregara la tarea",
                    active_manual_programs,
                    index=manual_program_index,
                    format_func=lambda item: f"{program_area(item)} - {item['name']}",
                    key="manual_task_program",
                )

                manual_area = program_area(manual_program)
                existing_tasks = load_tasks(str(manual_program["id"]))

                existing_crews = sorted(
                    {
                        str(task.get("cuadrilla") or "").strip()
                        for task in existing_tasks
                        if str(task.get("cuadrilla") or "").strip()
                    }
                )

                st.info(
                    f"Destino seleccionado: {manual_area} / Programa: {manual_program['name']}"
                )

                with st.form("manual_task_form", clear_on_submit=True):
                    manual_description = st.text_input("Descripcion de la tarea *")

                    date_col1, date_col2 = st.columns(2)
                    manual_start = date_col1.date_input(
                        "Fecha inicio *",
                        value=local_today(),
                        format="DD/MM/YYYY",
                    )
                    manual_end = date_col2.date_input(
                        "Fecha fin *",
                        value=local_today(),
                        format="DD/MM/YYYY",
                    )

                    crew_col1, crew_col2 = st.columns([1.0, 1.25])
                    suggested_crew = crew_col1.selectbox(
                        "Cuadrilla existente",
                        [""] + existing_crews,
                        format_func=lambda item: option_label(item, "Elegir / escribir nueva"),
                    )
                    manual_crew = crew_col2.text_input(
                        "Cuadrilla",
                        placeholder="Ej.: 555, 556A, 720",
                    )

                    ot_col, pte_col = st.columns(2)
                    manual_ot = ot_col.text_input("OT *", placeholder="Numero de OT")
                    manual_pte = pte_col.text_input("PTE", placeholder="PTE")

                    location_col, kks_col = st.columns([1.6, 1.0])
                    manual_location = location_col.text_input(
                        "Ubicacion tecnica",
                        placeholder="Ubicacion tecnica",
                    )
                    manual_kks = kks_col.text_input(
                        "KKS-TAG",
                        placeholder="KKS / TAG",
                    )

                    manual_submit = st.form_submit_button(
                        "Agregar tarea al programa",
                        type="primary",
                        use_container_width=True,
                    )

                if manual_submit:
                    description = manual_description.strip()
                    crew_value = manual_crew.strip() or suggested_crew.strip()
                    ot_value = ot_text(manual_ot)

                    if not description:
                        st.error("Completar la descripcion de la tarea.")
                    elif not crew_value:
                        st.error("Completar o elegir la cuadrilla.")
                    elif not ot_value:
                        st.error("Completar la OT.")
                    elif manual_end < manual_start:
                        st.error("La fecha fin no puede ser anterior a la fecha inicio.")
                    else:
                        duplicate = next(
                            (
                                task
                                for task in existing_tasks
                                if normalize(ot_text(task.get("nro_ot"))) == normalize(ot_value)
                            ),
                            None,
                        )

                        if duplicate:
                            st.error(
                                "Esa OT ya existe en el programa seleccionado. "
                                f"Cuadrilla: {duplicate.get('cuadrilla') or '-'} / "
                                f"Tarea: {task_title(duplicate) or '-'}"
                            )
                        else:
                            inferred_company, inferred_sector = infer_company_sector(
                                crew_value,
                                manual_area,
                            )

                            profile = st.session_state.get("profile", {})
                            manual_company = inferred_company or canonical_company(
                                profile.get("company")
                            )
                            manual_sector = inferred_sector or canonical_sector(
                                profile.get("sector")
                            )

                            positions = []
                            for task in existing_tasks:
                                raw = task.get("raw") or {}
                                if not isinstance(raw, dict):
                                    continue
                                try:
                                    positions.append(int(raw.get("_posicion_excel")))
                                except (TypeError, ValueError):
                                    pass
                            next_position = (
                                max(positions) + 1 if positions else len(existing_tasks)
                            )

                            manual_raw = {
                                "_origen": "MANUAL",
                                "_posicion_excel": next_position,
                                "PTE": manual_pte.strip(),
                                "Descripcion": description,
                                "OT": ot_value,
                                "Cuadrilla": crew_value,
                                "Fecha inicio": manual_start.isoformat(),
                                "Fecha fin": manual_end.isoformat(),
                                "Ubicacion tecnica": manual_location.strip(),
                                "KKS-TAG": manual_kks.strip(),
                            }

                            digest_source = {
                                "program_id": str(manual_program["id"]),
                                "manual": manual_raw,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            }
                            digest = hashlib.sha1(
                                json.dumps(
                                    digest_source,
                                    sort_keys=True,
                                    ensure_ascii=False,
                                ).encode("utf-8")
                            ).hexdigest()

                            task_row = {
                                "program_id": str(manual_program["id"]),
                                "area": manual_area,
                                "row_hash": digest,
                                "nro_ot": ot_value,
                                "tarea": description,
                                "empresa": manual_company,
                                "sector": manual_sector,
                                "cuadrilla": crew_value,
                                "fecha_inicio": manual_start.isoformat(),
                                "fecha_fin": manual_end.isoformat(),
                                "duracion": duration_days(
                                    manual_start.isoformat(),
                                    manual_end.isoformat(),
                                ),
                                "estado_programa": "SIN AVANCE",
                                "ubicacion_tecnica": manual_location.strip(),
                                "kks_tag": manual_kks.strip(),
                                "raw": manual_raw,
                            }

                            sb_insert("tasks", task_row)

                            company_label = manual_company or "Sin empresa detectada"
                            sector_label = manual_sector or "Sin sector detectado"
                            st.success(
                                f"OT {ot_value} agregada correctamente a "
                                f"{manual_program['name']} / {manual_area} / "
                                f"{company_label} / {sector_label} / Cuadrilla {crew_value}."
                            )
                            st.rerun()
