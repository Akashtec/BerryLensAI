import sqlite3
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from models.evidence import Evidence, VerificationResult
from models.schemas import EvidenceAssessment, VerificationReport

LOGGER = logging.getLogger(__name__)
DB_PATH = os.getenv(
    "BERRYLENS_DB_PATH",
    str(Path(__file__).resolve().parents[1] / "data" / "berrylens.db"),
)


def _ensure_database_directory(db_path: str | Path) -> Path:
    """Create the SQLite parent directory before opening the database."""
    database_path = Path(db_path).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path


class DatabaseManager:
    """Persist complete verification reports without breaking legacy tables."""

    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(_ensure_database_directory(db_path))
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_table()

    def create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                claim TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                research_status TEXT NOT NULL,
                report_json TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        columns = {row[1] for row in self.conn.execute('PRAGMA table_info(verifications)').fetchall()}
        if 'user_id' not in columns:
            self.conn.execute('ALTER TABLE verifications ADD COLUMN user_id INTEGER')
        self.conn.commit()

    def save(self, report: VerificationReport, user_id: int | None = None) -> int:
        payload = report.model_dump(mode="json")
        cursor = self.conn.execute(
            """
            INSERT INTO verifications
                (user_id, claim, verdict, confidence, research_status, report_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                report.claim,
                report.verdict.value,
                report.confidence,
                report.research_status.value,
                json.dumps(payload),
                report.timestamp.isoformat(),
            ),
        )
        self.conn.commit()
        report.id = cursor.lastrowid
        return cursor.lastrowid

    def create_user(self, email: str, password_hash: str) -> int:
        cursor = self.conn.execute(
            'INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)',
            (email.lower().strip(), password_hash, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_user_by_email(self, email: str):
        return self.conn.execute(
            'SELECT * FROM users WHERE email = ?', (email.lower().strip(),)
        ).fetchone()

    def get_user(self, user_id: int):
        return self.conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    def get_by_id(self, report_id: int, user_id: int | None = None) -> VerificationReport | None:
        if user_id is None:
            row = self.conn.execute(
                "SELECT report_json FROM verifications WHERE id = ? AND user_id IS NULL",
                (report_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT report_json FROM verifications WHERE id = ? AND user_id = ?",
                (report_id, user_id),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["report_json"])
        payload["id"] = report_id
        return VerificationReport.model_validate(payload)

    def list_reports(self, limit: int = 20, offset: int = 0, user_id: int | None = None) -> list[VerificationReport]:
        if user_id is None:
            query = "SELECT id, report_json FROM verifications WHERE user_id IS NULL ORDER BY id DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
        else:
            query = "SELECT id, report_json FROM verifications WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?"
            params = (user_id, limit, offset)
        rows = self.conn.execute(query, params,
        ).fetchall()
        reports = []
        for row in rows:
            payload = json.loads(row["report_json"])
            payload["id"] = row["id"]
            reports.append(VerificationReport.model_validate(payload))
        return reports

    def stats(self, user_id: int | None = None) -> dict[str, int | float]:
        if user_id is None:
            row = self.conn.execute(
                "SELECT COUNT(*) AS total, AVG(confidence) AS average FROM verifications WHERE user_id IS NULL"
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS total, AVG(confidence) AS average FROM verifications WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return {
            "total": row["total"],
            "average_confidence": round(row["average"] or 0, 3),
        }

    def close(self):
        self.conn.close()


def get_connection():
    database_path = _ensure_database_directory(DB_PATH)
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    database_path = _ensure_database_directory(DB_PATH)
    LOGGER.info("Initializing SQLite database at %s", database_path)
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS verdicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id INTEGER NOT NULL,
            verdict TEXT NOT NULL,
            confidence INTEGER,
            explanation TEXT,
            model_version TEXT DEFAULT 'berrylens-v1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (claim_id) REFERENCES claims(id)
        )
    """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verdict_id INTEGER NOT NULL,
            title TEXT,
            url TEXT,
            snippet TEXT,
            source TEXT,
            query TEXT,
            relevance_score REAL DEFAULT 0.0,
            FOREIGN KEY (verdict_id) REFERENCES verdicts(id)
        )
    """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS source_trust (
            domain TEXT PRIMARY KEY,
            trust_score REAL DEFAULT 0.5,
            category TEXT,
            verified_count INTEGER DEFAULT 0,
            refuted_count INTEGER DEFAULT 0
        )
    """)

        conn.commit()
    except sqlite3.Error as error:
        LOGGER.exception("SQLite initialization failed for %s", database_path)
        raise RuntimeError(
            f"Unable to initialize SQLite database at {database_path}: {error}"
        ) from error
    finally:
        if conn is not None:
            conn.close()
    LOGGER.info("SQLite database initialized at %s", database_path)


def save_claim(text: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO claims (text, status) VALUES (?, ?)", (text, 'pending'))
    claim_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return claim_id


def update_claim_status(claim_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE claims SET status = ? WHERE id = ?", (status, claim_id))
    conn.commit()
    conn.close()


def save_verdict(claim_id: int, result: VerificationResult) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO verdicts (claim_id, verdict, confidence, explanation) VALUES (?, ?, ?, ?)",
        (claim_id, result.verdict, result.confidence, result.explanation)
    )
    verdict_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return verdict_id


def save_evidence(verdict_id: int, evidence_list: List[Evidence]):
    conn = get_connection()
    cursor = conn.cursor()
    for ev in evidence_list:
        cursor.execute(
            "INSERT INTO evidence (verdict_id, title, url, snippet, source, query) VALUES (?, ?, ?, ?, ?, ?)",
            (verdict_id, ev.title, ev.url, ev.snippet, ev.source, ev.query)
        )
    conn.commit()
    conn.close()


def get_all_claims() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, v.verdict, v.confidence, v.explanation 
        FROM claims c 
        LEFT JOIN verdicts v ON c.id = v.claim_id 
        ORDER BY c.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_claim_by_id(claim_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, v.id as verdict_id, v.verdict, v.confidence, v.explanation 
        FROM claims c 
        LEFT JOIN verdicts v ON c.id = v.claim_id 
        WHERE c.id = ?
    """, (claim_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    claim = dict(row)
    cursor.execute("SELECT * FROM evidence WHERE verdict_id = ?", (claim.get('verdict_id'),))
    evidence_rows = cursor.fetchall()
    claim['evidence'] = [dict(r) for r in evidence_rows]

    conn.close()
    return claim


def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM claims")
    total_claims = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM verdicts")
    total_verdicts = cursor.fetchone()[0]

    cursor.execute("SELECT verdict, COUNT(*) FROM verdicts GROUP BY verdict")
    verdict_counts = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("SELECT AVG(confidence) FROM verdicts")
    avg_confidence = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'pending'")
    pending = cursor.fetchone()[0]

    conn.close()

    return {
        'total_claims': total_claims,
        'total_verdicts': total_verdicts,
        'verdict_counts': verdict_counts,
        'avg_confidence': round(avg_confidence, 1),
        'pending': pending
    }