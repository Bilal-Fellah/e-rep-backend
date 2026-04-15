# Shared helper functions for page uuid.
import uuid


def normalize_page_link(link: str) -> str:
    return link.split("?")[0].rstrip("/").lower()


def create_page_uuid(link: str) -> uuid.UUID:
    normalized_url = normalize_page_link(link)
    return uuid.uuid5(uuid.NAMESPACE_URL, normalized_url)
