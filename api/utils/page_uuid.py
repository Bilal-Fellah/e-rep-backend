# Shared helper functions for page uuid.
import re
import uuid

# Single source of truth for the social platforms a page may belong to. Mirrors
# the Page model's CHECK constraint; both page-creation paths validate against
# it so an invalid platform is rejected with a clear error before the DB.
ALLOWED_PAGE_PLATFORMS = {
    "facebook",
    "instagram",
    "x",
    "tiktok",
    "linkedin",
    "youtube",
}


def page_platform_error(platform: str) -> str | None:
    """Single source of truth for page-platform validation. Given an
    already-normalized (lowercased) platform, return a client-safe error
    message if it isn't supported, else None. Both page-creation paths
    (PageService.create_page and AuthService.create_entity_pages) call this so
    the rule and its message live in one place."""
    if platform not in ALLOWED_PAGE_PLATFORMS:
        return (
            f"Invalid page platform '{platform}'. "
            f"Allowed platforms are: {sorted(ALLOWED_PAGE_PLATFORMS)}"
        )
    return None


def normalize_page_link(link: str) -> str:
    if not isinstance(link, str):
        return ""

    cleaned = "".join(link.split())
    if not cleaned:
        return ""

    cleaned = cleaned.lower()
    cleaned = re.sub(r"^(https?://)?(web\.|m\.)", r"\1www.", cleaned)
    if "profile.php" not in cleaned:
        cleaned = cleaned.split("?", 1)[0]
    cleaned = cleaned.rstrip("/")
    return cleaned


def create_page_uuid(link: str) -> uuid.UUID:
    normalized_url = normalize_page_link(link)
    return uuid.uuid5(uuid.NAMESPACE_URL, normalized_url)
