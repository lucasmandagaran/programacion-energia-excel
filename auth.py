from __future__ import annotations

import streamlit as st

from ..config import ACCESS_PASSWORD, ADMIN_PASSWORD, AREAS, COMPANIES_BY_AREA, SECTORS_BY_AREA
from ..textutils import option_label
from .styles import app_header


def login_screen() -> None:
    app_header("Trabajos programados")
    with st.form("login_form"):
        mode = st.radio("Modo de ingreso", ["Cuadrilla / contratista", "Administrador"], horizontal=True)
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar", type="primary")
    if submitted:
        if mode.startswith("Administrador"):
            if password == ADMIN_PASSWORD:
                st.session_state.role = "admin"
                st.rerun()
            st.error("Clave administradora incorrecta.")
        else:
            if password == ACCESS_PASSWORD:
                st.session_state.role = "user"
                st.rerun()
            st.error("Contraseña incorrecta.")
    st.stop()


def profile_screen() -> None:
    app_header("Ingreso al programa")
    area = st.selectbox("Area", AREAS, index=0, key="profile_area_select")
    company_options = COMPANIES_BY_AREA[area]
    sector_options = SECTORS_BY_AREA[area]
    is_admin = st.session_state.get("role") == "admin"
    with st.form("profile_form"):
        admin_view = "Programa de tareas"
        if is_admin:
            admin_view = st.radio(
                "Ingresar a",
                ["Programa de tareas", "Avances / registros"],
                horizontal=True,
            )
        company = st.selectbox(
            "Empresa",
            company_options,
            index=0,
            format_func=lambda item: option_label(item, "Todas"),
            key=f"profile_company_{area}",
        )
        sector = st.selectbox(
            "Sector",
            sector_options,
            index=0,
            format_func=lambda item: option_label(item, "Todos"),
            key=f"profile_sector_{area}",
        )
        name_label = "Nombre" if not is_admin else "Nombre (opcional)"
        name = st.text_input(name_label, placeholder="Nombre y apellido / rol")
        if st.form_submit_button("Ingresar", type="primary"):
            if not is_admin and not name.strip():
                st.warning("Ingresar nombre de usuario.")
                st.stop()
            display_name = name.strip() or "Administrador"
            st.session_state.profile = {
                "area": area,
                "company": company,
                "sector": sector,
                "name": display_name,
                "admin_view": admin_view,
            }
            st.rerun()
    st.stop()


def require_session() -> None:
    if "role" not in st.session_state:
        login_screen()
    if "profile" not in st.session_state:
        profile_screen()
