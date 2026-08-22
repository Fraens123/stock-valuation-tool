from __future__ import annotations

import streamlit as st

from stock_valuation.knowledge.catalog import get_metric_info


def _display_title(info: dict) -> str:
    title_en = info.get("title_en")
    if title_en:
        return f"{info['title_de']} ({title_en})"
    return info["title_de"]


def metric_heading(metric_id: str) -> None:
    """Render a book-style metric heading and the central explanatory info popover."""
    info = get_metric_info(metric_id)
    if not info:
        st.subheader(metric_id)
        return

    title = _display_title(info)
    left, right = st.columns([12, 1])
    with left:
        st.subheader(title)
    with right:
        with st.popover("ⓘ"):
            st.markdown(f"### {title}")

            st.markdown("**Definition**")
            st.write(info["definition"])

            st.markdown("**Formel im Zielmodell**")
            st.code(info["target_formula"], language=None)

            excel_formula = info.get("excel_formula")
            if excel_formula:
                st.markdown("**Bisherige Excel-Logik**")
                st.code(excel_formula, language=None)

            st.markdown("**Bedeutung**")
            st.write(info["meaning"])

            st.markdown("**Interpretation**")
            st.write(info["interpretation"])

            pitfalls = info.get("pitfalls", [])
            if pitfalls:
                st.markdown("**Darauf achten**")
                for item in pitfalls:
                    st.markdown(f"- {item}")

            related = info.get("related", [])
            if related:
                st.markdown("**Zusammenhang mit**")
                st.write(" · ".join(related))

            chapter = info.get("chapter")
            kindle_page = info.get("kindle_page")
            if chapter and kindle_page:
                st.markdown(
                    f"**Im Buch nachlesen:** Kapitel {chapter}, Kindle-Seite **{kindle_page}**"
                )
            elif chapter:
                st.markdown(f"**Im Buch nachlesen:** Kapitel {chapter}")

            st.caption(f"Methodikstatus: {info.get('status', 'nicht klassifiziert')}")
