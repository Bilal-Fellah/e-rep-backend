# Shared helper functions for page uuid.
import re
import uuid


def normalize_page_link(link: str) -> str:
    if not isinstance(link, str):
        return ""

    cleaned = "".join(link.split())
    if not cleaned:
        return ""

    cleaned = cleaned.lower()
    cleaned = re.sub(r"^(https?://)?(web\.|m\.)", r"\1www.", cleaned)
    cleaned = cleaned.split("?", 1)[0]
    cleaned = cleaned.rstrip("/")
    return cleaned


def create_page_uuid(link: str) -> uuid.UUID:
    normalized_url = normalize_page_link(link)
    return uuid.uuid5(uuid.NAMESPACE_URL, normalized_url)
