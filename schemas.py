"""
هياكل البيانات المشتركة (Pydantic) بين محرك LangChain والمحرك المحلي ومحاكي التفاوض
"""
from typing import List, Literal
from pydantic import BaseModel, Field


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


# 5. جلسة التفاوض
class NegotiationTurn(BaseModel):
    speaker: str = Field(description="اسم المتحدث (ممثل الطرف الأضعف أو ممثل الطرف الأقوى)")
    argument: str = Field(description="حجة المتحدث واقتراحه")


class NegotiationSession(BaseModel):
    dialogue: List[NegotiationTurn] = Field(description="حوار التفاوض الدائر بين الطرفين")
    agreed_clause: str = Field(description="الصيغة القانونية التوافقية النهائية المقترحة (Win-Win)")
    benefits_for_party_a: str = Field(description="المكاسب والضمانات التي حققها الطرف الأول")
    benefits_for_party_b: str = Field(description="الحقوق والحماية التي نالها الطرف الثاني")


ISSUE_STATUSES = ("مخالف", "مبهم / عالي المخاطر")


def compute_score(items: List[ComplianceItem]) -> int:
    """مؤشر سلامة موحّد وقابل للتكرار بغض النظر عن المحرك المستخدم."""
    if not items:
        return 0
    weights = {"متوافق": 1.0, "مبهم / عالي المخاطر": 0.4, "غير مذكور": 0.5, "مخالف": 0.0}
    return round(100 * sum(weights.get(i.status, 0) for i in items) / len(items))


def report_stats(report: AuditReport) -> dict:
    return {
        "issues": sum(1 for i in report.items if i.status in ISSUE_STATUSES),
        "critical": sum(1 for i in report.items if i.risk_level == "حرج"),
        "traps": len(report.traps),
    }
