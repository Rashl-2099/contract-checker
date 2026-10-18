"""
قاعدة المعرفة القانونية: نظام العمل + القواعد الإلزامية للعقود التجارية والإيجار والخدمات التقنية والسرية
"""

# 1. قواعد عقود العمل (الأفراد والمنشآت)
SAUDI_LABOR_LAW_RULES = """
قواعد نظام العمل السعودي الإلزامية:
1. فترة التجربة (المادة 53): الأصل ألا تزيد على 90 يوماً، وتصل لـ 180 يوماً فقط بموافقة كتابية صريحة، ولا يجوز وضع العامل تحت التجربة أكثر من مرة لدى صاحب العمل نفسه.
2. ساعات العمل (المادة 98): الحد الأقصى 8 ساعات يومياً أو 48 ساعة أسبوعياً، والعمل الإضافي (المادة 107) يستحق عنه أجر إضافي يوازي أجر الساعة مضافاً إليه 50% من الأجر الأساسي.
3. مهلة الإشعار (المادة 75): لا تقل عن 60 يوماً للعقود غير المحددة المدة، و30 يوماً للمحددة المدة، والفسخ دون إشعار مقصور على الحالات الواردة في المادة 80.
4. الإجازة السنوية (المادة 109): لا تقل عن 21 يوماً (تزداد إلى 30 يوماً بعد 5 سنوات خدمة متصلة)، ولا يجوز التنازل عنها.
5. شرط عدم المنافسة (المادة 83): لا تتجاوز مدته سنتين مع تحديد المكان ونوع العمل بدقة.
6. مكافأة نهاية الخدمة (المادة 84): حق نظامي للعامل، وكل شرط يخالف أحكام النظام يقع باطلاً ما لم يكن أكثر فائدة للعامل (المادة 8).
"""

# 2. قواعد العقود التجارية وعقود الشركات (B2B / عقود التوريد والخدمات والسرية)
COMMERCIAL_CONTRACT_RULES = """
المعايير النظامية لفحص عقود الشركات والتوريد والخدمات التجارية (B2B):
1. سقف المسؤولية والتعويض (Limitation of Liability):
- يجب أن يتضمن العقد سقفاً مالياً محدداً للمسؤولية (مثل: ألا تتجاوز قيمة المبالغ المدفوعة أو نسبة مئوية محددة)، والبند الذي يفرض مسؤولية تعويضية مطلقة وغير محدودة يعد عالي المخاطر.

2. الشرط الجزائي وغرامات التأخير (Penalties & Delay Fines):
- يجب أن تكون غرامات التأخير منطقية (المعيار التجاري الشائع لا يتجاوز 10% إلى 20% كحد أقصى من قيمة العقد الإجمالية). الشروط الجزائية المبالغ فيها أو المفتوحة تشكل إجحافاً ومخاطرة نظامية.

3. سرية المعلومات (Confidentiality & NDA):
- يجب تحديد مدة سريان التزام السرية بعد انتهاء العقد (المعتاد تجارياً: من 2 إلى 5 سنوات). شروط السرية الأبدية أو غير المحددة زمنياً غير عملية وتشكل التزاماً مفرطاً.

4. آلية إنهاء العقد والإشعار (Termination for Convenience / Breach):
- يجب توفير مهلة إشعار كتابي عادلة للتصحيح (Cure Period) قبل الإنهاء بسبب الإخلال (عادة 14 إلى 30 يوماً)، والإنهاء الفوري دون مبرر أو إشعار يعد بنداً تعسفياً.

5. فض النزاعات والقوة القاهرة (Dispute Resolution & Force Majeure):
- يجب تحديد المحكمة التجارية المختصة مكانياً أو هيئة التحكيم، مع وجود نص صريح يعفي الأطراف في حالات القوة القاهرة والظروف الطارئة.

6. شروط الدفع والملكية الفكرية:
- مدة السداد المعتادة 30 إلى 60 يوماً من تاريخ الفاتورة، والملكية الفكرية السابقة للمزود (Background IP) تبقى له مع منح ترخيص استخدام.
"""

# 3. قواعد عقود الإيجار العقاري
LEASE_CONTRACT_RULES = """
المعايير النظامية لفحص عقود الإيجار العقاري (السكني والتجاري):
1. زيادة الأجرة: يجب أن تكون القيمة الإيجارية ثابتة خلال مدة العقد أو أن تحدد الزيادة بنسبة وموعد معلومين، والزيادة الأحادية في أي وقت تعد شرطاً تعسفياً.
2. مبلغ الضمان (التأمين): يسترد عند انتهاء العقد بعد خصم الأضرار الموثقة فقط، والنص على عدم استرداده بأي حال إجحاف بالمستأجر.
3. الصيانة: الصيانة الإنشائية والجوهرية (الهيكل، الأسقف، التمديدات الرئيسية) على المؤجر، والصيانة التشغيلية البسيطة على المستأجر.
4. الإخلاء والفسخ: يجب منح المستأجر مهلة إنذار معقولة (لا تقل عادة عن 30 يوماً) لسداد المتأخرات قبل الفسخ.
5. التجديد: مهلة الإشعار بعدم التجديد يجب أن تكون معقولة (30 إلى 90 يوماً)، والمهل الطويلة جداً تقيّد المستأجر.
6. التوثيق: يوصى بتوثيق العقد في الشبكة الإلكترونية لخدمات الإيجار (منصة إيجار) ليكون سنداً تنفيذياً.
"""

# 4. قواعد عقود الخدمات التقنية والاشتراكات السحابية (SaaS)
SAAS_CONTRACT_RULES = """
المعايير النظامية لفحص عقود الخدمات التقنية والاشتراكات السحابية (SaaS):
1. اتفاقية مستوى الخدمة (SLA): يجب تحديد نسبة توفر لا تقل عادة عن 99.5% مع تعويضات (Service Credits) عند الإخلال، وتقديم الخدمة "كما هي" دون ضمان يعد عالي المخاطر.
2. حماية البيانات: الالتزام بنظام حماية البيانات الشخصية، وعدم نقل البيانات خارج المملكة أو مشاركتها مع أطراف ثالثة إلا وفق الضوابط النظامية وبموافقة العميل.
3. ملكية البيانات: بيانات العميل ومحتواه ملك له، مع حقه في استرجاعها كاملة عند انتهاء العقد.
4. الأسعار: لا يجوز للمزود تعديل الرسوم بشكل أحادي خلال مدة الاشتراك، أو يجب ربط ذلك بإشعار كاف (60 يوماً على الأقل) وحق العميل في الإنهاء.
5. سقف المسؤولية: يجب أن يكون السقف متناسباً (عادة رسوم 12 شهراً)، والسقف الرمزي (رسوم شهر واحد) يفرغ الالتزام من مضمونه.
6. القانون الواجب التطبيق: يفضل إخضاع العقد للأنظمة السعودية وجهات التقاضي أو التحكيم داخل المملكة.
"""

# 5. قواعد اتفاقيات عدم الإفصاح والسرية (NDA)
NDA_CONTRACT_RULES = """
المعايير النظامية لفحص اتفاقيات عدم الإفصاح والسرية (NDA):
1. تعريف المعلومات السرية: يجب أن يكون محدداً ويستثني المعلومات المتاحة للعموم، والمعروفة مسبقاً للطرف المتلقي، والمطورة باستقلالية، وما يلزم الإفصاح عنه نظاماً.
2. مدة الالتزام: المعتاد من 2 إلى 5 سنوات بعد انتهاء الاتفاقية، والالتزام الأبدي غير عملي ويصعب إنفاذه (باستثناء الأسرار التجارية المعرّفة بدقة).
3. التعويض الاتفاقي: يجب أن يكون متناسباً مع الضرر المتوقع، والمبالغ الجزافية الضخمة عن كل مخالفة دون إثبات ضرر قابلة للتخفيض قضاءً وتشكل مخاطرة مالية كبيرة.
4. عدم الاستقطاب وعدم المنافسة: يجب تحديده بمدة لا تتجاوز سنتين ونطاق جغرافي ونوعي واضح.
5. إعادة المعلومات وإتلافها: يجب تنظيم آلية إعادة أو إتلاف المعلومات عند انتهاء الاتفاقية.
"""

# ---------------------------------------------------------------------------
# النسخة الإنجليزية من القواعد (تُستخدم عند اختيار واجهة English)
# ---------------------------------------------------------------------------
SAUDI_LABOR_LAW_RULES_EN = """
Mandatory rules of the Saudi Labor Law:
1. Probation (Article 53): should not exceed 90 days, extendable to a total of 180 days only by explicit written agreement; an employee may not be placed on probation more than once with the same employer.
2. Working hours (Article 98): maximum 8 hours per day or 48 hours per week; overtime (Article 107) is paid at the hourly wage plus 50% of the basic wage.
3. Notice period (Article 75): at least 60 days for indefinite contracts and 30 days for fixed-term contracts; termination without notice is limited to the cases in Article 80.
4. Annual leave (Article 109): at least 21 days (30 days after 5 years of continuous service) and may not be waived.
5. Non-compete (Article 83): may not exceed two years and must specify the place and type of work.
6. End-of-service award (Article 84): a statutory right of the employee; any condition contrary to the Law is void unless more beneficial to the employee (Article 8).
"""

COMMERCIAL_CONTRACT_RULES_EN = """
Standards for reviewing business, supply and commercial service contracts (B2B):
1. Limitation of liability: the contract should set a specific financial cap (e.g. amounts paid or a set percentage); absolute, unlimited liability is high risk.
2. Penalties and delay fines: delay penalties should be reasonable (common commercial practice does not exceed 10%-20% of the total contract value); excessive or open-ended penalties are unfair and a legal risk.
3. Confidentiality: the duration of the confidentiality obligation after expiry should be specified (typically 2 to 5 years); perpetual or indefinite confidentiality is impractical and excessive.
4. Termination and notice: a fair written notice and cure period (usually 14 to 30 days) should precede termination for breach; immediate termination without cause or notice is abusive.
5. Disputes and force majeure: the competent court or arbitral body should be specified, with an explicit clause excusing the parties in force majeure events.
6. Payment and intellectual property: usual payment terms are 30 to 60 days from invoice; the supplier's pre-existing IP (background IP) stays with the supplier with a licence granted.
"""

LEASE_CONTRACT_RULES_EN = """
Standards for reviewing real-estate lease contracts (residential and commercial):
1. Rent increase: rent should be fixed for the term, or any increase must have a known rate and date; a unilateral increase at any time is abusive.
2. Security deposit: refundable at expiry after deducting documented damage only; a deposit that is non-refundable in all cases is unfair to the tenant.
3. Maintenance: structural and major maintenance (structure, roofs, main installations) is the landlord's; minor operational maintenance is the tenant's.
4. Eviction and termination: the tenant should get a reasonable warning period (usually at least 30 days) to pay arrears before termination.
5. Renewal: the non-renewal notice period should be reasonable (30 to 90 days); very long notice periods restrict the tenant.
6. Registration: the lease should be registered on the Ejar platform to become an enforceable instrument.
"""

SAAS_CONTRACT_RULES_EN = """
Standards for reviewing technical services and cloud subscription (SaaS) contracts:
1. Service level agreement (SLA): availability of at least 99.5% with service credits for breaches; providing the service "as is" without any guarantee is high risk.
2. Data protection: comply with the Personal Data Protection Law (PDPL); no transfer of data outside the Kingdom or sharing with third parties except under the legal controls and with the client's consent.
3. Data ownership: client data and content belong to the client, with the right to retrieve it in full at expiry.
4. Pricing: the provider may not change fees unilaterally during the subscription, or must give adequate notice (at least 60 days) with the client's right to terminate.
5. Liability cap: the cap should be proportionate (typically 12 months of fees); a token cap (one month of fees) empties the obligation of meaning.
6. Governing law: the contract should preferably be governed by Saudi law with courts or arbitration inside the Kingdom.
"""

NDA_CONTRACT_RULES_EN = """
Standards for reviewing non-disclosure and confidentiality agreements (NDA):
1. Definition of confidential information: must be specific and exclude publicly available information, information already known to the recipient, independently developed information, and information required to be disclosed by law.
2. Duration: usually 2 to 5 years after expiry; a perpetual obligation is impractical and hard to enforce (except for precisely defined trade secrets).
3. Liquidated damages: must be proportionate to the expected harm; huge lump sums per breach without proof of damage may be reduced by courts and are a major financial risk.
4. Non-solicitation and non-compete: should not exceed two years with a clear geographic and subject scope.
5. Return and destruction: the agreement should regulate returning or destroying information at expiry.
"""

# خريطة تصنيفات العقود المدعومة في المنصة
# parties = (الطرف الأضعف الذي نمثله في التفاوض، الطرف الأقوى صاحب الصياغة)
CONTRACT_TYPES = {
    "عقد شركات / تجاري وتوريد (B2B)": {
        "label": "عقود الشركات والتوريد التجاري (B2B)",
        "rules": COMMERCIAL_CONTRACT_RULES,
        "demo_note": "تم تحميل نموذج عقد شركات وتوريد لاختبار الفخاخ والشروط الجزائية.",
        "parties": ("ممثل المزود (الطرف الثاني)", "ممثل العميل (الطرف الأول)"),
        "name_en": "Business / Commercial & Supply (B2B)",
        "label_en": "Business and Commercial Supply Contract (B2B)",
        "rules_en": COMMERCIAL_CONTRACT_RULES_EN,
        "demo_note_en": "A sample B2B supply contract was loaded to test traps and penalty clauses.",
        "parties_en": ("Provider's Representative (Second Party)", "Client's Representative (First Party)"),
    },
    "عقد عمل (أفراد ومنشآت)": {
        "label": "عقد عمل (نظام العمل السعودي)",
        "rules": SAUDI_LABOR_LAW_RULES,
        "demo_note": "تم تحميل نموذج عقد عمل لاختبار المخالفات النظامية.",
        "parties": ("ممثل الموظف", "ممثل الشركة"),
        "name_en": "Employment Contract (Individuals & Companies)",
        "label_en": "Employment Contract (Saudi Labor Law)",
        "rules_en": SAUDI_LABOR_LAW_RULES_EN,
        "demo_note_en": "A sample employment contract was loaded to test legal violations.",
        "parties_en": ("Employee's Representative", "Company's Representative"),
    },
    "عقد إيجار عقاري": {
        "label": "عقد إيجار عقاري (سكني / تجاري)",
        "rules": LEASE_CONTRACT_RULES,
        "demo_note": "تم تحميل نموذج عقد إيجار لاختبار شروط الزيادة والضمان والصيانة.",
        "parties": ("ممثل المستأجر", "ممثل المؤجر"),
        "name_en": "Real-Estate Lease",
        "label_en": "Real-Estate Lease (Residential / Commercial)",
        "rules_en": LEASE_CONTRACT_RULES_EN,
        "demo_note_en": "A sample lease was loaded to test rent increase, deposit and maintenance terms.",
        "parties_en": ("Tenant's Representative", "Landlord's Representative"),
    },
    "عقد خدمات تقنية / اشتراك سحابي (SaaS)": {
        "label": "عقد خدمات تقنية واشتراك سحابي (SaaS)",
        "rules": SAAS_CONTRACT_RULES,
        "demo_note": "تم تحميل نموذج اشتراك سحابي لاختبار مستوى الخدمة وحماية البيانات.",
        "parties": ("ممثل العميل المشترك", "ممثل مزود الخدمة"),
        "name_en": "Tech Services / Cloud Subscription (SaaS)",
        "label_en": "Technical Services and Cloud Subscription (SaaS)",
        "rules_en": SAAS_CONTRACT_RULES_EN,
        "demo_note_en": "A sample cloud subscription was loaded to test service levels and data protection.",
        "parties_en": ("Subscriber's Representative", "Service Provider's Representative"),
    },
    "اتفاقية عدم إفصاح وسرية (NDA)": {
        "label": "اتفاقية عدم إفصاح وسرية (NDA)",
        "rules": NDA_CONTRACT_RULES,
        "demo_note": "تم تحميل نموذج اتفاقية سرية لاختبار نطاق المعلومات والتعويض الاتفاقي.",
        "parties": ("ممثل الطرف المتلقي", "ممثل الطرف المفصح"),
        "name_en": "Non-Disclosure Agreement (NDA)",
        "label_en": "Non-Disclosure and Confidentiality Agreement (NDA)",
        "rules_en": NDA_CONTRACT_RULES_EN,
        "demo_note_en": "A sample NDA was loaded to test the information scope and liquidated damages.",
        "parties_en": ("Receiving Party's Representative", "Disclosing Party's Representative"),
    },
}


def type_info(category: str, lang: str = "ar") -> dict:
    """بيانات التصنيف باللغة المطلوبة (المفتاح الداخلي للتصنيف يبقى عربياً)."""
    info = CONTRACT_TYPES.get(category, {})
    if lang == "en":
        return {"name": info.get("name_en", category), "label": info.get("label_en", category),
                "rules": info.get("rules_en", COMMERCIAL_CONTRACT_RULES_EN), "demo_note": info.get("demo_note_en", ""),
                "parties": info.get("parties_en", ("Second Party's Representative", "First Party's Representative"))}
    return {"name": category, "label": info.get("label", category), "rules": info.get("rules", COMMERCIAL_CONTRACT_RULES),
            "demo_note": info.get("demo_note", ""), "parties": info.get("parties", ("ممثل الطرف الثاني", "ممثل الطرف الأول"))}
