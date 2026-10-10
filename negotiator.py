from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
# إذا كنت تستخدم Gemini:
# from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# هيكل بيانات جلسة التفاوض
class NegotiationTurn(BaseModel):
    speaker: str = Field(description="اسم المتحدث (ممثل الموظف أو ممثل الشركة)")
    argument: str = Field(description="حجة المتحدث واقتراحه")

class NegotiationSession(BaseModel):
    dialogue: List[NegotiationTurn] = Field(description="حوار التفاوض الدائر بين الطرفين")
    agreed_clause: str = Field(description="الصيغة القانونية التوافقية النهائية المقترحة (Win-Win)")
    benefits_for_party_a: str = Field(description="المكاسب والضمانات التي حققتها الشركة")
    benefits_for_party_b: str = Field(description="الحقوق والحماية التي نالها الموظف/المورد")

def run_negotiation(clause_title: str, problematic_text: str, issue_context: str) -> NegotiationSession:
    parser = PydanticOutputParser(pydantic_object=NegotiationSession)

    system_prompt = """أنت محاكي جلسات تفاوض قانونية وتجارية ذكي (Legal Negotiation Simulator).
أمامك بند تعاقدي غير متوازن أو مخالف للنظام. مهمتك إدارة حوار تفاوضي افتراضي ومقنع بين وكيلين:

1. [ممثل الطرف الثاني - الموظف/المورد]: يرفض النص المعيب بلباقة، ويستند للنظام والعدالة العقدية، ويطلب تعديلاً منصفاً.
2. [ممثل الطرف الأول - الشركة]: يتفهم الطلب لكنه يحرص على عدم تفريط الشركة في حقوقها وحمايتها التشغيلية، ويقترح حلاً وسطاً.
3. [الصياغة التوافقية]: صياغة بند قانوني رصين يحقق التوازن الكامل (Win-Win) دون مخالفة أي نظام.

{format_instructions}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", """البند محل النزاع: {clause_title}
النص في العقد: "{problematic_text}"
المشكلة أو المخالفة: {issue_context}

ابدأ جولة التفاوض واستخرج النتيجة التوافقية النهائية.""")
    ])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    # لنموذج Gemini:
    # llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)

    chain = prompt.partial(format_instructions=parser.get_format_instructions()) | llm | parser

    return chain.invoke({
        "clause_title": clause_title,
        "problematic_text": problematic_text,
        "issue_context": issue_context
    })