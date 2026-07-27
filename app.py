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

PRIORITY_LABELS = {"High": "高", "Medium": "中", "Low": "低", "Risk Review": "风险复核"}
MATCH_TYPE_LABELS = {
    "Standard SKU Match": "标准SKU匹配",
    "Standard SKU + Light Customization": "标准SKU + 轻度定制",
    "ODM Feasibility Review": "ODM可行性评估",
    "No Suitable Match": "无合适产品",
}
STRATEGY_LABELS = {
    "High-priority quotation preparation": "高优先级报价准备",
    "Request missing information": "补充关键信息",
    "Nurture and continue qualification": "持续培育与资格确认",
    "Manual risk review": "人工风险复核",
}
CATEGORY_LABELS = {
    "gaming_mouse": "电竞鼠标",
    "mechanical_keyboard": "机械键盘",
    "gaming_headset": "电竞耳机",
    "custom_cable": "客制化线材",
    "custom_keycap": "客制化键帽",
    "unknown": "未知品类",
}
CASE_TYPE_LABELS = {
    "complete_high_value": "完整高价值",
    "incomplete_high_value": "信息不完整但价值较高",
    "odm": "ODM定制",
    "low_quality": "低质量",
    "risk": "风险",
}
SCORE_LABELS = {
    "customer_credibility": "客户可信度",
    "requirement_clarity": "需求明确度",
    "moq_fit": "MOQ匹配度",
    "feasibility": "产品可行性",
    "commercial_value": "商业价值",
    "urgency": "采购紧迫度",
}
MISSING_FIELD_LABELS = {
    "Customer company name": "客户公司名称",
    "Customer country": "客户所在国家",
    "Customer type": "客户类型",
    "Requested quantity": "采购数量",
    "Target market": "目标市场",
    "Required delivery date": "期望交付日期",
    "Connection type": "连接方式",
    "Sensor model": "传感器型号",
    "Polling rate": "回报率",
    "Maximum mouse weight": "鼠标最大重量",
    "Keyboard/keycap layout": "键盘或键帽布局",
    "Hot-swap requirement": "热插拔要求",
    "Language layout": "语言布局",
    "Platform compatibility": "平台兼容性",
    "Microphone type": "麦克风类型",
    "Minimum battery life": "最低续航",
    "Cable form": "线材形式",
    "Connector A": "接口A",
    "Connector B": "接口B",
    "Aviator connector": "航插类型",
    "Keycap material": "键帽材质",
    "Manufacturing method": "制造工艺",
    "Keycap profile": "键帽高度",
}
TOOL_LABELS = {
    "extract_inquiry_fields": "提取询盘字段",
    "check_missing_fields": "检查缺失信息",
    "check_customer_profile": "检查客户与风险",
    "match_product_catalog": "匹配产品目录",
    "calculate_lead_score": "计算线索得分",
    "select_follow_up_strategy": "选择跟进策略",
    "generate_reply_draft": "生成回复草稿",
}
EVALUATION_LABELS = {
    "Field Extraction Accuracy": "基础字段提取准确率",
    "Product Match Accuracy": "产品匹配准确率",
    "Priority Classification Accuracy": "优先级分类准确率",
    "Missing Field Recall": "缺失字段召回率",
    "Tool Call Success Rate": "工作流步骤成功率",
    "Response Completeness": "回复格式完整率",
}


def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".txt":
        return uploaded_file.getvalue().decode("utf-8", errors="replace")
    if suffix == ".docx":
        document = Document(uploaded_file)
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    raise ValueError("仅支持TXT和DOCX文件。")


def current_result() -> WorkflowResult | None:
    return st.session_state.get("analysis_result")


def render_empty_state(message: str = "请先分析一封询盘，再查看此页面。") -> None:
    st.info(message)


def metric_row(result: WorkflowResult) -> None:
    columns = st.columns(4)
    columns[0].metric("线索得分", f"{result.lead_score.total}/100")
    columns[1].metric("优先级", PRIORITY_LABELS.get(result.lead_score.priority, result.lead_score.priority))
    columns[2].metric("信息完整度", f"{result.completeness_score}%")
    columns[3].metric("产品匹配度", f"{result.product_match.match_score}%")


with st.sidebar:
    st.markdown('<div class="brand-kicker">AI销售工程师助手</div>', unsafe_allow_html=True)
    st.title("GearLead AI")
    st.caption("电竞外设出口询盘资格评估与产品匹配")
    page = st.radio(
        "工作区",
        [
            "询盘分析",
            "线索评估",
            "产品匹配",
            "跟进助手",
            "CRM记录",
            "POC评估",
            "项目说明",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    if SETTINGS.llm_available:
        st.success(f"大模型已启用：{SETTINGS.openai_model}")
    else:
        st.markdown('<div class="status-line">演示模式<br><small>当前使用本地规则和模拟数据。</small></div>', unsafe_allow_html=True)
    st.caption("所有输出均需业务员审核。")


if page == "询盘分析":
    st.title("询盘分析")
    st.write("将英文B2B询盘转换为结构化采购需求，并生成可追溯的销售决策。")
    sample_rows, _ = load_evaluation_data()
    sample_options = {f"{row['id']} · {CASE_TYPE_LABELS.get(row['case_type'], row['case_type'])}": row["text"] for row in sample_rows}
    col_input, col_reference = st.columns([1.65, 1], gap="large")
    with col_input:
        uploaded = st.file_uploader("上传询盘文件", type=["txt", "docx"], help="当前POC支持TXT和DOCX。")
        selected_sample = st.selectbox("加载演示案例", ["手动输入或上传询盘", *sample_options.keys()])
        default_text = sample_options.get(selected_sample, "")
        if uploaded:
            try:
                default_text = read_uploaded_file(uploaded)
            except ValueError as exc:
                st.error(str(exc))
        inquiry_text = st.text_area("英文询盘", value=default_text, height=310, placeholder="请在此粘贴海外客户的英文询盘……")
        use_llm = st.toggle("使用已配置的大模型", value=False, disabled=not SETTINGS.llm_available, help="没有API Key时仍可使用本地演示流程。")
        analyze_clicked = st.button("开始分析", type="primary", width="stretch")
    with col_reference:
        st.subheader("决策范围")
        st.markdown(
            """
            - 提取客户、产品、数量、市场和定制需求
            - 检查缺失信息、商业提醒和风险信号
            - 返回产品目录中的前三名候选
            - 计算线索得分并选择跟进路径
            - 生成可由业务员审核的英文回复
            """
        )
        st.subheader("支持的产品品类")
        category_data = pd.DataFrame(
            {
                "产品品类": ["电竞鼠标", "机械键盘", "电竞耳机", "客制化线材", "客制化键帽"],
                "目录SKU数量": [4, 4, 4, 4, 4],
            }
        )
        st.dataframe(category_data, hide_index=True, width="stretch")
    if analyze_clicked:
        try:
            with st.spinner("正在运行七步询盘评估流程……"):
                st.session_state.analysis_result = analyze_inquiry(inquiry_text, use_llm=use_llm, db_path=DB_PATH)
            st.success("分析完成。请在线索评估、产品匹配和跟进助手页面查看详细结果。")
        except Exception as exc:
            st.error(f"分析失败：{exc}")
    result = current_result()
    if result:
        st.divider()
        metric_row(result)
        left, right = st.columns([1, 1], gap="large")
        with left:
            st.subheader("结构化需求")
            st.json(model_dump_compat(result.inquiry), expanded=2)
        with right:
            st.subheader("工作流执行记录")
            trace = pd.DataFrame(
                [{"处理步骤": TOOL_LABELS.get(name, name), "状态": "已完成" if ok else "失败"} for name, ok in result.tool_status.items()]
            )
            st.dataframe(trace, hide_index=True, width="stretch")

elif page == "线索评估":
    st.title("线索评估")
    result = current_result()
    if not result:
        render_empty_state()
    else:
        metric_row(result)
        if result.customer_check.manual_review_required:
            st.markdown('<div class="risk-line"><strong>需要人工复核。</strong> 在提供商业条款前，请先核查风险证据。</div>', unsafe_allow_html=True)
        left, right = st.columns([1.2, 1], gap="large")
        with left:
            st.subheader("评分明细")
            breakdown = model_dump_compat(result.lead_score.breakdown)
            score_frame = pd.DataFrame(
                {"评分维度": [SCORE_LABELS.get(key, key) for key in breakdown], "得分": list(breakdown.values())}
            ).set_index("评分维度")
            st.bar_chart(score_frame, horizontal=True, color="#087E5B")
            with st.expander("查看评分依据（系统原始说明）"):
                for explanation in result.lead_score.explanations:
                    st.write(explanation)
        with right:
            st.subheader("缺失信息")
            if result.missing_fields:
                for field in result.missing_fields:
                    st.write(f"- {MISSING_FIELD_LABELS.get(field, field)}")
            else:
                st.success("未发现必须补充的资格评估字段。")
            st.subheader("资格评估提醒")
            for warning in result.customer_check.quality_warnings:
                st.warning(f"信息质量：{warning}")
            for warning in result.customer_check.commercial_warnings:
                st.warning(f"商业确认：{warning}")
            st.subheader("风险证据")
            if result.customer_check.risk_flags:
                for flag in result.customer_check.risk_flags:
                    st.error(flag)
            else:
                st.success("POC规则未发现明确风险信号。")

elif page == "产品匹配":
    st.title("产品匹配")
    result = current_result()
    if not result:
        render_empty_state()
        with st.expander("浏览产品目录"):
            st.dataframe(pd.DataFrame(list_products(db_path=DB_PATH)), hide_index=True, width="stretch")
    else:
        match = result.product_match
        header_left, header_right = st.columns([1.4, 1])
        with header_left:
            st.markdown(f"### {MATCH_TYPE_LABELS.get(match.match_type, match.match_type)}")
            st.write(f"推荐基础SKU：**{match.recommended_sku or '无合适目录SKU'}**")
        with header_right:
            st.metric("最佳匹配度", f"{match.match_score}%")
        reason_col, gap_col = st.columns(2, gap="large")
        with reason_col:
            st.subheader("匹配依据")
            for reason in match.reasons or ["未找到正向匹配证据。"]:
                st.write(f"- {reason}")
        with gap_col:
            st.subheader("差距与待确认项")
            for gap in match.gaps or ["未发现产品目录差距。"]:
                st.write(f"- {gap}")
        st.subheader("候选产品前三名")
        candidate_rows = []
        for candidate in match.candidates:
            candidate_rows.append(
                {
                    "SKU": candidate.sku,
                    "产品名称": candidate.product_name,
                    "匹配度": candidate.match_score,
                    "MOQ": candidate.standard_moq,
                    "量产交期（天）": candidate.mass_production_lead_time_days,
                    "认证": ", ".join(candidate.certifications),
                    "待确认项": len(candidate.gaps),
                    "硬约束冲突": len(candidate.hard_constraint_gaps),
                }
            )
        if candidate_rows:
            st.dataframe(pd.DataFrame(candidate_rows), hide_index=True, width="stretch")
        else:
            st.warning("由于产品品类或技术需求信息不足，系统未返回候选产品。")

elif page == "跟进助手":
    st.title("跟进助手")
    result = current_result()
    if not result:
        render_empty_state()
    else:
        st.markdown('<div class="draft-banner"><strong>以下内容为业务员审核草稿。</strong> 在确认价格、交期、认证和客户身份前，请勿直接发送。</div>', unsafe_allow_html=True)
        left, right = st.columns([1, 1.55], gap="large")
        with left:
            st.subheader("推荐跟进路径")
            st.write(STRATEGY_LABELS.get(result.follow_up.strategy, result.follow_up.strategy))
            st.subheader("下一步行动")
            st.write(result.follow_up.next_action)
            st.metric("建议跟进时间", f"{result.follow_up.suggested_follow_up_days}天内")
            st.subheader("需要向客户确认的问题（英文）")
            for question in result.follow_up.questions or ["当前没有必须补充的客户问题。"]:
                st.write(f"- {question}")
        with right:
            st.subheader("英文回复草稿")
            edited_reply = st.text_area("审核并编辑", value=result.reply_draft, height=430, label_visibility="collapsed")
            if edited_reply != result.reply_draft:
                result.reply_draft = edited_reply
                st.session_state.analysis_result = result
            if st.button("保存至CRM", type="primary", width="stretch"):
                lead_id = save_lead_record(result, db_path=DB_PATH)
                st.success(f"已保存，线索编号：{lead_id}。")

elif page == "CRM记录":
    st.title("CRM记录")
    st.write("业务员审核后保存到本地SQLite的线索记录。当前未连接外部CRM。")
    leads = list_leads(db_path=DB_PATH)
    if not leads:
        render_empty_state("当前还没有保存CRM记录。")
    else:
        frame = pd.DataFrame(leads)
        filters = st.columns([1, 1, 2])
        priorities = ["全部", *sorted(frame["priority"].dropna().unique())]
        categories = ["全部", *sorted(frame["category"].dropna().unique())]
        priority_filter = filters[0].selectbox(
            "优先级",
            priorities,
            format_func=lambda value: PRIORITY_LABELS.get(value, value),
        )
        category_filter = filters[1].selectbox(
            "产品品类",
            categories,
            format_func=lambda value: CATEGORY_LABELS.get(value, value),
        )
        search = filters[2].text_input("搜索公司或SKU")
        if priority_filter != "全部":
            frame = frame[frame["priority"] == priority_filter]
        if category_filter != "全部":
            frame = frame[frame["category"] == category_filter]
        if search:
            mask = frame[["customer_name", "recommended_sku"]].fillna("").apply(lambda column: column.str.contains(search, case=False)).any(axis=1)
            frame = frame[mask]
        columns = ["lead_id", "created_at", "customer_name", "country", "category", "requested_quantity", "lead_score", "priority", "match_type", "recommended_sku", "next_action"]
        display_frame = frame[columns].copy()
        display_frame["category"] = display_frame["category"].map(lambda value: CATEGORY_LABELS.get(value, value))
        display_frame["priority"] = display_frame["priority"].map(lambda value: PRIORITY_LABELS.get(value, value))
        display_frame["match_type"] = display_frame["match_type"].map(lambda value: MATCH_TYPE_LABELS.get(value, value))
        display_frame = display_frame.rename(
            columns={
                "lead_id": "线索编号", "created_at": "创建时间", "customer_name": "客户名称",
                "country": "客户国家", "category": "产品品类", "requested_quantity": "采购数量",
                "lead_score": "线索得分", "priority": "优先级", "match_type": "匹配类型",
                "recommended_sku": "推荐SKU", "next_action": "下一步行动",
            }
        )
        st.dataframe(display_frame, hide_index=True, width="stretch")

elif page == "POC评估":
    st.title("POC评估")
    st.write("使用25条人工标注的合成询盘运行确定性工作流。结果只代表当前受控测试集，不代表生产环境准确率。")
    if st.button("运行评估", type="primary") or "evaluation_report" in st.session_state:
        if "evaluation_report" not in st.session_state:
            with st.spinner("正在评估25条询盘……"):
                st.session_state.evaluation_report = run_evaluation(db_path=DB_PATH)
        report = st.session_state.evaluation_report
        st.caption(f"数据集：{report.total_cases}条合成询盘，覆盖五个产品品类")
        metrics = report.metrics()
        columns = st.columns(3)
        for index, (label, value) in enumerate(metrics.items()):
            columns[index % 3].metric(EVALUATION_LABELS.get(label, label), f"{value:.1f}%")
        st.subheader("案例级审计")
        result_frame = pd.DataFrame(report.case_results)
        display_results = result_frame.rename(
            columns={
                "id": "案例编号", "case_type": "案例类型", "field_accuracy": "字段准确率",
                "expected_sku": "预期SKU", "actual_sku": "实际SKU", "product_ok": "产品正确",
                "expected_priority": "预期优先级", "actual_priority": "实际优先级",
                "priority_ok": "优先级正确", "score": "得分", "error": "错误",
            }
        )
        st.dataframe(display_results, hide_index=True, width="stretch")
        failures = result_frame[(~result_frame["product_ok"]) | (~result_frame["priority_ok"]) | (result_frame["error"] != "")]
        st.subheader("错误案例")
        if failures.empty:
            st.success("当前受控测试集没有出现产品或优先级错误。")
        else:
            st.dataframe(failures, hide_index=True, width="stretch")

elif page == "项目说明":
    st.title("关于GearLead AI")
    st.write("这是一个面向电竞外设出口首轮询盘处理的AI决策支持原型。")
    image_path = PROJECT_ROOT / "assets" / "gearlead_catalog.png"
    if image_path.exists():
        st.image(str(image_path), width="stretch")
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("架构原则")
        st.markdown(
            """
            - 大模型：可选的语言理解和回复优化
            - 简单规则：线索评分、风险路由和决策阈值
            - SQLite：产品目录、客户历史和CRM记录
            - 人工审核：最终商业判断和邮件确认
            """
        )
        st.subheader("Agent工作步骤")
        st.code("提取 -> 校验 -> 检查 -> 匹配 -> 评分 -> 路由 -> 草稿 -> 保存", language="text")
    with right:
        st.subheader("明确边界")
        st.markdown(
            """
            - 不自动发送邮件
            - 不承诺最终价格或交付时间
            - 不进行真实征信、制裁名单或贸易合规判断
            - 不将合成POC指标描述为生产准确率
            """
        )
        st.subheader("合规说明")
        st.info("本项目仅用于展示AI解决方案设计，不提供法律、金融、贸易合规或信用风险意见。所有生成回复均为业务员审核草稿。")
