from __future__ import annotations

from pe import config  # noqa: F401  (side effect: st.set_page_config + secrets)
from pe.ui.styles import hide_streamlit_chrome
from pe.ui.main_view import main

hide_streamlit_chrome()


if __name__ == "__main__":
    main()
