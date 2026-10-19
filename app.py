import re
import secrets

import streamlit as st
from pypdf import PdfReader

from compliance_engine import run_audit
from database import (clear_audits, delete_audit, get_audit, get_previous_score, get_recent_audits, get_stats,
                      init_db, save_audit_record)
from demo_contracts import demo_contract
from i18n import LANGS, engine_label, show, source_label, tr
from labor_law_data import CONTRACT_TYPES, type_info
from negotiator import llm_available, negotiate
from report_export import build_memo
from rules_engine import analyze_contract
from schemas import AuditReport, ISSUE_STATUSES, report_stats
from security import (HISTORY_MODE, LLM_LIMITER, LLM_SESSION_LIMIT, MAX_CONTRACT_CHARS, MAX_PDF_PAGES,
                      NEGOTIATION_SESSION_LIMIT, logger, md_escape, safe_html, within_session_limit)

# تهيئة قاعدة بيانات SQLite عند إقلاع التطبيق
init_db()

# ---------------------------------------------------------------------------
# اللغة: من الرابط (?lang=en) أو من آخر اختيار في الجلسة
# ---------------------------------------------------------------------------
if "lang" not in st.session_state:
    st.session_state.lang = "en" if st.query_params.get("lang") == "en" else "ar"
lang = st.session_state.lang
is_en = lang == "en"


def t(key: str, **kwargs) -> str:
    return tr(key, lang, **kwargs)


st.set_page_config(page_title=t("page_title"), page_icon="⚖️", layout="wide")

# ---------------------------------------------------------------------------
# التنسيق: اتجاه الصفحة حسب اللغة (RTL للعربية، LTR للإنجليزية) وخط Tajawal
# ---------------------------------------------------------------------------
direction, align, side = ("ltr", "left", "left") if is_en else ("rtl", "right", "right")
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');
.stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp input, .stApp textarea, .stApp button, .stApp summary,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stMetricValue"], .stApp [data-testid="stCaptionContainer"] {{
    font-family: 'Tajawal', sans-serif !important;
}}
.stApp [data-testid="stIconMaterial"], .stApp .material-symbols-rounded {{ font-family: 'Material Symbols Rounded' !important; }}
/* الاتجاه على المحتوى فقط، حتى لا يتأثر موضع الشريط الجانبي وحركة طيّه على الجوال */
[data-testid="stMain"], [data-testid="stSidebarUserContent"] {{ direction: {direction}; }}
.stApp [data-testid="stMarkdownContainer"], .stApp label, .stApp [data-testid="stMetric"],
.stApp [data-testid="stCaptionContainer"], .stApp h1, .stApp h2, .stApp h3 {{ text-align: {align}; }}
.stApp [data-testid="stMetricValue"] {{ font-weight: 500; }}
.stApp [data-testid="stChatMessage"] {{ direction: {direction}; text-align: {align}; }}
.stApp textarea {{ direction: {direction}; text-align: start; unicode-bidi: plaintext; }}
.clause-quote {{
    border-{side}: 4px solid #9aa4b2; background: rgba(150,160,175,.10); padding: .7rem 1rem;
    border-radius: 6px; margin: .3rem 0 .8rem; line-height: 1.9; font-size: .95rem; unicode-bidi: plaintext;
}}
.alt-clause {{
    border-{side}: 4px solid #21a366; background: rgba(33,163,102,.08); padding: .8rem 1rem;
    border-radius: 6px; margin: .3rem 0 .6rem; line-height: 1.9; unicode-bidi: plaintext;
}}
.meta-row {{ margin-bottom: .9rem; line-height: 1.9; }}
.hero-card {{
    border: 1px solid rgba(150,160,175,.35); border-radius: 12px; padding: 1.1rem 1.2rem; height: 100%;
    background: rgba(150,160,175,.06);
}}
.hero-card h4 {{ margin: 0 0 .4rem; }}
.engine-pill {{
    display: inline-block; padding: .15rem .7rem; border-radius: 999px; font-size: .8rem;
    background: rgba(255,75,75,.10); color: #d33; border: 1px solid rgba(255,75,75,.25);
    margin: 0 0 .35rem 0; margin-inline-end: .4rem;
}}
.st-key-lang_switch {{ display: flex; justify-content: flex-end; }}

/* التوافق مع الجوال */
@media (max-width: 640px) {{
    [data-testid="stMainBlockContainer"] {{ padding: 3.2rem 0.9rem 2rem; }}
    .stApp h1 {{ font-size: 1.55rem !important; line-height: 1.5 !important; }}
    .stApp h2 {{ font-size: 1.3rem !important; }}
    .stApp h3 {{ font-size: 1.12rem !important; line-height: 1.6 !important; }}
    .stApp [data-testid="stMetricValue"] {{ font-size: 1.8rem; }}
    .stApp [data-testid="stMetric"] {{ padding: .2rem 0; }}
    .stApp summary p {{ font-size: .9rem; line-height: 1.7; }}
    .stApp [data-testid="stChatMessage"] {{ padding: .6rem .5rem; gap: .5rem; }}
    .clause-quote, .alt-clause {{ padding: .6rem .75rem; font-size: .9rem; line-height: 1.8; }}
    .meta-row {{ font-size: .95rem; margin-bottom: .6rem; }}
    .hero-card {{ padding: .9rem 1rem; margin-bottom: .6rem; }}
    .engine-pill {{ font-size: .75rem; padding: .1rem .55rem; }}
    /* منع التكبير التلقائي في Safari عند الكتابة */
    .stApp input, .stApp textarea {{ font-size: 16px !important; }}
}}
</style>
""", unsafe_allow_html=True)

STATUS_BADGE = {"متوافق": "🟢", "مخالف": "🔴", "مبهم / عالي المخاطر": "🟠", "غير مذكور": "⚪"}


def ltr(text: str) -> str:
    """يعزل النص الإنجليزي داخل العناوين العربية حتى لا تنقلب أقواسه عند التفاف السطر على الجوال."""
    unbreakable = text.replace(" ", "\N{NO-BREAK SPACE}").replace("-", "\N{NON-BREAKING HYPHEN}")
    return "\N{LEFT-TO-RIGHT ISOLATE}" + unbreakable + "\N{POP DIRECTIONAL ISOLATE}"


def heading(key: str) -> str:
    """عنوان مع الجزء الإنجليزي المعزول (يُحذف عند الواجهة الإنجليزية إن كان مكرراً)."""
    extra = t(f"{key}_en_part")
    return f"{t(key)} {ltr(extra)}" if extra else t(key)


def detect_lang(report: AuditReport) -> str:
    return "ar" if re.search(r"[؀-ۿ]", report.contract_summary) else "en"


# تهيئة الذاكرة التفاعلية
for key, default in {"audit_report": None, "negotiation_data": {}, "audit_meta": {}, "_llm_audits": 0, "_llm_negs": 0}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# هوية عشوائية لكل جلسة: كل زائر يرى سجل فحوصاته فقط (إلا في الوضع المحلي المشترك HISTORY_MODE=shared)
if "_owner" not in st.session_state:
    st.session_state._owner = secrets.token_hex(16)
owner = None if HISTORY_MODE == "shared" else st.session_state._owner


def load_audit_into_state(record: dict):
    report = AuditReport.model_validate_json(record["report_json"])
    st.session_state.audit_report = report
    st.session_state.negotiation_data = {}
    st.session_state.audit_meta = {
        "id": record["id"], "category": record["contract_category"], "engine": record.get("engine") or "rules",
        "source": record.get("source") or "", "timestamp": record["timestamp"], "text": "",
        "prev_score": get_previous_score(record["contract_category"], record["id"], owner), "lang": detect_lang(report),
    }


def read_pdf(uploaded) -> tuple[str, int, bool]:
    """يقرأ نص الـ PDF بحد أقصى لعدد الصفحات؛ يعيد (النص، عدد الصفحات، هل اقتُطع)."""
    reader = PdfReader(uploaded)
    if reader.is_encrypted:
        raise PermissionError("encrypted PDF")
    total = len(reader.pages)
    parts = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        parts.append(page.extract_text() or "")
        if sum(len(x) for x in parts) > MAX_CONTRACT_CHARS:
            break
    return "\n".join(parts), total, total > MAX_PDF_PAGES


# ---------------------------------------------------------------------------
# مبدّل اللغة (أعلى الصفحة ليظهر أيضاً على الجوال)
# ---------------------------------------------------------------------------
def _on_lang_change():
    choice = st.session_state.get("lang_switch")
    if choice:
        st.session_state.lang = choice
        st.query_params["lang"] = choice
    else:  # الضغط على اللغة المختارة نفسها يلغي التحديد؛ نعيده كما كان
        st.session_state.lang_switch = st.session_state.lang


st.segmented_control(t("language"), options=list(LANGS), format_func=lambda c: LANGS[c], default=lang,
                     key="lang_switch", on_change=_on_lang_change, label_visibility="collapsed")

# ---------------------------------------------------------------------------
# الشريط الجانبي: إعدادات التدقيق
# ---------------------------------------------------------------------------
def remembered(name: str, options: list, default):
    """فهرس آخر اختيار محفوظ؛ الأدوات تحمل مفتاحاً لكل لغة، فيُنقل الاختيار عند تبديل اللغة."""
    value = st.session_state.get(f"_{name}", default)
    return options.index(value) if value in options else 0


def remember(name: str, value):
    st.session_state[f"_{name}"] = value
    return value


with st.sidebar:
    st.header(t("settings"))

    categories, sources = list(CONTRACT_TYPES), ["demo", "pdf", "text"]
    contract_category = remember("category", st.selectbox(
        t("choose_category"), categories, index=remembered("category", categories, categories[0]),
        format_func=lambda c: type_info(c, lang)["name"], key=f"category_{lang}"))
    input_source = remember("source", st.radio(
        t("source"), sources, index=remembered("source", sources, "demo"),
        format_func=lambda c: t(f"src_{c}"), key=f"source_{lang}"))

    contract_text, source_code = "", input_source
    if input_source == "demo":
        contract_text = demo_contract(contract_category, lang)
        st.info(type_info(contract_category, lang)["demo_note"])
    elif input_source == "pdf":
        uploaded_file = st.file_uploader(t("upload_label"), type=["pdf"])
        if uploaded_file:
            try:
                contract_text, pages, capped = read_pdf(uploaded_file)
                source_code = f"pdf:{uploaded_file.name[:120]}"
                if contract_text.strip():
                    st.success(t("pdf_ok", pages=pages))
                    if capped:
                        st.warning(t("pdf_capped", n=MAX_PDF_PAGES))
                else:
                    st.warning(t("pdf_empty"))
            except PermissionError:
                st.error(t("pdf_encrypted"))
            except Exception:
                logger.exception("PDF read failed")
                st.error(t("pdf_error"))
    else:
        contract_text = remember("paste", st.text_area(t("paste_label"), value=st.session_state.get("_paste", ""), height=220,
                                                       placeholder=t("paste_placeholder"), key=f"paste_{lang}"))

    with st.expander(t("engine_box"), expanded=False):
        engines = ["auto", "llm", "rules"]
        engine_choice = remember("engine", st.radio(
            t("engine_method"), engines, index=remembered("engine", engines, "auto"),
            format_func=lambda c: t(f"eng_{c}"), label_visibility="collapsed", key=f"engine_{lang}"))
        st.caption(t("key_ok") if llm_available() else t("key_missing"))

    if st.button(t("run"), type="primary", width="stretch"):
        if contract_text.strip():
            if len(contract_text) > MAX_CONTRACT_CHARS:
                contract_text = contract_text[:MAX_CONTRACT_CHARS]
                st.warning(t("text_truncated", n=f"{MAX_CONTRACT_CHARS:,}"))
            # حدود استخدام نموذج اللغة لحماية رصيد المفتاح: لكل جلسة ولكل الزوار مجتمعين
            run_engine = engine_choice
            if engine_choice != "rules" and llm_available():
                if within_session_limit(st.session_state._llm_audits, LLM_SESSION_LIMIT) and LLM_LIMITER.try_acquire():
                    st.session_state._llm_audits += 1
                else:
                    run_engine = "rules"
                    st.info(t("limit_audit"))
            with st.status(t("running"), expanded=True) as status:
                st.write(t("step_read"))
                st.write(t("step_check"))
                report, engine_used, warning = run_audit(contract_text, contract_category, run_engine, lang)
                st.write(t("step_traps"))
                stats = report_stats(report)
                audit_id = save_audit_record(
                    category=contract_category, score=report.compliance_score, issues=stats["issues"],
                    critical=stats["critical"], traps=stats["traps"], summary=report.contract_summary,
                    report_json=report.model_dump_json(), engine=engine_used, source=source_code, owner=owner,
                )
                st.write(t("step_save"))
                status.update(label=t("done"), state="complete", expanded=False)
            if warning:
                st.warning(warning)
            st.session_state.audit_report = report
            st.session_state.negotiation_data = {}
            st.session_state.audit_meta = {
                "id": audit_id, "category": contract_category, "engine": engine_used, "source": source_code,
                "text": contract_text, "prev_score": get_previous_score(contract_category, audit_id, owner), "lang": lang,
            }
        else:
            st.warning(t("need_input"))

    st.markdown("---")
    # استعراض سجل الفحوصات المحفوظة في SQLite
    st.subheader(f"{t('history')} {ltr('(SQLite DB)')}")
    if HISTORY_MODE != "shared":
        st.caption(t("history_private"))
    records = get_recent_audits(limit=8, owner=owner)
    if records:
        current_id = st.session_state.audit_meta.get("id")
        for r in records:
            audit_id, ts, cat, score, issues, _crit, traps, has_json, _eng = r
            marker = " ◀️" if audit_id == current_id else ""
            cat_name = type_info(cat, lang)["name"] if cat in CONTRACT_TYPES else cat
            st.caption(f"📅 **{ts}** | {cat_name}{marker}")
            st.caption(t("history_score", score=score, issues=issues, traps=traps))
            c_open, c_del = st.columns(2)
            if has_json and c_open.button(t("open"), key=f"open_{audit_id}", width="stretch"):
                record = get_audit(audit_id, owner)
                if record:
                    load_audit_into_state(record)
                st.rerun()
            if c_del.button(t("delete"), key=f"del_{audit_id}", width="stretch"):
                delete_audit(audit_id, owner)
                if audit_id == current_id:
                    st.session_state.audit_report = None
                    st.session_state.audit_meta = {}
                st.rerun()
            st.markdown("---")
        if st.button(t("clear_all"), width="stretch"):
            clear_audits(owner)
            st.rerun()
    else:
        st.caption(t("no_history"))

# ---------------------------------------------------------------------------
# الواجهة الرئيسية
# ---------------------------------------------------------------------------
st.title(heading("app_title"))
st.caption(t("app_caption"))

report: AuditReport = st.session_state.audit_report

if report is None:
    st.divider()
    db_stats = get_stats(owner)
    s1, s2, s3 = st.columns(3)
    s1.metric(t("stat_total"), db_stats["total"], border=True)
    s2.metric(t("stat_avg"), f"{db_stats['avg_score']}%", border=True)
    s3.metric(t("stat_traps"), db_stats["traps"], border=True)

    st.subheader(t("how_title"))
    for col, n in zip(st.columns(3), (1, 2, 3)):
        col.markdown(f'<div class="hero-card"><h4>{t(f"how{n}_t")}</h4><div>{t(f"how{n}_b")}</div></div>', unsafe_allow_html=True)
    st.info(t("start_hint"))
    st.stop()

meta = st.session_state.audit_meta
category = meta.get("category", contract_category)

# عند تغيير اللغة بعد الفحص: نتائج المحرك المحلي تُعاد فوراً باللغة الجديدة (مجاناً ودون اتصال)
if meta.get("lang") and meta.get("lang") != lang and meta.get("engine") == "rules" and meta.get("text"):
    report = analyze_contract(meta["text"], category, lang)
    st.session_state.audit_report = report
    st.session_state.negotiation_data = {}
    meta["lang"] = lang
elif meta.get("lang") and meta.get("lang") != lang:
    st.info("ℹ️ " + ("This report was generated in Arabic. Run the audit again to get its content in English."
                     if is_en else "هذا التقرير أُنشئ باللغة الإنجليزية. أعد الفحص للحصول على محتواه بالعربية."))

stats = report_stats(report)
traps_list, metadata_obj = report.traps, report.metadata

st.markdown(
    f'<span class="engine-pill">🤖 {safe_html(engine_label(meta.get("engine"), lang))}</span>'
    f'<span class="engine-pill">📁 {safe_html(type_info(category, lang)["name"])}</span>'
    f'<span class="engine-pill">📄 {safe_html(source_label(meta.get("source"), lang))}</span>',
    unsafe_allow_html=True,
)
st.write("")

# 1. المؤشرات الرئيسية
prev = meta.get("prev_score")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(t("m_score"), f"{report.compliance_score}%",
              delta=t("m_delta", d=report.compliance_score - prev) if prev is not None else None)
with col2:
    st.metric(t("m_issues"), stats["issues"], delta=-stats["issues"] if stats["issues"] else None)
with col3:
    st.metric(t("m_critical"), stats["critical"], delta=-stats["critical"] if stats["critical"] else None)
with col4:
    st.metric(t("m_traps"), stats["traps"], delta=-stats["traps"] if stats["traps"] else None)

st.divider()

# 2. بطاقة البيانات الجوهرية
st.subheader(heading("meta_title"))
m_col1, m_col2 = st.columns(2)
parties_str = (", " if is_en else "، ").join(metadata_obj.parties) if metadata_obj.parties else t("not_set")
rows = [("👥", "parties", parties_str), ("⏳", "duration", metadata_obj.effective_duration),
        ("💰", "financial", metadata_obj.financial_terms), ("🔄", "renewal", metadata_obj.renewal_clause)]
for col, (icon, key, value) in zip([m_col1, m_col1, m_col2, m_col2], rows):
    col.markdown(f'<div class="meta-row">{icon} <b>{t(key)}:</b> <bdi>{safe_html(value)}</bdi></div>', unsafe_allow_html=True)
with st.expander(t("summary")):
    st.markdown(md_escape(report.contract_summary))

# 3. كاشف الفخاخ التعاقدية
st.subheader(heading("traps_title"))
if traps_list:
    for trap in sorted(traps_list, key=lambda x: x.severity != "حرج جداً"):
        message = f"**{t('trap_prefix')}: {md_escape(trap.trap_name)}** ({show(trap.severity, lang)})\n\n{md_escape(trap.explanation)}"
        if trap.severity == "حرج جداً":
            st.error(message, icon="⚠️")
        else:
            st.warning(message, icon="🔶")
else:
    st.success(t("no_traps"))

st.divider()

# 4. تفاصيل فحص البنود ومحاكي التفاوض
st.subheader(t("clauses_title"))
view = remember("view", st.segmented_control(
    "view", ["all", "issues", "ok"], format_func=lambda c: t(f"view_{c}"), default=st.session_state.get("_view", "all"),
    label_visibility="collapsed", key=f"clause_view_{lang}") or "all")
weak_party, strong_party = type_info(category, lang)["parties"]


def party_name(rep_name: str) -> str:
    return rep_name.replace("'s Representative", "").replace("ممثل ", "")


for idx, item in enumerate(report.items):
    is_issue = item.status in ISSUE_STATUSES or item.status == "غير مذكور"
    if view == "issues" and not is_issue:
        continue
    if view == "ok" and item.status != "متوافق":
        continue
    badge = STATUS_BADGE.get(item.status, "⚪")

    with st.expander(f"**{md_escape(item.clause_title)}** | {t('dimension')}: [{show(item.risk_category, lang)}] — "
                     f"{t('status')}: {show(item.status, lang)} {badge}"):
        st.markdown(f"**{t('quote')}**")
        st.markdown(f'<div class="clause-quote">{safe_html(item.contract_snippet)}</div>', unsafe_allow_html=True)
        c_a, c_b = st.columns([3, 1])
        with c_a:
            st.markdown(f"**{t('analysis')}:** {md_escape(item.analysis)}")
            st.markdown(f"**{t('reference')}:** {md_escape(item.legal_reference)}")
        with c_b:
            st.markdown(f"**{t('risk_level')}:** {show(item.risk_level, lang)}")
            st.markdown(f"**{t('status')}:** {badge} {show(item.status, lang)}")
        if item.recommendation:
            st.markdown(t("alt_wording"))
            st.markdown(f'<div class="alt-clause">{safe_html(item.recommendation)}</div>', unsafe_allow_html=True)

        # محاكي التفاوض
        if is_issue:
            st.markdown("---")
            if st.button(t("negotiate_btn"), key=f"btn_neg_{idx}"):
                neg_engine_choice = engine_choice
                if engine_choice != "rules" and llm_available():
                    if within_session_limit(st.session_state._llm_negs, NEGOTIATION_SESSION_LIMIT) and LLM_LIMITER.try_acquire():
                        st.session_state._llm_negs += 1
                    else:
                        neg_engine_choice = "rules"
                        st.info(t("limit_neg"))
                with st.spinner(t("negotiating")):
                    session, neg_engine, neg_warning = negotiate(
                        clause_title=item.clause_title, problematic_text=item.contract_snippet,
                        issue_context=item.analysis, recommendation=item.recommendation,
                        legal_reference=item.legal_reference, contract_category=category,
                        engine=neg_engine_choice, lang=lang,
                    )
                    st.session_state.negotiation_data[idx] = session
                    if neg_warning:
                        st.caption(f"ℹ️ {neg_warning}")

            neg_result = st.session_state.negotiation_data.get(idx)
            if neg_result:
                st.markdown(t("minutes"))
                for turn_idx, turn in enumerate(neg_result.dialogue):
                    if turn.speaker.strip() == strong_party:
                        is_weak = False
                    elif turn.speaker.strip() == weak_party:
                        is_weak = True
                    else:
                        is_weak = turn_idx % 2 == 0
                    with st.chat_message("user" if is_weak else "assistant", avatar="👤" if is_weak else "🏢"):
                        st.markdown(f"**{md_escape(turn.speaker)}:** {md_escape(turn.argument)}")

                st.success(t("agreed", ww=ltr("(Win-Win)")))
                st.markdown(f'<div class="alt-clause">{safe_html(neg_result.agreed_clause)}</div>', unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                b1.info(f"🏢 **{t('gains', p=party_name(strong_party))}:**\n\n{md_escape(neg_result.benefits_for_party_a)}")
                b2.info(f"👤 **{t('gains', p=party_name(weak_party))}:**\n\n{md_escape(neg_result.benefits_for_party_b)}")

st.divider()

# 5. تصدير مذكرة الفحص القانوني
st.subheader(t("export_title"))
memo_text = build_memo(report, category, meta.get("engine", "rules"), meta.get("source", ""),
                       st.session_state.negotiation_data, lang)
st.download_button(
    label=t("download_md"),
    data=memo_text,
    file_name=t("memo_file"),
    mime="text/markdown",
    width="stretch",
)
st.download_button(
    label=t("download_json"),
    data=report.model_dump_json(indent=2),
    file_name="legal_due_diligence_report.json",
    mime="application/json",
    width="stretch",
)

if meta.get("text"):
    with st.expander(t("show_text")):
        st.markdown(f'<div class="clause-quote" style="white-space: pre-wrap;">{safe_html(meta["text"].strip())}</div>',
                    unsafe_allow_html=True)

st.caption(t("disclaimer"))
