"""
DeepFake Misuse Prevention System - LangGraph Definition
Three parallel workflows managed by a supervisor:
  1. registration  → verify_kyc → audit_log
  2. generation    → age_check → consent → legal_warning → sign → watermark → audit_log
  3. complaint     → suspend → notify → audit_log
"""

from langgraph.graph import StateGraph, END

from agent.state import DeepFakePreventionState
from agent.nodes import (
    supervisor_node,
    register_creator_node,
    verify_kyc_node,
    check_subject_age_node,
    check_subject_consent_node,
    display_legal_warning_node,
    generate_digital_signature_node,
    embed_watermark_node,
    intake_complaint_node,
    suspend_content_node,
    notify_parties_node,
    audit_log_node,
    hard_reject_node,
    blocked_node,
)


# ─── Conditional Edge Functions ───────────────────────────────────────────────

def route_by_workflow(state: DeepFakePreventionState) -> str:
    """Supervisor routes to the appropriate sub-flow."""
    wf = state.get("workflow_type", "generation")
    if wf == "registration":
        return "registration"
    elif wf == "complaint":
        return "complaint"
    return "generation"


def route_after_kyc(state: DeepFakePreventionState) -> str:
    return "audit_log" if not state.get("approved") else "audit_log"
    # Registration always ends at audit


def route_after_age_check(state: DeepFakePreventionState) -> str:
    if not state.get("age_check_passed"):
        return "hard_reject"
    return "check_subject_consent"


def route_after_consent(state: DeepFakePreventionState) -> str:
    if not state.get("consent_verified"):
        return "blocked"
    return "display_legal_warning"


def route_after_legal_warning(state: DeepFakePreventionState) -> str:
    if not state.get("legal_warning_acknowledged"):
        return "blocked"
    return "generate_digital_signature"


def route_after_identity_verify(state: DeepFakePreventionState) -> str:
    if not state.get("creator_id_verified"):
        return "blocked"
    return "check_subject_age"


# ─── Graph Builder ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct and compile the full LangGraph prevention pipeline."""
    graph = StateGraph(DeepFakePreventionState)

    # ── Add all nodes ────────────────────────────────────────────────────────
    graph.add_node("supervisor",                 supervisor_node)
    graph.add_node("register_creator",           register_creator_node)
    graph.add_node("verify_kyc",                 verify_kyc_node)
    graph.add_node("check_subject_age",          check_subject_age_node)
    graph.add_node("check_subject_consent",      check_subject_consent_node)
    graph.add_node("display_legal_warning",      display_legal_warning_node)
    graph.add_node("generate_digital_signature", generate_digital_signature_node)
    graph.add_node("embed_watermark",            embed_watermark_node)
    graph.add_node("intake_complaint",           intake_complaint_node)
    graph.add_node("suspend_content",            suspend_content_node)
    graph.add_node("notify_parties",             notify_parties_node)
    graph.add_node("audit_log",                  audit_log_node)
    graph.add_node("hard_reject",                hard_reject_node)
    graph.add_node("blocked",                    blocked_node)

    # ── Entry point ──────────────────────────────────────────────────────────
    graph.set_entry_point("supervisor")

    # ── Supervisor routes ────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "supervisor",
        route_by_workflow,
        {
            "registration": "register_creator",
            "generation":   "check_subject_age",
            "complaint":    "intake_complaint",
        },
    )

    # ── Registration flow ────────────────────────────────────────────────────
    graph.add_edge("register_creator", "verify_kyc")
    graph.add_edge("verify_kyc",       "audit_log")

    # ── Generation flow ──────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "check_subject_age",
        route_after_age_check,
        {
            "hard_reject":          "hard_reject",
            "check_subject_consent": "check_subject_consent",
        },
    )
    graph.add_conditional_edges(
        "check_subject_consent",
        route_after_consent,
        {
            "blocked":             "blocked",
            "display_legal_warning": "display_legal_warning",
        },
    )
    graph.add_conditional_edges(
        "display_legal_warning",
        route_after_legal_warning,
        {
            "blocked":                    "blocked",
            "generate_digital_signature": "generate_digital_signature",
        },
    )
    graph.add_edge("generate_digital_signature", "embed_watermark")
    graph.add_edge("embed_watermark",            "audit_log")

    # ── Complaint flow ────────────────────────────────────────────────────────
    graph.add_edge("intake_complaint",  "suspend_content")
    graph.add_edge("suspend_content",   "notify_parties")
    graph.add_edge("notify_parties",    "audit_log")

    # ── Terminal nodes ────────────────────────────────────────────────────────
    graph.add_edge("hard_reject", "audit_log")
    graph.add_edge("blocked",     "audit_log")
    graph.add_edge("audit_log",   END)

    return graph.compile()


# Singleton compiled graph
prevention_graph = build_graph()


def run_generation_workflow(
    creator_id: str,
    creator_name: str,
    subject_image_path: str,
    consent_token: str,
    subject_name: str,
    legal_acknowledged: bool,
    jurisdiction: str = "GENERAL",
    session_id: str = None,
) -> DeepFakePreventionState:
    """Convenience wrapper for the content generation flow."""
    import uuid
    initial_state: DeepFakePreventionState = {
        "session_id":                    session_id or str(uuid.uuid4()),
        "workflow_type":                 "generation",
        "creator_id":                    creator_id,
        "creator_name":                  creator_name,
        "creator_email":                 "",
        "creator_id_verified":           True,
        "creator_liveness_passed":       True,
        "subject_image_path":            subject_image_path,
        "subject_name":                  subject_name,
        "subject_contact":               "",
        "subject_age_estimate":          None,
        "age_check_passed":              False,
        "consent_token":                 consent_token,
        "consent_verified":              False,
        "consent_timestamp":             None,
        "consent_revoked":               False,
        "legal_warning_acknowledged":    legal_acknowledged,
        "legal_acknowledgement_timestamp": None,
        "jurisdiction":                  jurisdiction,
        "content_hash":                  None,
        "digital_signature":             None,
        "signature_algorithm":           None,
        "watermark_id":                  None,
        "watermark_embedded":            False,
        "content_id":                    None,
        "content_url":                   None,
        "content_suspended":             False,
        "content_deleted":               False,
        "complaint_id":                  None,
        "complainant_anonymous_id":      None,
        "complaint_reason":              None,
        "complaint_evidence_url":        None,
        "complaint_timestamp":           None,
        "takedown_executed":             False,
        "takedown_timestamp":            None,
        "notification_sent":             False,
        "law_enforcement_notified":      False,
        "victim_notified":               False,
        "audit_trail":                   [],
        "messages":                      [],
        "current_node":                  None,
        "error":                         None,
        "approved":                      False,
        "final_result":                  None,
    }
    return prevention_graph.invoke(initial_state)


def run_complaint_workflow(
    content_id: str,
    complaint_reason: str,
    evidence_url: str = "",
    session_id: str = None,
) -> DeepFakePreventionState:
    """Convenience wrapper for the complaint / takedown flow."""
    import uuid
    initial_state: DeepFakePreventionState = {
        "session_id":                    session_id or str(uuid.uuid4()),
        "workflow_type":                 "complaint",
        "creator_id":                    None,
        "creator_name":                  None,
        "creator_email":                 None,
        "creator_id_verified":           False,
        "creator_liveness_passed":       False,
        "subject_image_path":            None,
        "subject_name":                  None,
        "subject_contact":               None,
        "subject_age_estimate":          None,
        "age_check_passed":              False,
        "consent_token":                 None,
        "consent_verified":              False,
        "consent_timestamp":             None,
        "consent_revoked":               False,
        "legal_warning_acknowledged":    False,
        "legal_acknowledgement_timestamp": None,
        "jurisdiction":                  "GENERAL",
        "content_hash":                  None,
        "digital_signature":             None,
        "signature_algorithm":           None,
        "watermark_id":                  None,
        "watermark_embedded":            False,
        "content_id":                    content_id,
        "content_url":                   None,
        "content_suspended":             False,
        "content_deleted":               False,
        "complaint_id":                  None,
        "complainant_anonymous_id":      str(uuid.uuid4()),
        "complaint_reason":              complaint_reason,
        "complaint_evidence_url":        evidence_url,
        "complaint_timestamp":           None,
        "takedown_executed":             False,
        "takedown_timestamp":            None,
        "notification_sent":             False,
        "law_enforcement_notified":      False,
        "victim_notified":               False,
        "audit_trail":                   [],
        "messages":                      [],
        "current_node":                  None,
        "error":                         None,
        "approved":                      False,
        "final_result":                  None,
    }
    return prevention_graph.invoke(initial_state)


def run_registration_workflow(
    creator_name: str,
    creator_email: str,
    session_id: str = None,
) -> DeepFakePreventionState:
    """Convenience wrapper for the creator registration flow."""
    import uuid
    initial_state: DeepFakePreventionState = {
        "session_id":                    session_id or str(uuid.uuid4()),
        "workflow_type":                 "registration",
        "creator_id":                    None,
        "creator_name":                  creator_name,
        "creator_email":                 creator_email,
        "creator_id_verified":           False,
        "creator_liveness_passed":       False,
        "subject_image_path":            None,
        "subject_name":                  None,
        "subject_contact":               None,
        "subject_age_estimate":          None,
        "age_check_passed":              False,
        "consent_token":                 None,
        "consent_verified":              False,
        "consent_timestamp":             None,
        "consent_revoked":               False,
        "legal_warning_acknowledged":    False,
        "legal_acknowledgement_timestamp": None,
        "jurisdiction":                  "GENERAL",
        "content_hash":                  None,
        "digital_signature":             None,
        "signature_algorithm":           None,
        "watermark_id":                  None,
        "watermark_embedded":            False,
        "content_id":                    None,
        "content_url":                   None,
        "content_suspended":             False,
        "content_deleted":               False,
        "complaint_id":                  None,
        "complainant_anonymous_id":      None,
        "complaint_reason":              None,
        "complaint_evidence_url":        None,
        "complaint_timestamp":           None,
        "takedown_executed":             False,
        "takedown_timestamp":            None,
        "notification_sent":             False,
        "law_enforcement_notified":      False,
        "victim_notified":               False,
        "audit_trail":                   [],
        "messages":                      [],
        "current_node":                  None,
        "error":                         None,
        "approved":                      False,
        "final_result":                  None,
    }
    return prevention_graph.invoke(initial_state)
