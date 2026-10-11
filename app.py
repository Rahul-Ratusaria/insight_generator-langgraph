"""Run with: python -m streamlit run app.py"""
import tempfile
from pathlib import Path
import pandas as pd
import streamlit as st
from insight_generator.service import run_job
from insight_generator.export import to_excel, to_markdown

st.set_page_config(page_title="InsightForge | PDF Analytics", page_icon="📈", layout="wide")
st.title("📈 InsightForge")
st.caption("Evidence-grounded PDF analytics · Auditable KPI calculations · LangGraph review routing · SQLite caching")
with st.sidebar:
    st.header("Pipeline settings")
    provider = st.selectbox("Processing mode", ["demo", "openai"], help="Demo is free. OpenAI needs an API key and incurs usage charges.")
    model = st.text_input("OpenAI model", "gpt-4o-mini", disabled=provider == "demo")
    start = st.number_input("First page", min_value=1, value=1)
    end = st.number_input("Last page (0 = all)", min_value=0, value=0)
    force = st.checkbox("Reprocess cached pages", value=False)
    st.info("Calculated comparisons use only supported source numbers. Missing targets are not invented.")
upload = st.file_uploader("Upload an analytical PDF", type="pdf")
if upload and st.button("Analyze report", type="primary"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as fp:
        fp.write(upload.getbuffer())
        filename = Path(fp.name)
    try:
        with st.spinner("Extracting, validating and calculating..."):
            st.session_state["job"] = run_job(filename, provider=provider, model=model, start=int(start), end=int(end) or None, force=force)
    except Exception as exc:
        st.error(f"Processing failed: {exc}")
    finally:
        filename.unlink(missing_ok=True)
if "job" in st.session_state:
    job = st.session_state["job"]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Pages analyzed",len(job.pages))
    c2.metric("Verified observations",sum(len(p.insights) for p in job.pages))
    c3.metric("Calculated insights",len(job.analytical_insights))
    c4.metric("Pages for review",len(job.review_pages))
    t1,t2,t3,t4 = st.tabs(["Executive intelligence", "Metrics explorer", "Evidence & QA", "Export"])
    with t1:
        st.subheader("Evidence-backed analytical findings")
        if not job.analytical_insights:
            st.info("No safe numeric comparisons were identified. Source observations remain available under Evidence & QA.")
        for finding in job.analytical_insights:
            with st.container(border=True):
                st.markdown(f"### {finding.title}")
                st.write(finding.observation)
                st.markdown(f"**Business next step:** {finding.implication}")
                st.code(finding.calculation, language=None)
                for ev in finding.evidence:
                    st.caption(f"Page {ev.page} · {ev.quote}")
                st.caption(f"Assumption: {finding.caveat}")
        with st.expander("Full executive narrative"):
            st.text(job.executive_summary)
    with t2:
        if job.metrics:
            frame = pd.DataFrame([m.model_dump() for m in job.metrics])
            st.dataframe(frame, use_container_width=True, hide_index=True)
            numeric = frame[(frame.key.str.startswith("revenue_")) | (frame.key.str.endswith("_revenue"))]
            if not numeric.empty:
                st.bar_chart(numeric.set_index("label")["value"])
        else:
            st.info("No supported KPI patterns found in accepted pages.")
    with t3:
        for page in job.pages:
            with st.expander(f"Page {page.page} · {page.status.upper()} · {len(page.insights)} verified observations"):
                for item in page.insights:
                    st.markdown(f"**Observation:** {item.observation}")
                    st.caption(" | ".join(f"Source p.{e.page}: {e.quote}" for e in item.evidence))
                for issue in page.issues:
                    st.warning(issue)
        if job.review_pages:
            st.warning("Review pages: " + ", ".join(str(p) for p in job.review_pages))
    with t4:
        st.download_button("Download complete JSON",job.model_dump_json(indent=2),file_name="insightforge_report.json",mime="application/json")
        st.download_button("Download Markdown report",to_markdown(job),file_name="insightforge_report.md",mime="text/markdown")
        st.download_button("Download Excel workbook",to_excel(job),file_name="insightforge_report.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
