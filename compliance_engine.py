"""
خط معالجة واستدلال LangChain (LCEL) لفحص العقود، مقيد بهياكل Pydantic،
مع موزّع ذكي يرجع تلقائياً إلى المحرك المحلي عند غياب المفتاح أو تعذر الاتصال.
"""
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

from labor_law_data import type_info
from negotiator import llm_available
from rules_engine import analyze_contract
from security import logger
from schemas import (AuditReport, ComplianceItem, ContractMetadata, ContractTrap,  # noqa: F401 (إعادة تصدير)
                     compute_score)

load_dotenv()

MAX_CHARS = 60_000  # حماية من تجاوز حد السياق في العقود الطويلة جداً


SYSTEM_PROMPT_EN = """You are an expert legal and strategic advisor in Contract Lifecycle Management (CLM) under Saudi law.
Your task is to review the attached contract with professional precision against the following rules and standards for ({contract_type}):

Reference rules and standards:
{rules}

Mandatory tasks:
1. Extract the contract metadata card (parties, term, financial terms, and renewal).
2. Detect contractual traps (Killer Clauses) that actually appear in THIS contract's text. Report a trap only if you can point to the exact clause that creates it; never list a trap just because it is a common example. Use the severity value "حرج جداً" only for critical killer clauses, otherwise "متوسط".
3. Review every material clause in the contract (8 to 12 clauses) against the rules, quoting the exact contract text, and classify each clause by risk dimension. Mark a clause "متوافق" when it is balanced and complies with the rules; use "مخالف" only for clear violations and "مبهم / عالي المخاطر" for unclear or risky wording.
   Judge each clause on its own wording, independently of how unfavourable the rest of the contract is (e.g. mutual termination with 30 days' notice, or confidentiality limited to 2-5 years, is compliant).
4. If a material clause expected in this type of contract is missing, include it with the status "غير مذكور".
5. In recommendation, write a complete alternative wording ready to insert into the contract.
6. Write every free-text field (summary, metadata, clause titles, analysis, references, recommendations, trap names and explanations) in clear professional English.
   Keep the fixed enumeration values (status, risk_category, risk_level, severity) exactly as defined in the schema."""


def get_audit_chain(lang: str = "ar"):
    if lang == "en":
        return _build_chain(SYSTEM_PROMPT_EN, "Here is the contract text:\n\n{contract_text}")
    system_prompt = """أنت مستشار قانوني واستراتيجي خبير في إدارة وتدقيق العقود (Contract Lifecycle Management) وفق الأنظمة السعودية.
مهمتك فحص نص العقد المرفق بدقة احترافية وفق المعايير والقواعد التالية الخاصة بـ ({contract_type}):

القواعد والمعايير المرجعية:
{rules}

المهام الإلزامية:
1. استخراج بطاقة البيانات الجوهرية (الأطراف، المدة، الشروط المالية، والتجديد).
2. رصد الفخاخ التعاقدية (Killer Clauses) الموجودة فعلاً في نص هذا العقد، مثل: التعويض غير المحدود، أو فترات السرية غير المحددة، أو الشروط الجزائية المبالغ فيها، أو الإنهاء الفوري التعسفي. لا تذكر فخاً إلا إذا وُجد بند في العقد ينشئه، ولا تدرج الأمثلة السابقة لمجرد أنها أمثلة. استخدم الخطورة "حرج جداً" للفخاخ القاتلة فقط.
3. فحص كل بند جوهري في العقد (8 إلى 12 بنداً) ومطابقته مع اللوائح، مع اقتباس النص الحرفي من العقد، وتصنيف كل بند بحسب بعد المخاطرة (نظامي، مالي، تشغيلي، سرية). صنّف البند "متوافق" إذا كان متوازناً وموافقاً للقواعد، و"مخالف" للمخالفات الواضحة فقط، و"مبهم / عالي المخاطر" للصياغات الغامضة أو الخطرة.
   احكم على كل بند بحسب صياغته هو، بمعزل عن مدى إجحاف بقية العقد (مثلاً: الإنهاء المتبادل بإشعار 30 يوماً، أو السرية المحددة بسنتين إلى خمس سنوات، بند متوافق).
4. إذا غاب بند جوهري متوقع في هذا النوع من العقود فأدرجه بحالة "غير مذكور".
5. اكتب في recommendation صياغة بديلة كاملة جاهزة للإدراج في العقد.
6. اكتب جميع الحقول باللغة العربية الفصحى."""

    return _build_chain(system_prompt, "إليك نص العقد:\n\n{contract_text}")


def _build_chain(system_prompt: str, human_prompt: str):
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])

    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0, timeout=120, max_retries=1)
    return prompt | llm.with_structured_output(AuditReport)


def audit_contract_text(contract_text: str, contract_category: str, lang: str = "ar") -> AuditReport:
    """الفحص عبر LangChain + OpenAI."""
    info = type_info(contract_category, lang)
    report: AuditReport = get_audit_chain(lang).invoke({
        "contract_text": contract_text[:MAX_CHARS],
        "rules": info["rules"],
        "contract_type": info["label"],
    })
    # مؤشر سلامة موحد ومتسق بين المحركين بدلاً من تقدير النموذج الحر
    report.compliance_score = compute_score(report.items)
    return report


def run_audit(contract_text: str, contract_category: str, engine: str = "auto",
              lang: str = "ar") -> Tuple[AuditReport, str, Optional[str]]:
    """
    engine: "auto" | "llm" | "rules" — lang: "ar" | "en" (لغة نصوص التقرير)
    يعيد (التقرير، المحرك المستخدم فعلياً، رسالة تنبيه إن وجدت).
    """
    en = lang == "en"
    if engine == "rules":
        return analyze_contract(contract_text, contract_category, lang), "rules", None

    if not llm_available():
        warning = None
        if engine == "llm":
            warning = ("No valid OpenAI key in the .env file; the audit was run by the local legal expert engine." if en
                       else "لا يوجد مفتاح OpenAI صالح في ملف .env، تم الفحص بالمحرك المحلي للخبير القانوني.")
        return analyze_contract(contract_text, contract_category, lang), "rules", warning

    try:
        return audit_contract_text(contract_text, contract_category, lang), "llm", None
    except Exception:
        # التفاصيل في سجل الخادم فقط؛ المستخدم يرى رسالة عامة لا تكشف معلومات داخلية
        logger.exception("LLM audit failed; falling back to the rules engine")
        warning = ("The language model is unavailable right now; the audit was run by the local engine." if en
                   else "نموذج اللغة غير متاح حالياً، تم الفحص بالمحرك المحلي.")
        return analyze_contract(contract_text, contract_category, lang), "rules", warning
