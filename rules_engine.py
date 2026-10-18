"""
المحرك المحلي للخبير القانوني (Offline Expert Rules Engine)
يعمل دون اتصال بالإنترنت أو مفتاح API، ويُنتج نفس هيكل AuditReport الذي ينتجه خط LangChain،
ليكون محركاً احتياطياً يضمن عمل المنصة دائماً.
يدعم العقود العربية والإنجليزية، ويكتب نتائج التحليل بالعربية أو الإنجليزية حسب لغة الواجهة.
"""
import contextvars
import re
from dataclasses import dataclass
from typing import Callable, List, Optional

from schemas import AuditReport, ComplianceItem, ContractMetadata, ContractTrap, compute_score
from labor_law_data import type_info

# لغة نصوص التحليل الحالية ("ar" أو "en") — تُضبط داخل analyze_contract
_LANG = contextvars.ContextVar("rules_lang", default="ar")


def T(ar: str, en: str) -> str:
    return en if _LANG.get() == "en" else ar


# ---------------------------------------------------------------------------
# 1. تطبيع النص واستخراج الأرقام (عربي + إنجليزي)
# ---------------------------------------------------------------------------
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟـ]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٪٫", "0123456789%.")


def norm(text: str) -> str:
    text = _DIACRITICS.sub("", text).translate(_DIGITS).lower()
    text = re.sub("[إأآٱ]", "ا", text)
    return text.replace("ة", "ه").replace("ى", "ي")


def has(t: str, *patterns: str) -> bool:
    return any(re.search(norm(p), t) for p in patterns)


def _nums(t: str, unit_pattern: str) -> List[float]:
    vals = re.findall(r"(\d+(?:\.\d+)?)\s*\)?\s*(?:" + norm(unit_pattern) + ")", t)
    return [float(v) for v in vals]


def percents(t: str) -> List[float]:
    out = []
    for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*%|%\s*(\d+(?:\.\d+)?)", t):
        out.append(float(a or b))
    out += _nums(t, r"بالمائه|في المائه|بالمئه|percent|per cent")
    return out


def days(t: str) -> List[float]:
    vals = _nums(t, r"يوما|يوم|ايام|days?\b")
    if has(t, r"ليوم واحد|يوم واحد|\bone day\b"):
        vals.append(1)
    return vals


def months(t: str) -> List[float]:
    vals = _nums(t, r"اشهر|شهرا|شهور|شهر|months?\b")
    if has(t, r"شهر واحد|\bone month"):
        vals.append(1)
    return vals


_WORD_YEARS = {r"سنتين|سنتان|عامين|عامان|\btwo years?\b": 2, r"سنه واحده|عام واحد|\bone year\b": 1,
               r"ثلاث سنوات|ثلاثه اعوام|\bthree years\b": 3, r"اربع سنوات|اربعه اعوام|\bfour years\b": 4,
               r"خمس سنوات|خمسه اعوام|\bfive years\b": 5, r"عشر سنوات|\bten years\b": 10}


def years(t: str) -> List[float]:
    vals = _nums(t, r"سنوات|سنه|سنين|اعوام|عاما|عام|years?\b")
    for pat, v in _WORD_YEARS.items():
        if has(t, pat):
            vals.append(v)
    return vals


def fmt_years(y: float) -> str:
    if _LANG.get() == "en":
        return "one year" if y == 1 else f"{y:g} years"
    if y == 1:
        return "سنة واحدة"
    if y == 2:
        return "سنتان"
    return f"{y:g} سنوات" if 3 <= y <= 10 else f"{y:g} سنة"


def money(t: str) -> List[float]:
    vals = re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(?:ريال|ر\.س|sar\b|riyals?|saudi riyals)", t)
    vals += re.findall(r"(?:\bsar|\bsr)\s*(\d[\d,]*(?:\.\d+)?)", t)
    return [float(v.replace(",", "")) for v in vals]


# ---------------------------------------------------------------------------
# 2. نتيجة تقييم بند
# ---------------------------------------------------------------------------
OK, BAD, AMBIG, MISSING = "متوافق", "مخالف", "مبهم / عالي المخاطر", "غير مذكور"


@dataclass
class Finding:
    status: str
    level: str
    analysis: str
    ref: str
    rec: str
    trap: Optional[tuple] = None  # (اسم الفخ، الخطورة، الشرح)


def killer(name, analysis, ref, rec, explanation=None):
    return Finding(BAD, "حرج", analysis, ref, rec, (name, "حرج جداً", explanation or analysis))


def ok(analysis, ref, rec=None):
    return Finding(OK, "منخفض", analysis, ref,
                   rec or T("البند متوازن ولا يحتاج إلى تعديل جوهري.", "The clause is balanced and needs no substantive change."))


# ---------------------------------------------------------------------------
# 3. مقيّمات البنود
# ---------------------------------------------------------------------------
def ev_duration(t, ctx):
    ref = T("معيار وضوح المدة وآلية التجديد (مبدأ نفي الجهالة في العقود)",
            "Clarity of term and renewal mechanism (principle of eliminating contractual uncertainty)")
    auto = has(t, r"يتجدد\s*تلقائيا", r"تتجدد\s*تلقائيا", r"تجديد\s*تلقائي", r"يجدد\s*تلقائيا",
               r"automatically renew", r"renew(s|ing)? automatically", r"auto-?renew", r"automatic renewal")
    notice = max(days(t), default=None)
    mutual = has(t, r"(احد|اي من|لاي من|كل من) الطرفين", r"يحق للطرفين", r"either party", r"each party", r"both parties")
    one_sided = has(t, r"ما لم يقم الطرف الاول", r"الطرف الاول وحده", r"ما لم يخطر المستاجر",
                    r"unless the first party", r"first party alone", r"unless the tenant notifies") and not mutual
    if has(t, r"غير محدد[ه]? المده", r"مفتوح[ه]? المده", r"indefinite (term|period|duration)", r"open-ended"):
        return Finding(AMBIG, "متوسط", T("العقد غير محدد المدة، مما يجعل الالتزامات مفتوحة زمنياً ويصعّب الخروج منه.",
                                         "The contract has no fixed term, leaving obligations open-ended and making exit difficult."),
                       ref, T("تحديد مدة واضحة للعقد مع آلية تجديد صريحة بإشعار كتابي متبادل لا يقل عن 30 يوماً.",
                              "Set a clear term with an explicit renewal mechanism and mutual written notice of at least 30 days."))
    if auto and notice is None:
        return Finding(BAD, "حرج", T("العقد يتجدد تلقائياً دون تحديد مهلة أو آلية للإشعار بعدم التجديد (تجديد صامت).",
                                     "The contract renews automatically with no notice period or mechanism for non-renewal (silent renewal)."),
                       ref, T("ينص على حق كل طرف في عدم التجديد بإشعار كتابي قبل 30 إلى 60 يوماً من انتهاء المدة.",
                              "Give each party the right not to renew by written notice 30 to 60 days before expiry."),
                       (T("تجديد تلقائي صامت", "Silent automatic renewal"), "متوسط",
                        T("العقد يتجدد دون آلية خروج واضحة، فيبقى الطرف ملتزماً لمدد إضافية دون إرادة صريحة.",
                          "The contract renews without a clear exit, binding the party for extra terms without explicit consent.")))
    if auto and notice > 90:
        return Finding(AMBIG, "متوسط", T(f"مهلة الإشعار بعدم التجديد ({int(notice)} يوماً) طويلة جداً، وفوات الموعد يعني الالتزام بمدة كاملة جديدة.",
                                         f"The non-renewal notice period ({int(notice)} days) is very long; missing it means being bound for a whole new term."),
                       ref, T("تخفيض مهلة الإشعار بعدم التجديد إلى 60 يوماً كحد أقصى وجعلها حقاً متبادلاً للطرفين.",
                              "Reduce the non-renewal notice to a maximum of 60 days and make it a mutual right."),
                       (T("مهلة عدم تجديد طويلة", "Long non-renewal notice"), "متوسط",
                        T(f"اشتراط الإشعار قبل {int(notice)} يوماً يجعل التجديد التلقائي شبه حتمي ما لم تتم المتابعة الدقيقة للمواعيد.",
                          f"Requiring notice {int(notice)} days ahead makes automatic renewal almost inevitable unless deadlines are tracked closely.")))
    if auto and one_sided:
        return Finding(AMBIG, "متوسط", T("حق الإشعار بعدم التجديد مقصور على طرف واحد، مما يحرم الطرف الآخر من الخروج عند انتهاء المدة.",
                                         "Only one party may give notice of non-renewal, denying the other party an exit at the end of the term."),
                       ref, T("يحق لأي من الطرفين عدم تجديد العقد بموجب إشعار كتابي يرسل قبل 60 يوماً من تاريخ انتهاء مدته.",
                              "Either party may elect not to renew the contract by written notice sent 60 days before its expiry."))
    note = (T(f" مع آلية تجديد بإشعار مدته {int(notice)} يوماً.", f", with a renewal mechanism requiring {int(notice)} days' notice.")
            if auto and notice else ".")
    return ok(T("مدة العقد محددة وواضحة", "The contract term is defined and clear") + note +
              T(" يوصى بقيد موعد الإشعار في تقويم المتابعة.", " It is advisable to record the notice deadline in a follow-up calendar."), ref)


def ev_payment(t, ctx):
    ref = T("المعيار التجاري لشروط السداد (30 - 60 يوماً) وثبات المقابل المالي",
            "Commercial standard for payment terms (30-60 days) and fixed consideration")
    if has(t, r"(يحق|يجوز) (للمزود|للطرف الاول|للمؤجر|لصاحب العمل|للشركه) (تعديل|زياده|رفع|تغيير) (الرسوم|الاسعار|الاجره|القيمه|الاجر)",
           r"(provider|first party|landlord|employer|company) may (amend|increase|change|modify|adjust|raise) (the )?(fees|prices|rent|wage|salary|amount)"):
        notice = min(days(t), default=None)
        n_txt = T(f" بإشعار قصير مدته {int(notice)} أيام", f" with a short notice of {int(notice)} days") if notice else ""
        return Finding(BAD, "حرج", T(f"يملك الطرف الأقوى حق تعديل المقابل المالي بشكل أحادي{n_txt}، مما يفقد العقد ثباته المالي.",
                                     f"The stronger party may change the consideration unilaterally{n_txt}, removing the contract's financial certainty."),
                       ref, T("تكون الرسوم ثابتة طوال مدة الاشتراك، ولا يجوز تعديلها إلا عند التجديد بإشعار لا يقل عن 60 يوماً مع حق الطرف الآخر في عدم التجديد.",
                              "Fees are fixed for the whole subscription term and may only change on renewal with at least 60 days' notice and the other party's right not to renew."),
                       (T("تعديل أحادي للأسعار", "Unilateral price change"), "متوسط",
                        T("يحق للطرف الآخر رفع الأسعار متى شاء، فتتحول القيمة المتفق عليها إلى رقم غير مضمون.",
                          "The other party can raise prices at will, so the agreed amount is no longer guaranteed.")))
    if has(t, r"(يحق|يجوز)[^.]{0,30}(خصم|حسم|حجب)[^.]{0,30}(الاجر|الراتب|المستحقات)[^.]{0,30}(تقديره|اي وقت)",
           r"may (deduct|withhold)[^.]{0,30}(wage|salary|dues|entitlements)[^.]{0,30}(discretion|any time)"):
        return Finding(BAD, "حرج", T("يجيز البند الخصم من المستحقات بإرادة منفردة.", "The clause allows unilateral deductions from entitlements."), ref,
                       T("لا يجوز الخصم من المستحقات إلا في الحالات المحددة نظاماً وبعد إشعار مكتوب ومبرر.",
                         "No deduction from entitlements except in legally defined cases and after justified written notice."))
    due = [d for d in days(t) if d > 1]
    if due and max(due) > 90:
        return Finding(BAD, "حرج", T(f"مدة السداد ({int(max(due))} يوماً) طويلة جداً وتضغط على السيولة النقدية.",
                                     f"The payment period ({int(max(due))} days) is far too long and strains cash flow."),
                       ref, T("يلتزم الطرف المدين بسداد الفواتير المعتمدة خلال 30 يوماً من تاريخ استلامها، مع غرامة تأخير معقولة عن التأخر في السداد.",
                              "The paying party shall settle approved invoices within 30 days of receipt, with a reasonable late-payment charge."))
    if due and max(due) > 60:
        return Finding(AMBIG, "متوسط", T(f"مدة السداد ({int(max(due))} يوماً) أطول من المعيار التجاري المعتاد.",
                                         f"The payment period ({int(max(due))} days) is longer than the usual commercial standard."),
                       ref, T("تقليص مدة السداد إلى 30 - 45 يوماً من تاريخ الفاتورة المعتمدة.",
                              "Shorten the payment period to 30-45 days from the approved invoice date."))
    if not money(t) and not percents(t) and not has(t, r"\d"):
        return Finding(AMBIG, "متوسط", T("لم يحدد البند المقابل المالي بشكل رقمي واضح، مما يخلق جهالة في الثمن.",
                                         "The clause does not state the consideration in clear figures, creating uncertainty about the price."),
                       ref, T("تحديد المبلغ رقماً وكتابةً وطريقة ومواعيد السداد بدقة.",
                              "State the amount in figures and words, with precise payment method and dates."))
    return ok(T("المقابل المالي محدد بوضوح ومواعيد السداد ضمن المعيار المقبول.",
                "The consideration is clearly defined and payment dates are within the accepted standard."), ref)


def ev_late_penalty(t, ctx):
    ref = T("المعيار التجاري للشرط الجزائي: لا يتجاوز 10% - 20% من قيمة العقد، وللقضاء تخفيض التعويض الاتفاقي المبالغ فيه",
            "Commercial standard for penalty clauses: no more than 10%-20% of contract value; courts may reduce excessive agreed damages")
    pct = max(percents(t), default=None)
    capped = has(t, r"حد اقصي|بحد اقصي|لا تتجاوز|لا يتجاوز|سقف|بما لا يزيد", r"maximum|not exceed|\bcap(ped)?\b|up to a maximum")
    alt = T("في حال التأخير عن التسليم لأسباب تعود للمزود، تحتسب غرامة تأخير بنسبة 0.5% من قيمة المرحلة المتأخرة عن كل أسبوع تأخير، "
            "بحد أقصى 10% من القيمة الإجمالية للعقد، وبعد إشعار كتابي ومهلة تصحيح لا تقل عن 7 أيام.",
            "If delivery is delayed for reasons attributable to the Provider, a delay penalty of 0.5% of the delayed phase value applies per week of delay, "
            "capped at 10% of the total contract value, after written notice and a cure period of at least 7 days.")
    if pct is not None and pct >= 20:
        return killer(T("غرامة تأخير مرتفعة", "Excessive delay penalty"),
                      T(f"غرامة التأخير بنسبة {pct:g}% من قيمة العقد تعتبر مرتفعة جداً وغير منطقية، مما يعرض الطرف الملتزم لمخاطر مالية كبيرة قد تلتهم كامل هامش الربح.",
                        f"A delay penalty of {pct:g}% of the contract value is excessive and unreasonable, exposing the obligated party to major financial risk that could wipe out the entire profit margin."),
                      ref, alt)
    if pct is not None and pct > 10:
        return Finding(BAD, "حرج", T(f"غرامة التأخير ({pct:g}%) أعلى من المعيار التجاري المتعارف عليه.",
                                     f"The delay penalty ({pct:g}%) exceeds the accepted commercial standard."), ref, alt,
                       (T("شرط جزائي مرتفع", "High penalty clause"), "متوسط",
                        T(f"نسبة {pct:g}% تتجاوز السقف المعتاد وتعرض الطرف الملتزم لخسائر غير متناسبة.",
                          f"A rate of {pct:g}% exceeds the usual cap and exposes the obligated party to disproportionate losses.")))
    if pct is not None and not capped and not has(t, r"(اسبوع|يوم|شهر)", r"week|\bday|month"):
        return ok(T(f"نسبة الغرامة ({pct:g}%) ضمن الحدود المقبولة.", f"The penalty rate ({pct:g}%) is within acceptable limits."), ref)
    if not capped:
        return Finding(AMBIG, "متوسط", T("الغرامة غير مقيدة بسقف أعلى، فقد تتراكم مع طول مدة التأخير إلى مبالغ كبيرة.",
                                         "The penalty has no upper cap and may accumulate to large sums as the delay grows."), ref, alt)
    return ok(T("غرامة التأخير معقولة ومقيدة بسقف أعلى واضح.", "The delay penalty is reasonable and has a clear upper cap."), ref)


def ev_liability(t, ctx):
    ref = T("مبدأ تحديد سقف المسؤولية (Limitation of Liability) واستثناء الأضرار غير المباشرة",
            "Limitation of liability principle and exclusion of indirect damages")
    protective = has(t, r"(لا يتحمل|لا يسال|لا يكون مسؤولا|يستثني|باستثناء)[^.]{0,60}(غير المباشر|فوات|الارباح الفائته)",
                     r"(shall not be liable|not be responsible|excluding|exclude[sd]?)[^.]{0,60}(indirect|consequential|loss of profit)")
    capped = has(t, r"لا تتجاوز|لا يتجاوز|حد اقصي|سقف|بما لا يزيد", r"(not|no event|no case)[^.]{0,12}exceed|maximum|\bcap\b|limited to")
    unlimited = has(t, r"غير (ال)?محدود", r"(دون|بلا) (اي )?(حد|سقف)", r"كامل المسؤوليه", r"مسؤوليه مطلقه",
                    r"unlimited", r"without (any )?(limit|cap)", r"full liability", r"absolute liability") or (
        has(t, r"غير المباشر", r"فوات (ال)?ارباح", r"الارباح الفائته", r"indirect", r"consequential", r"loss of profits?") and not protective)
    alt = T("لا تتجاوز المسؤولية الإجمالية لأي من الطرفين بموجب هذا العقد قيمة المبالغ المدفوعة فعلياً خلال الاثني عشر شهراً السابقة للمطالبة، "
            "ولا يسأل أي طرف عن الأضرار غير المباشرة أو فوات الأرباح، وذلك فيما عدا حالات الغش أو الخطأ الجسيم.",
            "The total liability of either party under this contract shall not exceed the amounts actually paid in the twelve months preceding the claim, "
            "and neither party shall be liable for indirect damages or loss of profits, except in cases of fraud or gross negligence.")
    if unlimited and not capped:
        return killer(T("مسؤولية تعويضية غير محدودة", "Unlimited liability"),
                      T("تحمّل الطرف الملتزم مسؤولية تعويضية غير محدودة عن أي خسائر مباشرة أو غير مباشرة قد تصيب الطرف الآخر، بما يشمل فوات الأرباح، وهو ما قد يتجاوز قيمة العقد نفسه بأضعاف.",
                        "The obligated party bears unlimited liability for any direct or indirect losses suffered by the other party, including loss of profits, which could exceed the contract value many times over."),
                      ref, alt)
    if capped and has(t, r"شهر واحد", r"رسوم شهر", r"one month", r"month's fees"):
        return Finding(AMBIG, "متوسط", T("سقف المسؤولية رمزي (رسوم شهر واحد) لا يتناسب مع حجم المخاطر، مما يفرغ الالتزام من مضمونه.",
                                         "The liability cap is token (one month of fees) and disproportionate to the risk, emptying the obligation of meaning."),
                       ref, T(alt.replace("قيمة المبالغ المدفوعة فعلياً خلال الاثني عشر شهراً", "قيمة الرسوم المدفوعة خلال الاثني عشر شهراً"),
                              alt.replace("the amounts actually paid in the twelve months", "the fees paid in the twelve months")),
                       (T("سقف مسؤولية رمزي", "Token liability cap"), "متوسط",
                        T("مسؤولية المزود لا تتجاوز رسوم شهر واحد مهما بلغ حجم الضرر الواقع على العميل.",
                          "The provider's liability never exceeds one month of fees, however large the client's loss.")))
    if capped:
        return ok(T("المسؤولية مقيدة بسقف مالي واضح ومتوازن.", "Liability is limited by a clear and balanced financial cap."), ref)
    return Finding(AMBIG, "متوسط", T("لم يحدد البند سقفاً مالياً للمسؤولية، فتبقى المخاطر مفتوحة.",
                                     "The clause sets no financial cap on liability, leaving the risk open."), ref, alt)


def ev_confidentiality(t, ctx):
    ref = T("المعيار التجاري لمدة التزام السرية: 2 - 5 سنوات بعد انتهاء العقد",
            "Commercial standard for confidentiality duration: 2-5 years after expiry")
    alt = T("يلتزم كل طرف بالمحافظة على سرية المعلومات التي يطلع عليها خلال مدة العقد ولمدة ثلاث سنوات من تاريخ انتهائه، "
            "باستثناء المعلومات المتاحة للعموم أو المعروفة مسبقاً أو التي يلزم الإفصاح عنها بموجب الأنظمة، وتستمر حماية الأسرار التجارية المعرّفة كتابياً ما دامت محتفظة بسريتها.",
            "Each party shall keep confidential the information it receives during the term and for three years after expiry, "
            "except information that is public, already known, or required to be disclosed by law; trade secrets identified in writing remain protected as long as they stay confidential.")
    if has(t, r"الي الابد", r"ابدي", r"ابديه", r"بصفه دائمه", r"بشكل دائم", r"(دون|بدون) (اي )?سقف زمني",
           r"غير محدد[ه]? (المده|زمنيا)", r"لا ينقضي", r"مدي الحياه",
           r"forever", r"perpetual", r"permanent", r"without (any )?time limit", r"indefinite(ly)?", r"shall not lapse", r"in perpetuity"):
        return killer(T("سرية أبدية", "Perpetual confidentiality"),
                      T("التزام الطرف بالسرية الأبدية لجميع البيانات دون أي سقف زمني يعد التزاماً مفرطاً وغير عملي، ويبقي الطرف معرضاً للمطالبات بشكل دائم.",
                        "A perpetual confidentiality obligation over all data with no time limit is excessive and impractical, leaving the party exposed to claims forever."),
                      ref, alt)
    y = max(years(t), default=None)
    if y and y > 5:
        return Finding(AMBIG, "متوسط", T(f"مدة الالتزام بالسرية ({fmt_years(y)}) أطول من المعتاد تجارياً.",
                                         f"The confidentiality period ({fmt_years(y)}) is longer than commercially usual."), ref, alt)
    if y:
        return ok(T(f"التزام السرية محدد بمدة معقولة ({fmt_years(y)} بعد الانتهاء).",
                    f"The confidentiality obligation has a reasonable duration ({fmt_years(y)} after expiry)."), ref)
    return Finding(AMBIG, "منخفض", T("لم يحدد البند مدة الالتزام بالسرية بعد انتهاء العقد بوضوح.",
                                     "The clause does not clearly state how long confidentiality lasts after expiry."), ref, alt)


def ev_termination(t, ctx):
    labor = "عمل" in ctx["category"]
    ref = (T("نظام العمل: المادة 75 (مهلة الإشعار)، والمادة 77 (التعويض عن الإنهاء لسبب غير مشروع)، والمادة 80 (حالات الفسخ دون إشعار)",
             "Labor Law: Article 75 (notice period), Article 77 (compensation for termination without valid reason), Article 80 (termination without notice)")
           if labor else T("مبدأ الإشعار المسبق ومهلة التصحيح (Cure Period) قبل الإنهاء، وحظر الإنهاء التعسفي",
                           "Principle of prior notice and a cure period before termination, and prohibition of abusive termination"))
    immediate = has(t, r"فوري", r"فورا", r"(دون|بدون) (سابق )?(اشعار|انذار)", r"immediate(ly)?", r"without (prior )?notice")
    breach = has(t, r"اخلال", r"تاخر", r"مخالفه", r"اعسار", r"افلاس", r"الماده 80",
                 r"breach", r"late in pay", r"delay", r"default", r"insolven", r"bankrupt", r"article 80")
    arbitrary = has(t, r"لاي سبب", r"(دون|بدون) ابداء (ال)?اسباب", r"حسب تقديره", r"يراه مناسبا", r"في اي وقت",
                    r"for any reason", r"without (giving )?reasons?", r"at its (sole )?discretion", r"deems appropriate", r"sees fit", r"at any time")
    no_pay = has(t, r"(دون|بدون) (الالتزام )?(بسداد|سداد|دفع|مكافاه|تعويض)", r"لا يحق[^.]{0,40}المطالبه",
                 r"without (any )?(obligation to pay|payment|award|compensation)", r"not entitled to claim")
    mutual = has(t, r"(لاي|لكل) من الطرفين", r"لاي طرف", r"يحق للطرفين", r"either party", r"each party", r"both parties")
    if labor:
        alt = T("يحق لأي من الطرفين إنهاء العقد لسبب مشروع بإشعار كتابي لا تقل مدته عن 60 يوماً، ولا يجوز لصاحب العمل فسخ العقد دون إشعار أو مكافأة "
                "إلا في الحالات المنصوص عليها في المادة 80 من نظام العمل، مع حفظ حق العامل في مستحقاته النظامية كاملة.",
                "Either party may terminate the contract for a valid reason with written notice of at least 60 days; the employer may not terminate without notice or award "
                "except in the cases set out in Article 80 of the Labor Law, preserving the employee's full statutory entitlements.")
    else:
        alt = T("يحق لأي من الطرفين إنهاء العقد في حال إخلال الطرف الآخر إخلالاً جوهرياً لم يُعالَج خلال 30 يوماً من استلامه إشعاراً كتابياً بذلك، "
                "مع التزام الطرف المُنهي بسداد قيمة الأعمال المنجزة والمقبولة حتى تاريخ الإنهاء.",
                "Either party may terminate the contract if the other commits a material breach not remedied within 30 days of receiving written notice, "
                "with the terminating party paying for work completed and accepted up to the termination date.")
    if immediate and (arbitrary or not breach):
        extra = T(" كما يحرم البند الطرف الآخر من مستحقاته عن الأعمال المنجزة.", " It also deprives the other party of payment for completed work.") if no_pay else ""
        return killer(T("إنهاء فوري بدون إشعار", "Immediate termination without notice"),
                      T("حق الطرف الأقوى في إنهاء العقد بشكل فوري دون إشعار مسبق ودون مبرر يعد بنداً تعسفياً، ويعرض الطرف الآخر لمخاطر كبيرة.",
                        "The stronger party's right to terminate immediately, without prior notice or justification, is abusive and exposes the other party to major risk.") + extra,
                      ref, alt)
    if immediate and breach:
        return Finding(BAD, "حرج", T("يجيز البند الفسخ الفوري عند أي إخلال مهما كان بسيطاً دون منح مهلة إنذار أو تصحيح.",
                                     "The clause allows immediate termination for any breach, however minor, without a warning or cure period."), ref, alt,
                       (T("فسخ فوري دون مهلة تصحيح", "Immediate termination with no cure period"), "متوسط",
                        T("أي تأخير بسيط يمنح الطرف الآخر حق الفسخ والإخلاء فوراً دون فرصة للمعالجة.",
                          "Any minor delay lets the other party terminate and evict immediately with no chance to remedy.")))
    notice = min([d for d in days(t) if d > 1], default=None)
    min_notice = 60 if labor and has(t, r"غير محدد", r"indefinite") else 30
    if notice is not None and notice < min_notice:
        return Finding(AMBIG, "متوسط", T(f"مهلة الإشعار بالإنهاء ({int(notice)} يوماً) أقل من الحد المقبول ({min_notice} يوماً).",
                                         f"The termination notice ({int(notice)} days) is below the acceptable minimum ({min_notice} days)."), ref, alt)
    if notice is not None:
        note = "" if mutual else T(" مع ملاحظة أن حق الإنهاء غير متبادل بشكل صريح.", " Note that the termination right is not expressly mutual.")
        return ok(T(f"آلية الإنهاء واضحة بمهلة إشعار مقدارها {int(notice)} يوماً.{note}",
                    f"The termination mechanism is clear, with {int(notice)} days' notice.{note}"), ref)
    return Finding(AMBIG, "متوسط", T("آلية الإنهاء ومهلة الإشعار غير واضحة في النص.", "The termination mechanism and notice period are unclear."), ref, alt)


def ev_ip(t, ctx):
    ref = T("مبدأ ملكية العميل لبياناته ومخرجات العمل المخصص، واحتفاظ المزود بملكيته الفكرية السابقة (Background IP)",
            "Client ownership of its data and custom deliverables, with the provider retaining its pre-existing (background) IP")
    if has(t, r"(تؤول|تنتقل|تصبح)[^.]{0,40}(المزود|للطرف الاول)[^.]{0,80}(البيانات|المحتوي)",
           r"(vest|transfer|become the property)[^.]{0,40}(provider|first party)[^.]{0,80}(data|content)",
           r"(data|content)[^.]{0,120}(vest|transfer|become the property)[^.]{0,20}(provider|first party)"):
        return killer(T("الاستيلاء على بيانات العميل", "Seizure of client data"),
                      T("انتقال ملكية بيانات العميل ومحتواه إلى المزود يعني فقدان العميل السيطرة على أهم أصوله الرقمية وعدم قدرته على استرجاعها أو نقلها.",
                        "Transferring ownership of the client's data and content to the provider means the client loses control of its key digital assets and cannot retrieve or move them."),
                      ref, T("تبقى جميع البيانات والمحتوى الذي يرفعه العميل ملكاً خالصاً له، ويمنح العميل المزود ترخيصاً محدوداً لمعالجتها لغرض تقديم الخدمة فقط، "
                             "مع التزام المزود بتسليمها كاملة وحذفها من أنظمته خلال 30 يوماً من انتهاء الاتفاقية.",
                             "All data and content uploaded by the client remain its exclusive property; the client grants the provider a limited licence to process it solely to deliver the service, "
                             "and the provider shall return it in full and delete it from its systems within 30 days of expiry."))
    if has(t, r"(بما في ذلك|بما فيها|تشمل)[^.]{0,60}(السابقه|القائمه|الخلفيه)", r"(including|includes)[^.]{0,60}(pre-?existing|background)") \
            and not has(t, r"احتفاظ", r"يحتفظ", r"ترخيص", r"retain", r"licen[cs]e"):
        return Finding(BAD, "حرج", T("يستحوذ البند على الملكية الفكرية السابقة للمزود (أدواته ومكتباته) وليس فقط على الأعمال المطورة خصيصاً.",
                                     "The clause takes the provider's pre-existing IP (its tools and libraries), not just the custom-developed work."),
                       ref, T("تؤول للعميل حقوق الأعمال المطورة خصيصاً، ويحتفظ المزود بملكية أدواته السابقة مع منح العميل ترخيصاً دائماً لاستخدامها.",
                              "Rights in custom-developed work vest in the client, while the provider keeps its pre-existing tools and grants the client a perpetual licence to use them."),
                       (T("استحواذ على الملكية الفكرية السابقة", "Takeover of pre-existing IP"), "متوسط",
                        T("المزود يفقد ملكية أدواته الأساسية التي يبني بها أعماله لعملاء آخرين.",
                          "The provider loses the core tools it uses to build work for other clients.")))
    return ok(T("توزيع حقوق الملكية الفكرية متوازن ومحدد.", "The allocation of intellectual property rights is balanced and defined."), ref)


def ev_force_majeure(t, ctx):
    ref = T("مبدأ الإعفاء من المسؤولية عند القوة القاهرة والظروف الطارئة", "Exemption from liability for force majeure and unforeseen events")
    if has(t, r"لا (يعفي|تعتبر|يعتبر|يعتد)", r"shall not (exempt|excuse|be considered|constitute)"):
        return Finding(AMBIG, "متوسط", T("البند يقيد أو يستبعد آثار القوة القاهرة بشكل يحمّل أحد الطرفين مخاطر خارجة عن إرادته.",
                                         "The clause restricts or excludes force majeure, placing risks beyond a party's control on that party."), ref,
                       T("لا يسأل أي من الطرفين عن الإخلال الناتج عن القوة القاهرة، ويحق لأي منهما إنهاء العقد إذا استمرت أكثر من 90 يوماً.",
                         "Neither party is liable for failures caused by force majeure, and either may terminate if it lasts more than 90 days."))
    return ok(T("بند القوة القاهرة متوازن ويعفي الطرفين مع اشتراط الإشعار.", "The force majeure clause is balanced and excuses both parties subject to notice."), ref)


def ev_dispute(t, ctx):
    ref = T("تحديد الجهة القضائية أو التحكيمية المختصة والقانون الواجب التطبيق", "Specifying the competent court or arbitral body and the governing law")
    alt = T("يخضع هذا العقد لأنظمة المملكة العربية السعودية، وتختص المحاكم المختصة في مدينة الرياض (أو المركز السعودي للتحكيم التجاري) بالفصل في أي نزاع ينشأ عنه.",
            "This contract is governed by the laws of the Kingdom of Saudi Arabia, and the competent courts in Riyadh (or the Saudi Center for Commercial Arbitration) shall settle any dispute arising from it.")
    if has(t, r"يتنازل[^.]{0,30}(التقاضي|اللجوء|القضاء)", r"waive[^.]{0,30}(right to (sue|litigat)|court|judicial)"):
        return killer(T("التنازل عن حق التقاضي", "Waiver of the right to sue"),
                      T("يحرم البند أحد الطرفين من حقه الأصيل في اللجوء إلى القضاء.", "The clause deprives a party of its fundamental right to go to court."), ref, alt)
    if has(t, r"لندن|دبي|نيويورك|باريس|سنغافوره|ديلاوير|الامريكيه|البريطانيه|ولايه",
           r"london|dubai|new york|paris|singapore|delaware|\busa\b|united states|england|laws of the state"):
        return Finding(AMBIG, "متوسط", T("يخضع العقد لقانون أجنبي ومحاكم خارج المملكة، مما يرفع تكلفة التقاضي ويعقّد تنفيذ الأحكام.",
                                         "The contract is subject to foreign law and courts outside the Kingdom, raising litigation costs and complicating enforcement."),
                       ref, alt, (T("تقاضٍ في ولاية قضائية أجنبية", "Litigation in a foreign jurisdiction"), "متوسط",
                                  T("أي نزاع سيتطلب التقاضي في الخارج بتكاليف مرتفعة ووفق قوانين غير مألوفة للطرف المحلي.",
                                    "Any dispute would require litigation abroad at high cost and under laws unfamiliar to the local party.")))
    if has(t, r"(يختار|يحدد|حسب اختيار)[^.]{0,20}(الطرف الاول|العميل|المؤجر|المزود)",
           r"(chosen|selected|determined) by the (first party|client|landlord|provider)"):
        return Finding(AMBIG, "متوسط", T("اختيار جهة النظر في النزاع متروك لإرادة طرف واحد.", "The choice of forum is left to one party."), ref, alt)
    return ok(T("جهة فض النزاعات محددة داخل المملكة وبشكل واضح.", "The dispute resolution forum is clearly specified within the Kingdom."), ref)


def ev_probation(t, ctx):
    ref = T("نظام العمل - المادة 53: فترة التجربة لا تزيد على 90 يوماً، ويجوز مدها باتفاق مكتوب بحيث لا يتجاوز مجموعها 180 يوماً",
            "Labor Law - Article 53: probation may not exceed 90 days, extendable by written agreement to a total of 180 days")
    total = max(days(t) + [m * 30 for m in months(t)], default=None)
    alt = T("يخضع العامل لفترة تجربة مدتها 90 يوماً، ويجوز تمديدها مرة واحدة باتفاق مكتوب بين الطرفين على ألا يتجاوز مجموعها 180 يوماً، ولا تدخل فيها إجازتا عيدي الفطر والأضحى والإجازة المرضية.",
            "The employee is subject to a 90-day probation period, extendable once by written agreement up to a total of 180 days, excluding Eid holidays and sick leave.")
    open_ended = has(t, r"اكثر من مره", r"حسب تقديره", r"(دون|بدون) حد", r"more than once", r"at its discretion", r"without limit", r"indefinitely")
    if (total and total > 180) or open_ended:
        d_txt = T(f" ({int(total)} يوماً)", f" ({int(total)} days)") if total else ""
        return Finding(BAD, "حرج", T(f"فترة التجربة{d_txt} تتجاوز الحد النظامي أو قابلة للتمديد المفتوح بإرادة صاحب العمل.",
                                     f"The probation period{d_txt} exceeds the legal limit or can be extended open-endedly at the employer's will."), ref, alt,
                       (T("تجربة مفتوحة", "Open-ended probation"), "متوسط",
                        T("يبقى العامل تحت التجربة لفترة طويلة يمكن خلالها إنهاء عقده دون مكافأة أو تعويض.",
                          "The employee stays on probation for a long time during which the contract can be ended without award or compensation.")))
    if total and total > 90 and not has(t, r"(موافقه|اتفاق) (كتابي|مكتوب)", r"كتابه", r"written (agreement|consent)", r"in writing"):
        return Finding(AMBIG, "متوسط", T(f"فترة التجربة ({int(total)} يوماً) تتجاوز 90 يوماً دون نص على الاتفاق المكتوب.",
                                         f"The probation period ({int(total)} days) exceeds 90 days without stating a written agreement."), ref, alt)
    return ok(T("فترة التجربة ضمن الحد النظامي.", "The probation period is within the legal limit."), ref)


def ev_hours(t, ctx):
    ref = T("نظام العمل - المادة 98 (8 ساعات يومياً أو 48 ساعة أسبوعياً) والمادة 107 (أجر العمل الإضافي = أجر الساعة + 50% من الأجر الأساسي)",
            "Labor Law - Article 98 (8 hours/day or 48 hours/week) and Article 107 (overtime = hourly wage + 50% of basic wage)")
    per_day = [float(x) for x in re.findall(r"(\d+)\s*ساع(?:ات|ه)\s*(?:يوميا|في اليوم|كل يوم)", t)]
    per_day += [float(x) for x in re.findall(r"(\d+)\s*hours?\s*(?:per day|a day|daily|each day)", t)]
    per_week = [float(x) for x in re.findall(r"(\d+)\s*ساع(?:ات|ه)\s*(?:اسبوعيا|في الاسبوع)", t)]
    per_week += [float(x) for x in re.findall(r"(\d+)\s*hours?\s*(?:per week|a week|weekly)", t)]
    week_days = [float(x) for x in re.findall(r"(\d+)\s*ايام\s*(?:اسبوعيا|في الاسبوع)", t)]
    week_days += [float(x) for x in re.findall(r"(\d+)\s*days?\s*(?:per week|a week)", t)]
    weekly = max(per_week + ([max(per_day) * max(week_days)] if per_day and week_days else []), default=None)
    daily = max(per_day, default=None)
    alt = T("ساعات العمل الفعلية 8 ساعات يومياً بحد أقصى 48 ساعة أسبوعياً، ويستحق العامل عن كل ساعة عمل إضافية أجر الساعة مضافاً إليه 50% من أجره الأساسي.",
            "Actual working hours are 8 per day up to 48 per week, and each overtime hour is paid at the hourly wage plus 50% of the basic wage.")
    over = (daily and daily > 8) or (weekly and weekly > 48)
    if daily:
        hrs_txt = T(f" ({daily:g} ساعات يومياً" + (f"، {weekly:g} ساعة أسبوعياً)" if weekly else ")"),
                    f" ({daily:g} hours/day" + (f", {weekly:g} hours/week)" if weekly else ")"))
    else:
        hrs_txt = ""
    if has(t, r"لا يستحق[^.]{0,30}(اجر|مقابل)", r"(دون|بدون) (اجر|مقابل)( اضافي)?",
           r"not (be )?entitled to (any )?(overtime|additional) (pay|wage|compensation)", r"without (any )?(overtime |additional )?(pay|compensation)"):
        return killer(T("عمل إضافي بلا أجر", "Unpaid overtime"),
                      T(f"ساعات العمل{hrs_txt} مع حرمان العامل من أجر العمل الإضافي، وهو شرط باطل يخالف قاعدة آمرة في نظام العمل.",
                        f"Working hours{hrs_txt} while denying the employee overtime pay — a void condition contrary to a mandatory rule of the Labor Law."), ref, alt)
    if over:
        return Finding(BAD, "حرج", T(f"ساعات العمل{hrs_txt} تتجاوز الحد الأقصى النظامي.", f"Working hours{hrs_txt} exceed the legal maximum."), ref, alt)
    return ok(T("ساعات العمل ضمن الحد النظامي.", "Working hours are within the legal limit."), ref)


def ev_leave(t, ctx):
    ref = T("نظام العمل - المادة 109: إجازة سنوية لا تقل عن 21 يوماً تزاد إلى 30 يوماً بعد خمس سنوات متصلة، ولا يجوز التنازل عنها",
            "Labor Law - Article 109: annual leave of at least 21 days, rising to 30 after five continuous years; it may not be waived")
    d = min(days(t), default=None)
    alt = T("يستحق العامل إجازة سنوية مدفوعة الأجر مدتها 21 يوماً، تزاد إلى 30 يوماً إذا أمضى خمس سنوات متصلة في الخدمة.",
            "The employee is entitled to 21 days of paid annual leave, rising to 30 days after five years of continuous service.")
    if d is not None and d < 21:
        return Finding(BAD, "حرج", T(f"مدة الإجازة السنوية ({int(d)} يوماً) أقل من الحد الأدنى النظامي.",
                                     f"The annual leave ({int(d)} days) is below the legal minimum."), ref, alt)
    if has(t, r"التنازل عن الاجازه", r"يتنازل", r"waive (the )?(annual )?leave", r"in lieu of leave"):
        return Finding(BAD, "حرج", T("لا يجوز النص على تنازل العامل عن إجازته السنوية.", "The employee may not be required to waive annual leave."), ref, alt)
    return ok(T("مدة الإجازة السنوية متوافقة مع النظام.", "The annual leave complies with the Labor Law."), ref)


def ev_eos(t, ctx):
    ref = T("نظام العمل - المادة 84 (مكافأة نهاية الخدمة) والمادة 8 (بطلان كل شرط يخالف أحكام النظام ما لم يكن أكثر فائدة للعامل)",
            "Labor Law - Article 84 (end-of-service award) and Article 8 (any condition contrary to the Law is void unless more beneficial to the employee)")
    if has(t, r"يتنازل", r"لا يستحق", r"يسقط حق", r"(دون|بدون) مكافاه", r"حرمان",
           r"waive", r"not (be )?entitled", r"forfeit", r"without (an? )?(end-of-service )?award", r"deprived"):
        return killer(T("إسقاط مكافأة نهاية الخدمة", "Forfeiture of end-of-service award"),
                      T("اشتراط تنازل العامل عن مكافأة نهاية الخدمة باطل نظاماً، فهي حق مقرر بقوة النظام ولا يجوز الاتفاق على إسقاطه.",
                        "Requiring the employee to waive the end-of-service award is void; it is a statutory right that cannot be waived by agreement."),
                      ref, T("يستحق العامل عند انتهاء علاقة العمل مكافأة نهاية الخدمة المقررة في المادة 84 من نظام العمل، وفي حال الاستقالة تحتسب وفق أحكام المادة 85.",
                             "On the end of employment, the employee receives the end-of-service award under Article 84 of the Labor Law; on resignation it is calculated under Article 85."))
    return ok(T("أحكام مكافأة نهاية الخدمة متوافقة مع النظام.", "The end-of-service provisions comply with the Labor Law."), ref)


def ev_non_compete(t, ctx):
    ref = T("نظام العمل - المادة 83: ألا تزيد مدة عدم المنافسة على سنتين، وأن يحدد المكان ونوع العمل",
            "Labor Law - Article 83: a non-compete may not exceed two years and must specify the place and type of work")
    dur = max(years(t) + [m / 12 for m in months(t)], default=None)
    wide = has(t, r"(جميع|كافه) (دول|مناطق|انحاء)", r"العالم", r"دول الخليج", r"اي مكان",
               r"all (gcc|gulf|countries|regions)", r"worldwide", r"anywhere", r"gcc countries", r"gulf countries")
    alt = T("يلتزم الطرف بعدم العمل لدى منافس مباشر في ذات النشاط داخل مدينة مقر العمل لمدة لا تتجاوز سنة واحدة من تاريخ انتهاء العقد.",
            "The party undertakes not to work for a direct competitor in the same business within the city of work for no more than one year after expiry.")
    if dur and dur > 2:
        return Finding(BAD, "حرج", T(f"مدة عدم المنافسة ({fmt_years(dur)}) تتجاوز الحد الأقصى المسموح (سنتان)" + ("، مع نطاق جغرافي واسع جداً." if wide else "."),
                                     f"The non-compete period ({fmt_years(dur)}) exceeds the permitted maximum (two years)" + (", with a very wide geographic scope." if wide else ".")),
                       ref, alt, (T("قيد منافسة مفرط", "Excessive non-compete"), "متوسط",
                                  T("يمنع الطرف من العمل في مجاله لسنوات طويلة وعلى نطاق جغرافي واسع، مما يقيد مصدر رزقه.",
                                    "It bars the party from working in its field for years over a wide area, restricting its livelihood.")))
    if wide:
        return Finding(BAD, "حرج", T("النطاق الجغرافي لعدم المنافسة واسع وغير محدد بدقة.", "The geographic scope of the non-compete is wide and imprecise."), ref, alt)
    if dur is None:
        return Finding(AMBIG, "متوسط", T("لم يحدد البند مدة قيد عدم المنافسة.", "The clause does not state the non-compete period."), ref, alt)
    return ok(T("قيد عدم المنافسة محدد المدة والنطاق ضمن الحدود المقبولة.", "The non-compete has a defined period and scope within acceptable limits."), ref)


def ev_rent_increase(t, ctx):
    ref = T("ثبات الأجرة خلال مدة العقد، ووجوب تحديد نسبة الزيادة وموعدها مسبقاً (العقد الموحد - منصة إيجار)",
            "Rent should be fixed during the term, with any increase rate and date set in advance (Ejar unified contract)")
    alt = T("تكون القيمة الإيجارية ثابتة طوال مدة العقد، ولا تجوز زيادتها إلا عند التجديد بنسبة لا تتجاوز 5% وبإشعار كتابي قبل 90 يوماً من انتهاء المدة.",
            "Rent is fixed for the whole term and may only be increased on renewal by no more than 5% with written notice 90 days before expiry.")
    if has(t, r"(يحق|يجوز) للمؤجر (زياده|رفع|تعديل)", r"landlord may (increase|raise|adjust)") and \
            has(t, r"اي وقت", r"حسب تقديره", r"متي شاء", r"(دون|بدون) موافقه", r"at any time", r"at its discretion", r"without (the tenant's )?consent"):
        return killer(T("زيادة إيجار أحادية مفتوحة", "Open-ended unilateral rent increase"),
                      T("حق المؤجر في زيادة الأجرة في أي وقت ووفق تقديره المطلق يجعل الأجرة مجهولة ويهدد استقرار نشاط المستأجر.",
                        "The landlord's right to raise the rent at any time at its absolute discretion makes the rent uncertain and threatens the tenant's business."), ref, alt)
    pct = max(percents(t), default=None)
    if pct and pct > 5:
        return Finding(AMBIG, "متوسط", T(f"نسبة الزيادة ({pct:g}%) مرتفعة نسبياً.", f"The increase rate ({pct:g}%) is relatively high."), ref, alt)
    return ok(T("أحكام الأجرة وزيادتها محددة وواضحة.", "Rent and increase terms are defined and clear."), ref)


def ev_deposit(t, ctx):
    ref = T("مبلغ الضمان يسترد عند انتهاء العقد بعد خصم الأضرار الموثقة فقط", "The security deposit is refundable at expiry after deducting documented damage only")
    if has(t, r"لا يسترد", r"غير مسترد", r"لا يعاد", r"لا يرد", r"يصبح حقا للمؤجر",
           r"non-refundable", r"not refundable", r"shall not be (returned|refunded)", r"become the property of the landlord"):
        return Finding(BAD, "حرج", T("النص على عدم استرداد مبلغ الضمان بأي حال يحوله إلى أجرة مستترة ويخالف الغرض منه.",
                                     "Making the deposit non-refundable in all cases turns it into hidden rent and defeats its purpose."), ref,
                       T("يعاد مبلغ الضمان للمستأجر خلال 30 يوماً من تسليم العين، بعد خصم تكلفة الأضرار الموثقة بمحضر استلام مشترك إن وجدت.",
                         "The deposit is returned to the tenant within 30 days of handover, after deducting the cost of any damage documented in a joint handover report."),
                       (T("تأمين غير مسترد", "Non-refundable deposit"), "متوسط",
                        T("يخسر المستأجر مبلغ الضمان كاملاً حتى لو سلّم العين بحالة ممتازة.",
                          "The tenant loses the whole deposit even if the premises are returned in excellent condition.")))
    return ok(T("أحكام مبلغ الضمان متوازنة.", "The security deposit terms are balanced."), ref)


def ev_maintenance(t, ctx):
    ref = T("الصيانة الإنشائية والجوهرية على المؤجر، والتشغيلية البسيطة على المستأجر",
            "Structural and major maintenance is the landlord's; minor operational maintenance is the tenant's")
    alt = T("يتحمل المؤجر الصيانة الإنشائية والجوهرية للعقار والتمديدات الرئيسية، ويتحمل المستأجر الصيانة التشغيلية الدورية الناتجة عن الاستعمال المعتاد.",
            "The landlord bears structural and major maintenance of the property and main installations; the tenant bears routine operational maintenance from normal use.")
    tenant = has(t, r"يتحمل المستاجر", r"علي المستاجر", r"على المستاجر", r"tenant shall bear", r"borne by the tenant", r"tenant is responsible")
    if tenant and has(t, r"الانشائيه", r"الهيكليه", r"الجوهريه", r"التمديدات الرئيسيه", r"structural", r"foundational", r"main installations"):
        return Finding(BAD, "حرج", T("تحميل المستأجر الصيانة الإنشائية والهيكلية يحمّله تكاليف رأسمالية هي في الأصل من التزامات المالك.",
                                     "Making the tenant bear structural maintenance loads it with capital costs that are the owner's obligation."), ref, alt,
                       (T("تحميل المستأجر الصيانة الإنشائية", "Structural maintenance on the tenant"), "متوسط",
                        T("قد يتحمل المستأجر تكاليف ترميم ضخمة في عقار لا يملكه.", "The tenant may bear huge repair costs on a property it does not own.")))
    if tenant and has(t, r"(جميع|كافه) (اعمال )?الصيانه", r"all maintenance"):
        return Finding(AMBIG, "متوسط", T("تحميل المستأجر جميع أعمال الصيانة دون تمييز بين التشغيلية والجوهرية.",
                                         "The tenant bears all maintenance without distinguishing operational from major works."), ref, alt)
    return ok(T("توزيع التزامات الصيانة متوازن.", "Maintenance obligations are fairly allocated."), ref)


def ev_assignment(t, ctx):
    ref = T("حظر التنازل أو التأجير من الباطن إلا بموافقة الطرف الآخر", "No assignment or subletting without the other party's consent")
    if has(t, r"(يحق|يجوز) (للمؤجر|للمزود|للطرف الاول) التنازل[^.]{0,40}(دون|بدون) (موافقه|اشعار)",
           r"(landlord|provider|first party) may assign[^.]{0,40}without (consent|notice)"):
        return Finding(AMBIG, "متوسط", T("يحق لطرف واحد التنازل عن العقد لغيره دون موافقة الطرف الآخر.",
                                         "One party may assign the contract to others without the other party's consent."), ref,
                       T("لا يجوز لأي من الطرفين التنازل عن العقد أو أي من حقوقه لغيره إلا بموافقة كتابية مسبقة من الطرف الآخر.",
                         "Neither party may assign the contract or any of its rights without the other party's prior written consent."))
    return ok(T("أحكام التنازل والتأجير من الباطن مقيدة بالموافقة الكتابية وهذا متوازن.",
                "Assignment and subletting require written consent, which is balanced."), ref)


def ev_sla(t, ctx):
    ref = T("اتفاقية مستوى الخدمة (SLA): نسبة توفر لا تقل عن 99.5% مع تعويضات خدمة (Service Credits)",
            "Service level agreement (SLA): availability of at least 99.5% with service credits")
    alt = T("يلتزم المزود بنسبة توفر شهرية لا تقل عن 99.5%، وفي حال الإخلال يستحق العميل خصماً من رسوم الشهر التالي بنسبة 10% عن كل 0.5% نقص، مع حق الإنهاء إذا تكرر الإخلال ثلاثة أشهر.",
            "The provider commits to monthly availability of at least 99.5%; on breach the client receives a 10% credit on next month's fees for each 0.5% shortfall, with a right to terminate after three months of repeated breach.")
    if has(t, r"كما هي", r"(دون|بدون) (اي )?ضمان", r"لا يضمن", r"حسب الحاله",
           r"\bas is\b", r"without any (guarantee|warranty)", r"does not guarantee", r"no guarantee", r"\bas available\b"):
        return killer(T("خدمة بلا ضمان مستوى", "Service with no level guarantee"),
                      T("تقديم الخدمة \"كما هي\" دون أي التزام بنسبة توفر أو أداء يعني أن انقطاع الخدمة لأيام لا يرتب أي مسؤولية على المزود رغم استمرار دفع الرسوم.",
                        "Providing the service \"as is\" with no availability or performance commitment means days of outage create no liability for the provider, while fees keep being paid."),
                      ref, alt)
    pct = max(percents(t), default=None)
    if pct and pct < 99.5:
        return Finding(AMBIG, "متوسط", T(f"نسبة التوفر المضمونة ({pct:g}%) أقل من المعيار المتعارف عليه.",
                                         f"The guaranteed availability ({pct:g}%) is below the accepted standard."), ref, alt)
    if pct and not has(t, r"خصم", r"رصيد", r"تعويض", r"credit", r"discount", r"compensat"):
        return Finding(AMBIG, "منخفض", T("نسبة التوفر محددة لكن دون تعويضات عند الإخلال بها.",
                                         "Availability is defined but with no credits when it is breached."), ref, alt)
    return ok(T("مستوى الخدمة محدد مع آلية تعويض واضحة.", "The service level is defined with a clear compensation mechanism."), ref)


def ev_data(t, ctx):
    ref = T("نظام حماية البيانات الشخصية: ضوابط نقل البيانات خارج المملكة والإفصاح عنها للغير بموافقة صاحبها",
            "Personal Data Protection Law: controls on transferring data outside the Kingdom and disclosing it to others with the owner's consent")
    alt = T("يلتزم المزود بمعالجة بيانات العميل وفق نظام حماية البيانات الشخصية ولوائحه، وتخزينها داخل المملكة، "
            "وعدم الإفصاح عنها لأي طرف ثالث أو نقلها للخارج إلا بموافقة كتابية مسبقة من العميل ووفق الضوابط النظامية.",
            "The provider shall process client data in accordance with the Personal Data Protection Law and its regulations, store it inside the Kingdom, "
            "and not disclose it to any third party or transfer it abroad except with the client's prior written consent and under the legal controls.")
    consent = has(t, r"موافقه (العميل|كتابيه|صاحب)", r"نظام حمايه البيانات", r"consent of the client", r"client's (prior )?(written )?consent",
                  r"written consent", r"personal data protection law", r"\bpdpl\b")
    abroad = has(t, r"خارج المملكه", r"خوادم (خارجيه|اجنبيه)", r"اي دوله", r"outside the kingdom", r"outside saudi", r"foreign servers", r"any country")
    share = has(t, r"(مشاركه|مشاركتها|بيع|بيعها|الافصاح عنها)[^.]{0,40}(اطراف ثالثه|الغير|طرف ثالث)",
                r"(share|sell|disclose)[^.]{0,40}(third part|others)")
    if share and not consent:
        return killer(T("مشاركة البيانات مع أطراف ثالثة", "Sharing data with third parties"),
                      T("يجيز البند للمزود مشاركة بيانات العميل مع أطراف ثالثة" + (" ونقلها إلى خوادم خارج المملكة" if abroad else "") +
                        " دون موافقة، مما يعرض العميل لمخالفات نظام حماية البيانات الشخصية وتسرب بيانات عملائه.",
                        "The clause lets the provider share client data with third parties" + (" and move it to servers outside the Kingdom" if abroad else "") +
                        " without consent, exposing the client to Personal Data Protection Law violations and leaks of its customers' data."), ref, alt)
    if abroad and not consent:
        return Finding(BAD, "حرج", T("نقل البيانات ومعالجتها خارج المملكة دون ضوابط أو موافقة.",
                                     "Data is transferred and processed outside the Kingdom without controls or consent."), ref, alt,
                       (T("نقل البيانات خارج المملكة", "Data transferred outside the Kingdom"), "متوسط",
                        T("قد يعرض العميل لمخالفات نظامية ويصعّب الرقابة على بياناته.",
                          "It may expose the client to legal violations and make it hard to control its data.")))
    if consent:
        return ok(T("معالجة البيانات خاضعة لنظام حماية البيانات الشخصية وموافقة العميل.",
                    "Data processing is subject to the Personal Data Protection Law and the client's consent."), ref)
    return Finding(AMBIG, "متوسط", T("أحكام حماية البيانات عامة وغير كافية.", "The data protection provisions are general and insufficient."), ref, alt)


def ev_nda_scope(t, ctx):
    ref = T("تعريف المعلومات السرية يجب أن يكون محدداً مع الاستثناءات المعتادة (المتاحة للعموم، المعروفة مسبقاً، المطورة باستقلالية)",
            "The definition of confidential information must be specific with the usual exclusions (public, previously known, independently developed)")
    alt = T("المعلومات السرية هي المعلومات غير المتاحة للعموم التي يفصح عنها الطرف المفصح كتابياً ويصفها بأنها سرية لغرض هذه الاتفاقية، "
            "ولا تشمل: المعلومات المتاحة للعموم، أو المعروفة للطرف المتلقي قبل الإفصاح، أو المطورة باستقلالية، أو التي يلزم الإفصاح عنها نظاماً.",
            "Confidential Information means non-public information disclosed in writing by the Disclosing Party and marked confidential for the purpose of this Agreement, "
            "and excludes information that is public, known to the Receiving Party before disclosure, independently developed, or required to be disclosed by law.")
    broad = has(t, r"(جميع|كافه|اي) المعلومات", r"(all|any) information") and \
        has(t, r"متاحه للعموم", r"سواء كانت", r"بغض النظر", r"قبل توقيع", r"publicly available", r"whether or not", r"regardless", r"before or after")
    excl = has(t, r"باستثناء", r"لا تشمل", r"يستثني", r"لا تعد معلومات سريه", r"\bexcept", r"excluding", r"shall not include", r"does not include")
    if broad and not excl:
        return Finding(BAD, "حرج", T("تعريف المعلومات السرية مطاط يشمل حتى المعلومات المتاحة للعموم والسابقة على الاتفاقية، مما يجعل أي استخدام لمعلومات عامة مخالفة.",
                                     "The definition is so broad it covers even public and pre-existing information, making any use of general information a breach."),
                       ref, alt, (T("تعريف مطاط للمعلومات السرية", "Overbroad definition of confidential information"), "متوسط",
                                  T("يمكن اعتبار أي معلومة عامة إفشاءً للسر وترتيب التعويض عليها.",
                                    "Any public information could be treated as a disclosure and trigger damages.")))
    if excl:
        return ok(T("تعريف المعلومات السرية محدد ويتضمن الاستثناءات المعتادة.", "The definition is specific and includes the usual exclusions."), ref)
    return Finding(AMBIG, "متوسط", T("تعريف المعلومات السرية لا يتضمن الاستثناءات المعتادة.", "The definition does not include the usual exclusions."), ref, alt)


def ev_liquidated(t, ctx):
    ref = T("التعويض الاتفاقي يجب أن يتناسب مع الضرر المتوقع، وللقضاء تخفيضه إذا كان مبالغاً فيه",
            "Liquidated damages must be proportionate to the expected harm; courts may reduce excessive amounts")
    alt = T("في حال الإخلال بالتزامات السرية، يلتزم الطرف المخل بتعويض الطرف المتضرر عن الأضرار الفعلية المثبتة، بحد أقصى 500,000 ريال، مع حفظ حق المتضرر في طلب وقف الإخلال.",
            "In case of breach of confidentiality, the breaching party shall compensate the injured party for proven actual damage up to SAR 500,000, without prejudice to the right to seek an order stopping the breach.")
    amt = max(money(t), default=None)
    per_breach = has(t, r"عن كل مخالفه", r"for (each|every) breach", r"per breach")
    no_proof = has(t, r"(دون|بدون) (ال)?(حاجه )?(ل|الي )?اثبات (ال)?ضرر", r"without (the )?need to prove", r"without proof of (damage|harm)")
    if (amt and amt >= 1_000_000) or (per_breach and no_proof):
        amt_txt = T(f"{amt:,.0f} ريال ", f"of SAR {amt:,.0f} ") if amt else ""
        return killer(T("تعويض اتفاقي مبالغ فيه", "Excessive liquidated damages"),
                      T(f"تعويض جزافي {amt_txt}عن كل مخالفة دون حاجة لإثبات الضرر يعرض الطرف المتلقي لمطالبات ضخمة لا تتناسب مع أي ضرر فعلي.",
                        f"A lump sum {amt_txt}per breach without proof of damage exposes the receiving party to huge claims unrelated to any actual harm."),
                      ref, alt)
    if amt:
        return ok(T("التعويض الاتفاقي محدد ومتناسب.", "The liquidated damages are defined and proportionate."), ref)
    return Finding(AMBIG, "منخفض", T("آلية التعويض عن الإخلال غير محددة.", "The compensation mechanism for breach is undefined."), ref, alt)


# ---------------------------------------------------------------------------
# 4. مكتبة البنود وتوزيعها على تصنيفات العقود
# ---------------------------------------------------------------------------
@dataclass
class ClauseSpec:
    title: str
    title_en: str
    category: str
    locate: List[str]
    fn: Callable
    missing_level: str = "متوسط"
    missing_rec: str = ""
    missing_rec_en: str = ""


CLAUSES = {
    "duration": ClauseSpec("مدة سريان العقد", "Contract Term", "نظامي وقانوني",
                           [r"مده (العقد|الاتفاقيه|الايجار|الاشتراك|هذا العقد)", r"تسري", r"سريان", r"يتجدد|تتجدد|التجديد", r"تبدا من",
                            r"term of (the|this) (agreement|contract)|contract term|lease term|subscription term|term and effectiveness",
                            r"valid for|shall be valid", r"\brenew", r"starting from|commencing"], ev_duration,
                           "متوسط", "تحديد مدة العقد وتاريخ بدايته ونهايته وآلية تجديده بوضوح.",
                           "Clearly state the contract term, its start and end dates, and the renewal mechanism."),
    "payment": ClauseSpec("المقابل المالي وشروط الدفع", "Consideration and Payment Terms", "مالي وتعويضي",
                          [r"الاجر\b|الاجر ", r"الرسوم", r"الدفع|السداد|تدفع|يصرف", r"قيمه (الاتفاقيه|العقد) الاجماليه|القيمه الايجاريه|الاجره", r"ريال", r"الفاتوره",
                           r"\bwage\b|salary", r"\bfees\b", r"payment|payable|\bpaid\b", r"total value|contract value|annual rent|\brent\b", r"\bsar\b|riyal", r"invoice"],
                          ev_payment, "حرج", "تحديد المقابل المالي رقماً وكتابةً ومواعيد وطريقة السداد.",
                          "State the consideration in figures and words with payment dates and method."),
    "late_penalty": ClauseSpec("غرامات التأخير", "Delay Penalties", "مالي وتعويضي", [r"غرام", r"تاخير|تاخر", r"شرط جزائي", r"penalt", r"delay|\blate\b"],
                               ev_late_penalty, "منخفض", "إضافة شرط جزائي متوازن (0.5% أسبوعياً بحد أقصى 10%) لحماية الجدول الزمني.",
                               "Add a balanced penalty clause (0.5% per week, capped at 10%) to protect the schedule."),
    "liability": ClauseSpec("حدود المسؤولية والتعويض", "Limitation of Liability and Indemnity", "مالي وتعويضي",
                            [r"المسؤوليه", r"التعويض|تعويضيه", r"الخسائر|الاضرار", r"liabilit", r"indemn|compensat", r"loss|damage"], ev_liability,
                            "حرج", "إضافة بند يحدد سقف المسؤولية بقيمة العقد ويستثني الأضرار غير المباشرة.",
                            "Add a clause capping liability at the contract value and excluding indirect damages."),
    "confidentiality": ClauseSpec("السرية وحفظ البيانات", "Confidentiality and Data Protection", "سرية وحقوق فكرية",
                                  [r"سريه|السري\b", r"الابد|ابدي", r"مده الالتزام", r"اسرار",
                                   r"confidential", r"forever|perpetual", r"duration of the confidentiality", r"secrets"], ev_confidentiality,
                                  "متوسط", "إضافة التزام متبادل بالسرية لمدة 3 سنوات بعد انتهاء العقد.",
                                  "Add a mutual confidentiality obligation lasting 3 years after expiry."),
    "termination": ClauseSpec("الإنهاء وأحكام الفسخ", "Termination", "نظامي وقانوني",
                              [r"انهاء|الانهاء", r"فسخ", r"الاخلاء", r"terminat", r"evict", r"rescind|rescission"], ev_termination,
                              "حرج", "تنظيم حالات الإنهاء ومهلة الإشعار والتصحيح وتسوية المستحقات عند الإنهاء.",
                              "Regulate termination grounds, notice and cure periods, and settlement of dues on termination."),
    "ip": ClauseSpec("الملكية الفكرية", "Intellectual Property", "سرية وحقوق فكرية",
                     [r"الملكيه الفكريه", r"ملكيه البيانات", r"تؤول", r"حقوق", r"intellectual property", r"data ownership|ownership of (the )?data", r"\bvest", r"rights"],
                     ev_ip, "متوسط", "تحديد ملكية مخرجات العمل والملكية الفكرية السابقة لكل طرف.",
                     "Define ownership of deliverables and each party's pre-existing intellectual property."),
    "force_majeure": ClauseSpec("القوة القاهرة", "Force Majeure", "تشغيلي وإجرائي", [r"القوه القاهره", r"الظروف الطارئه", r"force majeure", r"unforeseen"],
                                ev_force_majeure, "متوسط", "إضافة بند قوة قاهرة يعفي الطرفين ويجيز الإنهاء إذا استمرت أكثر من 90 يوماً.",
                                "Add a force majeure clause excusing both parties and allowing termination after 90 days."),
    "dispute": ClauseSpec("تسوية النزاعات والقانون الواجب التطبيق", "Dispute Resolution and Governing Law", "نظامي وقانوني",
                          [r"نزاع", r"المحاكم|المحكمه", r"تحكيم", r"القانون الواجب|تخضع", r"dispute", r"courts?\b", r"arbitration", r"governing law|governed by"],
                          ev_dispute, "متوسط", "تحديد القانون الواجب التطبيق والمحكمة أو هيئة التحكيم المختصة.",
                          "Specify the governing law and the competent court or arbitral body."),
    "probation": ClauseSpec("فترة التجربة", "Probation Period", "نظامي وقانوني", [r"تجربه", r"probation"], ev_probation,
                            "منخفض", "تحديد فترة تجربة لا تتجاوز 90 يوماً.", "Set a probation period not exceeding 90 days."),
    "hours": ClauseSpec("ساعات العمل والعمل الإضافي", "Working Hours and Overtime", "تشغيلي وإجرائي",
                        [r"ساعات العمل", r"ساعات|ساعه", r"working hours", r"\bhours?\b"], ev_hours,
                        "متوسط", "تحديد ساعات العمل بما لا يتجاوز 8 ساعات يومياً و48 أسبوعياً.", "Limit working hours to 8 per day and 48 per week."),
    "leave": ClauseSpec("الإجازة السنوية", "Annual Leave", "نظامي وقانوني", [r"اجازه", r"\bleave\b|vacation"], ev_leave,
                        "متوسط", "النص على إجازة سنوية لا تقل عن 21 يوماً.", "Provide annual leave of at least 21 days."),
    "eos": ClauseSpec("مكافأة نهاية الخدمة", "End-of-Service Award", "مالي وتعويضي", [r"نهايه الخدمه", r"end-of-service|end of service|gratuity"], ev_eos,
                      "منخفض", "الإحالة إلى أحكام المادة 84 من نظام العمل.", "Refer to Article 84 of the Labor Law."),
    "non_compete": ClauseSpec("عدم المنافسة", "Non-Competition", "نظامي وقانوني", [r"منافس", r"استقطاب", r"عملائه", r"compet", r"solicit", r"clients"],
                              ev_non_compete, "منخفض", "في حال الحاجة، تقييد عدم المنافسة بسنة واحدة ونطاق جغرافي محدد.",
                              "If needed, limit the non-compete to one year and a defined area."),
    "rent_increase": ClauseSpec("زيادة الأجرة", "Rent Increase", "مالي وتعويضي", [r"زياده", r"رفع", r"increase", r"raise"], ev_rent_increase,
                                "منخفض", "النص صراحة على ثبات الأجرة طوال مدة العقد.", "State explicitly that rent is fixed for the whole term."),
    "deposit": ClauseSpec("مبلغ الضمان (التأمين)", "Security Deposit", "مالي وتعويضي", [r"الضمان|تامين|التامين", r"deposit|security|insurance"], ev_deposit,
                          "منخفض", "تحديد مبلغ الضمان وشروط استرداده.", "Specify the deposit amount and refund conditions."),
    "maintenance": ClauseSpec("الصيانة", "Maintenance", "تشغيلي وإجرائي", [r"صيانه", r"maintenance"], ev_maintenance,
                              "متوسط", "توزيع التزامات الصيانة بين المؤجر والمستأجر.", "Allocate maintenance obligations between landlord and tenant."),
    "assignment": ClauseSpec("التنازل والتأجير من الباطن", "Assignment and Subletting", "تشغيلي وإجرائي",
                             [r"الباطن", r"التنازل عن العقد", r"sub-?let", r"\bassign"], ev_assignment,
                             "منخفض", "تنظيم التنازل عن العقد والتأجير من الباطن.", "Regulate assignment and subletting."),
    "sla": ClauseSpec("مستوى الخدمة (SLA)", "Service Level (SLA)", "تشغيلي وإجرائي",
                      [r"مستوي الخدمه", r"التوفر|توفر", r"ضمان", r"service level", r"availability", r"guarantee|warranty"], ev_sla,
                      "حرج", "إضافة اتفاقية مستوى خدمة بنسبة توفر 99.5% وتعويضات عن الإخلال.",
                      "Add an SLA with 99.5% availability and service credits for breaches."),
    "data_protection": ClauseSpec("حماية البيانات الشخصية", "Personal Data Protection", "سرية وحقوق فكرية",
                                  [r"حمايه البيانات", r"بيانات العميل", r"خوادم", r"معالجه", r"data protection", r"client('s)? data", r"servers", r"process"],
                                  ev_data, "حرج", "إضافة التزام صريح بنظام حماية البيانات الشخصية وتخزين البيانات داخل المملكة.",
                                  "Add an explicit commitment to the Personal Data Protection Law and in-Kingdom data storage."),
    "nda_scope": ClauseSpec("تعريف المعلومات السرية", "Definition of Confidential Information", "سرية وحقوق فكرية",
                            [r"تعريف", r"المعلومات السريه", r"تشمل", r"definition", r"confidential information", r"includes"], ev_nda_scope,
                            "حرج", "إضافة تعريف دقيق للمعلومات السرية مع الاستثناءات المعتادة.",
                            "Add a precise definition of confidential information with the usual exclusions."),
    "liquidated": ClauseSpec("التعويض الاتفاقي", "Liquidated Damages", "مالي وتعويضي",
                             [r"تعويض اتفاقي", r"التعويض", r"عن كل مخالفه", r"liquidated damages", r"compensation|damages", r"for each breach"], ev_liquidated,
                             "منخفض", "تحديد آلية تعويض متناسبة عن الإخلال.", "Define a proportionate compensation mechanism for breach."),
}

# (مفتاح البند، عنوان عربي بديل، عنوان إنجليزي بديل)
CATEGORY_CLAUSES = {
    "عقد شركات / تجاري وتوريد (B2B)": [("duration", None, None), ("payment", None, None), ("late_penalty", None, None), ("liability", None, None),
                                        ("confidentiality", None, None), ("ip", None, None), ("termination", "الإنهاء الفوري", "Immediate Termination"),
                                        ("force_majeure", None, None), ("dispute", None, None)],
    "عقد عمل (أفراد ومنشآت)": [("duration", "مدة العقد", "Contract Term"), ("payment", "الأجر وشروط الصرف", "Wage and Payment"),
                               ("probation", None, None), ("hours", None, None), ("leave", None, None), ("eos", None, None),
                               ("non_compete", None, None), ("termination", "إنهاء عقد العمل", "Termination of Employment"),
                               ("confidentiality", "سرية معلومات العمل", "Confidentiality of Work Information"), ("dispute", None, None)],
    "عقد إيجار عقاري": [("duration", "مدة الإيجار والتجديد", "Lease Term and Renewal"), ("payment", "الأجرة وطريقة السداد", "Rent and Payment Method"),
                        ("rent_increase", None, None), ("deposit", None, None), ("maintenance", None, None),
                        ("termination", "الفسخ والإخلاء", "Termination and Eviction"), ("assignment", None, None), ("dispute", None, None)],
    "عقد خدمات تقنية / اشتراك سحابي (SaaS)": [("duration", "مدة الاشتراك", "Subscription Term"), ("payment", "الرسوم وشروط الدفع", "Fees and Payment Terms"),
                                               ("sla", None, None), ("data_protection", None, None), ("liability", None, None),
                                               ("ip", "ملكية البيانات والمحتوى", "Data and Content Ownership"),
                                               ("termination", None, None), ("confidentiality", None, None), ("dispute", None, None)],
    "اتفاقية عدم إفصاح وسرية (NDA)": [("duration", "مدة الاتفاقية", "Agreement Term"), ("nda_scope", None, None),
                                       ("confidentiality", "مدة الالتزام بالسرية", "Duration of Confidentiality"),
                                       ("liquidated", None, None), ("non_compete", "عدم الاستقطاب والمنافسة", "Non-Solicitation and Non-Competition"),
                                       ("dispute", None, None)],
}


# ---------------------------------------------------------------------------
# 5. تقسيم العقد وتحديد مواضع البنود
# ---------------------------------------------------------------------------
_HEADER = re.compile(r"^(?:المادة|البند|مادة|بند|article|clause|section)\s*\(?\s*[\d٠-٩]*\s*\)?", re.IGNORECASE)
_HEADER_STRIP = re.compile(r"^(?:المادة|البند|مادة|بند|article|clause|section)\s*\(?\s*[\d٠-٩]*\s*\)?[^:：]{0,60}[:：]\s*", re.IGNORECASE)


def split_segments(text: str) -> List[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    merged, i = [], 0
    while i < len(lines):
        ln = lines[i]
        is_header = bool(_HEADER.match(ln)) and (ln.rstrip().endswith((":", "：")) or len(ln) < 50)
        if is_header and i + 1 < len(lines):
            merged.append(f"{ln} {lines[i + 1]}")
            i += 2
            continue
        merged.append(ln)
        i += 1
    segments = []
    for seg in merged:
        if len(seg) > 600:
            segments += [p.strip() for p in re.split(r"(?<=[.؟!؛])\s+", seg) if p.strip()]
        else:
            segments.append(seg)
    return segments


def locate(segments_norm: List[str], spec: ClauseSpec) -> List[int]:
    patterns = [re.compile(norm(p)) for p in spec.locate]
    scored = []
    for idx, seg in enumerate(segments_norm):
        head = seg[:45]
        score = sum((2 if p.search(head) else 1) for p in patterns if p.search(seg))
        if score:
            scored.append((score, idx))
    if not scored:
        return []
    top = max(s for s, _ in scored)
    return sorted(idx for s, idx in scored if s == top)[:2]


def strip_header(seg: str) -> str:
    return _HEADER_STRIP.sub("", seg).strip()


def _short(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------------------
# 6. استخراج البيانات الجوهرية
# ---------------------------------------------------------------------------
_PARTY_RE = re.compile(
    r"^\s*((?:الطرف\s+ال[أا]ول|الطرف\s+الثاني|المؤجر|المستأجر|الطرف\s+المفصح|الطرف\s+المتلقي"
    r"|first\s+party|second\s+party|landlord|tenant|disclosing\s+party|receiving\s+party))\s*(\([^)]*\))?\s*[:：]\s*(.+)$",
    re.MULTILINE | re.IGNORECASE)


def extract_parties(text: str) -> List[str]:
    parties = []
    for role, role_note, name in _PARTY_RE.findall(text):
        name = re.split(r"[،,]|\s+ويشار|\s+hereinafter", name, flags=re.IGNORECASE)[0].strip()
        label = role_note.strip("() ") if role_note else role
        if name and len(parties) < 4:
            parties.append(name if "(" in name else f"{name} ({label})")
    return parties


def _split_renewal(duration_txt: str):
    """يفصل جملة المدة عن جملة التجديد (عربي أو إنجليزي)."""
    parts = re.split(r"،\s*(?=و?(?:يتجدد|تتجدد))", duration_txt, maxsplit=1)
    if len(parts) > 1:
        return parts[0], parts[1]
    m = re.search(r"\s*,?\s*(?:and (?:it )?shall (?:automatically )?renew|renewing automatically|renews automatically)", duration_txt, re.IGNORECASE)
    if m:
        renewal = duration_txt[m.start():].strip(" ,")
        renewal = re.sub(r"^and\s+", "", renewal, flags=re.IGNORECASE)
        if renewal.lower().startswith("shall"):
            renewal = "It " + renewal
        return duration_txt[:m.start()].strip(" ,"), renewal[:1].upper() + renewal[1:]
    return duration_txt, (duration_txt if has(norm(duration_txt), r"تجدد|تجديد", r"\brenew") else "")


# ---------------------------------------------------------------------------
# 7. نقطة الدخول الرئيسية
# ---------------------------------------------------------------------------
def analyze_contract(contract_text: str, contract_category: str, lang: str = "ar") -> AuditReport:
    token = _LANG.set("en" if lang == "en" else "ar")
    try:
        return _analyze(contract_text, contract_category, lang)
    finally:
        _LANG.reset(token)


def _analyze(contract_text: str, contract_category: str, lang: str) -> AuditReport:
    category = contract_category if contract_category in CATEGORY_CLAUSES else next(iter(CATEGORY_CLAUSES))
    segments = split_segments(contract_text)
    segments_norm = [norm(s) for s in segments]
    ctx = {"category": category, "full": norm(contract_text)}

    items, traps, located_text = [], [], {}
    for key, title_ar, title_en in CATEGORY_CLAUSES[category]:
        spec = CLAUSES[key]
        title = T(title_ar or spec.title, title_en or spec.title_en)
        idxs = locate(segments_norm, spec)
        if not idxs:
            items.append(ComplianceItem(
                clause_title=title, contract_snippet=T("— لم يرد نص صريح لهذا البند في العقد —", "— No explicit text for this clause in the contract —"),
                status=MISSING, risk_category=spec.category,
                legal_reference=T("مبدأ نفي الجهالة: وجوب تنظيم الالتزامات الجوهرية صراحة في العقد",
                                  "Principle of eliminating uncertainty: material obligations must be regulated expressly in the contract"),
                risk_level=spec.missing_level,
                analysis=T(f"لم يتضمن العقد بنداً ينظم «{title}»، وغياب هذا البند يترك المسألة للتفسير والنزاع.",
                           f"The contract has no clause governing \"{title}\"; its absence leaves the matter open to interpretation and dispute."),
                recommendation=T(spec.missing_rec, spec.missing_rec_en)))
            continue
        original = " ".join(segments[i] for i in idxs)
        located_text[key] = " ".join(strip_header(segments[i]) for i in idxs)
        finding: Finding = spec.fn(" ".join(segments_norm[i] for i in idxs), ctx)
        items.append(ComplianceItem(
            clause_title=title, contract_snippet=_short(original, 420), status=finding.status, risk_category=spec.category,
            legal_reference=finding.ref, risk_level=finding.level, analysis=finding.analysis, recommendation=finding.rec))
        if finding.trap:
            traps.append(ContractTrap(trap_name=finding.trap[0], severity=finding.trap[1], explanation=finding.trap[2]))

    # البيانات الجوهرية
    not_set = T("غير محدد في العقد", "Not specified in the contract")
    parties = extract_parties(contract_text) or [T("لم يتم التعرف على أسماء الأطراف بشكل آلي", "Party names could not be identified automatically")]
    duration_txt = located_text.get("duration", "")
    effective, renewal = _split_renewal(duration_txt) if duration_txt else ("", "")
    if not renewal and "termination" in located_text:
        renewal = located_text["termination"]
    metadata = ContractMetadata(
        parties=parties,
        effective_duration=_short(effective, 160) if duration_txt else not_set,
        financial_terms=_short(located_text.get("payment") or located_text.get("liquidated", not_set), 180),
        renewal_clause=_short(renewal, 180) if renewal else T("لا يوجد نص صريح للتجديد أو الإنهاء", "No explicit renewal or termination provision"),
    )

    counts = {s: sum(1 for i in items if i.status == s) for s in (OK, BAD, AMBIG, MISSING)}
    critical_traps = sum(1 for t in traps if t.severity == "حرج جداً")
    label = type_info(category, lang)["label"]
    names = [p.split(" (")[0] for p in parties[:2]]
    if lang == "en":
        names = [n.rstrip(".") for n in names]
        summary = (f"{label} between {' and '.join(names)}. "
                   f"{len(items)} key clauses reviewed: {counts[OK]} compliant, {counts[BAD]} non-compliant, {counts[AMBIG]} ambiguous or high-risk, "
                   f"{counts[MISSING]} not mentioned, with {len(traps)} contractual traps detected"
                   f"{f', {critical_traps} of them critical' if traps else ''}.")
    else:
        summary = (f"{label} بين {' و'.join(names)}. "
                   f"تم فحص {len(items)} بنداً جوهرياً: {counts[OK]} متوافق، {counts[BAD]} مخالف، {counts[AMBIG]} مبهم أو عالي المخاطر، "
                   f"{counts[MISSING]} غير مذكور، مع رصد {len(traps)} فخاخ تعاقدية"
                   f"{' منها ' + str(critical_traps) + ' حرجة جداً' if traps else ''}.")

    return AuditReport(contract_summary=summary, compliance_score=compute_score(items), metadata=metadata, traps=traps, items=items)
