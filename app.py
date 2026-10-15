import html

import streamlit as st
from pypdf import PdfReader

from compliance_engine import run_audit
from database import (clear_audits, delete_audit, get_audit, get_previous_score, get_recent_audits, get_stats,
                      init_db, save_audit_record)
from demo_contracts import DEMO_CONTRACTS
from labor_law_data import CONTRACT_TYPES
from negotiator import llm_available, negotiate
from report_export import ENGINE_LABELS, build_memo
from schemas import AuditReport, ISSUE_STATUSES, report_stats

# تهيئة قاعدة بيانات SQLite عند إقلاع التطبيق
init_db()

st.set_page_config(
    page_title="منصة تدقيق العقود الشاملة | Legal Due Diligence",
    page_icon="⚖️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# التنسيق: اتجاه عربي (RTL) وخط Tajawal
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');
.stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp input, .stApp textarea, .stApp button, .stApp summary,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stMetricValue"], .stApp [data-testid="stCaptionContainer"] {
    font-family: 'Tajawal', sans-serif !important;
}
.stApp [data-testid="stIconMaterial"], .stApp .material-symbols-rounded { font-family: 'Material Symbols Rounded' !important; }
.stApp { direction: rtl; }
.stApp [data-testid="stMarkdownContainer"], .stApp label, .stApp [data-testid="stMetric"],
.stApp [data-testid="stCaptionContainer"], .stApp h1, .stApp h2, .stApp h3 { text-align: right; }
.stApp [data-testid="stMetricValue"] { font-weight: 500; }
.stApp [data-testid="stChatMessage"] { direction: rtl; text-align: right; }
.stApp textarea { direction: rtl; text-align: right; }
.clause-quote {
    border-right: 4px solid #9aa4b2; background: rgba(150,160,175,.10); padding: .7rem 1rem;
    border-radius: 6px; margin: .3rem 0 .8rem; line-height: 1.9; font-size: .95rem;
}
.alt-clause {
    border-right: 4px solid #21a366; background: rgba(33,163,102,.08); padding: .8rem 1rem;
    border-radius: 6px; margin: .3rem 0 .6rem; line-height: 1.9;
}
.meta-row { margin-bottom: .9rem; line-height: 1.9; }
.hero-card {
    border: 1px solid rgba(150,160,175,.35); border-radius: 12px; padding: 1.1rem 1.2rem; height: 100%;
    background: rgba(150,160,175,.06);
}
.hero-card h4 { margin: 0 0 .4rem; }
.engine-pill {
    display: inline-block; padding: .15rem .7rem; border-radius: 999px; font-size: .8rem;
    background: rgba(255,75,75,.10); color: #d33; border: 1px solid rgba(255,75,75,.25); margin-left: .4rem;
}
</style>
""", unsafe_allow_html=True)

SOURCE_DEMO, SOURCE_PDF, SOURCE_TEXT = "نموذج تجريبي جاهز (Demo)", "رفع ملف PDF", "لصق نص العقد"
ENGINE_OPTIONS = {
    "تلقائي (LangChain عند توفر المفتاح)": "auto",
    "LangChain + OpenAI فقط": "llm",
    "المحرك المحلي (بدون إنترنت)": "rules",
}
STATUS_BADGE = {"متوافق": "🟢", "مخالف": "🔴", "مبهم / عالي المخاطر": "🟠", "غير مذكور": "⚪"}

# تهيئة الذاكرة التفاعلية
for key, default in {"audit_report": None, "negotiation_data": {}, "audit_meta": {}}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def load_audit_into_state(record: dict):
    st.session_state.audit_report = AuditReport.model_validate_json(record["report_json"])
    st.session_state.negotiation_data = {}
    st.session_state.audit_meta = {
        "id": record["id"], "category": record["contract_category"], "engine": record.get("engine") or "rules",
        "source": record.get("source") or "", "timestamp": record["timestamp"], "text": "",
        "prev_score": get_previous_score(record["contract_category"], record["id"]),
    }


def read_pdf(uploaded) -> tuple[str, int]:
    reader = PdfReader(uploaded)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text, len(reader.pages)


# ---------------------------------------------------------------------------
# الشريط الجانبي: إعدادات التدقيق
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ إعدادات التدقيق")

    contract_category = st.selectbox("اختر تصنيف العقد:", list(CONTRACT_TYPES))
    input_source = st.radio("مصدر المستند:", [SOURCE_DEMO, SOURCE_PDF, SOURCE_TEXT])

    contract_text, source_label = "", input_source
    if input_source == SOURCE_DEMO:
        contract_text = DEMO_CONTRACTS[contract_category]
        st.info(CONTRACT_TYPES[contract_category]["demo_note"])
    elif input_source == SOURCE_PDF:
        uploaded_file = st.file_uploader("ارفع وثيقة العقد (PDF)", type=["pdf"])
        if uploaded_file:
            try:
                contract_text, pages = read_pdf(uploaded_file)
                source_label = f"ملف PDF: {uploaded_file.name}"
                if contract_text.strip():
                    st.success(f"تمت قراءة الملف بنجاح ({pages} صفحة)")
                else:
                    st.warning("الملف لا يحتوي على نص قابل للاستخراج (قد يكون صورة ممسوحة ضوئياً).")
            except Exception as err:
                st.error(f"تعذرت قراءة الملف: {err}")
    else:
        contract_text = st.text_area("الصق نص العقد هنا:", height=220, placeholder="المادة (1) ...")
        source_label = "نص ملصق"

    with st.expander("🤖 محرك التحليل (LangChain)", expanded=False):
        engine_choice = ENGINE_OPTIONS[st.radio("طريقة الفحص:", list(ENGINE_OPTIONS), label_visibility="collapsed")]
        if llm_available():
            st.caption("🟢 مفتاح OpenAI مهيأ في ملف .env — سيتم التحليل عبر LangChain.")
        else:
            st.caption("⚪ لا يوجد مفتاح OpenAI — سيعمل المحرك المحلي للخبير القانوني.")

    if st.button("🚀 بدء الفحص والتدقيق الشامل", type="primary", width="stretch"):
        if contract_text.strip():
            with st.status("جاري الفحص والتدقيق الشامل...", expanded=True) as status:
                st.write("📄 قراءة المستند وتجهيز النص...")
                st.write("🔍 فحص البنود ومطابقتها مع الأنظمة والمعايير...")
                report, engine_used, warning = run_audit(contract_text, contract_category, engine_choice)
                st.write("🚨 رصد الفخاخ التعاقدية وتقدير المخاطر...")
                stats = report_stats(report)
                audit_id = save_audit_record(
                    category=contract_category, score=report.compliance_score, issues=stats["issues"],
                    critical=stats["critical"], traps=stats["traps"], summary=report.contract_summary,
                    report_json=report.model_dump_json(), engine=engine_used, source=source_label,
                )
                st.write("🗄️ حفظ السجل في قاعدة بيانات SQLite...")
                status.update(label="اكتمل الفحص بنجاح ✅", state="complete", expanded=False)
            if warning:
                st.warning(warning)
            st.session_state.audit_report = report
            st.session_state.negotiation_data = {}
            st.session_state.audit_meta = {
                "id": audit_id, "category": contract_category, "engine": engine_used, "source": source_label,
                "text": contract_text, "prev_score": get_previous_score(contract_category, audit_id),
            }
        else:
            st.warning("الرجاء اختيار نموذج أو رفع ملف أو لصق نص العقد أولاً.")

    st.markdown("---")
    # استعراض سجل الفحوصات المحفوظة في SQLite
    st.subheader("🗄️ سجل الفحوصات (SQLite DB)")
    records = get_recent_audits(limit=8)
    if records:
        current_id = st.session_state.audit_meta.get("id")
        for r in records:
            audit_id, ts, cat, score, issues, _crit, traps, has_json, _eng = r
            marker = " ◀️" if audit_id == current_id else ""
            st.caption(f"📅 **{ts}** | {cat}{marker}")
            st.caption(f"درجة الأمان: `{score}%` | ملاحظات: `{issues}` | فخاخ: `{traps}`")
            c_open, c_del = st.columns(2)
            if has_json and c_open.button("📂 عرض", key=f"open_{audit_id}", width="stretch"):
                load_audit_into_state(get_audit(audit_id))
                st.rerun()
            if c_del.button("🗑️ حذف", key=f"del_{audit_id}", width="stretch"):
                delete_audit(audit_id)
                if audit_id == current_id:
                    st.session_state.audit_report = None
                    st.session_state.audit_meta = {}
                st.rerun()
            st.markdown("---")
        if st.button("🧹 مسح السجل بالكامل", width="stretch"):
            clear_audits()
            st.rerun()
    else:
        st.caption("لا توجد سجلات محفوظة حتى الآن.")

# ---------------------------------------------------------------------------
# الواجهة الرئيسية
# ---------------------------------------------------------------------------
st.title("⚖️ منصة تدقيق العقود والفحص النافي للجهالة (Legal Due Diligence)")
st.caption("كاشف الفخاخ، محاكي التفاوض، وتصدير التقارير، قاعدة بيانات SQLite، نظام متكامل مبني بواسطة LangChain")

report: AuditReport = st.session_state.audit_report

if report is None:
    st.divider()
    db_stats = get_stats()
    s1, s2, s3 = st.columns(3)
    s1.metric("إجمالي الفحوصات المؤرشفة", db_stats["total"], border=True)
    s2.metric("متوسط مؤشر السلامة", f"{db_stats['avg_score']}%", border=True)
    s3.metric("إجمالي الفخاخ المرصودة", db_stats["traps"], border=True)

    st.subheader("كيف تعمل المنصة؟")
    cards = [
        ("1️⃣ اختر المستند", "حدد تصنيف العقد (عمل، شركات، إيجار، SaaS، سرية) ثم استخدم النموذج التجريبي أو ارفع ملف PDF أو الصق النص."),
        ("2️⃣ فحص شامل", "يطابق المحرك كل بند مع الأنظمة والمعايير، ويستخرج البيانات الجوهرية ويرصد الفخاخ القاتلة."),
        ("3️⃣ فاوض وصدّر", "شغّل محاكي التفاوض على البنود المعيبة للوصول لصياغة متوازنة، ثم حمّل مذكرة الفحص القانوني."),
    ]
    for col, (title, body) in zip(st.columns(3), cards):
        col.markdown(f'<div class="hero-card"><h4>{title}</h4><div>{body}</div></div>', unsafe_allow_html=True)
    st.info("👈 ابدأ من الشريط الجانبي بالضغط على زر **بدء الفحص والتدقيق الشامل**.")
    st.stop()

meta = st.session_state.audit_meta
category = meta.get("category", contract_category)
stats = report_stats(report)
traps_list, metadata_obj = report.traps, report.metadata

st.markdown(
    f'<span class="engine-pill">🤖 {ENGINE_LABELS.get(meta.get("engine"), "—")}</span>'
    f'<span class="engine-pill">📁 {html.escape(category)}</span>'
    f'<span class="engine-pill">📄 {html.escape(meta.get("source") or "—")}</span>',
    unsafe_allow_html=True,
)
st.write("")

# 1. المؤشرات الرئيسية
prev = meta.get("prev_score")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("مؤشر السلامة القانونية", f"{report.compliance_score}%",
              delta=f"{report.compliance_score - prev:+d}% عن الفحص السابق" if prev is not None else None)
with col2:
    st.metric("بنود غير متوازنة", stats["issues"], delta=-stats["issues"] if stats["issues"] else None)
with col3:
    st.metric("مخاطر قانونية حرجة", stats["critical"], delta=-stats["critical"] if stats["critical"] else None)
with col4:
    st.metric("فخاخ تعاقدية مرصودة", stats["traps"], delta=-stats["traps"] if stats["traps"] else None)

st.divider()

# 2. بطاقة البيانات الجوهرية
st.subheader("📌 بطاقة البيانات الجوهرية والالتزامات (Contract Metadata)")
m_col1, m_col2 = st.columns(2)
parties_str = "، ".join(metadata_obj.parties) if metadata_obj.parties else "غير محدد"
with m_col1:
    st.markdown(f'<div class="meta-row">👥 <b>أطراف التعاقد:</b> {html.escape(parties_str)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="meta-row">⏳ <b>المدة والسريان:</b> {html.escape(metadata_obj.effective_duration)}</div>', unsafe_allow_html=True)
with m_col2:
    st.markdown(f'<div class="meta-row">💰 <b>المقابل المالي وشروط الدفع:</b> {html.escape(metadata_obj.financial_terms)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="meta-row">🔄 <b>أحكام التجديد والإنهاء:</b> {html.escape(metadata_obj.renewal_clause)}</div>', unsafe_allow_html=True)
with st.expander("📋 الملخص التنفيذي"):
    st.write(report.contract_summary)

# 3. كاشف الفخاخ التعاقدية
st.subheader("🚨 رادار الفخاخ التعاقدية والشروط الخطرة (Killer Clauses)")
if traps_list:
    for trap in sorted(traps_list, key=lambda t: t.severity != "حرج جداً"):
        message = f"**فخ: {trap.trap_name}** ({trap.severity})\n\n{trap.explanation}"
        if trap.severity == "حرج جداً":
            st.error(message, icon="⚠️")
        else:
            st.warning(message, icon="🔶")
else:
    st.success("لم يتم رصد فخاخ تعاقدية في هذا العقد. 👏")

st.divider()

# 4. تفاصيل فحص البنود ومحاكي التفاوض
st.subheader("🔍 تفاصيل فحص البنود ومحاكي التفاوض الآلي")
view = st.segmented_control("عرض:", ["الكل", "المخالفات والمخاطر فقط", "المتوافقة فقط"], default="الكل",
                            label_visibility="collapsed")
weak_party, strong_party = CONTRACT_TYPES.get(category, {}).get("parties", ("الطرف الثاني", "الطرف الأول"))

for idx, item in enumerate(report.items):
    is_issue = item.status in ISSUE_STATUSES or item.status == "غير مذكور"
    if view == "المخالفات والمخاطر فقط" and not is_issue:
        continue
    if view == "المتوافقة فقط" and item.status != "متوافق":
        continue
    badge = STATUS_BADGE.get(item.status, "⚪")

    with st.expander(f"**{item.clause_title}** | البعد: [{item.risk_category}] — الحالة: {item.status} {badge}"):
        st.markdown("**النص المقتبس من العقد:**")
        st.markdown(f'<div class="clause-quote">{html.escape(item.contract_snippet)}</div>', unsafe_allow_html=True)
        c_a, c_b = st.columns([3, 1])
        with c_a:
            st.markdown(f"**التحليل الفني:** {item.analysis}")
            st.markdown(f"**السند القانوني / المعيار:** {item.legal_reference}")
        with c_b:
            st.markdown(f"**مستوى الخطورة:** {item.risk_level}")
            st.markdown(f"**الحالة:** {badge} {item.status}")
        if item.recommendation:
            st.markdown("💡 **الصياغة البديلة المقترحة:**")
            st.markdown(f'<div class="alt-clause">{html.escape(item.recommendation)}</div>', unsafe_allow_html=True)

        # محاكي التفاوض
        if is_issue:
            st.markdown("---")
            if st.button("🤝 تشغيل محاكي التفاوض الآلي لهذا البند", key=f"btn_neg_{idx}"):
                with st.spinner("🤖 جاري التفاوض الآلي بين الوكلاء للوصول إلى تسوية عادلة..."):
                    session, neg_engine, neg_warning = negotiate(
                        clause_title=item.clause_title, problematic_text=item.contract_snippet,
                        issue_context=item.analysis, recommendation=item.recommendation,
                        legal_reference=item.legal_reference, contract_category=category,
                        engine=engine_choice,
                    )
                    st.session_state.negotiation_data[idx] = session
                    if neg_warning:
                        st.caption(f"ℹ️ {neg_warning}")

            neg_result = st.session_state.negotiation_data.get(idx)
            if neg_result:
                st.markdown("#### 💬 محضر جلسة التفاوض الافتراضية:")
                for turn_idx, turn in enumerate(neg_result.dialogue):
                    if turn.speaker.strip() == strong_party:
                        is_weak = False
                    elif turn.speaker.strip() == weak_party:
                        is_weak = True
                    else:
                        is_weak = turn_idx % 2 == 0
                    with st.chat_message("user" if is_weak else "assistant", avatar="👤" if is_weak else "🏢"):
                        st.markdown(f"**{turn.speaker}:** {turn.argument}")

                st.success("📜 **الصيغة التوافقية المتفق عليها (Win-Win):**")
                st.markdown(f'<div class="alt-clause">{html.escape(neg_result.agreed_clause)}</div>', unsafe_allow_html=True)
                b1, b2 = st.columns(2)
                b1.info(f"🏢 **مكاسب {strong_party.replace('ممثل ', '')}:**\n\n{neg_result.benefits_for_party_a}")
                b2.info(f"👤 **مكاسب {weak_party.replace('ممثل ', '')}:**\n\n{neg_result.benefits_for_party_b}")

st.divider()

# 5. تصدير مذكرة الفحص القانوني
st.subheader("📄 تصدير مذكرة الفحص القانوني")
memo_text = build_memo(report, category, meta.get("engine", "rules"), meta.get("source", ""),
                       st.session_state.negotiation_data)
st.download_button(
    label="📥 تحميل مذكرة الفحص القانوني (Markdown / Text)",
    data=memo_text,
    file_name="legal_due_diligence_report.md",
    mime="text/markdown",
    width="stretch",
)
st.download_button(
    label="🧾 تصدير بيانات الفحص (JSON)",
    data=report.model_dump_json(indent=2),
    file_name="legal_due_diligence_report.json",
    mime="application/json",
    width="stretch",
)

if meta.get("text"):
    with st.expander("📜 عرض نص العقد المفحوص"):
        st.markdown(f'<div class="clause-quote" style="white-space: pre-wrap;">{html.escape(meta["text"].strip())}</div>',
                    unsafe_allow_html=True)

st.caption("⚠️ هذا التحليل استرشادي صادر عن نظام آلي، ولا يغني عن مراجعة محامٍ مرخص قبل التوقيع.")
