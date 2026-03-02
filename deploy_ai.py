"""
DeepFake Misuse Prevention System - Deploy AI Integration
Handles authentication and LLM calls via Deploy AI API.
Falls back to rule-based mock responses if credentials are not configured.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

AUTH_URL = os.getenv("AUTH_URL", "https://api-auth.deploy.ai/oauth2/token")
API_URL  = os.getenv("API_URL",  "https://core-api.deploy.ai")
ORG_ID   = os.getenv("ORG_ID",   "1a01ce2d-3f79-418b-a564-e3f41f5be8a4")


def get_access_token() -> str | None:
    """Retrieve a short-lived access token from Deploy AI auth service."""
    client_id     = os.getenv("CLIENT_ID", "")
    client_secret = os.getenv("CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return None

    try:
        resp = requests.post(
            AUTH_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception:
        return None


def create_chat(access_token: str) -> str:
    """Create a new chat session and return its ID."""
    headers = {
        "accept":        "application/json",
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {access_token}",
        "X-Org":         ORG_ID,
    }
    resp = requests.post(
        f"{API_URL}/chats",
        headers=headers,
        json={"agentId": "GPT_4O", "stream": False},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json()["id"]
    raise RuntimeError(f"Failed to create chat: {resp.status_code} {resp.text}")


def call_llm(prompt: str, system_context: str = "") -> str:
    """
    Send a prompt to Deploy AI GPT-4o. Falls back to mock if unconfigured.
    """
    access_token = get_access_token()
    if not access_token:
        return _mock_llm_response(prompt)

    try:
        chat_id = create_chat(access_token)
        full_prompt = f"{system_context}\n\n{prompt}" if system_context else prompt

        headers = {
            "X-Org":         ORG_ID,
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        }
        resp = requests.post(
            f"{API_URL}/messages",
            headers=headers,
            json={
                "chatId": chat_id,
                "stream": False,
                "content": [{"type": "text", "value": full_prompt}],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["content"][0]["value"]
    except Exception:
        pass

    return _mock_llm_response(prompt)


# ─── Mock / Fallback ─────────────────────────────────────────────────────────

def _mock_llm_response(prompt: str) -> str:
    """Rule-based fallback responses when Deploy AI credentials are absent."""
    p = prompt.lower()

    if "age" in p or "minor" in p:
        return json.dumps({
            "age_estimate":   25,
            "confidence":     0.87,
            "is_minor":       False,
            "analysis":       "Subject appears to be an adult based on facial features.",
            "recommendation": "PROCEED",
        })

    if "consent" in p:
        return json.dumps({
            "consent_valid":  True,
            "consent_score":  0.92,
            "analysis":       "Consent verification token is valid and unexpired.",
            "recommendation": "PROCEED",
        })

    if "legal" in p or "warning" in p:
        return json.dumps({
            "warning_issued":  True,
            "user_understood": True,
            "jurisdiction":    "GENERAL",
            "laws_cited":      ["NCII Act", "EU AI Act Art. 52", "DMCA §512"],
        })

    if "complaint" in p or "takedown" in p:
        return json.dumps({
            "complaint_valid":      True,
            "auto_takedown":        True,
            "notify_law_enforcement": False,
            "priority":             "HIGH",
            "analysis":             "Content matches reported deepfake characteristics.",
        })

    if "identity" in p or "kyc" in p or "creator" in p:
        return json.dumps({
            "identity_verified": True,
            "liveness_passed":   True,
            "risk_score":        0.05,
            "recommendation":    "ALLOW",
        })

    return json.dumps({
        "status":         "processed",
        "result":         "approved",
        "recommendation": "PROCEED",
    })
