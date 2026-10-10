import streamlit as st
from pypdf import PdfReader
from compliance_engine import audit_contract_text
from negotiator import run_negotiation
from database import init_db, save_audit_record, get_recent_audits

# تهيئة قاعدة بيانات SQLite عند إقلاع التطبيق
init_db()

st.set_page_config(
    page_title="منصة تدقيق العقود الشاملة | Legal Due Diligence",
    page_icon="⚖️",
    layout="wide"
)

DEMO_LABOR_CONTRACT = """
عقد عمل محدد المدة
الطرف الأول: شركة التقنية الحديثة
الطرف الثاني: الموظف

المادة (3) فترة التجربة:
يخضع الطرف الثاني لفترة تجربة مدتها (150) يوماً، ويحق للطرف الأول فسخ العقد خلالها دون إشعار أو تعويض.

المادة (5) ساعات العمل:
ساعات العمل الرسمية (9) ساعات يومياً لمدة 6 أيام أسبوعياً (54 ساعة أسبوعياً).

المادة (7) الإجازة السنوية:
يستحق الطرف الثاني إجازة سنوية مدفوعة الأجر قدرها (15) يوماً عن كل عام.

المادة (9) إنهاء العقد:
يجوز لأي طرف إنهاء العقد بمهلة إشعار لا تتجاوز 15 يوماً.

المادة (11) عدم المنافسة:
يلتزم الموظف بعدم العمل لدى أي منافس داخل المملكة لمدة 4 سنوات من تاريخ انتهاء العقد.
"""

DEMO_B2B_CONTRACT = """
اتفاقية تقديم خدمات تقنية وتوريد برمجيات (B2B)
الطرف الأول: شركة العميل القابضة
الطرف الثاني: مؤسسة الحلول البرمجية (المزود)

المادة (2) المدة والسريان:
تسري هذه الاتفاقية لمدة سنتين، وتتجدد تلقائياً لمدد مماثلة ما لم يقم الطرف الأول وحده بإشعار الطرف الثاني قبل 90 يوماً.

المادة (4) غرامات التأخير:
في حال تأخر المزود عن تسليم أي مرحلة لمدة تتجاوز 3 أيام، يحق للعميل حسم غرامة قدرها 40% من كامل قيمة العقد دفعة واحدة.

المادة (6) حدود المسؤولية والتعويض:
يتحمل المزود كامل المسؤولية التعويضية غير المحدودة عن أي خسائر مباشرة أو غير مباشرة أو فوات أرباح قد تصيب العميل جراء تشغيل النظام.

المادة (8) السرية وحفظ البيانات:
يلتزم المزود بالسرية التامة لجميع البيانات الفنية إلى الأبد وبصفة دائمة دون أي سقف زمني بعد انتهاء الاتفاقية.

المادة (10) الإنهاء الفوري:
يحق للعميل وحده إنهاء هذه الاتفاقية في أي وقت وبأثر فوري دون إشعار مسبق ودون الالتزام بسداد أي فواتير عن الأعمال المنجزة جزئياً.
"""

# تهيئة الذاكرة التفاعلية
if "audit_report" not in st.session_state:
    st.session_state.audit_report = None
if "negotiation_data" not in st.session_state:
    st.session_state.negotiation_data = {}

st.title("⚖️ منصة تدقيق العقود والفحص النافي للجهالة (Legal Due Diligence)")
st.caption("نظام متكامل مبني بواسطة LangChain | قاعدة بيانات SQLite، كاشف الفخاخ، محاكي التفاوض، وتصدير التقارير")

with st.sidebar:
    st.header("⚙️ إعدادات التدقيق")
    
    contract_category = st.selectbox(
        "اختر تصنيف العقد:",
        ["عقد عمل (أفراد ومنشآت)", "عقد شركات / تجاري وتوريد (B2B)"]
    )
    
    input_source = st.radio("مصدر المستند:", ["نموذج تجريبي جاهز (Demo)", "رفع ملف PDF"])
    
    contract_text = ""
    if input_source == "نموذج تجريبي جاهز (Demo)":
        if "عمل" in contract_category:
            contract_text = DEMO_LABOR_CONTRACT
            st.info("تم تحميل نموذج عقد عمل لاختبار المخالفات.")
        else:
            contract_text = DEMO_B2B_CONTRACT
            st.info("تم تحميل نموذج عقد شركات وتوريد لاختبار الفخاخ والشروط الجزائية.")
    else:
        uploaded_file = st.file_uploader("ارفع وثيقة العقد (PDF)", type=["pdf"])
        if uploaded_file:
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    contract_text += text + "\n"
            st.success(f"تمت قراءة الملف بنجاح ({len(reader.pages)} صفحة)")

    if st.button("🚀 بدء الفحص والتدقيق الشامل", type="primary", use_container_width=True):
        if contract_text:
            with st.spinner("جاري التحليل واستخراج المخاطر وحفظ السجل..."):
                try:
                    st.session_state.negotiation_data = {}
                    report = audit_contract_text(contract_text, contract_category)
                    st.session_state.audit_report = report
                    
                    # حفظ التقرير في قاعدة بيانات SQLite
                    issues_cnt = sum(1 for item in report.items if item.status in ["مخالف", "مبهم / عالي المخاطر"])
                    crit_cnt = sum(1 for item in report.items if item.risk_level == "حرج")
                    traps_cnt = len(getattr(report, "traps", []))
                    
                    save_audit_record(
                        category=contract_category,
                        score=report.compliance_score,
                        issues=issues_cnt,
                        critical=crit_cnt,
                        traps=traps_cnt,
                        summary=report.contract_summary
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"حدث خطأ أثناء المعالجة: {str(e)}")
        else:
            st.warning("الرجاء اختيار نموذج أو رفع ملف أولاً.")

    st.markdown("---")
    # استعراض سجل الفحوصات المحفوظة في SQLite
    st.subheader("🗄️ سجل الفحوصات (SQLite DB)")
    records = get_recent_audits(limit=5)
    if records:
        for r in records:
            st.caption(f"📅 **{r[1]}** | {r[2]}")
            st.caption(f"درجة الأمان: `{r[3]}%` | ملاحظات: `{r[4]}` | فخاخ: `{r[6]}`")
            st.markdown("---")
    else:
        st.caption("لا توجد سجلات محفوظة حتى الآن.")

# استعراض النتائج
if st.session_state.audit_report:
    report = st.session_state.audit_report
    
    traps_list = getattr(report, "traps", [])
    metadata_obj = getattr(report, "metadata", None)
    
    # 1. المؤشرات الرئيسية
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("مؤشر السلامة القانونية", f"{report.compliance_score}%")
    with col2:
        issues_count = sum(1 for item in report.items if item.status in ["مخالف", "مبهم / عالي المخاطر"])
        st.metric("بنود غير متوازنة", issues_count, delta=-issues_count if issues_count > 0 else 0)
    with col3:
        critical_count = sum(1 for item in report.items if item.risk_level == "حرج")
        st.metric("مخاطر قانونية حرجة", critical_count, delta=-critical_count if critical_count > 0 else 0)
    with col4:
        st.metric("فخاخ تعاقدية مرصودة", len(traps_list), delta=-len(traps_list) if len(traps_list) > 0 else 0)

    st.divider()

    # 2. بطاقة البيانات الجوهرية
    if metadata_obj:
        st.subheader("📌 بطاقة البيانات الجوهرية والالتزامات (Contract Metadata)")
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            parties_str = ', '.join(metadata_obj.parties) if getattr(metadata_obj, "parties", None) else "غير محدد"
            st.markdown(f"**👥 أطراف التعاقد:** {parties_str}")
            st.markdown(f"**⏳ المدة والسريان:** {getattr(metadata_obj, 'effective_duration', 'غير محدد')}")
        with m_col2:
            st.markdown(f"**💰 المقابل المالي وشروط الدفع:** {getattr(metadata_obj, 'financial_terms', 'غير محدد')}")
            st.markdown(f"**🔄 أحكام التجديد والإنهاء:** {getattr(metadata_obj, 'renewal_clause', 'غير محدد')}")

    # 3. كاشف الفخاخ التعاقدية
    if traps_list:
        st.subheader("🚨 رادار الفخاخ التعاقدية والشروط الخطرة (Killer Clauses)")
        for trap in traps_list:
            st.error(f"⚠️ **فخ: {trap.trap_name}** ({trap.severity})\n\n{trap.explanation}")

    st.divider()

    # 4. تفاصيل فحص البنود ومحاكي التفاوض
    st.subheader("🔍 تفاصيل فحص البنود ومحاكي التفاوض الآلي")
    for idx, item in enumerate(report.items):
        badge = "🔴" if item.risk_level == "حرج" else "🟡" if item.risk_level == "متوسط" else "🟢"
        risk_dim = getattr(item, "risk_category", "عام")
        
        with st.expander(f"{badge} **{item.clause_title}** | البعد: [{risk_dim}] — الحالة: {item.status}"):
            st.markdown(f"**النص المقتبس:**\n> {item.contract_snippet}")
            st.markdown(f"**السند القانوني / المعيار:** {item.legal_reference}")
            st.markdown(f"**التحليل الفني:** {item.analysis}")
            if item.recommendation:
                st.info(f"💡 **الصياغة البديلة المبدئية:** {item.recommendation}")
            
            # محاكي التفاوض
            if item.status in ["مخالف", "مبهم / عالي المخاطر"]:
                st.markdown("---")
                if st.button("🤝 تشغيل محاكي التفاوض الآلي لهذا البند", key=f"btn_neg_{idx}"):
                    with st.spinner("🤖 جاري التفاوض الآلي بين الوكلاء للوصول إلى تسوية عادلة..."):
                        try:
                            res = run_negotiation(
                                clause_title=item.clause_title,
                                problematic_text=item.contract_snippet,
                                issue_context=item.analysis
                            )
                            st.session_state.negotiation_data[idx] = res
                        except Exception as err:
                            st.error(f"خطأ في محاكي التفاوض: {str(err)}")
                
                if idx in st.session_state.negotiation_data:
                    neg_result = st.session_state.negotiation_data[idx]
                    st.markdown("#### 💬 محضر جلسة التفاوض الافتراضية:")
                    for turn in neg_result.dialogue:
                        if any(k in turn.speaker for k in ["الموظف", "المورد", "الثاني"]):
                            with st.chat_message("user", avatar="👤"):
                                st.write(f"**{turn.speaker}:** {turn.argument}")
                        else:
                            with st.chat_message("assistant", avatar="🏢"):
                                st.write(f"**{turn.speaker}:** {turn.argument}")
                    
                    st.success("### 📜 الصيغة التوافقية المتفق عليها (Win-Win):")
                    st.markdown(f"> *{neg_result.agreed_clause}*")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.info(f"🏢 **مكاسب الطرف الأول:**\n{neg_result.benefits_for_party_a}")
                    with c2:
                        st.info(f"👤 **مكاسب الطرف الثاني:**\n{neg_result.benefits_for_party_b}")

    st.divider()

    # 5. تصدير مذكرة الفحص القانوني
    st.subheader("📄 تصدير مذكرة الفحص القانوني")
    memo_text = f"""# مذكرة الفحص القانوني النافي للجهالة (Legal Due Diligence Memo)
تاريخ التقرير: 2026/10/03
تصنيف العقد: {contract_category}
مؤشر السلامة القانونية: {report.compliance_score}%

## 1. بطاقة البيانات الجوهرية:
- الأطراف: {', '.join(metadata_obj.parties) if metadata_obj and getattr(metadata_obj, 'parties', None) else 'غير محدد'}
- المدة والسريان: {getattr(metadata_obj, 'effective_duration', 'غير محدد') if metadata_obj else 'غير محدد'}
- الشروط المالية: {getattr(metadata_obj, 'financial_terms', 'غير محدد') if metadata_obj else 'غير محدد'}
- أحكام التجديد: {getattr(metadata_obj, 'renewal_clause', 'غير محدد') if metadata_obj else 'غير محدد'}

## 2. الملخص التنفيذي:
{report.contract_summary}

## 3. الفخاخ والشروط القاتلة المرصودة:
"""
    for t in traps_list:
        memo_text += f"- [{t.severity}] {t.trap_name}: {t.explanation}\n"

    memo_text += "\n## 4. نتائج فحص البنود:\n"
    for item in report.items:
        memo_text += f"\n### {item.clause_title} ({item.status} - خطورة {item.risk_level})\n"
        memo_text += f"- النص بالعقد: {item.contract_snippet}\n"
        memo_text += f"- السند: {item.legal_reference}\n"
        memo_text += f"- التحليل: {item.analysis}\n"
        if item.recommendation:
            memo_text += f"- التوصية البديلة: {item.recommendation}\n"

    st.download_button(
        label="📥 تحميل مذكرة الفحص القانوني (Markdown / Text)",
        data=memo_text,
        file_name="legal_due_diligence_report.md",
        mime="text/markdown",
        use_container_width=True
    )