import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

DB_NAME = str(Path(__file__).resolve().parent / "contracts_audit.db")

_EXTRA_COLUMNS = {"report_json": "TEXT", "engine": "TEXT", "source": "TEXT", "owner": "TEXT"}


def _connect():
    return sqlite3.connect(DB_NAME)


def _scope(owner: Optional[str]) -> Tuple[str, tuple]:
    """قيد الملكية: كل زائر يرى سجلاته فقط. owner=None يعني سجلاً مشتركاً (الوضع المحلي الفردي)."""
    return ("owner = ?", (owner,)) if owner is not None else ("1 = 1", ())


def init_db():
    """إنشاء جدول سجلات فحص العقود إذا لم يكن موجوداً، وترقية الجدول القديم بالأعمدة الجديدة"""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                contract_category TEXT NOT NULL,
                compliance_score INTEGER NOT NULL,
                issues_count INTEGER NOT NULL,
                critical_count INTEGER NOT NULL,
                traps_count INTEGER NOT NULL,
                summary TEXT
            )
        """)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(audit_logs)")}
        for column, col_type in _EXTRA_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE audit_logs ADD COLUMN {column} {col_type}")


def save_audit_record(category: str, score: int, issues: int, critical: int, traps: int, summary: str,
                      report_json: Optional[str] = None, engine: Optional[str] = None, source: Optional[str] = None,
                      owner: Optional[str] = None) -> int:
    """حفظ نتيجة فحص جديدة في قاعدة البيانات وإرجاع رقمها"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO audit_logs (
                timestamp, contract_category, compliance_score,
                issues_count, critical_count, traps_count, summary, report_json, engine, source, owner
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now_str, category, score, issues, critical, traps, summary, report_json, engine, source, owner))
        return cur.lastrowid


def get_recent_audits(limit: int = 10, owner: Optional[str] = None):
    """استرجاع آخر عمليات التدقيق لعرضها في لوحة التحكم"""
    clause, params = _scope(owner)
    with _connect() as conn:
        return conn.execute(f"""
            SELECT id, timestamp, contract_category, compliance_score, issues_count, critical_count, traps_count,
                   report_json IS NOT NULL, engine
            FROM audit_logs
            WHERE {clause}
            ORDER BY id DESC
            LIMIT ?
        """, (*params, limit)).fetchall()


def get_audit(audit_id: int, owner: Optional[str] = None) -> Optional[dict]:
    clause, params = _scope(owner)
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT * FROM audit_logs WHERE id = ? AND {clause}", (audit_id, *params)).fetchone()
        return dict(row) if row else None


def get_previous_score(category: str, before_id: int, owner: Optional[str] = None) -> Optional[int]:
    """درجة آخر فحص سابق لنفس التصنيف (لحساب التغير في المؤشر)"""
    clause, params = _scope(owner)
    with _connect() as conn:
        row = conn.execute(f"""
            SELECT compliance_score FROM audit_logs
            WHERE contract_category = ? AND id < ? AND {clause} ORDER BY id DESC LIMIT 1
        """, (category, before_id, *params)).fetchone()
        return row[0] if row else None


def get_stats(owner: Optional[str] = None) -> dict:
    clause, params = _scope(owner)
    with _connect() as conn:
        total, avg, traps = conn.execute(
            f"SELECT COUNT(*), COALESCE(AVG(compliance_score), 0), COALESCE(SUM(traps_count), 0) FROM audit_logs WHERE {clause}",
            params).fetchone()
        return {"total": total, "avg_score": round(avg), "traps": traps}


def delete_audit(audit_id: int, owner: Optional[str] = None):
    clause, params = _scope(owner)
    with _connect() as conn:
        conn.execute(f"DELETE FROM audit_logs WHERE id = ? AND {clause}", (audit_id, *params))


def clear_audits(owner: Optional[str] = None):
    clause, params = _scope(owner)
    with _connect() as conn:
        conn.execute(f"DELETE FROM audit_logs WHERE {clause}", params)
