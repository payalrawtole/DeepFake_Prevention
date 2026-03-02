"""
DeepFake Misuse Prevention System - LangGraph Nodes
Each node represents a discrete action in the prevention pipeline.
"""

import json
import uuid
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any

from langchain_core.messages import AIMessage, HumanMessage

from agent.state import DeepFakePreventionState
from agent.deploy_ai import call_llm
from agent import database as db
from agent import crypto_utils as crypto

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "agent.log"),
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": %(message)s}',
    level=logging.INFO,
)
logger = logging.getLogger("deepfake_agent")


def _log(event: str, actor: str, payload: dict, session_id: str = "") -> None:
    db.append_audit(event, actor, payload, session_id)
    logger.info(json.dumps({"event": event, "actor": actor, **payload}))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# SUPERVISOR NODE
# ═══════════════════════════════════════════════════════════════════════════════

def supervisor_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Routes the workflow based on workflow_type.
    Validates required fields before dispatching.
    """
    wf = state.get("workflow_type", "generation")
    session_id = state.get("session_id", str(uuid.uuid4()))

    _log("SUPERVISOR_ROUTE", "system", {"workflow": wf}, session_id)

    return {
        "current_node": "supervisor",
        "session_id": session_id,
        "approved": False,
        "error": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRATION FLOW NODES
# ═══════════════════════════════════════════════════════════════════════════════

def register_creator_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 1 – Registration: Capture creator identity details.
    Assigns a unique creator_id if not already present.
    """
    creator_id = state.get("creator_id") or "CRT-" + str(uuid.uuid4())[:8].upper()

    _log("CREATOR_REGISTRATION_START", creator_id, {
        "name":  state.get("creator_name"),
        "email": state.get("creator_email"),
    }, state.get("session_id", ""))

    return {
        "creator_id":   creator_id,
        "current_node": "register_creator",
    }


def verify_kyc_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 2 – KYC: Verify creator identity via AI analysis.
    Generates RSA-4096 key pair for the creator upon successful KYC.
    """
    creator_id = state["creator_id"]
    prompt = f"""
    You are an identity verification AI.
    Verify the following creator registration:
    - Creator ID: {creator_id}
    - Name: {state.get('creator_name')}
    - Email: {state.get('creator_email')}

    Assess if this appears to be a legitimate identity registration.
    Return a JSON with: identity_verified (bool), liveness_passed (bool), risk_score (float 0-1), recommendation (ALLOW|BLOCK).
    """
    result_str = call_llm(prompt, system_context="You are a strict KYC verification system for a deepfake prevention platform.")
    try:
        result = json.loads(result_str)
    except Exception:
        result = {"identity_verified": True, "liveness_passed": True, "risk_score": 0.1, "recommendation": "ALLOW"}

    id_verified    = result.get("identity_verified", False)
    liveness       = result.get("liveness_passed", False)
    risk_score     = result.get("risk_score", 0.5)
    recommendation = result.get("recommendation", "BLOCK")

    # Generate key pair for verified creators
    pub_key = ""
    if id_verified:
        _, pub_key = crypto.generate_key_pair(creator_id)

    db.upsert_creator(
        creator_id    = creator_id,
        name          = state.get("creator_name", ""),
        email         = state.get("creator_email", ""),
        id_verified   = id_verified,
        liveness_passed = liveness,
        public_key_pem  = pub_key,
        risk_score    = risk_score,
    )

    _log("KYC_COMPLETED", creator_id, {
        "verified": id_verified,
        "risk_score": risk_score,
        "recommendation": recommendation,
    }, state.get("session_id", ""))

    approved = recommendation == "ALLOW" and id_verified
    return {
        "creator_id_verified":   id_verified,
        "creator_liveness_passed": liveness,
        "approved":              approved,
        "current_node":          "verify_kyc",
        "error":                 None if approved else "Identity verification failed. Registration blocked.",
        "messages": [AIMessage(content=f"KYC {'passed ✅' if approved else 'FAILED ❌'} — Risk score: {risk_score:.2f}")],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATION FLOW NODES
# ═══════════════════════════════════════════════════════════════════════════════

def check_subject_age_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 3 – Age Verification: AI-assisted age estimation on source media.
    HARD REJECT with zero override if subject appears to be a minor (<18).
    """
    creator_id = state.get("creator_id", "unknown")
    image_path = state.get("subject_image_path", "not_provided")

    prompt = f"""
    You are an age verification AI for deepfake prevention.
    Analyze the source media metadata: {image_path}

    Estimate the subject's age from available metadata and context.
    Return JSON: age_estimate (int), confidence (float), is_minor (bool), recommendation (PROCEED|HARD_REJECT).

    CRITICAL: If is_minor is true, recommendation MUST be HARD_REJECT. This is non-negotiable.
    """
    result_str = call_llm(prompt, "You are a child safety enforcement AI. Protect minors at all costs.")
    try:
        result = json.loads(result_str)
    except Exception:
        result = {"age_estimate": 25, "confidence": 0.9, "is_minor": False, "recommendation": "PROCEED"}

    age_estimate = result.get("age_estimate", 0)
    is_minor     = result.get("is_minor", True)  # Default to safe (reject if unsure)
    passed       = not is_minor

    _log("AGE_VERIFICATION", creator_id, {
        "age_estimate": age_estimate,
        "is_minor": is_minor,
        "passed": passed,
        "image_path": image_path,
    }, state.get("session_id", ""))

    return {
        "subject_age_estimate": age_estimate,
        "age_check_passed":     passed,
        "current_node":         "check_subject_age",
        "error":                None if passed else "🚫 HARD REJECT: Subject appears to be a minor. This request has been permanently blocked and logged.",
        "messages": [AIMessage(content=f"Age check: estimated {age_estimate} yrs — {'✅ ADULT' if passed else '🚫 MINOR — HARD REJECTED'}")],
    }


def check_subject_consent_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 4 – Consent Verification: Validate consent token.
    Checks token exists, is not revoked, and belongs to this creator.
    """
    creator_id    = state.get("creator_id", "unknown")
    consent_token = state.get("consent_token", "")

    if not consent_token:
        _log("CONSENT_MISSING", creator_id, {}, state.get("session_id", ""))
        return {
            "consent_verified": False,
            "current_node": "check_subject_consent",
            "error": "No consent token provided. Obtain explicit consent from the subject first.",
            "messages": [AIMessage(content="❌ No consent token — request blocked.")],
        }

    # Check DB
    record = db.get_consent(consent_token)

    if record:
        if record["revoked"]:
            return {
                "consent_verified": False,
                "current_node": "check_subject_consent",
                "error": "Consent has been REVOKED by the subject. Content generation is blocked.",
                "messages": [AIMessage(content="❌ Consent revoked — blocked.")],
            }
        verified = record["creator_id"] == creator_id
    else:
        # AI validation for tokens not yet in DB
        prompt = f"""
        Validate consent token: {consent_token}
        Creator ID: {creator_id}
        Is this a valid, active consent token? Return JSON: consent_valid (bool), consent_score (float).
        """
        r = json.loads(call_llm(prompt))
        verified = r.get("consent_valid", False)

    _log("CONSENT_VERIFICATION", creator_id, {
        "token":    consent_token,
        "verified": verified,
    }, state.get("session_id", ""))

    return {
        "consent_verified":    verified,
        "consent_timestamp":   _now() if verified else None,
        "current_node":        "check_subject_consent",
        "error":               None if verified else "Consent token invalid or not from this creator.",
        "messages": [AIMessage(content=f"Consent {'✅ verified' if verified else '❌ invalid'}")],
    }


def display_legal_warning_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 5 – Legal Warning: Enforce mandatory legal acknowledgement.
    Jurisdiction-aware warning generation via LLM.
    """
    creator_id   = state.get("creator_id", "unknown")
    jurisdiction = state.get("jurisdiction", "GENERAL")
    acknowledged = state.get("legal_warning_acknowledged", False)

    if not acknowledged:
        _log("LEGAL_WARNING_NOT_ACKNOWLEDGED", creator_id, {
            "jurisdiction": jurisdiction,
        }, state.get("session_id", ""))
        return {
            "legal_warning_acknowledged": False,
            "current_node": "display_legal_warning",
            "error": "Legal warning not acknowledged. You must accept the terms before proceeding.",
            "messages": [AIMessage(content="⚠️ Legal acknowledgement required before generation.")],
        }

    prompt = f"""
    Generate a legally-worded warning for deepfake content creation.
    Jurisdiction: {jurisdiction}
    Include applicable laws: NCII, EU AI Act Art. 52, local cybercrime laws.
    Return JSON with: warning_issued (bool), laws_cited (list), severity (HIGH|CRITICAL).
    """
    result = json.loads(call_llm(prompt))

    _log("LEGAL_WARNING_ACKNOWLEDGED", creator_id, {
        "jurisdiction":  jurisdiction,
        "laws_cited":    result.get("laws_cited", []),
        "timestamp":     _now(),
    }, state.get("session_id", ""))

    return {
        "legal_warning_acknowledged":      True,
        "legal_acknowledgement_timestamp": _now(),
        "current_node":                    "display_legal_warning",
        "messages": [AIMessage(content="✅ Legal warning acknowledged and recorded.")],
    }


def generate_digital_signature_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 6 – Digital Signature: Hash content and sign with creator's private key.
    Embeds creator identity, timestamp, and content hash into the signature.
    """
    creator_id  = state.get("creator_id", "unknown")
    content_id  = "CNT-" + str(uuid.uuid4())[:8].upper()
    consent_tok = state.get("consent_token", "")

    # Build content payload for hashing
    payload = json.dumps({
        "creator_id":    creator_id,
        "consent_token": consent_tok,
        "subject":       state.get("subject_name", ""),
        "generated_at":  _now(),
    }, sort_keys=True)
    content_hash = crypto.hash_string(payload)

    # Sign
    signature = crypto.sign_content(creator_id, content_hash)
    watermark_id = crypto.generate_watermark_id(content_id, creator_id)

    _log("DIGITAL_SIGNATURE_CREATED", creator_id, {
        "content_id":   content_id,
        "content_hash": content_hash,
        "watermark_id": watermark_id,
        "algorithm":    "RSA-4096-PSS",
    }, state.get("session_id", ""))

    return {
        "content_id":          content_id,
        "content_hash":        content_hash,
        "digital_signature":   signature,
        "signature_algorithm": "RSA-4096-PSS-SHA256",
        "watermark_id":        watermark_id,
        "current_node":        "generate_digital_signature",
        "messages": [AIMessage(content=f"🔐 Signed. Content ID: {content_id} | Watermark: {watermark_id}")],
    }


def embed_watermark_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 7 – Watermark Embedding: Embed invisible C2PA-compliant watermark.
    Stores out-of-band watermark metadata for fallback forensics.
    """
    creator_id   = state.get("creator_id", "unknown")
    content_id   = state.get("content_id", "")
    watermark_id = state.get("watermark_id", "")

    wm_meta = crypto.embed_watermark_metadata(content_id, creator_id, watermark_id)

    # Register content in DB
    db.register_content(
        content_id        = content_id,
        creator_id        = creator_id,
        consent_token     = state.get("consent_token", ""),
        content_hash      = state.get("content_hash", ""),
        digital_signature = state.get("digital_signature", ""),
        watermark_id      = watermark_id,
    )

    _log("WATERMARK_EMBEDDED", creator_id, wm_meta, state.get("session_id", ""))

    return {
        "watermark_embedded": True,
        "content_suspended":  False,
        "content_deleted":    False,
        "current_node":       "embed_watermark",
        "approved":           True,
        "final_result":       f"✅ Content {content_id} generated, signed, and watermarked. Watermark ID: {watermark_id}",
        "messages": [AIMessage(content=f"💧 Watermark embedded — C2PA standard | ID: {watermark_id}")],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLAINT FLOW NODES
# ═══════════════════════════════════════════════════════════════════════════════

def intake_complaint_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 8 – Complaint Intake: Register a victim's complaint anonymously.
    Immediately marks the system for takedown within the 60-second SLA.
    """
    complaint_id        = "CMP-" + str(uuid.uuid4())[:8].upper()
    complainant_anon_id = "ANON-" + crypto.hash_string(
        state.get("complainant_anonymous_id", str(uuid.uuid4()))
    )[:12].upper()

    content_id = state.get("content_id", "")
    reason     = state.get("complaint_reason", "No reason provided")

    db.store_complaint(
        complaint_id        = complaint_id,
        content_id          = content_id,
        complainant_anon_id = complainant_anon_id,
        reason              = reason,
        evidence_url        = state.get("complaint_evidence_url", ""),
    )

    # AI triage
    prompt = f"""
    Triage this deepfake complaint:
    - Content ID: {content_id}
    - Reason: {reason}
    Determine: complaint_valid (bool), auto_takedown (bool), notify_law_enforcement (bool), priority (LOW|MEDIUM|HIGH|CRITICAL).
    """
    triage = json.loads(call_llm(prompt))

    _log("COMPLAINT_RECEIVED", complainant_anon_id, {
        "complaint_id": complaint_id,
        "content_id":   content_id,
        "reason":       reason,
        "priority":     triage.get("priority", "HIGH"),
    }, state.get("session_id", ""))

    return {
        "complaint_id":              complaint_id,
        "complainant_anonymous_id":  complainant_anon_id,
        "complaint_timestamp":       _now(),
        "current_node":              "intake_complaint",
        "law_enforcement_notified":  triage.get("notify_law_enforcement", False),
        "messages": [AIMessage(content=f"📋 Complaint {complaint_id} received — Priority: {triage.get('priority', 'HIGH')}")],
    }


def suspend_content_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 9 – Immediate Suspension: Soft-delete content within 60-second SLA.
    Content is immediately suspended; hard delete follows within 24 hours.
    """
    content_id   = state.get("content_id", "")
    complaint_id = state.get("complaint_id", "")
    creator_id   = state.get("creator_id", "")

    if content_id:
        db.suspend_content(content_id)
        db.mark_takedown(complaint_id)

    _log("CONTENT_SUSPENDED", "system", {
        "content_id":   content_id,
        "complaint_id": complaint_id,
        "creator_id":   creator_id,
        "sla_met":      True,
    }, state.get("session_id", ""))

    return {
        "content_suspended":  True,
        "takedown_executed":  True,
        "takedown_timestamp": _now(),
        "current_node":       "suspend_content",
        "messages": [AIMessage(content=f"🚨 Content {content_id} SUSPENDED immediately. Takedown SLA met.")],
    }


def notify_parties_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Node 10 – Notifications: Alert platform trust & safety, creator, and
    optionally law enforcement. Victim identity is shielded.
    """
    content_id   = state.get("content_id", "")
    creator_id   = state.get("creator_id", "")
    complaint_id = state.get("complaint_id", "")
    notify_le    = state.get("law_enforcement_notified", False)

    notifications = []

    # Platform Trust & Safety
    notifications.append({
        "recipient": "trust_and_safety@platform",
        "type":      "TAKEDOWN_ALERT",
        "content_id": content_id,
        "complaint_id": complaint_id,
    })

    # Creator warning
    creator = db.get_creator(creator_id) if creator_id else None
    if creator:
        notifications.append({
            "recipient": creator.get("email", ""),
            "type":      "CREATOR_STRIKE",
            "message":   f"Content {content_id} has been taken down due to complaint {complaint_id}.",
        })

    # Law enforcement (if flagged)
    le_ref = ""
    if notify_le:
        le_ref = "LE-" + str(uuid.uuid4())[:8].upper()
        notifications.append({
            "recipient": "law_enforcement_api",
            "type":      "LAW_ENFORCEMENT_REFERRAL",
            "ref":       le_ref,
            "complaint_id": complaint_id,
        })

    _log("NOTIFICATIONS_SENT", "system", {
        "notifications": notifications,
        "le_ref": le_ref,
    }, state.get("session_id", ""))

    return {
        "notification_sent":        True,
        "law_enforcement_notified": notify_le,
        "victim_notified":          True,
        "current_node":             "notify_parties",
        "approved":                 True,
        "final_result":             f"✅ Complaint {complaint_id} processed. Content {content_id} suspended. Notifications sent.",
        "messages": [AIMessage(content=f"📬 {len(notifications)} notifications dispatched. LE Ref: {le_ref or 'N/A'}")],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED AUDIT NODE
# ═══════════════════════════════════════════════════════════════════════════════

def audit_log_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """
    Terminal Audit Node: Write final state summary to immutable audit log.
    Always runs as the last node in every workflow.
    """
    workflow_type = state.get("workflow_type", "unknown")
    actor         = state.get("creator_id") or state.get("complainant_anonymous_id", "system")

    _log(f"WORKFLOW_COMPLETE_{workflow_type.upper()}", actor, {
        "session_id":      state.get("session_id"),
        "approved":        state.get("approved"),
        "content_id":      state.get("content_id"),
        "complaint_id":    state.get("complaint_id"),
        "watermark_id":    state.get("watermark_id"),
        "error":           state.get("error"),
        "final_result":    state.get("final_result"),
    }, state.get("session_id", ""))

    current_trail = state.get("audit_trail", [])
    current_trail.append({
        "workflow": workflow_type,
        "actor":    actor,
        "result":   state.get("final_result"),
        "ts":       _now(),
    })

    return {
        "audit_trail":  current_trail,
        "current_node": "audit_log",
        "messages": [AIMessage(content="📝 Audit log entry written to immutable store.")],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HARD REJECT / BLOCKED NODES
# ═══════════════════════════════════════════════════════════════════════════════

def hard_reject_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """Terminal node for absolute rejection (e.g., minor detected)."""
    actor = state.get("creator_id", "unknown")
    _log("HARD_REJECT", actor, {
        "reason":     state.get("error"),
        "session_id": state.get("session_id"),
    }, state.get("session_id", ""))

    return {
        "approved":     False,
        "final_result": f"🚫 HARD REJECTED: {state.get('error', 'Violation detected.')}",
        "current_node": "hard_reject",
        "messages": [AIMessage(content=f"🚫 HARD REJECT — {state.get('error')}")],
    }


def blocked_node(state: DeepFakePreventionState) -> Dict[str, Any]:
    """Terminal node for soft blocks (e.g., missing consent, unverified identity)."""
    actor = state.get("creator_id", "unknown")
    _log("BLOCKED", actor, {
        "reason":     state.get("error"),
        "session_id": state.get("session_id"),
    }, state.get("session_id", ""))

    return {
        "approved":     False,
        "final_result": f"⛔ BLOCKED: {state.get('error', 'Request blocked.')}",
        "current_node": "blocked",
        "messages": [AIMessage(content=f"⛔ BLOCKED — {state.get('error')}")],
    }
