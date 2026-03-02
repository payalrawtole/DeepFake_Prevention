"""
DeepFake Misuse Prevention System - Database Layer
SQLite-backed storage for creators, content, complaints, and audit logs.
All writes to audit_log are append-only (no UPDATE/DELETE on that table).
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "deepfake_prevention.db",
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = _connect()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS creators (
            creator_id       TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            email            TEXT NOT NULL UNIQUE,
            id_verified      INTEGER DEFAULT 0,
            liveness_passed  INTEGER DEFAULT 0,
            public_key_pem   TEXT,
            risk_score       REAL DEFAULT 0.0,
            registered_at    TEXT NOT NULL,
            blocked          INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS consent_records (
            consent_token    TEXT PRIMARY KEY,
            creator_id       TEXT NOT NULL,
            subject_name     TEXT,
            subject_contact  TEXT,
            granted_at       TEXT NOT NULL,
            expires_at       TEXT,
            revoked          INTEGER DEFAULT 0,
            revoked_at       TEXT,
            FOREIGN KEY(creator_id) REFERENCES creators(creator_id)
        );

        CREATE TABLE IF NOT EXISTS content_registry (
            content_id        TEXT PRIMARY KEY,
            creator_id        TEXT NOT NULL,
            consent_token     TEXT,
            content_url       TEXT,
            content_hash      TEXT,
            digital_signature TEXT,
            watermark_id      TEXT,
            created_at        TEXT NOT NULL,
            suspended         INTEGER DEFAULT 0,
            deleted           INTEGER DEFAULT 0,
            suspended_at      TEXT,
            deleted_at        TEXT,
            FOREIGN KEY(creator_id) REFERENCES creators(creator_id)
        );

        CREATE TABLE IF NOT EXISTS complaints (
            complaint_id           TEXT PRIMARY KEY,
            content_id             TEXT,
            complainant_anon_id    TEXT NOT NULL,
            reason                 TEXT NOT NULL,
            evidence_url           TEXT,
            submitted_at           TEXT NOT NULL,
            takedown_executed      INTEGER DEFAULT 0,
            takedown_at            TEXT,
            law_enforcement_ref    TEXT,
            status                 TEXT DEFAULT 'OPEN'
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT,
            event_type   TEXT NOT NULL,
            actor_id     TEXT,
            payload      TEXT,
            logged_at    TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


# ─── Creator ──────────────────────────────────────────────────────────────────

def upsert_creator(
    creator_id: str,
    name: str,
    email: str,
    id_verified: bool = False,
    liveness_passed: bool = False,
    public_key_pem: str = "",
    risk_score: float = 0.0,
) -> None:
    conn = _connect()
    conn.execute("""
        INSERT INTO creators (creator_id, name, email, id_verified, liveness_passed,
                              public_key_pem, risk_score, registered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(creator_id) DO UPDATE SET
            id_verified     = excluded.id_verified,
            liveness_passed = excluded.liveness_passed,
            public_key_pem  = excluded.public_key_pem,
            risk_score      = excluded.risk_score
    """, (
        creator_id, name, email,
        int(id_verified), int(liveness_passed),
        public_key_pem, risk_score,
        _now(),
    ))
    conn.commit()
    conn.close()


def get_creator(creator_id: str) -> Optional[Dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM creators WHERE creator_id = ?", (creator_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_creators() -> List[Dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM creators ORDER BY registered_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Consent ─────────────────────────────────────────────────────────────────

def store_consent(
    consent_token: str,
    creator_id: str,
    subject_name: str,
    subject_contact: str,
) -> None:
    conn = _connect()
    conn.execute("""
        INSERT OR REPLACE INTO consent_records
            (consent_token, creator_id, subject_name, subject_contact, granted_at)
        VALUES (?, ?, ?, ?, ?)
    """, (consent_token, creator_id, subject_name, subject_contact, _now()))
    conn.commit()
    conn.close()


def revoke_consent(consent_token: str) -> None:
    conn = _connect()
    conn.execute("""
        UPDATE consent_records SET revoked = 1, revoked_at = ?
        WHERE consent_token = ?
    """, (_now(), consent_token))
    conn.commit()
    conn.close()

    # Cascade: suspend all content generated under this consent
    content_rows = conn.execute(
        "SELECT content_id FROM content_registry WHERE consent_token = ?",
        (consent_token,)
    ).fetchall() if False else []   # conn already closed; handled in suspend below

    conn2 = _connect()
    rows = conn2.execute(
        "SELECT content_id FROM content_registry WHERE consent_token = ?",
        (consent_token,)
    ).fetchall()
    for r in rows:
        suspend_content(r["content_id"])
    conn2.close()


def get_consent(consent_token: str) -> Optional[Dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM consent_records WHERE consent_token = ?", (consent_token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Content Registry ─────────────────────────────────────────────────────────

def register_content(
    content_id: str,
    creator_id: str,
    consent_token: str,
    content_hash: str,
    digital_signature: str,
    watermark_id: str,
    content_url: str = "",
) -> None:
    conn = _connect()
    conn.execute("""
        INSERT INTO content_registry
            (content_id, creator_id, consent_token, content_url,
             content_hash, digital_signature, watermark_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        content_id, creator_id, consent_token, content_url,
        content_hash, digital_signature, watermark_id, _now(),
    ))
    conn.commit()
    conn.close()


def suspend_content(content_id: str) -> None:
    conn = _connect()
    conn.execute("""
        UPDATE content_registry SET suspended = 1, suspended_at = ?
        WHERE content_id = ?
    """, (_now(), content_id))
    conn.commit()
    conn.close()


def delete_content(content_id: str) -> None:
    conn = _connect()
    conn.execute("""
        UPDATE content_registry SET deleted = 1, deleted_at = ?
        WHERE content_id = ?
    """, (_now(), content_id))
    conn.commit()
    conn.close()


def get_content(content_id: str) -> Optional[Dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM content_registry WHERE content_id = ?", (content_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_content() -> List[Dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM content_registry ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Complaints ───────────────────────────────────────────────────────────────

def store_complaint(
    complaint_id: str,
    content_id: str,
    complainant_anon_id: str,
    reason: str,
    evidence_url: str = "",
) -> None:
    conn = _connect()
    conn.execute("""
        INSERT INTO complaints
            (complaint_id, content_id, complainant_anon_id,
             reason, evidence_url, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (complaint_id, content_id, complainant_anon_id, reason, evidence_url, _now()))
    conn.commit()
    conn.close()


def mark_takedown(complaint_id: str) -> None:
    conn = _connect()
    conn.execute("""
        UPDATE complaints
        SET takedown_executed = 1, takedown_at = ?, status = 'TAKEDOWN_COMPLETE'
        WHERE complaint_id = ?
    """, (_now(), complaint_id))
    conn.commit()
    conn.close()


def get_all_complaints() -> List[Dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM complaints ORDER BY submitted_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_complaint(complaint_id: str) -> Optional[Dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM complaints WHERE complaint_id = ?", (complaint_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Audit Log (append-only) ─────────────────────────────────────────────────

def append_audit(
    event_type: str,
    actor_id: str,
    payload: Dict[str, Any],
    session_id: str = "",
) -> None:
    conn = _connect()
    conn.execute("""
        INSERT INTO audit_log (session_id, event_type, actor_id, payload, logged_at)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, event_type, actor_id, json.dumps(payload), _now()))
    conn.commit()
    conn.close()


def get_audit_log(limit: int = 100) -> List[Dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY logged_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Helper ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
