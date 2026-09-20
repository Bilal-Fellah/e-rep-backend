import os
from typing import Any

import requests

from api.utils.logging_utils import instrument_service_class


RESEND_SEND_EMAIL_URL = "https://api.resend.com/emails"


@instrument_service_class
class EmailService:
    @staticmethod
    def _normalize_recipients(value) -> list[str]:
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            raise ValueError("'to' must be a string email or a list of emails")

        normalized = []
        for item in items:
            if not isinstance(item, str):
                raise ValueError("Every recipient in 'to' must be a string")
            recipient = item.strip()
            if not recipient:
                raise ValueError("Recipient emails cannot be empty")
            normalized.append(recipient)

        if len(normalized) < 1:
            raise ValueError("At least one recipient email is required")

        return normalized

    @staticmethod
    def _normalize_reply_to(value) -> list[str] | None:
        if value is None:
            return None

        if isinstance(value, str):
            item = value.strip()
            if not item:
                raise ValueError("'reply_to' cannot be empty")
            return [item]

        if isinstance(value, list):
            normalized = []
            for item in value:
                if not isinstance(item, str):
                    raise ValueError("Every 'reply_to' entry must be a string")
                email = item.strip()
                if not email:
                    raise ValueError("'reply_to' entries cannot be empty")
                normalized.append(email)
            if len(normalized) < 1:
                raise ValueError("'reply_to' cannot be an empty list")
            return normalized

        raise ValueError("'reply_to' must be a string email or a list of emails")

    @staticmethod
    def _resolve_from_address(from_email: str | None, from_name: str | None) -> str:
        sender_email = (
            (from_email or "").strip()
            or (os.getenv("MAIL_FROM_EMAIL") or "").strip()
            or (os.getenv("RESEND_FROM_EMAIL") or "").strip()
        )
        if not sender_email:
            raise RuntimeError(
                "No sender email configured. Set MAIL_FROM_EMAIL (or RESEND_FROM_EMAIL) or pass from_email."
            )

        sender_name = (
            (from_name or "").strip()
            or (os.getenv("MAIL_FROM_NAME") or "").strip()
        )

        return f"{sender_name} <{sender_email}>" if sender_name else sender_email

    @staticmethod
    def send_email(
        *,
        to,
        subject: str | None,
        html: str | None = None,
        text: str | None = None,
        reply_to=None,
        from_email: str | None = None,
        from_name: str | None = None,
        tags: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        api_key = (os.getenv("RESEND_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("RESEND_API_KEY is not configured")

        recipients = EmailService._normalize_recipients(to)

        clean_subject = (subject or "").strip()
        if not clean_subject:
            raise ValueError("'subject' is required")

        clean_html = html.strip() if isinstance(html, str) else None
        clean_text = text.strip() if isinstance(text, str) else None
        if not clean_html and not clean_text:
            raise ValueError("At least one of 'html' or 'text' is required")

        resolved_reply_to = EmailService._normalize_reply_to(reply_to)
        if resolved_reply_to is None:
            default_reply_to = (os.getenv("MAIL_REPLY_TO") or "").strip()
            if default_reply_to:
                resolved_reply_to = [default_reply_to]

        payload: dict[str, Any] = {
            "from": EmailService._resolve_from_address(from_email, from_name),
            "to": recipients,
            "subject": clean_subject,
        }

        if clean_html:
            payload["html"] = clean_html
        if clean_text:
            payload["text"] = clean_text
        if resolved_reply_to:
            payload["reply_to"] = resolved_reply_to
        if tags is not None:
            payload["tags"] = tags

        response = requests.post(
            RESEND_SEND_EMAIL_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        body = response.json() if response.content else {}

        return {
            "id": body.get("id"),
            "provider": "resend",
            "status_code": response.status_code,
            "response": body,
        }
