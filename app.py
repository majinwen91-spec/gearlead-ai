from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
from docx import Document

from gearlead.config import PROJECT_ROOT, get_settings
from gearlead.database import initialize_database
from gearlead.schemas import WorkflowResult, model_dump_compat
from gearlead.services.evaluation_service import load_evaluation_data, run_evaluation
from gearlead.services.product_service import list_products
from gearlead.tools.crm_writer import list_leads, save_lead_record
from gearlead.workflow import analyze_inquiry


st.set_page_config(
    page_title="GearLead AI",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { color: #18212b; }
    [data-testid="stSidebar"] { border-right: 1px solid #dfe3e8; }
    [data-testid="stSidebar"] h1 { font-size: 1.35rem; letter-spacing: 0; }
    h1, h2, h3 { letter-spacing: 0 !important; }
    h1 { font-size: 2rem !important; }
    h2 { font-size: 1.3rem !important; margin-top: 0.5rem !important; }
    h3 { font-size: 1rem !important; }
    .brand-kicker { color: #087e5b; font-size: .78rem; font-weight: 700; text-transform: uppercase; }
    .status-line { padding: .6rem .75rem; border-left: 3px solid #087e5b; background: #edf7f3; }
    .risk-line { padding: .6rem .75rem; border-left: 3px solid #c74d3b; background: #fff3f0; }
    .draft-banner { padding: .6rem .75rem; border: 1px solid #d7a21e; background: #fff9e8; }
    [data-testid="stMetric"] { background: #fff; border: 1px solid #dfe3e8; padding: .8rem; border-radius: 6px; }
    [data-testid="stDataFrame"] { border: 1px solid #dfe3e8; border-radius: 6px; }
    div.stButton > button { border-radius: 6px; font-weight: 650; }
    div[data-baseweb="select"] > div, textarea, input { border-radius: 6px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


SETTINGS = get_settings()
DB_PATH = initialize_database()


def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".txt":
        return uploaded_file.getvalue().decode("utf-8", errors="replace")
    if suffix == ".docx":
        document = Document(uploaded_file)
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    raise ValueError("Only TXT and DOCX files are supported.")


def current_result() -> WorkflowResult | None:
    return st.session_state.get("analysis_result")


def render_empty_state(message: str = "Analyze an inquiry first to populate this view.") -> None:
    st.info(message)


def metric_row(result: WorkflowResult) -> None:
    columns = st.columns(4)
    columns[0].metric("Lead score", f"{result.lead_score.total}/100")
    columns[1].metric("Priority", result.lead_score.priority)
    columns[2].metric("Completeness", f"{result.completeness_score}%")
    columns[3].metric("Product match", f"{result.product_match.match_score}%")


with st.sidebar:
    st.markdown('<div class="brand-kicker">AI Sales Engineer Assistant</div>', unsafe_allow_html=True)
    st.title("GearLead AI")
    st.caption("Gaming peripherals export inquiry qualification")
    page = st.radio(
        "Workspace",
        [
            "Inquiry Analyzer",
            "Lead Qualification",
            "Product Matching",
            "Follow-up Assistant",
            "CRM Records",
            "Evaluation",
            "About Project",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    if SETTINGS.llm_available:
        st.success(f"LLM enabled: {SETTINGS.openai_model}")
    else:
        st.markdown('<div class="status-line">Demo mode<br><small>Rules and local data are active.</small></div>', unsafe_allow_html=True)
    st.caption("All outputs require salesperson review.")


if page == "Inquiry Analyzer":
    st.title("Inquiry Analyzer")
    st.write("Turn an English B2B inquiry into structured purchasing requirements and a traceable sales decision.")
    sample_rows, _ = load_evaluation_data()
    sample_options = {f"{row['id']} · {row['case_type'].replace('_', ' ').title()}": row["text"] for row in sample_rows}
    col_input, col_reference = st.columns([1.65, 1], gap="large")
    with col_input:
        uploaded = st.file_uploader("Upload inquiry", type=["txt", "docx"], help="TXT and DOCX are supported in this POC.")
        selected_sample = st.selectbox("Load a demo case", ["Write or upload an inquiry", *sample_options.keys()])
        default_text = sample_options.get(selected_sample, "")
        if uploaded:
            try:
                default_text = read_uploaded_file(uploaded)
            except ValueError as exc:
                st.error(str(exc))
        inquiry_text = st.text_area("English inquiry", value=default_text, height=310, placeholder="Paste the buyer's English inquiry here...")
        use_llm = st.toggle("Use configured LLM", value=False, disabled=not SETTINGS.llm_available, help="The rules-only workflow remains available without an API key.")
        analyze_clicked = st.button("Analyze inquiry", type="primary", width="stretch")
    with col_reference:
        st.subheader("Decision scope")
        st.markdown(
            """
            - Extract buyer, product, quantity, market, and customization fields
            - Check missing information and explicit commercial risks
            - Match the top three catalog products
            - Score and route the inquiry
            - Draft a reviewable English reply
            """
        )
        st.subheader("Supported categories")
        category_data = pd.DataFrame(
            {
                "Category": ["Gaming mouse", "Mechanical keyboard", "Gaming headset", "Custom cable", "Custom keycap"],
                "Catalog SKUs": [4, 4, 4, 4, 4],
            }
        )
        st.dataframe(category_data, hide_index=True, width="stretch")
    if analyze_clicked:
        try:
            with st.spinner("Running seven-step qualification workflow..."):
                st.session_state.analysis_result = analyze_inquiry(inquiry_text, use_llm=use_llm, db_path=DB_PATH)
            st.success("Analysis complete. Open the qualification, matching, and follow-up views for details.")
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
    result = current_result()
    if result:
        st.divider()
        metric_row(result)
        left, right = st.columns([1, 1], gap="large")
        with left:
            st.subheader("Extracted request")
            st.json(model_dump_compat(result.inquiry), expanded=2)
        with right:
            st.subheader("Workflow trace")
            trace = pd.DataFrame(
                [{"Tool": name.replace("_", " ").title(), "Status": "Completed" if ok else "Failed"} for name, ok in result.tool_status.items()]
            )
            st.dataframe(trace, hide_index=True, width="stretch")

elif page == "Lead Qualification":
    st.title("Lead Qualification")
    result = current_result()
    if not result:
        render_empty_state()
    else:
        metric_row(result)
        if result.customer_check.manual_review_required:
            st.markdown('<div class="risk-line"><strong>Manual review required.</strong> Verify the risk evidence before sharing commercial terms.</div>', unsafe_allow_html=True)
        left, right = st.columns([1.2, 1], gap="large")
        with left:
            st.subheader("Score breakdown")
            breakdown = model_dump_compat(result.lead_score.breakdown)
            score_frame = pd.DataFrame(
                {"Dimension": [key.replace("_", " ").title() for key in breakdown], "Points": list(breakdown.values())}
            ).set_index("Dimension")
            st.bar_chart(score_frame, horizontal=True, color="#087E5B")
            with st.expander("Scoring evidence"):
                for explanation in result.lead_score.explanations:
                    st.write(explanation)
        with right:
            st.subheader("Missing information")
            if result.missing_fields:
                for field in result.missing_fields:
                    st.write(f"- {field}")
            else:
                st.success("No required qualification fields are missing.")
            st.subheader("Risk evidence")
            if result.customer_check.risk_flags:
                for flag in result.customer_check.risk_flags:
                    st.error(flag)
            else:
                st.success("No explicit risk signal detected by the POC rules.")

elif page == "Product Matching":
    st.title("Product Matching")
    result = current_result()
    if not result:
        render_empty_state()
        with st.expander("Browse the product catalog"):
            st.dataframe(pd.DataFrame(list_products(db_path=DB_PATH)), hide_index=True, width="stretch")
    else:
        match = result.product_match
        header_left, header_right = st.columns([1.4, 1])
        with header_left:
            st.markdown(f"### {match.match_type}")
            st.write(f"Recommended base SKU: **{match.recommended_sku or 'No suitable catalog SKU'}**")
        with header_right:
            st.metric("Best match score", f"{match.match_score}%")
        reason_col, gap_col = st.columns(2, gap="large")
        with reason_col:
            st.subheader("Why it matches")
            for reason in match.reasons or ["No positive catalog evidence was found."]:
                st.write(f"- {reason}")
        with gap_col:
            st.subheader("Gaps and confirmations")
            for gap in match.gaps or ["No catalog gap detected."]:
                st.write(f"- {gap}")
        st.subheader("Top candidates")
        candidate_rows = []
        for candidate in match.candidates:
            candidate_rows.append(
                {
                    "SKU": candidate.sku,
                    "Product": candidate.product_name,
                    "Match": candidate.match_score,
                    "MOQ": candidate.standard_moq,
                    "Lead time (days)": candidate.mass_production_lead_time_days,
                    "Certifications": ", ".join(candidate.certifications),
                    "Open gaps": len(candidate.gaps),
                }
            )
        if candidate_rows:
            st.dataframe(pd.DataFrame(candidate_rows), hide_index=True, width="stretch")
        else:
            st.warning("No candidates were returned because the category or technical requirements were insufficient.")

elif page == "Follow-up Assistant":
    st.title("Follow-up Assistant")
    result = current_result()
    if not result:
        render_empty_state()
    else:
        st.markdown('<div class="draft-banner"><strong>Draft for salesperson review.</strong> Do not send before confirming price, lead time, certification, and customer identity.</div>', unsafe_allow_html=True)
        left, right = st.columns([1, 1.55], gap="large")
        with left:
            st.subheader("Recommended route")
            st.write(result.follow_up.strategy)
            st.subheader("Next action")
            st.write(result.follow_up.next_action)
            st.metric("Suggested follow-up", f"{result.follow_up.suggested_follow_up_days} day(s)")
            st.subheader("Questions to ask")
            for question in result.follow_up.questions or ["No required follow-up question was generated."]:
                st.write(f"- {question}")
        with right:
            st.subheader("English reply draft")
            edited_reply = st.text_area("Review and edit", value=result.reply_draft, height=430, label_visibility="collapsed")
            if edited_reply != result.reply_draft:
                result.reply_draft = edited_reply
                st.session_state.analysis_result = result
            if st.button("Save to CRM", type="primary", width="stretch"):
                lead_id = save_lead_record(result, db_path=DB_PATH)
                st.success(f"Saved as {lead_id}.")

elif page == "CRM Records":
    st.title("CRM Records")
    st.write("Local SQLite records created after salesperson review. No external CRM is connected.")
    leads = list_leads(db_path=DB_PATH)
    if not leads:
        render_empty_state("No CRM record has been saved yet.")
    else:
        frame = pd.DataFrame(leads)
        filters = st.columns([1, 1, 2])
        priorities = ["All", *sorted(frame["priority"].dropna().unique())]
        categories = ["All", *sorted(frame["category"].dropna().unique())]
        priority_filter = filters[0].selectbox("Priority", priorities)
        category_filter = filters[1].selectbox("Category", categories)
        search = filters[2].text_input("Search company or SKU")
        if priority_filter != "All":
            frame = frame[frame["priority"] == priority_filter]
        if category_filter != "All":
            frame = frame[frame["category"] == category_filter]
        if search:
            mask = frame[["customer_name", "recommended_sku"]].fillna("").apply(lambda column: column.str.contains(search, case=False)).any(axis=1)
            frame = frame[mask]
        columns = ["lead_id", "created_at", "customer_name", "country", "category", "requested_quantity", "lead_score", "priority", "match_type", "recommended_sku", "next_action"]
        st.dataframe(frame[columns], hide_index=True, width="stretch")

elif page == "Evaluation":
    st.title("POC Evaluation")
    st.write("Run the deterministic workflow against 25 manually labeled synthetic inquiries. Results measure this bounded test set, not production accuracy.")
    if st.button("Run evaluation", type="primary") or "evaluation_report" in st.session_state:
        if "evaluation_report" not in st.session_state:
            with st.spinner("Evaluating 25 inquiries..."):
                st.session_state.evaluation_report = run_evaluation(db_path=DB_PATH)
        report = st.session_state.evaluation_report
        st.caption(f"Dataset: {report.total_cases} synthetic inquiries across five product categories")
        metrics = report.metrics()
        columns = st.columns(3)
        for index, (label, value) in enumerate(metrics.items()):
            columns[index % 3].metric(label, f"{value:.1f}%")
        st.subheader("Case-level audit")
        result_frame = pd.DataFrame(report.case_results)
        st.dataframe(result_frame, hide_index=True, width="stretch")
        failures = result_frame[(~result_frame["product_ok"]) | (~result_frame["priority_ok"]) | (result_frame["error"] != "")]
        st.subheader("Error cases")
        if failures.empty:
            st.success("No product or priority error occurred on the current controlled set.")
        else:
            st.dataframe(failures, hide_index=True, width="stretch")

elif page == "About Project":
    st.title("About GearLead AI")
    st.write("A portfolio POC that models the first-response workflow of an export salesperson and sales engineer for gaming peripherals.")
    image_path = PROJECT_ROOT / "assets" / "gearlead_catalog.png"
    if image_path.exists():
        st.image(str(image_path), width="stretch")
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Architecture principle")
        st.markdown(
            """
            - LLM: optional language understanding and reply polishing
            - Rules: lead scoring, risk routing, and decision thresholds
            - SQLite: product catalog, customer history, and CRM records
            - Human review: final commercial judgment and email approval
            """
        )
        st.subheader("Agent tools")
        st.code("extract -> validate -> check -> match -> score -> route -> draft -> save", language="text")
    with right:
        st.subheader("Explicit boundaries")
        st.markdown(
            """
            - No automatic email sending
            - No final price or delivery commitment
            - No real credit, sanctions, or trade-compliance decision
            - No claim that synthetic POC metrics represent production accuracy
            """
        )
        st.subheader("Compliance notice")
        st.info("This project is a portfolio demo for AI solution design. It does not provide legal, financial, trade compliance, or credit risk advice. All generated replies are drafts for salesperson review.")
