"""
تصدير مذكرة الفحص القانوني النافي للجهالة (Markdown) — بالعربية أو الإنجليزية
"""
from datetime import datetime
from typing import Dict, Optional

from i18n import engine_label, show, source_label, tr
from labor_law_data import type_info
from schemas import AuditReport, NegotiationSession, report_stats

# متاح للتوافق مع الاستخدامات القديمة
ENGINE_LABELS = {"llm": "LangChain + OpenAI", "rules": "المحرك المحلي للخبير القانوني"}


def build_memo(report: AuditReport, category: str, engine: str = "rules", source: str = "",
               negotiations: Optional[Dict[int, NegotiationSession]] = None, lang: str = "ar") -> str:
    stats = report_stats(report)
    md = report.metadata
    sep = ", " if lang == "en" else "، "
    lines = [
        tr("memo_title", lang),
        "",
        f"- **{tr('memo_date', lang)}:** {datetime.now().strftime('%Y/%m/%d %H:%M')}",
        f"- **{tr('memo_category', lang)}:** {type_info(category, lang)['name']}",
        f"- **{tr('memo_source', lang)}:** {source_label(source, lang)}",
        f"- **{tr('memo_engine', lang)}:** {engine_label(engine, lang)}",
        f"- **{tr('memo_score', lang)}:** {report.compliance_score}%",
        "- " + tr("memo_counts", lang, i=stats["issues"], c=stats["critical"], t=stats["traps"]),
        "",
        tr("memo_s1", lang),
        report.contract_summary,
        "",
        tr("memo_s2", lang),
        f"- **{tr('parties', lang)}:** {sep.join(md.parties) if md.parties else tr('not_set', lang)}",
        f"- **{tr('duration', lang)}:** {md.effective_duration}",
        f"- **{tr('financial', lang)}:** {md.financial_terms}",
        f"- **{tr('renewal', lang)}:** {md.renewal_clause}",
        "",
        tr("memo_s3", lang),
    ]
    if report.traps:
        lines += [f"- **[{show(t.severity, lang)}] {t.trap_name}:** {t.explanation}" for t in report.traps]
    else:
        lines.append(tr("memo_no_traps", lang))

    lines += ["", tr("memo_s4", lang)]
    for idx, item in enumerate(report.items):
        lines += [
            "",
            f"### {idx + 1}. {item.clause_title} — {show(item.status, lang)} "
            f"({tr('memo_sev', lang)}: {show(item.risk_level, lang)} | {tr('dimension', lang)}: {show(item.risk_category, lang)})",
            f"> {item.contract_snippet}",
            "",
            f"- **{tr('reference', lang)}:** {item.legal_reference}",
            f"- **{tr('analysis', lang)}:** {item.analysis}",
            f"- **{tr('memo_alt', lang)}:** {item.recommendation}",
        ]
        session = (negotiations or {}).get(idx)
        if session:
            lines += ["", tr("memo_neg", lang)]
            lines += [f"- **{turn.speaker}:** {turn.argument}" for turn in session.dialogue]
            lines += [f"- **{tr('memo_agreed', lang)}:** {session.agreed_clause}"]

    lines += ["", "---", tr("memo_disclaimer", lang)]
    return "\n".join(lines)
