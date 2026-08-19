from __future__ import annotations

import streamlit as st

from ..config import APP_TITLE


def hide_streamlit_chrome() -> None:
    st.markdown(
        """
        <style>
        :root {
            --pe-gap: 0.45rem;
        }
        #MainMenu,
        footer,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stHeaderActionElements"],
        [data-testid="stStatusWidget"],
        [data-testid="stLogo"],
        [data-testid="stAppDeployButton"],
        [data-testid="stAppCreatorAvatar"],
        [data-testid="stAppCreatorBadge"],
        [data-testid="stViewerBadge"],
        .stDeployButton,
        .viewerBadge_container__1QSob,
        [class*="viewerBadge"],
        [class*="ViewerBadge"],
        [class*="hostedWithStreamlit"],
        [class*="HostedWithStreamlit"],
        [class*="creatorAvatar"],
        [class*="CreatorAvatar"],
        a[href*="streamlit.io"],
        a[href*="github.com/lucasmandagaran/programacion-energia-excel"] {
            display: none !important;
            visibility: hidden !important;
        }
        header {
            height: 0 !important;
            min-height: 0 !important;
            background: transparent !important;
        }
        .block-container {
            padding-top: 1.05rem !important;
            padding-bottom: 1rem !important;
            max-width: 100% !important;
        }
        h1 {
            font-size: clamp(1.75rem, 3.4vw, 2.55rem) !important;
            line-height: 1.05 !important;
            margin-bottom: 0.2rem !important;
        }
        h2, h3 {
            margin-top: 0.45rem !important;
            margin-bottom: 0.35rem !important;
        }
        [data-testid="stVerticalBlock"] {
            gap: var(--pe-gap) !important;
        }
        [data-testid="stHorizontalBlock"] {
            gap: 0.55rem !important;
        }
        [data-testid="stExpander"] {
            margin-bottom: 0.35rem !important;
        }
        [data-testid="stDataFrame"] {
            margin-top: 0.15rem !important;
        }
        [data-testid="stDataFrame"] div[role="row"]:hover,
        [data-testid="stDataFrame"] div[role="gridcell"]:hover {
            filter: brightness(1.05) !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            min-height: 2.25rem !important;
            padding-top: 0.35rem !important;
            padding-bottom: 0.35rem !important;
        }
        .stTextInput input,
        .stSelectbox div[data-baseweb="select"],
        .stMultiSelect div[data-baseweb="select"],
        .stDateInput input {
            min-height: 2.25rem !important;
        }
        .pe-header {
            margin: 0 0 0.25rem 0;
        }
        .pe-header h1 {
            margin: 0 !important;
        }
        .pe-subtitle {
            margin: 0.05rem 0 0.35rem 0;
            color: rgba(250, 250, 250, 0.68);
            font-size: 0.88rem;
        }
        @media (max-width: 760px) {
            .block-container {
                padding-left: 0.55rem !important;
                padding-right: 0.55rem !important;
                padding-top: 0.55rem !important;
            }
            h1 {
                font-size: 1.65rem !important;
            }
            .stCaptionContainer,
            [data-testid="stCaptionContainer"] {
                font-size: 0.78rem !important;
            }
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def app_header(subtitle: str = "") -> None:
    subtitle_html = f'<div class="pe-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="pe-header">
            <h1>{APP_TITLE}</h1>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
