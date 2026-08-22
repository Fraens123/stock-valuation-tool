from __future__ import annotations

import streamlit as st

from stock_valuation.knowledge.catalog import get_metric_info


def metric_heading(metric_id: str) -> None:
    info = get_metric_info(metric_id)
    if not info:
        st.subheader(metric_id)
        return

    left, right = st.columns([12, 1])
    with left:
        st.subheader(f"{info['title_de']} ({info['title_en']})")
    with right:
        with st.popover("ⓘ"):
            st.markdown(f"### {info['title_de']} ({info['title_en']})")
            st.markdown("**Definition**")
            st.write(info["definition"])
            st.markdown("**Formel**")
            st.code(info["formula"], language=None)
            st.markdown("**Bedeutung**")
            st.write(info["meaning"])
            st.markdown("**Interpretation**")
            st.write(info["interpretation"])
            st.markdown("**Darauf achten**")
            for item in info.get("pitfalls", []):
                st.markdown(f"- {item}")
            related = info.get("related", [])
            if related:
                st.markdown("**Zusammenhang mit**")
                st.write(" · ".join(related))
            st.markdown(
                f"**Im Buch nachlesen:** Kapitel {info['chapter']}, Kindle-Seite **{info['kindle_page']}**"
            )
