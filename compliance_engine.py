import os
from typing import List, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
# إذا كنت تستخدم Gemini:
# from langchain_google_genai import ChatGoogleGenerativeAI

from labor_law_data import SAUDI_LABOR_LAW_RULES, COMMERCIAL_CONTRACT_RULES

load_dotenv()

# 1. بطاقة البيانات الجوهرية للعقد
class ContractMetadata(BaseModel):
    parties: List[str] = Field(description="أسماء أطراف العقد ومسمياتهم")
    effective_duration: str = Field(description="مدة العقد وتاريخ البدء والانتهاء إن وجد")
    financial_terms: str = Field(description="القيمة المالية الإجمالية، الرواتب، أو طريقة السداد")
    renewal_clause: str = Field(description="شرط التجديد والمدة المطلوبة للإشعار بعدم التجديد")

# 2. كاشف الفخاخ والشروط القاتلة
class ContractTrap(BaseModel):
    trap_name: str = Field(description="اسم الفخ التعاقدي (مثل: تعويض مفتوح، تجديد صامت، فسخ تعسفي)")
    severity: Literal["حرج جداً", "متوسط"] = Field(description="درجة خطورة الفخ")
    explanation: str = Field(description="لماذا يعد هذا البند فخاً وما الضرر المحتمل منه؟")

# 3. بنود الفحص التفصيلية مع تصنيف أبعاد الخطر
class ComplianceItem(BaseModel):
    clause_title: str = Field(description="اسم البند المستخرج من العقد")
    contract_snippet: str = Field(description="النص الحرفي المقتبس من العقد")
    status: Literal["متوافق", "مخالف", "غير مذكور", "مبهم / عالي المخاطر"] = Field(description="حالة البند")
    risk_category: Literal["نظامي وقانوني", "مالي وتعويضي", "تشغيلي وإجرائي", "سرية وحقوق فكرية"] = Field(description="بعد المخاطرة التعاقدية")
    legal_reference: str = Field(description="القاعدة المرجعية أو المعيار التجاري المطبق")
    risk_level: Literal["منخفض", "متوسط", "حرج"] = Field(description="مستوى الخطورة")
    analysis: str = Field(description="التحليل القانوني للسبب")
    recommendation: str = Field(description="الصياغة البديلة المقترحة للتصحيح")

# 4. التقرير التنفيذي الشامل
class AuditReport(BaseModel):
    contract_summary: str = Field(description="ملخص تنفيذي لنوع العقد وأطرافه وموضوعه")
    compliance_score: int = Field(description="مؤشر السلامة والامتثال من 100")
    metadata: ContractMetadata = Field(description="بيانات العقد الجوهرية")
    traps: List[ContractTrap] = Field(description="الفخاخ التعاقدية المكتشفة")
    items: List[ComplianceItem] = Field(description="قائمة البنود المفحوصة")

def get_audit_chain():
    parser = PydanticOutputParser(pydantic_object=AuditReport)
    
    system_prompt = """أنت مستشار قانوني واستراتيجي خبير في إدارة وتدقيق العقود (Contract Lifecycle Management).
مهمتك فحص نص العقد المرفق بدقة احترافية وفق المعايير والقواعد التالية الخاصة بـ ({contract_type}):

القواعد والمعايير المرجعية:
{rules}

المهام الإلزامية:
1. استخراج بطاقة البيانات الجوهرية (الأطراف، المدة، الشروط المالية، والتجديد).
2. رصد الفخاخ التعاقدية (Killer Clauses) مثل: التعويض غير المحدود، أو فترات السرية غير المحددة، أو الشروط الجزائية المبالغ فيها.
3. فحص البنود ومطابقتها مع اللوائح، وتصنيف كل بند بحسب بعد المخاطرة (نظامي، مالي، تشغيلي، سرية).
4. الالتزام الصارم بهيكل البيانات المهيكل.

{format_instructions}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "إليك نص العقد:\n\n{contract_text}")
    ])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    # أو لـ Gemini:
    # llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

    chain = prompt.partial(format_instructions=parser.get_format_instructions()) | llm | parser
    return chain

def audit_contract_text(contract_text: str, contract_category: str) -> AuditReport:
    chain = get_audit_chain()
    
    if "شركات" in contract_category or "تجاري" in contract_category:
        selected_rules = COMMERCIAL_CONTRACT_RULES
        contract_type_label = "عقود الشركات والتوريد التجاري (B2B)"
    else:
        selected_rules = SAUDI_LABOR_LAW_RULES
        contract_type_label = "عقد عمل (نظام العمل)"
        
    return chain.invoke({
        "contract_text": contract_text,
        "rules": selected_rules,
        "contract_type": contract_type_label
    })