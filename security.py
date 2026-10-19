"""
طبقة الحماية في المنصة:
- تعقيم النصوص غير الموثوقة (نص العقد ومخرجات نموذج اللغة) قبل عرضها، لمنع حقن Markdown/HTML.
- حدود استخدام نموذج اللغة لكل جلسة ولكل الزوار مجتمعين، لحماية رصيد مفتاح OpenAI.
- إعدادات خصوصية سجل الفحوصات وحدود حجم المدخلات.
القيم قابلة للتعديل من متغيرات البيئة (.env محلياً أو Streamlit Secrets سحابياً).
"""
import html
import logging
import os
import re
import threading
import time
from collections import deque

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("contract_checker")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# عدد الفحوصات والتفاوضات عبر نموذج اللغة المسموح بها لكل جلسة (0 أو أقل = بلا حد)
LLM_SESSION_LIMIT = _int_env("LLM_SESSION_LIMIT", 5)
NEGOTIATION_SESSION_LIMIT = _int_env("NEGOTIATION_SESSION_LIMIT", 10)
# الحد الأعلى لاستدعاءات نموذج اللغة في الساعة لكل الزوار مجتمعين (0 أو أقل = بلا حد)
LLM_HOURLY_LIMIT = _int_env("LLM_HOURLY_LIMIT", 60)

# حدود المدخلات
MAX_CONTRACT_CHARS = _int_env("MAX_CONTRACT_CHARS", 100_000)
MAX_PDF_PAGES = _int_env("MAX_PDF_PAGES", 60)

# "session" (الافتراضي): كل زائر يرى سجله فقط — "shared": سجل واحد مشترك (للاستخدام الفردي على جهاز خاص)
HISTORY_MODE = "shared" if os.getenv("HISTORY_MODE", "session").strip().lower() == "shared" else "session"


# ---------------------------------------------------------------------------
# تعقيم النصوص
# ---------------------------------------------------------------------------
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:])")
_HTML_MD_ENTITIES = str.maketrans({"[": "&#91;", "]": "&#93;", "(": "&#40;", ")": "&#41;", "!": "&#33;",
                                   "*": "&#42;", "_": "&#95;", "`": "&#96;", "$": "&#36;", ":": "&#58;", "~": "&#126;"})


_AUTOLINK = re.compile(r"(?i)\b(https?|ftp)(?=:)|\b(www)(?=\.)|(@)(?=[\w-])")


def md_escape(text) -> str:
    """يعطّل تنسيقات Markdown في نص غير موثوق (الروابط والصور ومعادلات $ وألوان :red[]) ليُعرض كنص عادي.
    كما يكسر الربط التلقائي للعناوين (https:// و www. والبريد) بفاصل غير مرئي حتى لا تتحول إلى روابط قابلة للنقر."""
    defanged = _AUTOLINK.sub(lambda m: m.group(0) + "\N{ZERO WIDTH SPACE}", str(text))
    return _MD_SPECIAL.sub(r"\\\1", defanged)


def safe_html(text) -> str:
    """تهريب HTML ورموز Markdown معاً، للنصوص التي تُدرج داخل كتل HTML."""
    return html.escape(str(text), quote=True).translate(_HTML_MD_ENTITIES)


# ---------------------------------------------------------------------------
# حد الاستدعاءات العام (مشترك بين كل الجلسات داخل نفس عملية الخادم)
# ---------------------------------------------------------------------------
class HourlyLimiter:
    def __init__(self, limit: int):
        self.limit = limit
        self._calls = deque()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        if self.limit <= 0:
            return True
        now = time.time()
        with self._lock:
            while self._calls and now - self._calls[0] > 3600:
                self._calls.popleft()
            if len(self._calls) >= self.limit:
                logger.warning("Hourly LLM limit reached (%s calls)", self.limit)
                return False
            self._calls.append(now)
            return True


LLM_LIMITER = HourlyLimiter(LLM_HOURLY_LIMIT)


def within_session_limit(used: int, limit: int) -> bool:
    return limit <= 0 or used < limit
