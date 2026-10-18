"""
محاكي التفاوض الآلي (Multi-Agent Negotiation)
- المسار الأساسي: وكلاء LangChain + OpenAI يديرون حواراً تفاوضياً حقيقياً.
- المسار الاحتياطي: قوالب تفاوض خبيرة تعمل محلياً دون اتصال.
"""
import os
import re
from typing import Optional, Tuple

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

from labor_law_data import type_info
from schemas import NegotiationSession, NegotiationTurn

load_dotenv()


def llm_available() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or "your_" in key:
        return False
    try:
        import langchain_openai  # noqa: F401
    except ImportError:
        return False
    return True


def _get_llm(temperature: float):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=temperature, timeout=90, max_retries=1)


def _parties(contract_category: Optional[str], lang: str = "ar") -> Tuple[str, str]:
    return type_info(contract_category or "", lang)["parties"]


# ---------------------------------------------------------------------------
# 1. المسار الأساسي: LangChain (LCEL + Structured Output)
# ---------------------------------------------------------------------------
def run_negotiation(clause_title: str, problematic_text: str, issue_context: str,
                    contract_category: Optional[str] = None, lang: str = "ar") -> NegotiationSession:
    weak, strong = _parties(contract_category, lang)
    if lang == "en":
        return _run_negotiation_en(clause_title, problematic_text, issue_context, weak, strong)

    system_prompt = """أنت محاكي جلسات تفاوض قانونية وتجارية ذكي (Legal Negotiation Simulator) يعمل وفق الأنظمة السعودية.
أمامك بند تعاقدي غير متوازن أو مخالف للنظام. مهمتك إدارة حوار تفاوضي افتراضي ومقنع من 4 إلى 6 جولات بين وكيلين يتناوبان الحديث، ويبدأ الحوار بالوكيل الأول:

1. [{weak}]: يرفض النص المعيب بلباقة، ويستند للنظام والعدالة العقدية والمعايير التجارية، ويطلب تعديلاً منصفاً بأرقام محددة.
2. [{strong}]: يتفهم الطلب لكنه يحرص على عدم التفريط في حقوقه وحمايته التشغيلية، ويقترح حلاً وسطاً.
3. [الصياغة التوافقية]: صياغة بند قانوني رصين بالعربية الفصحى يحقق التوازن الكامل (Win-Win) دون مخالفة أي نظام.

استخدم في حقل speaker الاسمين حرفياً: "{weak}" و"{strong}". اجعل benefits_for_party_a لمكاسب {strong} و benefits_for_party_b لمكاسب {weak}."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", """البند محل النزاع: {clause_title}
النص في العقد: "{problematic_text}"
المشكلة أو المخالفة: {issue_context}

ابدأ جولة التفاوض واستخرج النتيجة التوافقية النهائية."""),
    ])

    chain = prompt | _get_llm(0.3).with_structured_output(NegotiationSession)
    return chain.invoke({
        "weak": weak, "strong": strong,
        "clause_title": clause_title,
        "problematic_text": problematic_text,
        "issue_context": issue_context,
    })


def _run_negotiation_en(clause_title, problematic_text, issue_context, weak, strong) -> NegotiationSession:
    system_prompt = """You are an intelligent legal and commercial negotiation simulator (Legal Negotiation Simulator) operating under Saudi law.
You are given an unbalanced or non-compliant contract clause. Run a persuasive simulated negotiation of 4 to 6 rounds between two agents who take turns speaking, starting with the first agent:

1. [{weak}]: politely rejects the defective wording, relies on the law, contractual fairness and commercial standards, and requests a fair amendment with specific figures.
2. [{strong}]: understands the request but is careful not to give up its rights and operational protection, and proposes a compromise.
3. [Agreed wording]: draft a sound legal clause in clear English that achieves full balance (Win-Win) without violating any law.

Use exactly these two names in the speaker field: "{weak}" and "{strong}". Put {strong}'s gains in benefits_for_party_a and {weak}'s gains in benefits_for_party_b. Write every field in English."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", """Disputed clause: {clause_title}
Contract text: "{problematic_text}"
Problem or violation: {issue_context}

Start the negotiation and produce the final agreed outcome."""),
    ])
    chain = prompt | _get_llm(0.3).with_structured_output(NegotiationSession)
    return chain.invoke({"weak": weak, "strong": strong, "clause_title": clause_title,
                         "problematic_text": problematic_text, "issue_context": issue_context})


# ---------------------------------------------------------------------------
# 2. المسار الاحتياطي: قوالب التفاوض الخبيرة
# ---------------------------------------------------------------------------
# كل قالب: (افتتاح الطرف الأضعف، رد الطرف الأقوى، المقترح المضاد، الإغلاق، الصياغة التوافقية، مكاسب الأقوى، مكاسب الأضعف)
TEMPLATES = {
    "late_penalty": (
        "غرامة بهذه النسبة تلتهم كامل هامش الربح من أول تأخير بسيط، والمعيار التجاري لا يتجاوز 10% من قيمة العقد، كما يملك القضاء تخفيض الشرط الجزائي المبالغ فيه.",
        "الالتزام بالجدول الزمني جوهري لنا، وأي تأخير يعطل عملياتنا ويكبدنا خسائر فعلية، لذلك نحتاج إلى رادع قوي.",
        "نتفق على أهمية الرادع؛ لذا نقترح غرامة تدريجية 0.5% أسبوعياً من قيمة المرحلة المتأخرة فقط، بحد أقصى 10%، مع مهلة تصحيح 7 أيام بعد الإشعار.",
        "نقبل الغرامة التدريجية بشرط رفع السقف إلى 10% من القيمة الإجمالية، وحقنا في الإنهاء إذا بلغت الغرامة سقفها.",
        "في حال التأخير لأسباب تعود للمزود، تحتسب غرامة بنسبة 0.5% من قيمة المرحلة المتأخرة عن كل أسبوع تأخير، بحد أقصى 10% من القيمة الإجمالية للعقد، بعد إشعار كتابي ومهلة تصحيح 7 أيام، ويحق للعميل الإنهاء إذا بلغت الغرامات سقفها.",
        "رادع فعال ومتدرج للتأخير مع حق الإنهاء عند بلوغ السقف.",
        "سقف واضح للغرامة يحمي هامش الربح، وتحميل الغرامة على المرحلة المتأخرة فقط مع مهلة تصحيح.",
    ),
    "liability": (
        "المسؤولية غير المحدودة عن الأضرار غير المباشرة وفوات الأرباح مخاطرة لا يمكن تأمينها، وقد تتجاوز قيمة العقد أضعافاً.",
        "نحتاج إلى ضمان التعويض الكامل إذا تسبب النظام في توقف أعمالنا.",
        "نقترح سقفاً يعادل قيمة المبالغ المدفوعة خلال 12 شهراً، مع استثناء الأضرار غير المباشرة، وإبقاء المسؤولية مفتوحة فقط في حالات الغش والخطأ الجسيم وانتهاك السرية.",
        "نقبل ذلك على أن يكون السقف مساوياً لقيمة العقد الإجمالية، وأن يلتزم المزود بوثيقة تأمين مسؤولية مهنية.",
        "لا تتجاوز المسؤولية الإجمالية لأي من الطرفين القيمة الإجمالية للعقد، ولا يسأل أي طرف عن الأضرار غير المباشرة أو فوات الأرباح، وذلك فيما عدا حالات الغش أو الخطأ الجسيم أو الإخلال بالسرية، ويلتزم المزود بالاحتفاظ بوثيقة تأمين مسؤولية مهنية سارية طوال مدة العقد.",
        "سقف تعويض مرتفع يغطي قيمة العقد، مع تأمين مهني يضمن الملاءة.",
        "مخاطر محددة وقابلة للتأمين، واستبعاد الأضرار غير المباشرة.",
    ),
    "confidentiality": (
        "الالتزام الأبدي بالسرية غير عملي ويبقينا معرضين للمطالبة بلا نهاية، حتى لو أصبحت المعلومات متقادمة أو عامة.",
        "بعض بياناتنا الفنية تبقى حساسة لسنوات طويلة ولا نقبل أن تصبح مباحة بانتهاء العقد.",
        "نقترح مدة 3 سنوات بعد الانتهاء للمعلومات العامة، مع حماية مستمرة فقط للأسرار التجارية المعرّفة كتابياً، واستثناءات المعلومات المتاحة للعموم.",
        "نوافق بشرط أن تكون المدة 5 سنوات وأن نحدد قائمة الأسرار التجارية في ملحق.",
        "يلتزم كل طرف بسرية المعلومات خلال مدة العقد ولمدة خمس سنوات من انتهائه، وتستمر حماية الأسرار التجارية المحددة في الملحق ما دامت محتفظة بسريتها، ولا يشمل الالتزام المعلومات المتاحة للعموم أو المعروفة مسبقاً أو المطلوب الإفصاح عنها نظاماً.",
        "حماية ممتدة لأسراره التجارية الحساسة.",
        "سقف زمني واضح للالتزام واستثناءات تمنع المطالبات التعسفية.",
    ),
    "termination": (
        "الإنهاء الفوري دون إشعار أو سداد قيمة الأعمال المنجزة يهدد استقرار العلاقة ويجعل استثمارنا في المشروع بلا ضمانة.",
        "نحتاج إلى مرونة الخروج السريع إذا لم يحقق الطرف الآخر النتائج المطلوبة.",
        "نقترح أن يكون الإنهاء للإخلال الجوهري بعد إشعار ومهلة تصحيح 30 يوماً، والإنهاء للملاءمة بإشعار 60 يوماً، مع سداد قيمة الأعمال المنجزة.",
        "نقبل بمهلة تصحيح 15 يوماً للإخلال الجوهري، وإشعار 30 يوماً للإنهاء دون سبب مع سداد المنجز فقط.",
        "يحق لأي من الطرفين إنهاء العقد في حال الإخلال الجوهري الذي لم يعالج خلال 15 يوماً من الإشعار الكتابي، كما يحق لأي منهما إنهاؤه دون سبب بإشعار كتابي مدته 30 يوماً، ويلتزم الطرف المنهي بسداد قيمة الأعمال المنجزة والمقبولة حتى تاريخ الإنهاء.",
        "مرونة في الخروج من العقد بإشعار قصير نسبياً.",
        "مهلة تصحيح وإشعار مسبق وضمان سداد الأعمال المنجزة.",
    ),
    "termination_labor": (
        "فسخ العقد فوراً دون إشعار أو مكافأة لأي سبب يخالف المادة 75 (مهلة الإشعار) ويحصر النظام الفسخ دون إشعار في حالات المادة 80 فقط.",
        "نحتاج إلى القدرة على إنهاء العلاقة بسرعة إذا ارتكب الموظف مخالفة جسيمة.",
        "هذا مكفول لكم نظاماً في حالات المادة 80؛ أما في غيرها فنطلب إشعاراً مدته 60 يوماً مع صرف المستحقات النظامية كاملة.",
        "نقبل ذلك مع حقنا في إعفاء الموظف من العمل خلال مدة الإشعار مع صرف أجره.",
        "يحق لأي من الطرفين إنهاء العقد لسبب مشروع بإشعار كتابي مدته 60 يوماً، ويجوز لصاحب العمل إعفاء العامل من العمل خلال مدة الإشعار مع صرف أجره كاملاً، ولا يجوز الفسخ دون إشعار أو مكافأة إلا في الحالات الواردة في المادة 80 من نظام العمل.",
        "إنهاء فوري مكفول في المخالفات الجسيمة وإمكانية الإعفاء من العمل خلال الإشعار.",
        "إشعار نظامي كامل وحفظ المكافأة والمستحقات.",
    ),
    "duration": (
        "آلية التجديد بصيغتها الحالية قد تلزمنا بمدة كاملة جديدة دون إرادة حقيقية منا.",
        "التجديد التلقائي يضمن استمرارية الخدمة دون انقطاع إداري.",
        "لا نعارض التجديد التلقائي بشرط أن يكون حق عدم التجديد متبادلاً وبمهلة إشعار معقولة لا تتجاوز 60 يوماً.",
        "نوافق على التبادل ومهلة 60 يوماً.",
        "يتجدد العقد تلقائياً لمدة مماثلة ما لم يخطر أي من الطرفين الآخر كتابياً برغبته في عدم التجديد قبل 60 يوماً من تاريخ انتهاء مدته.",
        "استمرارية الخدمة دون إجراءات تجديد متكررة.",
        "حق متبادل ومعقول في الخروج عند نهاية المدة.",
    ),
    "payment": (
        "تعديل المقابل المالي بشكل أحادي يفقد العقد قيمته ويجعل الميزانية غير قابلة للتخطيط.",
        "التكاليف التشغيلية تتغير ونحتاج إلى مرونة في التسعير.",
        "نقترح تثبيت الأسعار طوال المدة، وأي تعديل يكون عند التجديد فقط بإشعار 60 يوماً وبنسبة لا تتجاوز 5%.",
        "نقبل التثبيت للسنة الأولى مع حق التعديل عند التجديد بإشعار 60 يوماً وبحد أقصى 7%.",
        "تكون الرسوم ثابتة طوال مدة العقد، ويجوز تعديلها عند التجديد فقط بإشعار كتابي قبل 60 يوماً وبنسبة لا تتجاوز 7%، مع حق الطرف الآخر في عدم التجديد.",
        "حق تعديل الأسعار دورياً لمواكبة التكاليف.",
        "ثبات مالي خلال المدة وسقف واضح لأي زيادة مستقبلية.",
    ),
    "probation": (
        "فترة التجربة المذكورة تتجاوز الحد النظامي في المادة 53، والتمديد المفتوح يبقي الموظف في حالة عدم استقرار.",
        "نحتاج وقتاً كافياً لتقييم أداء الموظف في المهام المعقدة.",
        "نقترح 90 يوماً قابلة للتمديد مرة واحدة باتفاق مكتوب بحيث لا تتجاوز 180 يوماً، مع تقييم مكتوب في نهاية الفترة الأولى.",
        "موافقون، مع تقييم أداء موثق عند اليوم 75.",
        "يخضع العامل لفترة تجربة مدتها 90 يوماً، ويجوز تمديدها مرة واحدة باتفاق مكتوب على ألا يتجاوز مجموعها 180 يوماً، ويجرى تقييم مكتوب للأداء قبل نهاية الفترة الأولى.",
        "فترة تقييم كافية ضمن الإطار النظامي.",
        "فترة تجربة نظامية محددة وتقييم شفاف.",
    ),
    "hours": (
        "ساعات العمل تتجاوز الحد النظامي، وحرمان الموظف من أجر العمل الإضافي شرط باطل وفق المادتين 98 و107.",
        "طبيعة العمل تتطلب ساعات ممتدة في أوقات الذروة.",
        "نتفهم ذلك؛ لذا نقترح 8 ساعات يومياً و48 أسبوعياً، مع احتساب أي ساعات إضافية بأجر الساعة + 50% وفق النظام.",
        "نقبل مع حقنا في جدولة العمل الإضافي مسبقاً في أوقات الذروة.",
        "ساعات العمل الفعلية 8 ساعات يومياً بحد أقصى 48 ساعة أسبوعياً، ويجوز تكليف العامل بعمل إضافي بإشعار مسبق، ويستحق عنه أجر الساعة مضافاً إليه 50% من أجره الأساسي.",
        "مرونة تشغيلية في أوقات الذروة.",
        "ساعات نظامية وأجر عادل عن العمل الإضافي.",
    ),
    "leave": (
        "مدة الإجازة أقل من الحد الأدنى في المادة 109 من نظام العمل، وهذا شرط باطل نظاماً.",
        "نخشى تأثير الإجازات الطويلة على سير العمل.",
        "نقترح 21 يوماً كما يقرر النظام، مع تنسيق مواعيدها مسبقاً وفق جدول يعتمده المدير المباشر.",
        "موافقون على 21 يوماً مع جدولة مسبقة.",
        "يستحق العامل إجازة سنوية مدفوعة الأجر مدتها 21 يوماً تزاد إلى 30 يوماً بعد خمس سنوات متصلة، ويحدد موعدها بالتنسيق المسبق مع صاحب العمل.",
        "جدولة مسبقة للإجازات تضمن استمرارية العمل.",
        "إجازة نظامية كاملة.",
    ),
    "eos": (
        "اشتراط التنازل عن مكافأة نهاية الخدمة باطل وفق المادة 8 من نظام العمل، فالمكافأة حق نظامي.",
        "نريد تحفيز الموظفين على البقاء مدة أطول.",
        "يمكن تحقيق ذلك بحوافز بقاء إضافية، مع تطبيق المادتين 84 و85 كما هما في حالة الاستقالة.",
        "نقبل مع ربط مكافأة بقاء إضافية بإتمام ثلاث سنوات.",
        "يستحق العامل مكافأة نهاية الخدمة وفق المادتين 84 و85 من نظام العمل، ويمنح مكافأة بقاء إضافية عند إتمام ثلاث سنوات متصلة في الخدمة.",
        "أداة تحفيز مشروعة لاستبقاء الكفاءات.",
        "حفظ الحق النظامي الكامل في المكافأة.",
    ),
    "non_compete": (
        "قيد عدم المنافسة بهذه المدة والنطاق الجغرافي يتجاوز ما تسمح به المادة 83، ويمنع الموظف من كسب رزقه.",
        "نحتاج إلى حماية عملائنا وأسرارنا من المنافسين المباشرين.",
        "نقترح سنة واحدة، وقصر القيد على المنافسين المباشرين في نفس النشاط داخل المدينة.",
        "نقبل بسنة ونصف داخل المملكة للمنافسين المباشرين فقط.",
        "يلتزم العامل بعد انتهاء العقد بعدم العمل لدى منافس مباشر في ذات النشاط داخل المملكة لمدة سنة ونصف، ويقتصر القيد على الأعمال التي تتيح له الاطلاع على عملاء صاحب العمل أو أسراره.",
        "حماية فعلية للعملاء والأسرار من المنافسين المباشرين.",
        "قيد محدد ونظامي لا يتجاوز سنتين.",
    ),
    "rent_increase": (
        "حق زيادة الأجرة في أي وقت يجعل الأجرة مجهولة ويهدد استقرار النشاط ويخالف مبدأ ثبات الأجرة.",
        "أسعار السوق تتغير ولا نريد أن نخسر القيمة العادلة للعقار.",
        "نقترح تثبيت الأجرة طوال المدة، مع زيادة عند التجديد لا تتجاوز 5% وبإشعار 90 يوماً.",
        "نقبل بزيادة 5% عند التجديد بشرط مراجعة الأجرة وفق السوق كل 3 سنوات.",
        "تكون القيمة الإيجارية ثابتة طوال مدة العقد، ويجوز زيادتها عند التجديد بنسبة لا تتجاوز 5% بإشعار كتابي قبل 90 يوماً، مع مراجعة الأجرة وفق أسعار السوق مرة كل ثلاث سنوات.",
        "زيادة دورية مضمونة ومراجعة سوقية منتظمة.",
        "استقرار الأجرة خلال المدة وسقف معلوم لأي زيادة.",
    ),
    "deposit": (
        "التأمين غير المسترد يتحول إلى أجرة مستترة ويخالف الغرض منه كضمان للأضرار.",
        "نحتاج إلى ضمان يغطي أي أضرار أو متأخرات عند الإخلاء.",
        "نقترح استرداد التأمين خلال 30 يوماً من التسليم بعد خصم الأضرار الموثقة بمحضر استلام مشترك.",
        "موافقون مع حق خصم المتأخرات وفواتير الخدمات غير المسددة.",
        "يعاد مبلغ الضمان للمستأجر خلال 30 يوماً من تسليم العين، بعد خصم تكلفة الأضرار الموثقة بمحضر استلام مشترك والمتأخرات وفواتير الخدمات غير المسددة إن وجدت.",
        "ضمان فعلي يغطي الأضرار والمتأخرات.",
        "استرداد مضمون للتأمين عند التسليم السليم.",
    ),
    "maintenance": (
        "تحميلنا الصيانة الإنشائية والهيكلية يعني تحمل تكاليف رأسمالية في عقار لا نملكه.",
        "لا نريد تحمل تكاليف صيانة ناتجة عن سوء الاستخدام.",
        "نقترح أن تكون الصيانة الإنشائية والجوهرية على المؤجر، والتشغيلية وما ينتج عن سوء الاستخدام على المستأجر.",
        "نقبل هذا التقسيم.",
        "يتحمل المؤجر الصيانة الإنشائية والجوهرية للعقار والتمديدات الرئيسية، ويتحمل المستأجر الصيانة التشغيلية الدورية وإصلاح ما ينتج عن سوء الاستخدام.",
        "حماية من تكاليف الإصلاحات الناتجة عن سوء الاستخدام.",
        "إعفاء من التكاليف الإنشائية والرأسمالية.",
    ),
    "sla": (
        "تقديم الخدمة كما هي دون أي ضمان يعني أن نستمر في الدفع حتى لو توقفت الخدمة لأيام.",
        "لا يمكننا ضمان التوفر الكامل بسبب عوامل خارجة عن إرادتنا.",
        "لا نطلب 100%؛ نقترح توفراً شهرياً 99.5% مع خصومات خدمة عند الإخلال وحق الإنهاء عند التكرار.",
        "نقبل 99.5% مع استثناء فترات الصيانة المجدولة المعلنة مسبقاً.",
        "يلتزم المزود بنسبة توفر شهرية لا تقل عن 99.5% باستثناء الصيانة المجدولة المعلنة قبل 72 ساعة، ويستحق العميل خصماً بنسبة 10% من رسوم الشهر عن كل 0.5% نقص، مع حق الإنهاء إذا تكرر الإخلال ثلاثة أشهر متتالية.",
        "استثناء الصيانة المجدولة وسقف معلوم للتعويض.",
        "ضمان مستوى خدمة قابل للقياس وتعويضات عن الانقطاع.",
    ),
    "data_protection": (
        "مشاركة بياناتنا مع أطراف ثالثة ونقلها للخارج دون موافقة يعرضنا لمخالفات نظام حماية البيانات الشخصية.",
        "نحتاج إلى استخدام مزودين فرعيين وبنية سحابية عالمية لتحسين الخدمة.",
        "نقبل المزودين الفرعيين بشرط إعلامنا بقائمتهم وموافقتنا المسبقة، وتخزين البيانات داخل المملكة.",
        "نوافق على التخزين داخل المملكة مع حق استخدام مزودين فرعيين معتمدين بعد الإشعار.",
        "يلتزم المزود بمعالجة بيانات العميل وفق نظام حماية البيانات الشخصية وتخزينها داخل المملكة، ولا يجوز له الإفصاح عنها لطرف ثالث إلا لمزودين فرعيين يوافق عليهم العميل كتابياً ويلتزمون بذات الضوابط.",
        "مرونة استخدام مزودين فرعيين معتمدين.",
        "امتثال نظامي كامل وسيطرة على البيانات.",
    ),
    "ip": (
        "انتقال ملكية البيانات أو الملكية الفكرية بهذا الشكل يفقدنا السيطرة على أصولنا الأساسية.",
        "نحتاج إلى حقوق كافية لتقديم الخدمة وتطوير منتجاتنا.",
        "نقترح أن تبقى الملكية لصاحبها الأصلي مع منح ترخيص محدود للاستخدام لغرض العقد فقط.",
        "نقبل مع حقنا في استخدام بيانات إحصائية مجمعة لا تكشف الهوية.",
        "تبقى البيانات والمحتوى والملكية الفكرية السابقة ملكاً لصاحبها الأصلي، ويمنح كل طرف الآخر ترخيصاً محدوداً لاستخدامها لغرض تنفيذ العقد فقط، ويجوز للمزود استخدام بيانات إحصائية مجمعة لا تكشف هوية العميل.",
        "ترخيص كافٍ لتقديم الخدمة واستخدام إحصاءات مجمعة.",
        "الاحتفاظ بملكية الأصول والبيانات.",
    ),
    "nda_scope": (
        "تعريف المعلومات السرية يشمل حتى المعلومات المتاحة للعموم، وهذا يجعل أي استخدام لمعلومات عامة مخالفة.",
        "نخشى أن تستغل الاستثناءات للتهرب من الالتزام.",
        "نقترح تعريفاً محدداً مع الاستثناءات المعتادة، وعبء إثبات الاستثناء على الطرف المتلقي.",
        "نقبل بشرط أن يكون عبء الإثبات على المتلقي.",
        "المعلومات السرية هي المعلومات غير المتاحة للعموم التي يفصح عنها الطرف المفصح لغرض الاتفاقية، ولا تشمل المعلومات المتاحة للعموم أو المعروفة مسبقاً أو المطورة باستقلالية أو المطلوب الإفصاح عنها نظاماً، ويقع عبء إثبات الاستثناء على الطرف المتلقي.",
        "عبء الإثبات على المتلقي يمنع التهرب.",
        "تعريف واضح يستثني المعلومات العامة.",
    ),
    "liquidated": (
        "تعويض جزافي ضخم عن كل مخالفة دون إثبات ضرر لا يتناسب مع أي ضرر محتمل، والقضاء يملك تخفيضه أصلاً.",
        "نحتاج إلى رادع قوي لحماية معلوماتنا الحساسة.",
        "نقترح التعويض عن الأضرار الفعلية المثبتة بحد أقصى معقول، مع حقكم في طلب وقف الإخلال فوراً.",
        "نقبل بحد أقصى مليون ريال وحقنا في الأمر المستعجل بوقف الإخلال.",
        "في حال الإخلال بالسرية يلتزم الطرف المخل بتعويض الأضرار الفعلية المثبتة بحد أقصى مليون ريال، مع حق الطرف المتضرر في طلب وقف الإخلال بصفة مستعجلة.",
        "رادع مالي معتبر وحق الوقف المستعجل.",
        "تعويض متناسب مرتبط بضرر فعلي وسقف واضح.",
    ),
    "dispute": (
        "التقاضي في ولاية قضائية أجنبية يرفع التكاليف ويعقّد تنفيذ الأحكام داخل المملكة.",
        "اعتدنا على هذا الإطار القانوني في جميع عقودنا.",
        "نقترح الأنظمة السعودية والمركز السعودي للتحكيم التجاري، وهو مركز معترف به دولياً.",
        "نقبل التحكيم في المركز السعودي على أن تكون لغة التحكيم العربية والإنجليزية.",
        "يخضع هذا العقد لأنظمة المملكة العربية السعودية، ويحال أي نزاع إلى المركز السعودي للتحكيم التجاري في الرياض، وتكون لغة التحكيم العربية مع جواز تقديم المستندات بالإنجليزية.",
        "مركز تحكيم دولي محايد وقبول المستندات بالإنجليزية.",
        "تقاضٍ محلي أقل تكلفة وأسهل تنفيذاً.",
    ),
}


# English versions of the negotiation templates (same structure as TEMPLATES)
TEMPLATES_EN = {
    "late_penalty": (
        "A penalty at this rate wipes out the whole profit margin with the first minor delay; the commercial standard does not exceed 10% of the contract value, and courts may reduce excessive penalty clauses.",
        "Meeting the schedule is essential for us; any delay disrupts our operations and causes real losses, so we need a strong deterrent.",
        "We agree on the need for a deterrent, so we propose a graduated penalty of 0.5% per week on the delayed phase only, capped at 10%, with a 7-day cure period after notice.",
        "We accept the graduated penalty provided the cap is 10% of the total value and we may terminate once the penalties reach the cap.",
        "If delivery is delayed for reasons attributable to the Provider, a penalty of 0.5% of the delayed phase value applies per week of delay, capped at 10% of the total contract value, after written notice and a 7-day cure period; the Client may terminate if penalties reach the cap.",
        "An effective, graduated deterrent against delay with a right to terminate at the cap.",
        "A clear cap that protects the profit margin, applied only to the delayed phase with a cure period.",
    ),
    "liability": (
        "Unlimited liability for indirect damages and loss of profits is an uninsurable risk that could exceed the contract value many times over.",
        "We need full compensation if the system causes our business to stop.",
        "We propose a cap equal to the amounts paid in 12 months, excluding indirect damages, with liability left uncapped only for fraud, gross negligence and breach of confidentiality.",
        "We accept, provided the cap equals the total contract value and the Provider maintains professional liability insurance.",
        "The total liability of either party shall not exceed the total contract value, and neither party shall be liable for indirect damages or loss of profits, except for fraud, gross negligence or breach of confidentiality; the Provider shall maintain valid professional liability insurance throughout the term.",
        "A high liability cap covering the contract value, backed by professional insurance.",
        "Defined, insurable risk with indirect damages excluded.",
    ),
    "confidentiality": (
        "A perpetual confidentiality obligation is impractical and leaves us exposed to claims forever, even when the information becomes outdated or public.",
        "Some of our technical data stays sensitive for many years, and we cannot accept it becoming free to use when the contract ends.",
        "We propose 3 years after expiry for general information, with continued protection only for trade secrets identified in writing, and exclusions for public information.",
        "We agree, provided the period is 5 years and the trade secrets are listed in an annex.",
        "Each party shall keep information confidential during the term and for five years after expiry; trade secrets listed in the annex remain protected as long as they stay confidential, and the obligation does not cover information that is public, previously known or required to be disclosed by law.",
        "Extended protection for its sensitive trade secrets.",
        "A clear time limit and exclusions that prevent abusive claims.",
    ),
    "termination": (
        "Immediate termination without notice or payment for completed work threatens the relationship and leaves our investment in the project unprotected.",
        "We need the flexibility to exit quickly if the other party does not deliver the required results.",
        "We propose termination for material breach after notice and a 30-day cure period, and termination for convenience with 60 days' notice, with payment for completed work.",
        "We accept a 15-day cure period for material breach and 30 days' notice for termination without cause, paying only for completed work.",
        "Either party may terminate the contract for a material breach not remedied within 15 days of written notice, and either party may terminate without cause by 30 days' written notice; the terminating party shall pay for work completed and accepted up to the termination date.",
        "Flexibility to exit the contract with relatively short notice.",
        "A cure period, prior notice and guaranteed payment for completed work.",
    ),
    "termination_labor": (
        "Terminating the contract immediately without notice or award for any reason violates Article 75 (notice period), and the Law limits termination without notice to the cases in Article 80.",
        "We need to be able to end the relationship quickly if the employee commits a serious violation.",
        "That right is already guaranteed to you in the cases of Article 80; in all other cases we ask for 60 days' notice with full payment of statutory entitlements.",
        "We accept, with our right to release the employee from work during the notice period while paying the wage.",
        "Either party may terminate the contract for a valid reason by 60 days' written notice; the employer may release the employee from work during the notice period while paying the full wage, and may not terminate without notice or award except in the cases set out in Article 80 of the Labor Law.",
        "Immediate termination guaranteed for serious violations, plus the option to release the employee during notice.",
        "Full statutory notice and protection of the award and entitlements.",
    ),
    "duration": (
        "The current renewal mechanism could bind us for a whole new term without any real choice on our part.",
        "Automatic renewal ensures continuity of service without administrative interruption.",
        "We do not object to automatic renewal, provided the right not to renew is mutual with a reasonable notice period of no more than 60 days.",
        "We agree to mutuality and a 60-day notice period.",
        "The contract shall automatically renew for a similar period unless either party notifies the other in writing of its wish not to renew 60 days before its expiry.",
        "Continuity of service without repeated renewal procedures.",
        "A mutual and reasonable right to exit at the end of the term.",
    ),
    "payment": (
        "Unilateral changes to the consideration remove the contract's value and make budgeting impossible.",
        "Operating costs change and we need pricing flexibility.",
        "We propose fixed prices for the whole term, with any change only on renewal, with 60 days' notice and no more than 5%.",
        "We accept fixed prices for the first year, with the right to adjust on renewal with 60 days' notice and a maximum of 7%.",
        "Fees are fixed for the whole term of the contract and may be adjusted only on renewal by written notice 60 days in advance and by no more than 7%, with the other party's right not to renew.",
        "The right to adjust prices periodically to reflect costs.",
        "Financial stability during the term and a clear cap on future increases.",
    ),
    "probation": (
        "The stated probation period exceeds the legal limit in Article 53, and open-ended extension keeps the employee in a state of instability.",
        "We need enough time to assess the employee's performance on complex tasks.",
        "We propose 90 days, extendable once by written agreement up to 180 days, with a written evaluation at the end of the first period.",
        "Agreed, with a documented performance review on day 75.",
        "The employee is subject to a 90-day probation period, extendable once by written agreement up to a total of 180 days, with a written performance evaluation before the end of the first period.",
        "Sufficient assessment time within the legal framework.",
        "A defined statutory probation period and a transparent evaluation.",
    ),
    "hours": (
        "The working hours exceed the legal limit, and denying overtime pay is a void condition under Articles 98 and 107.",
        "The nature of the work requires extended hours at peak times.",
        "We understand, so we propose 8 hours per day and 48 per week, with any extra hours paid at the hourly wage + 50% as required by law.",
        "We accept, with our right to schedule overtime in advance at peak times.",
        "Actual working hours are 8 per day up to 48 per week; the employee may be assigned overtime with prior notice and shall be paid the hourly wage plus 50% of the basic wage for it.",
        "Operational flexibility at peak times.",
        "Legal working hours and fair pay for overtime.",
    ),
    "leave": (
        "The leave period is below the minimum in Article 109 of the Labor Law, which makes the condition void.",
        "We are concerned about the impact of long leave on operations.",
        "We propose 21 days as the Law requires, with dates coordinated in advance under a schedule approved by the direct manager.",
        "We agree to 21 days with advance scheduling.",
        "The employee is entitled to 21 days of paid annual leave, rising to 30 days after five continuous years, with dates set in advance in coordination with the employer.",
        "Advance scheduling of leave that keeps operations running.",
        "Full statutory leave.",
    ),
    "eos": (
        "Requiring the employee to waive the end-of-service award is void under Article 8 of the Labor Law; the award is a statutory right.",
        "We want to motivate employees to stay longer.",
        "That can be achieved with additional retention bonuses, while applying Articles 84 and 85 as they are in case of resignation.",
        "We accept, linking an extra retention bonus to completing three years.",
        "The employee is entitled to the end-of-service award under Articles 84 and 85 of the Labor Law, and receives an additional retention bonus on completing three continuous years of service.",
        "A lawful incentive to retain talent.",
        "Full protection of the statutory award.",
    ),
    "non_compete": (
        "A non-compete of this length and geographic scope goes beyond what Article 83 allows and prevents the employee from earning a living.",
        "We need to protect our clients and secrets from direct competitors.",
        "We propose one year, limited to direct competitors in the same business within the city.",
        "We accept a year and a half within the Kingdom for direct competitors only.",
        "After the contract ends, the employee shall not work for a direct competitor in the same business within the Kingdom for a year and a half, limited to roles that would give access to the employer's clients or secrets.",
        "Real protection of clients and secrets from direct competitors.",
        "A defined, lawful restriction not exceeding two years.",
    ),
    "rent_increase": (
        "A right to raise the rent at any time makes the rent uncertain, threatens the business and breaches the principle of fixed rent.",
        "Market prices change and we do not want to lose the fair value of the property.",
        "We propose fixed rent for the whole term, with an increase on renewal of no more than 5% and 90 days' notice.",
        "We accept a 5% increase on renewal, provided rent is reviewed against the market every 3 years.",
        "Rent is fixed for the whole term of the contract and may be increased on renewal by no more than 5% with written notice 90 days in advance, with a market review of the rent once every three years.",
        "Guaranteed periodic increases and a regular market review.",
        "Stable rent during the term and a known cap on any increase.",
    ),
    "deposit": (
        "A non-refundable deposit becomes hidden rent and defeats its purpose as security against damage.",
        "We need security covering any damage or arrears on eviction.",
        "We propose refunding the deposit within 30 days of handover after deducting damage documented in a joint handover report.",
        "Agreed, with the right to deduct arrears and unpaid utility bills.",
        "The deposit is returned to the tenant within 30 days of handover, after deducting the cost of damage documented in a joint handover report and any arrears or unpaid utility bills.",
        "Real security covering damage and arrears.",
        "A guaranteed refund of the deposit on proper handover.",
    ),
    "maintenance": (
        "Making us bear structural maintenance means paying capital costs on a property we do not own.",
        "We do not want to pay for maintenance caused by misuse.",
        "We propose structural and major maintenance on the landlord, and operational maintenance and misuse repairs on the tenant.",
        "We accept this split.",
        "The landlord bears structural and major maintenance of the property and main installations, and the tenant bears routine operational maintenance and repairs caused by misuse.",
        "Protection from repair costs caused by misuse.",
        "Exemption from structural and capital costs.",
    ),
    "sla": (
        "Providing the service \"as is\" with no guarantee means we keep paying even if the service is down for days.",
        "We cannot guarantee full availability because of factors beyond our control.",
        "We are not asking for 100%; we propose 99.5% monthly availability with service credits for breaches and a right to terminate for repeated failures.",
        "We accept 99.5%, excluding scheduled maintenance announced in advance.",
        "The Provider commits to monthly availability of at least 99.5%, excluding scheduled maintenance announced 72 hours in advance; the Client receives a 10% credit on the month's fees for each 0.5% shortfall and may terminate after three consecutive months of breach.",
        "Scheduled maintenance excluded and a known cap on compensation.",
        "A measurable service level guarantee and credits for outages.",
    ),
    "data_protection": (
        "Sharing our data with third parties and moving it abroad without consent exposes us to violations of the Personal Data Protection Law.",
        "We need sub-processors and global cloud infrastructure to improve the service.",
        "We accept sub-processors provided we are informed of them and give prior consent, and data is stored inside the Kingdom.",
        "We agree to in-Kingdom storage, with the right to use approved sub-processors after notice.",
        "The Provider shall process client data in accordance with the Personal Data Protection Law and store it inside the Kingdom, and may not disclose it to any third party except sub-processors approved in writing by the Client and bound by the same controls.",
        "Flexibility to use approved sub-processors.",
        "Full legal compliance and control over the data.",
    ),
    "ip": (
        "Transferring ownership of our data or intellectual property this way makes us lose control of our core assets.",
        "We need sufficient rights to deliver the service and develop our products.",
        "We propose that ownership stays with the original owner, with a limited licence to use it for the purpose of the contract only.",
        "We accept, with our right to use aggregated, anonymised statistics.",
        "Data, content and pre-existing intellectual property remain the property of their original owner; each party grants the other a limited licence to use them solely to perform the contract, and the Provider may use aggregated statistics that do not identify the Client.",
        "A sufficient licence to deliver the service and use aggregated statistics.",
        "Retained ownership of assets and data.",
    ),
    "nda_scope": (
        "The definition covers even publicly available information, so any use of general information becomes a breach.",
        "We fear the exclusions will be used to evade the obligation.",
        "We propose a specific definition with the usual exclusions, with the burden of proving an exclusion on the Receiving Party.",
        "We accept, provided the burden of proof is on the recipient.",
        "Confidential Information means non-public information disclosed by the Disclosing Party for the purpose of the Agreement, and excludes information that is public, previously known, independently developed or required to be disclosed by law; the Receiving Party bears the burden of proving any exclusion.",
        "Burden of proof on the recipient prevents evasion.",
        "A clear definition that excludes public information.",
    ),
    "liquidated": (
        "A huge lump sum per breach without proof of damage is out of proportion to any possible harm, and courts can reduce it anyway.",
        "We need a strong deterrent to protect our sensitive information.",
        "We propose compensation for proven actual damage up to a reasonable cap, with your right to seek an immediate order stopping the breach.",
        "We accept a cap of SAR 1 million and our right to urgent injunctive relief.",
        "In case of breach of confidentiality, the breaching party shall compensate proven actual damage up to SAR 1 million, without prejudice to the injured party's right to seek urgent relief stopping the breach.",
        "A meaningful financial deterrent and the right to urgent relief.",
        "Proportionate compensation tied to actual damage with a clear cap.",
    ),
    "dispute": (
        "Litigating in a foreign jurisdiction raises costs and complicates enforcing judgments inside the Kingdom.",
        "We are used to this legal framework in all our contracts.",
        "We propose Saudi law and the Saudi Center for Commercial Arbitration, an internationally recognised centre.",
        "We accept arbitration at the Saudi Center, with Arabic and English as the languages of arbitration.",
        "This contract is governed by the laws of the Kingdom of Saudi Arabia, and any dispute shall be referred to the Saudi Center for Commercial Arbitration in Riyadh, with Arabic as the language of arbitration and documents admissible in English.",
        "A neutral, internationally recognised arbitration centre and documents accepted in English.",
        "Local, lower-cost dispute resolution that is easier to enforce.",
    ),
}

_KEY_HINTS = [
    (r"اتفاقي", "liquidated"), (r"غرام|تاخير|جزائي", "late_penalty"), (r"مسؤولي", "liability"),
    (r"تعريف", "nda_scope"), (r"مستوي الخدمه|sla", "sla"), (r"حمايه البيانات", "data_protection"),
    (r"ملكيه", "ip"), (r"سريه|السري\b|اسرار", "confidentiality"), (r"انهاء|فسخ|اخلاء", "termination"),
    (r"تجربه", "probation"), (r"ساعات", "hours"), (r"اجازه", "leave"), (r"نهايه الخدمه|مكافاه", "eos"),
    (r"منافس|استقطاب", "non_compete"), (r"زياده", "rent_increase"), (r"ضمان|تامين", "deposit"),
    (r"صيانه", "maintenance"), (r"نزاع|القانون", "dispute"), (r"مده|تجديد|سريان", "duration"),
    (r"دفع|اجر|رسوم|مالي", "payment"),
]

_KEY_HINTS_EN = [
    (r"liquidated", "liquidated"), (r"penalt|delay", "late_penalty"), (r"liabilit", "liability"),
    (r"definition", "nda_scope"), (r"service level|\bsla\b", "sla"), (r"confidential", "confidentiality"),
    (r"data protection", "data_protection"), (r"ownership|intellectual property", "ip"), (r"terminat|evict", "termination"),
    (r"probation", "probation"), (r"hours", "hours"), (r"\bleave\b", "leave"), (r"end-of-service|end of service|gratuity", "eos"),
    (r"compet|solicit", "non_compete"), (r"increase", "rent_increase"), (r"deposit", "deposit"),
    (r"maintenance", "maintenance"), (r"dispute|governing law", "dispute"), (r"\bterm\b|renew", "duration"),
    (r"payment|wage|fees|\brent\b", "payment"),
]


def guess_clause_key(title: str) -> Optional[str]:
    from rules_engine import norm
    t = norm(title)
    return next((key for pat, key in _KEY_HINTS + _KEY_HINTS_EN if re.search(pat, t)), None)


def offline_negotiation(clause_title: str, issue_context: str, recommendation: str = "",
                        legal_reference: str = "", contract_category: Optional[str] = None, lang: str = "ar") -> NegotiationSession:
    weak, strong = _parties(contract_category, lang)
    key = guess_clause_key(clause_title) or ""
    if key == "termination" and "عمل" in (contract_category or ""):
        key = "termination_labor"
    tpl = (TEMPLATES_EN if lang == "en" else TEMPLATES).get(key)
    if tpl:
        w1, s1, w2, s2, agreed, ben_a, ben_b = tpl
    elif lang == "en":
        w1 = f"We have reservations about the \"{clause_title}\" clause as currently drafted: {issue_context}"
        s1 = "We understand your point, but the clause was drafted to protect our operational interests and we cannot give up that protection entirely."
        w2 = f"We are not asking to remove the protection, only to balance it in line with {legal_reference or 'accepted standards'}. We propose the following wording: {recommendation}"
        s2 = "We accept the proposal in principle, provided the implementation and written-notice mechanisms are clear."
        agreed = recommendation or "The clause shall be redrafted to balance the parties' obligations in accordance with applicable law."
        ben_a, ben_b = "Core operational protection preserved.", "Unfairness removed and contractual balance achieved."
    else:
        w1 = f"نتحفظ على بند «{clause_title}» بصيغته الحالية؛ {issue_context}"
        s1 = "نتفهم ملاحظتكم، لكن البند وضع لحماية مصالحنا التشغيلية ولا يمكننا التخلي عن هذه الحماية بالكامل."
        w2 = f"لا نطلب إلغاء الحماية بل تحقيق التوازن وفق {legal_reference or 'المعايير المتعارف عليها'}. نقترح الصياغة التالية: {recommendation}"
        s2 = "نقبل المقترح من حيث المبدأ مع التأكيد على وضوح آليات التنفيذ والإشعار الكتابي."
        agreed = recommendation or "يعاد صياغة البند بما يحقق التوازن بين التزامات الطرفين وفق الأنظمة المعمول بها."
        ben_a, ben_b = "الحفاظ على الحماية التشغيلية الأساسية.", "إزالة الإجحاف وتحقيق التوازن العقدي."
    dialogue = [NegotiationTurn(speaker=weak, argument=w1), NegotiationTurn(speaker=strong, argument=s1),
                NegotiationTurn(speaker=weak, argument=w2), NegotiationTurn(speaker=strong, argument=s2)]
    return NegotiationSession(dialogue=dialogue, agreed_clause=agreed, benefits_for_party_a=ben_a, benefits_for_party_b=ben_b)


# ---------------------------------------------------------------------------
# 3. الموزع الذكي: LangChain أولاً ثم الاحتياطي
# ---------------------------------------------------------------------------
def negotiate(clause_title: str, problematic_text: str, issue_context: str, recommendation: str = "",
              legal_reference: str = "", contract_category: Optional[str] = None,
              engine: str = "auto", lang: str = "ar") -> Tuple[NegotiationSession, str, Optional[str]]:
    """يعيد (جلسة التفاوض، المحرك المستخدم، رسالة تنبيه إن وجدت)."""
    en = lang == "en"

    def fallback():
        return offline_negotiation(clause_title, issue_context, recommendation, legal_reference, contract_category, lang)

    if engine != "rules" and llm_available():
        try:
            return run_negotiation(clause_title, problematic_text, issue_context, contract_category, lang), "llm", None
        except Exception as err:  # الرجوع للمحرك المحلي عند أي خطأ في الاتصال
            warning = (f"Could not reach the language model ({type(err).__name__}); the local negotiation simulator was used." if en
                       else f"تعذر الاتصال بنموذج اللغة ({type(err).__name__})، تم استخدام محاكي التفاوض المحلي.")
            return fallback(), "rules", warning
    warning = None if engine == "rules" else (
        "No valid OpenAI key; the local negotiation simulator was used." if en else "لا يوجد مفتاح OpenAI صالح، تم استخدام محاكي التفاوض المحلي.")
    return fallback(), "rules", warning
