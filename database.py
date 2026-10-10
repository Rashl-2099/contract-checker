import sqlite3
from datetime import datetime

DB_NAME = "contracts_audit.db"

def init_db():
    """إنشاء جدول سجلات فحص العقود إذا لم يكن موجوداً"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
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
    conn.commit()
    conn.close()

def save_audit_record(category: str, score: int, issues: int, critical: int, traps: int, summary: str):
    """حفظ نتيجة فحص جديدة في قاعدة البيانات"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("""
        INSERT INTO audit_logs (
            timestamp, contract_category, compliance_score, 
            issues_count, critical_count, traps_count, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now_str, category, score, issues, critical, traps, summary))
    conn.commit()
    conn.close()

def get_recent_audits(limit: int = 10):
    """استرجاع آخر عمليات التدقيق لعرضها في لوحة التحكم"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, contract_category, compliance_score, issues_count, critical_count, traps_count
        FROM audit_logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows