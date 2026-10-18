"""
طبقة الترجمة: نصوص الواجهة بالعربية والإنجليزية، وتعريب/ترجمة القيم الثابتة في التقرير.
القيم الداخلية (التصنيفات، الحالات، مستويات الخطورة) تبقى عربية في الكود وقاعدة البيانات،
وتُترجم عند العرض فقط.
"""
from typing import Optional

LANGS = {"ar": "العربية", "en": "English"}

# key: (عربي, English)
STRINGS = {
    # عام
    "page_title": ("منصة تدقيق العقود الشاملة | Legal Due Diligence", "Contract Due Diligence Platform | Legal Due Diligence"),
    "app_title": ("⚖️ منصة تدقيق العقود والفحص النافي للجهالة", "⚖️ Contract Audit & Legal Due Diligence Platform"),
    "app_title_en_part": ("(Legal Due Diligence)", ""),
    "app_caption": ("كاشف الفخاخ، محاكي التفاوض، وتصدير التقارير، قاعدة بيانات SQLite، نظام متكامل مبني بواسطة LangChain",
                    "Trap detector, negotiation simulator and report export, with an SQLite database — an integrated system built with LangChain"),
    "language": ("اللغة / Language", "Language / اللغة"),
    "disclaimer": ("⚠️ هذا التحليل استرشادي صادر عن نظام آلي، ولا يغني عن مراجعة محامٍ مرخص قبل التوقيع.",
                   "⚠️ This analysis is indicative and produced by an automated system; it does not replace review by a licensed lawyer before signing."),

    # الشريط الجانبي
    "settings": ("⚙️ إعدادات التدقيق", "⚙️ Audit Settings"),
    "choose_category": ("اختر تصنيف العقد:", "Contract type:"),
    "source": ("مصدر المستند:", "Document source:"),
    "src_demo": ("نموذج تجريبي جاهز (Demo)", "Ready-made sample (Demo)"),
    "src_pdf": ("رفع ملف PDF", "Upload a PDF"),
    "src_text": ("لصق نص العقد", "Paste contract text"),
    "upload_label": ("ارفع وثيقة العقد (PDF)", "Upload the contract (PDF)"),
    "pdf_ok": ("تمت قراءة الملف بنجاح ({pages} صفحة)", "File read successfully ({pages} pages)"),
    "pdf_empty": ("الملف لا يحتوي على نص قابل للاستخراج (قد يكون صورة ممسوحة ضوئياً).",
                  "The file has no extractable text (it may be a scanned image)."),
    "pdf_error": ("تعذرت قراءة الملف: {err}", "Could not read the file: {err}"),
    "paste_label": ("الصق نص العقد هنا:", "Paste the contract text here:"),
    "paste_placeholder": ("المادة (1) ...", "Article (1) ..."),
    "engine_box": ("🤖 محرك التحليل (LangChain)", "🤖 Analysis engine (LangChain)"),
    "engine_method": ("طريقة الفحص:", "Audit method:"),
    "eng_auto": ("تلقائي (LangChain عند توفر المفتاح)", "Automatic (LangChain when a key is available)"),
    "eng_llm": ("LangChain + OpenAI فقط", "LangChain + OpenAI only"),
    "eng_rules": ("المحرك المحلي (بدون إنترنت)", "Local engine (offline)"),
    "key_ok": ("🟢 مفتاح OpenAI مهيأ في ملف .env — سيتم التحليل عبر LangChain.", "🟢 OpenAI key configured in .env — analysis will run through LangChain."),
    "key_missing": ("⚪ لا يوجد مفتاح OpenAI — سيعمل المحرك المحلي للخبير القانوني.", "⚪ No OpenAI key — the local legal expert engine will be used."),
    "run": ("🚀 بدء الفحص والتدقيق الشامل", "🚀 Run full audit"),
    "running": ("جاري الفحص والتدقيق الشامل...", "Running the full audit..."),
    "step_read": ("📄 قراءة المستند وتجهيز النص...", "📄 Reading the document and preparing the text..."),
    "step_check": ("🔍 فحص البنود ومطابقتها مع الأنظمة والمعايير...", "🔍 Checking clauses against laws and standards..."),
    "step_traps": ("🚨 رصد الفخاخ التعاقدية وتقدير المخاطر...", "🚨 Detecting contractual traps and assessing risk..."),
    "step_save": ("🗄️ حفظ السجل في قاعدة بيانات SQLite...", "🗄️ Saving the record to the SQLite database..."),
    "done": ("اكتمل الفحص بنجاح ✅", "Audit completed ✅"),
    "need_input": ("الرجاء اختيار نموذج أو رفع ملف أو لصق نص العقد أولاً.", "Please choose a sample, upload a file or paste the contract text first."),
    "history": ("🗄️ سجل الفحوصات", "🗄️ Audit history"),
    "history_score": ("درجة الأمان: `{score}%` | ملاحظات: `{issues}` | فخاخ: `{traps}`",
                      "Safety score: `{score}%` | Issues: `{issues}` | Traps: `{traps}`"),
    "open": ("📂 عرض", "📂 Open"),
    "delete": ("🗑️ حذف", "🗑️ Delete"),
    "clear_all": ("🧹 مسح السجل بالكامل", "🧹 Clear all history"),
    "no_history": ("لا توجد سجلات محفوظة حتى الآن.", "No saved records yet."),

    # الصفحة الرئيسية
    "stat_total": ("إجمالي الفحوصات المؤرشفة", "Archived audits"),
    "stat_avg": ("متوسط مؤشر السلامة", "Average safety score"),
    "stat_traps": ("إجمالي الفخاخ المرصودة", "Total traps detected"),
    "how_title": ("كيف تعمل المنصة؟", "How does it work?"),
    "how1_t": ("1️⃣ اختر المستند", "1️⃣ Choose a document"),
    "how1_b": ("حدد تصنيف العقد (عمل، شركات، إيجار، SaaS، سرية) ثم استخدم النموذج التجريبي أو ارفع ملف PDF أو الصق النص.",
               "Pick the contract type (employment, B2B, lease, SaaS, NDA), then use the sample, upload a PDF or paste the text."),
    "how2_t": ("2️⃣ فحص شامل", "2️⃣ Full audit"),
    "how2_b": ("يطابق المحرك كل بند مع الأنظمة والمعايير، ويستخرج البيانات الجوهرية ويرصد الفخاخ القاتلة.",
               "The engine checks every clause against laws and standards, extracts the key data and flags killer clauses."),
    "how3_t": ("3️⃣ فاوض وصدّر", "3️⃣ Negotiate & export"),
    "how3_b": ("شغّل محاكي التفاوض على البنود المعيبة للوصول لصياغة متوازنة، ثم حمّل مذكرة الفحص القانوني.",
               "Run the negotiation simulator on flawed clauses to reach balanced wording, then download the legal memo."),
    "start_hint": ("👈 ابدأ من الشريط الجانبي بالضغط على زر **بدء الفحص والتدقيق الشامل**.",
                   "👈 Start from the sidebar by pressing **Run full audit**."),

    # النتائج
    "m_score": ("مؤشر السلامة القانونية", "Legal safety score"),
    "m_delta": ("{d:+d}% عن الفحص السابق", "{d:+d}% vs previous audit"),
    "m_issues": ("بنود غير متوازنة", "Unbalanced clauses"),
    "m_critical": ("مخاطر قانونية حرجة", "Critical legal risks"),
    "m_traps": ("فخاخ تعاقدية مرصودة", "Contractual traps"),
    "meta_title": ("📌 بطاقة البيانات الجوهرية والالتزامات", "📌 Contract Metadata & Obligations"),
    "meta_title_en_part": ("(Contract Metadata)", ""),
    "parties": ("أطراف التعاقد", "Parties"),
    "duration": ("المدة والسريان", "Term and effectiveness"),
    "financial": ("المقابل المالي وشروط الدفع", "Consideration and payment terms"),
    "renewal": ("أحكام التجديد والإنهاء", "Renewal and termination"),
    "not_set": ("غير محدد", "Not specified"),
    "summary": ("📋 الملخص التنفيذي", "📋 Executive summary"),
    "traps_title": ("🚨 رادار الفخاخ التعاقدية والشروط الخطرة", "🚨 Contractual Traps Radar"),
    "traps_title_en_part": ("(Killer Clauses)", "(Killer Clauses)"),
    "trap_prefix": ("فخ", "Trap"),
    "no_traps": ("لم يتم رصد فخاخ تعاقدية في هذا العقد. 👏", "No contractual traps were found in this contract. 👏"),
    "clauses_title": ("🔍 تفاصيل فحص البنود ومحاكي التفاوض الآلي", "🔍 Clause Review & Negotiation Simulator"),
    "view_all": ("الكل", "All"),
    "view_issues": ("المخالفات والمخاطر فقط", "Issues & risks only"),
    "view_ok": ("المتوافقة فقط", "Compliant only"),
    "dimension": ("البعد", "Dimension"),
    "status": ("الحالة", "Status"),
    "quote": ("النص المقتبس من العقد:", "Quoted contract text:"),
    "analysis": ("التحليل الفني", "Analysis"),
    "reference": ("السند القانوني / المعيار", "Legal basis / standard"),
    "risk_level": ("مستوى الخطورة", "Risk level"),
    "alt_wording": ("💡 **الصياغة البديلة المقترحة:**", "💡 **Suggested alternative wording:**"),
    "negotiate_btn": ("🤝 تشغيل محاكي التفاوض الآلي لهذا البند", "🤝 Run the negotiation simulator for this clause"),
    "negotiating": ("🤖 جاري التفاوض الآلي بين الوكلاء للوصول إلى تسوية عادلة...", "🤖 The agents are negotiating a fair settlement..."),
    "minutes": ("#### 💬 محضر جلسة التفاوض الافتراضية:", "#### 💬 Negotiation session transcript:"),
    "agreed": ("📜 **الصيغة التوافقية المتفق عليها {ww}:**", "📜 **Agreed wording {ww}:**"),
    "gains": ("مكاسب {p}", "Gains for {p}"),
    "export_title": ("📄 تصدير مذكرة الفحص القانوني", "📄 Export the Legal Due Diligence Memo"),
    "download_md": ("📥 تحميل مذكرة الفحص القانوني (Markdown / Text)", "📥 Download the legal memo (Markdown / Text)"),
    "download_json": ("🧾 تصدير بيانات الفحص (JSON)", "🧾 Export audit data (JSON)"),
    "show_text": ("📜 عرض نص العقد المفحوص", "📜 Show the audited contract text"),
    "memo_file": ("مذكرة_الفحص_القانوني.md", "legal_due_diligence_memo.md"),

    # المذكرة
    "memo_title": ("# مذكرة الفحص القانوني النافي للجهالة (Legal Due Diligence Memo)", "# Legal Due Diligence Memo"),
    "memo_date": ("تاريخ التقرير", "Report date"),
    "memo_category": ("تصنيف العقد", "Contract type"),
    "memo_source": ("مصدر المستند", "Document source"),
    "memo_engine": ("محرك التحليل", "Analysis engine"),
    "memo_score": ("مؤشر السلامة القانونية", "Legal safety score"),
    "memo_counts": ("**بنود غير متوازنة:** {i} | **مخاطر حرجة:** {c} | **فخاخ مرصودة:** {t}",
                    "**Unbalanced clauses:** {i} | **Critical risks:** {c} | **Traps detected:** {t}"),
    "memo_s1": ("## 1. الملخص التنفيذي", "## 1. Executive Summary"),
    "memo_s2": ("## 2. بطاقة البيانات الجوهرية", "## 2. Contract Metadata"),
    "memo_s3": ("## 3. الفخاخ والشروط القاتلة المرصودة", "## 3. Detected Traps and Killer Clauses"),
    "memo_no_traps": ("- لم يتم رصد فخاخ تعاقدية.", "- No contractual traps were detected."),
    "memo_s4": ("## 4. نتائج فحص البنود", "## 4. Clause Review Results"),
    "memo_sev": ("خطورة", "risk"),
    "memo_alt": ("الصياغة البديلة المقترحة", "Suggested alternative wording"),
    "memo_neg": ("**محضر جلسة التفاوض الآلي:**", "**Automated negotiation transcript:**"),
    "memo_agreed": ("الصيغة التوافقية (Win-Win)", "Agreed wording (Win-Win)"),
    "memo_disclaimer": ("_هذه المذكرة استرشادية صادرة عن نظام آلي، ولا تغني عن مراجعة محامٍ مرخص قبل التوقيع._",
                        "_This memo is indicative, produced by an automated system, and does not replace review by a licensed lawyer before signing._"),
}

STATUS = {"متوافق": "Compliant", "مخالف": "Non-compliant", "مبهم / عالي المخاطر": "Ambiguous / High risk", "غير مذكور": "Not mentioned"}
LEVEL = {"منخفض": "Low", "متوسط": "Medium", "حرج": "Critical"}
DIMENSION = {"نظامي وقانوني": "Legal & Regulatory", "مالي وتعويضي": "Financial & Compensation",
             "تشغيلي وإجرائي": "Operational & Procedural", "سرية وحقوق فكرية": "Confidentiality & IP"}
SEVERITY = {"حرج جداً": "Very critical", "متوسط": "Medium"}
ENGINE = {"llm": ("LangChain + OpenAI", "LangChain + OpenAI"), "rules": ("المحرك المحلي للخبير القانوني", "Local legal expert engine")}


def tr(key: str, lang: str, **kwargs) -> str:
    text = STRINGS[key][1 if lang == "en" else 0]
    return text.format(**kwargs) if kwargs else text


def show(value: str, lang: str) -> str:
    """يترجم القيم الثابتة (الحالة، الخطورة، البعد) عند العرض بالإنجليزية."""
    if lang != "en":
        return value
    for table in (STATUS, LEVEL, DIMENSION, SEVERITY):
        if value in table:
            return table[value]
    return value


def engine_label(engine: Optional[str], lang: str) -> str:
    pair = ENGINE.get(engine or "", None)
    return pair[1 if lang == "en" else 0] if pair else "—"


def source_label(source: Optional[str], lang: str) -> str:
    """مصدر المستند يُحفظ كرمز (demo / text / pdf:اسم الملف)؛ السجلات القديمة تُعرض كما هي."""
    if not source:
        return "—"
    if source == "demo":
        return tr("src_demo", lang)
    if source == "text":
        return "Pasted text" if lang == "en" else "نص ملصق"
    if source.startswith("pdf:"):
        return ("PDF file: " if lang == "en" else "ملف PDF: ") + source[4:]
    return source
