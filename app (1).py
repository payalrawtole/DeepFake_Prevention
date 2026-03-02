"""
DeepFake Misuse Prevention System
Streamlit Web Application
"""

import uuid
import json
import streamlit as st
from datetime import datetime, timezone

from agent import database as db
from agent.graph import (
    run_registration_workflow,
    run_generation_workflow,
    run_complaint_workflow,
)
from agent.crypto_utils import generate_consent_token

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DeepFake Misuse Prevention",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Init DB ──────────────────────────────────────────────────────────────────
db.init_db()

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }
    .main-header h1 { font-size: 2.2rem; margin: 0; }
    .main-header p  { font-size: 1rem; opacity: 0.85; margin: 0.5rem 0 0; }

    .status-card {
        background: #f8f9fa;
        border-left: 5px solid #0f3460;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        margin: 0.5rem 0;
    }
    .status-pass  { border-left-color: #28a745; background: #f0fff4; }
    .status-fail  { border-left-color: #dc3545; background: #fff5f5; }
    .status-warn  { border-left-color: #ffc107; background: #fffbf0; }

    .legal-box {
        background: #fff3cd;
        border: 2px solid #ffc107;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    .legal-box h4 { color: #856404; }

    .signature-box {
        background: #e8f4fd;
        border: 1px solid #bee3f8;
        border-radius: 8px;
        padding: 1rem;
        font-family: monospace;
        font-size: 0.8rem;
        word-break: break-all;
    }

    .complaint-box {
        background: #fff5f5;
        border: 2px solid #fc8181;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }

    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
    }
    .metric-card .metric-value { font-size: 2rem; font-weight: 700; color: #0f3460; }
    .metric-card .metric-label { font-size: 0.85rem; color: #666; }

    .step-indicator {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
        flex-wrap: wrap;
    }
    .step-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .step-done    { background: #d4edda; color: #155724; }
    .step-current { background: #cce5ff; color: #004085; }
    .step-pending { background: #f8f9fa; color: #6c757d; }

    .sidebar .sidebar-content { background: #1a1a2e; }
    div[data-testid="stSidebar"] { background: #1a1a2e; }
    div[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🛡️ DeepFake Misuse Prevention System</h1>
    <p>Consent-first • Cryptographically accountable • Victim-first takedown</p>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar Navigation ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Navigation")
    page = st.radio(
        "Select Portal",
        ["🏠 Overview", "👤 Creator Registration", "🎬 Generation Request",
         "🚨 Complaint / Takedown", "📊 Admin Dashboard"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**System Status**")
    st.markdown("🟢 Identity Service: Online")
    st.markdown("🟢 Takedown Engine: Online")
    st.markdown("🟢 Audit Logger: Online")
    st.markdown("🟢 Signature Service: Online")
    st.markdown("---")
    st.markdown("**Legal Resources**")
    st.markdown("• [NCII Helpline](#)")
    st.markdown("• [Report Cybercrime](#)")
    st.markdown("• [Legal Aid](#)")
    st.caption("DeepFake Prevention Platform v1.0")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🏠 Overview":
    st.subheader("System Architecture Overview")

    col1, col2, col3, col4 = st.columns(4)
    stats = {
        "creators":   len(db.get_all_creators()),
        "content":    len(db.get_all_content()),
        "complaints": len(db.get_all_complaints()),
        "audit":      len(db.get_audit_log(limit=9999)),
    }
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{stats['creators']}</div>
            <div class="metric-label">Registered Creators</div></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{stats['content']}</div>
            <div class="metric-label">Content Entries</div></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{stats['complaints']}</div>
            <div class="metric-label">Complaints Filed</div></div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-value">{stats['audit']}</div>
            <div class="metric-label">Audit Log Entries</div></div>""", unsafe_allow_html=True)

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 🔄 Generation Workflow")
        st.markdown("""
```
START
  │
  ▼
[Supervisor] ─── workflow_type = "generation"
  │
  ▼
[Age Verification] ──── Minor? ──► [HARD REJECT]
  │ Adult
  ▼
[Consent Check] ──── No consent? ──► [BLOCKED]
  │ Consent verified
  ▼
[Legal Warning] ──── Not acknowledged? ──► [BLOCKED]
  │ Acknowledged
  ▼
[Digital Signature] (RSA-4096)
  │
  ▼
[Watermark Embedding] (C2PA + LSB)
  │
  ▼
[Audit Log] ──► END
```
        """)

    with col_b:
        st.markdown("### 🚨 Complaint Workflow")
        st.markdown("""
```
START
  │
  ▼
[Supervisor] ─── workflow_type = "complaint"
  │
  ▼
[Complaint Intake] (anonymous)
  │  ⏱ < 60 seconds
  ▼
[Content SUSPENDED immediately]
  │
  ▼
[Notify: T&S + Creator + LE if flagged]
  │
  ▼
[Audit Log] ──► END
```
        """)

    st.markdown("---")
    st.markdown("### 🔐 Key Safeguards")
    safeguards = [
        ("🧒 Minor Protection",      "AI hard-rejects any source media where subject appears under 18. Zero human override."),
        ("✅ Consent Verification",   "Cryptographic consent tokens with OTP delivery to subject. Revocable at any time."),
        ("⚖️ Legal Warning Gate",     "Mandatory jurisdiction-aware legal acknowledgement with timestamp before generation."),
        ("🔐 RSA-4096 Signature",     "Every output cryptographically signed with creator's private key stored in vault."),
        ("💧 C2PA Watermark",         "Invisible watermark conforming to Coalition for Content Provenance & Authenticity."),
        ("⚡ 60-Second Takedown",     "Complaint triggers immediate content suspension within SLA; hard delete in 24 hrs."),
        ("🕵️ Anonymous Reporting",    "Victim identity shielded throughout complaint process."),
        ("📋 Immutable Audit Log",    "All events written to append-only SQLite (WORM-equivalent); supports LE API."),
    ]
    for icon_title, desc in safeguards:
        with st.expander(icon_title):
            st.write(desc)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: CREATOR REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "👤 Creator Registration":
    st.subheader("👤 Creator Identity Registration & KYC")
    st.info("All creators must complete identity verification (KYC) before generating any content. Your identity is securely stored and used only for accountability.")

    with st.form("registration_form"):
        st.markdown("#### Personal Details")
        col1, col2 = st.columns(2)
        with col1:
            creator_name  = st.text_input("Full Legal Name *", placeholder="Jane Smith")
        with col2:
            creator_email = st.text_input("Email Address *",   placeholder="jane@example.com")

        st.markdown("#### Identity Verification")
        st.markdown("""<div class="status-card status-warn">
            ⚠️ In production: Government ID upload + liveness check (facial video) required.
            This demo simulates the KYC result via AI analysis.
        </div>""", unsafe_allow_html=True)
        id_type = st.selectbox("ID Type", ["Passport", "National ID", "Driver's License"])
        id_number = st.text_input("ID Number (simulated)", placeholder="e.g. ABC123456")

        st.markdown("#### Jurisdiction")
        jurisdiction = st.selectbox("Your Country / Jurisdiction", [
            "GENERAL", "European Union", "United States", "United Kingdom",
            "India", "Australia", "Canada", "Singapore",
        ])

        submitted = st.form_submit_button("🔐 Register & Verify Identity", use_container_width=True)

    if submitted:
        if not creator_name or not creator_email:
            st.error("Please fill in all required fields.")
        else:
            with st.spinner("🔄 Running KYC verification..."):
                result = run_registration_workflow(
                    creator_name=creator_name,
                    creator_email=creator_email,
                )

            st.markdown("### Verification Result")
            if result.get("creator_id_verified"):
                st.success("✅ Identity Verified Successfully")
                st.markdown(f"""<div class="status-card status-pass">
                    <strong>Creator ID:</strong> {result.get('creator_id')}<br>
                    <strong>KYC Status:</strong> Verified ✅<br>
                    <strong>Liveness Check:</strong> {'Passed ✅' if result.get('creator_liveness_passed') else 'Pending'}<br>
                    <strong>RSA-4096 Key Pair:</strong> Generated & Stored 🔐<br>
                    <strong>Registered:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
                </div>""", unsafe_allow_html=True)
                st.info(f"📋 Save your Creator ID: **{result.get('creator_id')}** — needed for generation requests.")
            else:
                st.error("❌ Identity Verification Failed")
                st.markdown(f"""<div class="status-card status-fail">
                    <strong>Reason:</strong> {result.get('error', 'KYC verification failed.')}<br>
                    <strong>Action Required:</strong> Please re-submit with valid government-issued ID.
                </div>""", unsafe_allow_html=True)

            for msg in result.get("messages", []):
                if hasattr(msg, "content"):
                    st.caption(f"Agent: {msg.content}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: GENERATION REQUEST
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🎬 Generation Request":
    st.subheader("🎬 Content Generation Request")
    st.warning("⚠️ All generation requests are cryptographically signed and permanently logged. False or malicious requests are traceable.")

    tab1, tab2 = st.tabs(["📋 New Request", "🔑 Generate Consent Token"])

    with tab2:
        st.markdown("#### Generate Consent Token for Subject")
        st.info("Send this token to the subject. They must confirm consent by returning this token to you.")
        with st.form("consent_form"):
            cg_creator_id      = st.text_input("Your Creator ID", placeholder="CRT-XXXXXXXX")
            cg_subject_name    = st.text_input("Subject Full Name", placeholder="Subject Name")
            cg_subject_contact = st.text_input("Subject Email / Phone", placeholder="subject@email.com")
            gen_token = st.form_submit_button("🔑 Generate Consent Token", use_container_width=True)

        if gen_token:
            if cg_creator_id and cg_subject_contact:
                token = generate_consent_token(cg_creator_id, cg_subject_contact)
                db.store_consent(token, cg_creator_id, cg_subject_name, cg_subject_contact)
                st.success("✅ Consent Token Generated")
                st.code(token, language=None)
                st.info("📨 In production: This token is delivered to the subject via OTP/email. They must confirm before proceeding.")
            else:
                st.error("Creator ID and subject contact are required.")

    with tab1:
        st.markdown("#### Step 1 — Legal Warning")
        st.markdown("""<div class="legal-box">
            <h4>⚖️ MANDATORY LEGAL WARNING</h4>
            <p><strong>Creating deepfake content without explicit consent is a criminal offence</strong> in most jurisdictions, including:</p>
            <ul>
                <li>🇪🇺 EU AI Act Article 52 — mandatory disclosure obligations</li>
                <li>🇬🇧 NCII (Non-Consensual Intimate Images) Act</li>
                <li>🇺🇸 DMCA §512 and state-level deepfake criminal statutes</li>
                <li>🇮🇳 IT Act Section 66E, 67, 67A</li>
            </ul>
            <p><strong>Creating deepfake content to blackmail, defame, or harm any person is a serious crime</strong> punishable by imprisonment and/or significant fines.</p>
            <p>Your digital identity, IP address, and a cryptographic signature will be <strong>permanently embedded</strong> in all generated content. This can be retrieved immediately upon a legal complaint.</p>
            <p><em>Psychological support resources: <a href="#">Helpline</a> | <a href="#">Legal Aid for Victims</a></em></p>
        </div>""", unsafe_allow_html=True)

        legal_ack = st.checkbox(
            "✅ I have read and understood the legal warning. I confirm I have explicit consent from the subject and will use this content lawfully.",
            key="legal_ack",
        )

        if legal_ack:
            st.success("✅ Legal acknowledgement recorded with timestamp.")

            st.markdown("#### Step 2 — Generation Details")
            with st.form("generation_form"):
                col1, col2 = st.columns(2)
                with col1:
                    gen_creator_id   = st.text_input("Your Creator ID *", placeholder="CRT-XXXXXXXX")
                    gen_creator_name = st.text_input("Your Name *", placeholder="Jane Smith")
                with col2:
                    gen_consent_tok  = st.text_input("Consent Token *", placeholder="CT-XXXX...")
                    gen_subject      = st.text_input("Subject Name *", placeholder="Subject Full Name")

                gen_image_desc = st.text_input("Source Image Description", placeholder="e.g. LinkedIn profile photo")
                gen_jurisdiction = st.selectbox("Jurisdiction", [
                    "GENERAL", "European Union", "United States", "United Kingdom",
                    "India", "Australia", "Canada",
                ])

                submit_gen = st.form_submit_button("🚀 Submit Generation Request", use_container_width=True)

            if submit_gen:
                if not all([gen_creator_id, gen_creator_name, gen_consent_tok, gen_subject]):
                    st.error("Please fill in all required fields.")
                else:
                    with st.spinner("🔄 Running prevention pipeline..."):
                        result = run_generation_workflow(
                            creator_id          = gen_creator_id,
                            creator_name        = gen_creator_name,
                            subject_image_path  = gen_image_desc,
                            consent_token       = gen_consent_tok,
                            subject_name        = gen_subject,
                            legal_acknowledged  = True,
                            jurisdiction        = gen_jurisdiction,
                        )

                    st.markdown("### Pipeline Result")
                    steps = {
                        "Age Check":       result.get("age_check_passed"),
                        "Consent":         result.get("consent_verified"),
                        "Legal Warning":   result.get("legal_warning_acknowledged"),
                        "Digital Sig":     bool(result.get("digital_signature")),
                        "Watermark":       result.get("watermark_embedded"),
                    }

                    st.markdown('<div class="step-indicator">', unsafe_allow_html=True)
                    for step, passed in steps.items():
                        cls = "step-done" if passed else "step-fail"
                        icon = "✅" if passed else "❌"
                        st.markdown(
                            f'<span class="step-badge {cls}">{icon} {step}</span>',
                            unsafe_allow_html=True,
                        )
                    st.markdown('</div>', unsafe_allow_html=True)

                    if result.get("approved"):
                        st.success(result.get("final_result", "✅ Request approved."))
                        st.markdown(f"""<div class="signature-box">
                            <strong>Content ID:</strong> {result.get('content_id')}<br>
                            <strong>Watermark ID:</strong> {result.get('watermark_id')}<br>
                            <strong>Signature Algorithm:</strong> {result.get('signature_algorithm')}<br>
                            <strong>Content Hash:</strong> {result.get('content_hash', '')[:40]}...<br>
                            <strong>Digital Signature:</strong> {str(result.get('digital_signature', ''))[:60]}...
                        </div>""", unsafe_allow_html=True)
                    else:
                        final = result.get("final_result") or result.get("error", "Request blocked.")
                        if "HARD" in (final or ""):
                            st.error(final)
                        else:
                            st.warning(final)

                    with st.expander("🔍 Agent Messages"):
                        for msg in result.get("messages", []):
                            if hasattr(msg, "content"):
                                st.caption(f"• {msg.content}")
        else:
            st.info("☝️ You must acknowledge the legal warning before accessing the generation form.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: COMPLAINT / TAKEDOWN
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "🚨 Complaint / Takedown":
    st.subheader("🚨 Complaint & Immediate Takedown Portal")
    st.markdown("""<div class="complaint-box">
        <strong>🔒 Your identity is fully protected.</strong>
        You do not need to reveal who you are. Your complaint will be processed anonymously.
        Content will be <strong>suspended within 60 seconds</strong> of submission.
        <br><br>
        <em>If you are in immediate danger, please contact emergency services or a helpline:
        <a href="#">Victim Support</a> | <a href="#">Cybercrime Helpline</a></em>
    </div>""", unsafe_allow_html=True)

    tab_c1, tab_c2 = st.tabs(["📝 File New Complaint", "🔍 Track Complaint"])

    with tab_c1:
        with st.form("complaint_form"):
            st.markdown("#### What content are you reporting?")
            content_id_input = st.text_input(
                "Content ID (if known)",
                placeholder="CNT-XXXXXXXX (check watermark metadata)",
                help="If you don't know the Content ID, describe the content below."
            )
            evidence_url = st.text_input(
                "Link to the deepfake content",
                placeholder="https://..."
            )

            st.markdown("#### Why are you reporting this?")
            reason_category = st.selectbox("Category", [
                "Non-consensual intimate imagery (NCII)",
                "Identity theft / impersonation",
                "Blackmail / extortion material",
                "Reputation damage / defamation",
                "Harassment",
                "Content involves a minor",
                "Other",
            ])
            reason_detail = st.text_area(
                "Additional details (optional — do not include personal information)",
                height=100,
            )

            st.markdown("#### Notification Preference")
            notify_le = st.checkbox(
                "🚔 I want this referred to law enforcement",
                value=False,
            )

            submit_complaint = st.form_submit_button(
                "🚨 Submit Complaint & Trigger Immediate Takedown",
                use_container_width=True,
            )

        if submit_complaint:
            full_reason = f"{reason_category}. {reason_detail}".strip()
            with st.spinner("⚡ Processing complaint and suspending content..."):
                result = run_complaint_workflow(
                    content_id      = content_id_input or f"UNKNOWN-{uuid.uuid4().hex[:6].upper()}",
                    complaint_reason= full_reason,
                    evidence_url    = evidence_url,
                )

            if result.get("takedown_executed"):
                st.success("✅ Complaint Received — Content SUSPENDED Immediately")
                st.markdown(f"""<div class="status-card status-pass">
                    <strong>Complaint ID:</strong> {result.get('complaint_id')}<br>
                    <strong>Your Anonymous Reference:</strong> {result.get('complainant_anonymous_id')}<br>
                    <strong>Content Status:</strong> {'🚫 SUSPENDED' if result.get('content_suspended') else 'Processing'}<br>
                    <strong>Takedown Time:</strong> {result.get('takedown_timestamp', 'Just now')}<br>
                    <strong>Notifications Sent:</strong> {'Yes ✅' if result.get('notification_sent') else 'Pending'}<br>
                    <strong>Law Enforcement:</strong> {'Notified 🚔' if result.get('law_enforcement_notified') else 'Not requested'}
                </div>""", unsafe_allow_html=True)
                st.info("📋 Save your Complaint ID for tracking. Hard deletion will occur within 24 hours.")

                st.markdown("""
                **What happens next:**
                1. ✅ Content has been immediately suspended (soft-deleted)
                2. 📬 Platform Trust & Safety team has been alerted
                3. ⚠️ Creator account has been flagged and warned
                4. 🗑️ Hard deletion will be completed within 24 hours
                5. 📝 Permanent audit record created — available for legal proceedings
                """)
            else:
                st.error("There was an issue processing your complaint. Please try again or contact support.")

            with st.expander("🔍 Agent Messages"):
                for msg in result.get("messages", []):
                    if hasattr(msg, "content"):
                        st.caption(f"• {msg.content}")

    with tab_c2:
        st.markdown("#### Track Your Complaint")
        track_id = st.text_input("Enter Complaint ID", placeholder="CMP-XXXXXXXX")
        if st.button("🔍 Track"):
            record = db.get_complaint(track_id)
            if record:
                status_icon = "✅" if record["takedown_executed"] else "⏳"
                st.markdown(f"""<div class="status-card">
                    <strong>Complaint ID:</strong> {record['complaint_id']}<br>
                    <strong>Status:</strong> {status_icon} {record['status']}<br>
                    <strong>Content ID:</strong> {record['content_id']}<br>
                    <strong>Submitted:</strong> {record['submitted_at']}<br>
                    <strong>Takedown:</strong> {'Executed ✅' if record['takedown_executed'] else 'Pending ⏳'}<br>
                    <strong>Takedown Time:</strong> {record.get('takedown_at') or 'Pending'}
                </div>""", unsafe_allow_html=True)
            else:
                st.warning("Complaint ID not found. Please check and try again.")

    st.markdown("---")
    st.markdown("""
    **🆘 Immediate Help Resources**
    | Resource | Contact |
    |---|---|
    | Cyber Crime Helpline | 1930 (India) / 101 (UK) |
    | Non-Consensual Image Abuse | [StopNCII.org](https://stopncii.org) |
    | Internet Watch Foundation | [iwf.org.uk](https://iwf.org.uk) |
    | Revenge Porn Helpline | 0345 6000 459 |
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Admin Dashboard":
    st.subheader("📊 Admin Dashboard — Trust & Safety")
    st.warning("🔒 In production: This section requires Trust & Safety officer authentication with MFA.")

    dashboard_tab1, dashboard_tab2, dashboard_tab3, dashboard_tab4 = st.tabs([
        "📋 Audit Log", "🎬 Content Registry", "👤 Creators", "🚨 Complaints"
    ])

    with dashboard_tab1:
        st.markdown("#### Immutable Audit Log")
        st.caption("Append-only — entries cannot be modified or deleted.")
        limit = st.slider("Show last N entries", 10, 200, 50)
        logs = db.get_audit_log(limit=limit)
        if logs:
            for entry in logs:
                try:
                    payload = json.loads(entry.get("payload", "{}"))
                except Exception:
                    payload = {}
                with st.expander(f"[{entry['logged_at']}] {entry['event_type']} — Actor: {entry['actor_id']}"):
                    st.json(payload)
        else:
            st.info("No audit entries yet. Use the system to generate events.")

    with dashboard_tab2:
        st.markdown("#### Content Registry")
        contents = db.get_all_content()
        if contents:
            for c in contents:
                status = "🚫 SUSPENDED" if c["suspended"] else ("🗑️ DELETED" if c["deleted"] else "✅ ACTIVE")
                with st.expander(f"{status} | {c['content_id']} | Creator: {c['creator_id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Created:** {c['created_at']}")
                        st.markdown(f"**Consent Token:** {c['consent_token']}")
                        st.markdown(f"**Watermark ID:** {c['watermark_id']}")
                    with col2:
                        st.markdown(f"**Content Hash:** {c['content_hash'][:20]}..." if c['content_hash'] else "N/A")
                        st.markdown(f"**Signature:** {str(c['digital_signature'])[:20]}..." if c['digital_signature'] else "N/A")
                        st.markdown(f"**Suspended At:** {c.get('suspended_at') or 'N/A'}")

                    if not c["suspended"] and not c["deleted"]:
                        if st.button(f"🚫 Manual Suspend {c['content_id']}", key=f"sus_{c['content_id']}"):
                            db.suspend_content(c['content_id'])
                            db.append_audit("MANUAL_SUSPEND", "admin", {"content_id": c['content_id']})
                            st.rerun()
        else:
            st.info("No content registered yet.")

    with dashboard_tab3:
        st.markdown("#### Creator Registry")
        creators = db.get_all_creators()
        if creators:
            for c in creators:
                icon = "🚫" if c["blocked"] else ("✅" if c["id_verified"] else "⏳")
                with st.expander(f"{icon} {c['name']} | {c['email']} | ID: {c['creator_id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Registered:** {c['registered_at']}")
                        st.markdown(f"**KYC Verified:** {'✅' if c['id_verified'] else '❌'}")
                        st.markdown(f"**Liveness:** {'✅' if c['liveness_passed'] else '❌'}")
                    with col2:
                        st.markdown(f"**Risk Score:** {c['risk_score']:.2f}")
                        st.markdown(f"**Public Key:** {'✅ Generated' if c['public_key_pem'] else '❌ Missing'}")
                        st.markdown(f"**Blocked:** {'🚫 Yes' if c['blocked'] else 'No'}")
        else:
            st.info("No creators registered yet.")

    with dashboard_tab4:
        st.markdown("#### Complaint Cases")
        complaints = db.get_all_complaints()
        if complaints:
            for c in complaints:
                priority_icon = "🔴" if not c["takedown_executed"] else "🟢"
                with st.expander(f"{priority_icon} {c['complaint_id']} | {c['status']} | Content: {c['content_id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Submitted:** {c['submitted_at']}")
                        st.markdown(f"**Reason:** {c['reason']}")
                        st.markdown(f"**Evidence:** {c.get('evidence_url') or 'None provided'}")
                    with col2:
                        st.markdown(f"**Takedown Executed:** {'✅' if c['takedown_executed'] else '❌ Pending'}")
                        st.markdown(f"**Takedown Time:** {c.get('takedown_at') or 'N/A'}")
                        st.markdown(f"**LE Ref:** {c.get('law_enforcement_ref') or 'N/A'}")

                    if not c["takedown_executed"]:
                        if st.button(f"⚡ Force Takedown", key=f"td_{c['complaint_id']}"):
                            db.suspend_content(c["content_id"])
                            db.mark_takedown(c["complaint_id"])
                            db.append_audit("FORCED_TAKEDOWN", "admin", {
                                "complaint_id": c["complaint_id"],
                                "content_id": c["content_id"],
                            })
                            st.rerun()
        else:
            st.info("No complaints filed yet.")

    st.markdown("---")
    st.markdown("#### 🔑 Law Enforcement API Endpoint")
    st.markdown("""
    ```
    POST /api/v1/le/retrieve-creator-identity
    Authorization: Bearer <LE_TOKEN>
    {
        "complaint_id": "CMP-XXXXXXXX",
        "legal_order_ref": "COURT-ORDER-2026-XXXXX",
        "jurisdiction": "IN"
    }
    ```
    Returns: creator identity, digital signature, full audit trail, key pair reference.
    """)
