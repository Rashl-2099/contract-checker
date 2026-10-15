"""
خط معالجة واستدلال LangChain (LCEL) لفحص العقود، مقيد بهياكل Pydantic،
مع موزّع ذكي يرجع تلقائياً إلى المحرك المحلي عند غياب المفتاح أو تعذر الاتصال.
"""
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

from labor_law_data import CONTRACT_TYPES, COMMERCIAL_CONTRACT_RULES
from negotiator import llm_available
from rules_engine import analyze_contract
from schemas import (AuditReport, ComplianceItem, ContractMetadata, ContractTrap,  # noqa: F401 (إعادة تصدير)
                     compute_score)

load_dotenv()

MAX_CHARS = 60_000  # حماية من تجاوز حد السياق في العقود الطويلة جداً


def get_audit_chain():
    system_prompt = """أنت مستشار قانوني واستراتيجي خبير في إدارة وتدقيق العقود (Contract Lifecycle Management) وفق الأنظمة السعودية.
مهمتك فحص نص العقد المرفق بدقة احترافية وفق المعايير والقواعد التالية الخاصة بـ ({contract_type}):

القواعد والمعايير المرجعية:
{rules}

المهام الإلزامية:
1. استخراج بطاقة البيانات الجوهرية (الأطراف، المدة، الشروط المالية، والتجديد).
2. رصد الفخاخ التعاقدية (Killer Clauses) مثل: التعويض غير المحدود، أو فترات السرية غير المحددة، أو الشروط الجزائية المبالغ فيها، أو الإنهاء الفوري التعسفي. استخدم الخطورة "حرج جداً" للفخاخ القاتلة فقط.
3. فحص كل بند جوهري في العقد (8 إلى 12 بنداً) ومطابقته مع اللوائح، مع اقتباس النص الحرفي من العقد، وتصنيف كل بند بحسب بعد المخاطرة (نظامي، مالي، تشغيلي، سرية).
4. إذا غاب بند جوهري متوقع في هذا النوع من العقود فأدرجه بحالة "غير مذكور".
5. اكتب في recommendation صياغة بديلة كاملة جاهزة للإدراج في العقد.
6. اكتب جميع الحقول باللغة العربية الفصحى."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "إليك نص العقد:\n\n{contract_text}"),
    ])

    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0, timeout=120, max_retries=1)
    return prompt | llm.with_structured_output(AuditReport)


def audit_contract_text(contract_text: str, contract_category: str) -> AuditReport:
    """الفحص عبر LangChain + OpenAI."""
    config = CONTRACT_TYPES.get(contract_category, {})
    report: AuditReport = get_audit_chain().invoke({
        "contract_text": contract_text[:MAX_CHARS],
        "rules": config.get("rules", COMMERCIAL_CONTRACT_RULES),
        "contract_type": config.get("label", contract_category),
    })
    # مؤشر سلامة موحد ومتسق بين المحركين بدلاً من تقدير النموذج الحر
    report.compliance_score = compute_score(report.items)
    return report


def run_audit(contract_text: str, contract_category: str, engine: str = "auto") -> Tuple[AuditReport, str, Optional[str]]:
    """
    engine: "auto" | "llm" | "rules"
    يعيد (التقرير، المحرك المستخدم فعلياً، رسالة تنبيه إن وجدت).
    """
    if engine == "rules":
        return analyze_contract(contract_text, contract_category), "rules", None

    if not llm_available():
        warning = "لا يوجد مفتاح OpenAI صالح في ملف .env، تم الفحص بالمحرك المحلي للخبير القانوني." if engine == "llm" else None
        return analyze_contract(contract_text, contract_category), "rules", warning

    try:
        return audit_contract_text(contract_text, contract_category), "llm", None
    except Exception as err:
        warning = f"تعذر إكمال الفحص عبر نموذج اللغة ({type(err).__name__}: {str(err)[:160]})، تم الرجوع للمحرك المحلي."
        return analyze_contract(contract_text, contract_category), "rules", warning
