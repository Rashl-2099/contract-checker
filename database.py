import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_NAME = str(Path(__file__).resolve().parent / "contracts_audit.db")

_EXTRA_COLUMNS = {"report_json": "TEXT", "engine": "TEXT", "source": "TEXT"}


def _connect():
    return sqlite3.connect(DB_NAME)


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
                      report_json: Optional[str] = None, engine: Optional[str] = None, source: Optional[str] = None) -> int:
    """حفظ نتيجة فحص جديدة في قاعدة البيانات وإرجاع رقمها"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO audit_logs (
                timestamp, contract_category, compliance_score,
                issues_count, critical_count, traps_count, summary, report_json, engine, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now_str, category, score, issues, critical, traps, summary, report_json, engine, source))
        return cur.lastrowid


def get_recent_audits(limit: int = 10):
    """استرجاع آخر عمليات التدقيق لعرضها في لوحة التحكم"""
    with _connect() as conn:
        return conn.execute("""
            SELECT id, timestamp, contract_category, compliance_score, issues_count, critical_count, traps_count,
                   report_json IS NOT NULL, engine
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()


def get_audit(audit_id: int) -> Optional[dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_logs WHERE id = ?", (audit_id,)).fetchone()
        return dict(row) if row else None


def get_previous_score(category: str, before_id: int) -> Optional[int]:
    """درجة آخر فحص سابق لنفس التصنيف (لحساب التغير في المؤشر)"""
    with _connect() as conn:
        row = conn.execute("""
            SELECT compliance_score FROM audit_logs
            WHERE contract_category = ? AND id < ? ORDER BY id DESC LIMIT 1
        """, (category, before_id)).fetchone()
        return row[0] if row else None


def get_stats() -> dict:
    with _connect() as conn:
        total, avg, traps = conn.execute(
            "SELECT COUNT(*), COALESCE(AVG(compliance_score), 0), COALESCE(SUM(traps_count), 0) FROM audit_logs").fetchone()
        return {"total": total, "avg_score": round(avg), "traps": traps}


def delete_audit(audit_id: int):
    with _connect() as conn:
        conn.execute("DELETE FROM audit_logs WHERE id = ?", (audit_id,))


def clear_audits():
    with _connect() as conn:
        conn.execute("DELETE FROM audit_logs")
