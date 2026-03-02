"""
DeepFake Misuse Prevention System - State Definitions
LangGraph typed state for all agent workflows.
"""

from typing import Optional, Annotated, List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class DeepFakePreventionState(TypedDict):
    """
    Unified state for the DeepFake Misuse Prevention agent.
    Covers generation, complaint, and registration workflows.
    """

    # ─── Session ────────────────────────────────────────────────────────────────
    session_id: str
    workflow_type: str          # "generation" | "complaint" | "registration"
    current_node: Optional[str]
    error: Optional[str]
    approved: bool
    final_result: Optional[str]

    # ─── Creator Identity ────────────────────────────────────────────────────────
    creator_id: Optional[str]
    creator_name: Optional[str]
    creator_email: Optional[str]
    creator_id_verified: bool   # KYC / government ID verified
    creator_liveness_passed: bool

    # ─── Subject / Source Media ──────────────────────────────────────────────────
    subject_image_path: Optional[str]
    subject_name: Optional[str]
    subject_contact: Optional[str]   # email / phone for consent OTP
    subject_age_estimate: Optional[int]
    age_check_passed: bool           # False if minor detected → hard reject

    # ─── Consent ─────────────────────────────────────────────────────────────────
    consent_token: Optional[str]
    consent_verified: bool
    consent_timestamp: Optional[str]
    consent_revoked: bool

    # ─── Legal Warning ────────────────────────────────────────────────────────────
    legal_warning_acknowledged: bool
    legal_acknowledgement_timestamp: Optional[str]
    jurisdiction: Optional[str]

    # ─── Digital Signature & Watermark ────────────────────────────────────────────
    content_hash: Optional[str]
    digital_signature: Optional[str]
    signature_algorithm: Optional[str]
    watermark_id: Optional[str]
    watermark_embedded: bool

    # ─── Generated Content ────────────────────────────────────────────────────────
    content_id: Optional[str]
    content_url: Optional[str]
    content_suspended: bool
    content_deleted: bool

    # ─── Complaint ────────────────────────────────────────────────────────────────
    complaint_id: Optional[str]
    complainant_anonymous_id: Optional[str]
    complaint_reason: Optional[str]
    complaint_evidence_url: Optional[str]
    complaint_timestamp: Optional[str]
    takedown_executed: bool
    takedown_timestamp: Optional[str]

    # ─── Notifications ────────────────────────────────────────────────────────────
    notification_sent: bool
    law_enforcement_notified: bool
    victim_notified: bool

    # ─── Audit Trail ──────────────────────────────────────────────────────────────
    audit_trail: List[Dict[str, Any]]

    # ─── LLM Messages ─────────────────────────────────────────────────────────────
    messages: Annotated[list, add_messages]
