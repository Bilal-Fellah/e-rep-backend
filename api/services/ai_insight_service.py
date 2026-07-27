import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from api.repositories.ai_insight_repository import find_by_key, upsert
from api.services.openrouter_client import call_llm, get_primary_model_id


service_logger = logging.getLogger("service_errors")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _log_service_error(message: str, error: Exception, context: dict | None = None) -> None:
    payload = {
        "timestamp": _utc_now_iso(),
        "severity": "high",
        "category": "service_error",
        "class_name": "ai_insight_service",
        "method_name": "get_or_generate_insight",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
    }
    service_logger.critical(json.dumps(payload, ensure_ascii=True, default=str))


PROMPTS = {
    "top_brands": (
        "You are a senior social media analyst reviewing brand rankings for a telecom category "
        "(the reader may work at one of these brands or may be a competitor doing market research — "
        "write neutrally, without assuming you're advising any single brand's team). "
        "Analyze the ranking data. Structure your response as:\n"
        "1. Headline: one sentence capturing the single most important takeaway from this ranking.\n"
        "2. What happened: who's leading and by how much, notable gains/losses across brands, with numbers.\n"
        "3. Likely driver: a brief, clearly-labeled hypothesis for what's driving the biggest mover "
        "(e.g. a platform-specific push, a viral post, a lull in activity) — mark it as a hypothesis, "
        "not fact, if you're not certain.\n"
        "4. Platform pattern: which network(s) are contributing most to gains or losses, and for which brand.\n"
        "Order points by importance, not by table order. Use only numbers given, never invent data."
        "Format the response in markdown: use **1. Headline:** style bold labels for each section,"
        " and use '-' for any sub-points within a section."
    ),

    "graph": (
        "You are a senior social media analyst reviewing trend data for a telecom brand "
        "(the reader may work at this brand or may be a competitor doing market research — write "
        "neutrally, without assuming you're advising the brand's own team). "
        "Analyze the trend for this metric. Structure your response as:\n"
        "1. Headline: one sentence capturing the single most important takeaway.\n"
        "2. What happened: the trend shape, spikes/drops, and the most recent 7-day change with numbers.\n"
        "3. Likely driver: a brief, clearly-labeled hypothesis for what caused the biggest movement "
        "(e.g. campaign, platform algorithm shift, seasonal event) — mark it as a hypothesis, not fact, "
        "if you're not certain.\n"
        "4. Competitive read: how this brand's trend compares to others shown, if more than one is present.\n"
        "Order points by importance, not chronological order. Use only numbers given, never invent data."
        "Format the response in markdown: use **1. Headline:** style bold labels for each section,"
        " and use '-' for any sub-points within a section."
    ),

    "sentiment": (
        "You are a senior social media analyst reviewing audience sentiment for a telecom brand "
        "(the reader may work at this brand or may be a competitor doing market research — write "
        "neutrally, without assuming you're advising the brand's own team). "
        "Analyze the sentiment data. Structure your response as:\n"
        "1. Headline: one sentence capturing the single most important takeaway.\n"
        "2. What happened: the overall score, the positive/neutral/negative split, with numbers.\n"
        "3. Notable shift: the day or period with the most unusual change (e.g. a spike in negative "
        "sentiment or an unusually positive day), with numbers, and a brief hypothesis for why — "
        "mark it as a hypothesis, not fact, if you're not certain.\n"
        "4. Trend read: whether sentiment is improving, worsening, or stable over the period, with evidence.\n"
        "Order points by importance, not chronological order. Use only numbers given, never invent data."
        "Format the response in markdown: use **1. Headline:** style bold labels for each section,"
        " and use '-' for any sub-points within a section."
    ),

    "posts_timeline": (
        "You are a senior social media analyst reviewing recent posts for a telecom brand "
        "(the reader may work at this brand or may be a competitor doing market research — write "
        "neutrally, without assuming you're advising the brand's own team). "
        "Analyze the posts. Structure your response as:\n"
        "1. Headline: one sentence capturing the single most important takeaway.\n"
        "2. What happened: the common themes or content types across posts, and which platform is "
        "performing best by engagement, with numbers.\n"
        "3. Likely driver: a brief, clearly-labeled hypothesis for why the top-performing post(s) "
        "outperformed the rest (e.g. content type, timing, platform fit) — mark it as a hypothesis, "
        "not fact, if you're not certain.\n"
        "4. Content pattern: what type of content appears to consistently drive more interactions "
        "across the set, if a pattern is visible.\n"
        "Order points by importance, not post order. Use only numbers/text given, never invent data."
        "Format the response in markdown: use **1. Headline:** style bold labels for each section,"
        " and use '-' for any sub-points within a section."
    ),
}

def _normalize_for_hash(value):
    if isinstance(value, dict):
        return {k: _normalize_for_hash(value[k]) for k in sorted(value.keys())}

    if isinstance(value, list):
        normalized = [_normalize_for_hash(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), default=str),
        )

    return value


def build_cache_key(view_type: str, filters: dict) -> str:
    """
    SHA1 hash of view_type + sorted/normalized filters dict.
    Sort list values before hashing so order doesn't change keys.
    """
    normalized_filters = _normalize_for_hash(filters or {})
    payload = json.dumps(
        {"view_type": view_type, "filters": normalized_filters},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _filter_header(filters: dict) -> str:
    if not filters:
        return ""

    parts = [f"{k}: {v}" for k, v in filters.items()]
    return " | ".join(parts)


def serialize_top_brands(rows: list[dict], filters: dict) -> str:
    """
    Input: list of {rank, brand, total, ig, li, tt, x}
    Output: markdown table + filter header line.
    """

    lines = []
    header = _filter_header(filters)
    if header:
        lines.append(header)
    lines.append("| Rank | Brand | Total | IG | LI | TT | X |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|")

    for row in rows or []:
        lines.append(
            "| {rank} | {brand} | {total} | {ig} | {li} | {tt} | {x} |".format(
                rank=row.get("rank", "-"),
                brand=row.get("brand", "-"),
                total=row.get("total", "-"),
                ig=row.get("ig", "-"),
                li=row.get("li", "-"),
                tt=row.get("tt", "-"),
                x=row.get("x", "-"),
            )
        )

    return "\n".join(lines)


def _extract_series_points(points):
    extracted = []
    for p in points or []:
        if isinstance(p, dict):
            date = p.get("date")
            value = p.get("value")
        else:
            date = p[0] if len(p) > 0 else None
            value = p[1] if len(p) > 1 else None
        extracted.append((date, value))
    return extracted


def serialize_graph(stats: dict, series: dict, filters: dict) -> str:
    """
    Input: stats = {brand: {last7, prev7, change}}, series = {brand: [(date, value), ...]}
    Output: metric/period header + one stat line per brand + downsampled series lines.
    """

    lines = []
    header = _filter_header(filters)
    if header:
        lines.append(header)

    if stats:
        lines.append("Brand stats:")
        for brand, row in stats.items():
            lines.append(
                f"- {brand}: last7={row.get('last7')}, prev7={row.get('prev7')}, change={row.get('change')}"
            )

    if series:
        lines.append("Series:")
        for brand, points in series.items():
            normalized_points = _extract_series_points(points)
            step = max(1, len(normalized_points) // 20) if normalized_points else 1
            downsampled = normalized_points[::step]
            formatted = ", ".join(f"{d}:{v}" for d, v in downsampled)
            lines.append(f"- {brand} ({len(downsampled)} pts): {formatted}")

    return "\n".join(lines)


def serialize_sentiment(data: dict, filters: dict) -> str:
    """
    Input: {score, pos_pct, neu_pct, neg_pct, daily: [{date, pos, neu, neg}]}
    Output: summary header lines + one line per day.
    """
    data = data or {}
    lines = []

    header = _filter_header(filters)
    if header:
        lines.append(header)

    lines.append(f"Score: {data.get('score')}")
    lines.append(
        f"Split: positive={data.get('pos_pct')}%, neutral={data.get('neu_pct')}%, negative={data.get('neg_pct')}%"
    )

    lines.append("Daily:")
    for day in data.get("daily", []) or []:
        lines.append(
            f"- {day.get('date')}: pos={day.get('pos')}, neu={day.get('neu')}, neg={day.get('neg')}"
        )

    return "\n".join(lines)


def serialize_posts(posts: list[dict], filters: dict) -> str:
    """
    Input: list of {platform, likes, comments, interactions, caption}
    Top 15 by interactions, captions truncated to 200 chars.
    """
    rows = sorted(posts or [], key=lambda p: p.get("interactions") or 0, reverse=True)[:15]

    lines = []
    header = _filter_header(filters)
    if header:
        lines.append(header)

    for idx, post in enumerate(rows, start=1):
        caption = (post.get("caption") or "")[:200]
        lines.append(
            f"Post {idx} — {post.get('platform', '-')}, likes={post.get('likes', 0)}, comments={post.get('comments', 0)}, interactions={post.get('interactions', 0)}"
        )
        lines.append(f"Caption: {caption}")
        lines.append("")

    return "\n".join(lines).strip()


SERIALIZERS = {
    "top_brands": serialize_top_brands,
    "graph": serialize_graph,
    "sentiment": serialize_sentiment,
    "posts_timeline": serialize_posts,
}


def get_or_generate_insight(view_type: str, filters: dict, raw_data) -> dict:
    """
    Return cached summary when valid; otherwise generate with LLM and cache.
    """
    cache_key = build_cache_key(view_type, filters or {})
    row = find_by_key(cache_key)

    now = datetime.utcnow()
    if row and row.expires_at > now:
        return {"summary": row.summary_text, "cached": True}

    serializer = SERIALIZERS.get(view_type)
    if serializer is None:
        raise ValueError(f"Unknown view_type: {view_type}")

    prompt = PROMPTS.get(view_type)
    if prompt is None:
        raise ValueError(f"Missing prompt for view_type: {view_type}")

    if view_type == "graph":
        graph_data = raw_data if isinstance(raw_data, dict) else {}
        data_block = serializer(
            graph_data.get("stats", {}),
            graph_data.get("series", {}),
            filters or {},
        )
    elif view_type == "top_brands":
        rows = raw_data.get("rows") if isinstance(raw_data, dict) else raw_data
        if rows is None and isinstance(raw_data, dict):
            rows = raw_data.get("data", [])
        data_block = serializer(rows or [], filters or {})
    elif view_type == "posts_timeline":
        posts = raw_data.get("posts") if isinstance(raw_data, dict) else raw_data
        if posts is None and isinstance(raw_data, dict):
            posts = raw_data.get("data", [])
        data_block = serializer(posts or [], filters or {})
    else:
        sentiment_data = raw_data if isinstance(raw_data, dict) else {}
        data_block = serializer(sentiment_data, filters or {})

    try:
        summary = call_llm(prompt, data_block)
    except Exception as error:
        _log_service_error(
            "LLM call failed",
            error,
            context={
                "view_type": view_type,
                "cache_key": cache_key,
                "has_filters": bool(filters),
                "data_block_length": len(data_block or ""),
                "model": get_primary_model_id() or "unconfigured",
            },
        )
        return {"error": "llm_failed"}

    expires_at = now + timedelta(hours=24)
    upsert(
        cache_key=cache_key,
        view_type=view_type,
        summary_text=summary,
        model_used=get_primary_model_id() or "unconfigured",
        expires_at=expires_at,
    )

    return {"summary": summary, "cached": False}
