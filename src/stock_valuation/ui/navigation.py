from __future__ import annotations

import streamlit as st


def render_navigation() -> None:
    """Render the user-facing navigation.

    Technical diagnostics remain in the repository but are intentionally excluded from the
    normal workflow. The user should move through the analysis, not through provider internals.
    """
    with st.sidebar:
        st.markdown("### Aktienanalyse")
        st.page_link("app.py", label="Übersicht")
        st.page_link("pages/0_Unternehmen.py", label="Unternehmen")
        st.page_link("pages/1_Datenimport.py", label="Finanzdaten")
        st.page_link("pages/2_Manuelle_Daten.py", label="Manuelle Daten")
        st.page_link("pages/4_Kennzahlen.py", label="Kennzahlen")
