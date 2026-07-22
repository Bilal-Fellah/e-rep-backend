import hashlib
import json
from datetime import datetime, timedelta

from api.repositories.ai_insight_repository import find_by_key, upsert
from api.services.openrouter_client import OPENROUTER_MODEL_ID, call_llm


PROMPTS = {
    "top_brands": "You are a social media analyst. Write 4-6 bullet points: leader and why, notable gains/losses, platform patterns, one actionable insight. Use only numbers given, never invent data.",
    "graph": "Summarize the trend: shape (spikes/drops/plateaus), brand comparison if multiple brands are present, and the most recent 7-day change with numbers. Use only numbers given.",
    "sentiment": "Summarize sentiment: overall score and split, any day with an unusual shift in negative sentiment, overall trend direction. Use only numbers given.",
    "posts_timeline": "Identify patterns across posts: common themes, best-performing platform by engagement, what type of content drives the most interactions.",
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
    except Exception:
        return {"error": "llm_failed"}

    expires_at = now + timedelta(hours=24)
    upsert(
        cache_key=cache_key,
        view_type=view_type,
        summary_text=summary,
        model_used=OPENROUTER_MODEL_ID,
        expires_at=expires_at,
    )

    return {"summary": summary, "cached": False}
