"""
تصدير مذكرة الفحص القانوني النافي للجهالة (Markdown)
"""
from datetime import datetime
from typing import Dict, Optional

from schemas import AuditReport, NegotiationSession, report_stats

ENGINE_LABELS = {"llm": "LangChain + OpenAI", "rules": "المحرك المحلي للخبير القانوني"}


def build_memo(report: AuditReport, category: str, engine: str = "rules", source: str = "",
               negotiations: Optional[Dict[int, NegotiationSession]] = None) -> str:
    stats = report_stats(report)
    md = report.metadata
    lines = [
        "# مذكرة الفحص القانوني النافي للجهالة (Legal Due Diligence Memo)",
        "",
        f"- **تاريخ التقرير:** {datetime.now().strftime('%Y/%m/%d %H:%M')}",
        f"- **تصنيف العقد:** {category}",
        f"- **مصدر المستند:** {source or '—'}",
        f"- **محرك التحليل:** {ENGINE_LABELS.get(engine, engine)}",
        f"- **مؤشر السلامة القانونية:** {report.compliance_score}%",
        f"- **بنود غير متوازنة:** {stats['issues']} | **مخاطر حرجة:** {stats['critical']} | **فخاخ مرصودة:** {stats['traps']}",
        "",
        "## 1. الملخص التنفيذي",
        report.contract_summary,
        "",
        "## 2. بطاقة البيانات الجوهرية",
        f"- **الأطراف:** {'، '.join(md.parties) if md.parties else 'غير محدد'}",
        f"- **المدة والسريان:** {md.effective_duration}",
        f"- **المقابل المالي وشروط الدفع:** {md.financial_terms}",
        f"- **أحكام التجديد والإنهاء:** {md.renewal_clause}",
        "",
        "## 3. الفخاخ والشروط القاتلة المرصودة",
    ]
    if report.traps:
        lines += [f"- **[{t.severity}] {t.trap_name}:** {t.explanation}" for t in report.traps]
    else:
        lines.append("- لم يتم رصد فخاخ تعاقدية.")

    lines += ["", "## 4. نتائج فحص البنود"]
    for idx, item in enumerate(report.items):
        lines += [
            "",
            f"### {idx + 1}. {item.clause_title} — {item.status} (خطورة: {item.risk_level} | البعد: {item.risk_category})",
            f"> {item.contract_snippet}",
            "",
            f"- **السند القانوني / المعيار:** {item.legal_reference}",
            f"- **التحليل:** {item.analysis}",
            f"- **الصياغة البديلة المقترحة:** {item.recommendation}",
        ]
        session = (negotiations or {}).get(idx)
        if session:
            lines += ["", "**محضر جلسة التفاوض الآلي:**"]
            lines += [f"- **{turn.speaker}:** {turn.argument}" for turn in session.dialogue]
            lines += [f"- **الصيغة التوافقية (Win-Win):** {session.agreed_clause}"]

    lines += [
        "",
        "---",
        "_هذه المذكرة استرشادية صادرة عن نظام آلي، ولا تغني عن مراجعة محامٍ مرخص قبل التوقيع._",
    ]
    return "\n".join(lines)
