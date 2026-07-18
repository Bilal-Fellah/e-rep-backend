# Business logic for comment-sentiment aggregation.
#
# The inference model stores a per-comment integer `label` (0-4), but the product
# surfaces a **3-class** scale. The 5 raw labels collapse into 3 buckets:
#   0 Very Negative, 1 Negative  -> negative
#   2 Neutral                    -> neutral
#   3 Positive,      4 Very Positive -> positive
# This service turns the raw per-label counts produced by CommentRepository into
# stable, frontend-friendly shapes keyed by those buckets (counts, percentages,
# a single sentiment score, positive share, trend series, and example comments).
from api.repositories.comment_repository import CommentRepository

# Raw label (0-4) -> bucket.
LABEL_TO_BUCKET = {0: "negative", 1: "negative", 2: "neutral", 3: "positive", 4: "positive"}
# Buckets in display order.
BUCKETS = ("negative", "neutral", "positive")
# Numeric value per bucket, used to compute the [-1, 1] sentiment score.
BUCKET_SCORE = {"negative": -1, "neutral": 0, "positive": 1}
# Raw labels that make up each bucket (for example-comment queries).
BUCKET_LABELS = {"negative": [0, 1], "neutral": [2], "positive": [3, 4]}

# Ranking is volume-aware so a brand with a couple of comments can't top a brand
# with thousands:
#   - entities below RANKING_MIN_COMMENTS are excluded (not enough signal);
#   - rows are ordered by `ranking_score`, the raw score shrunk toward neutral
#     for small samples: score * total / (total + RANKING_SHRINKAGE_K).
RANKING_MIN_COMMENTS = 5
RANKING_SHRINKAGE_K = 20


def _num(value, default=0):
    """Coerce SQL aggregate results (Decimal/None) to plain numbers."""
    if value is None:
        return default
    return float(value)


def _comment_to_dict(comment) -> dict:
    """Minimal comment shape for example lists (no internal/session fields)."""
    return {
        "id": comment.id,
        "text": comment.text,
        "author_username": comment.author_username,
        "confidence": comment.confidence,
        "likes_count": comment.likes_count,
        "comment_timestamp": (
            comment.comment_timestamp.isoformat()
            if comment.comment_timestamp
            else None
        ),
    }


def _shape_counts(rows: list[tuple]) -> dict:
    """
    Turn [(raw_label, count, avg_confidence)] into a stable summary dict bucketed
    into negative/neutral/positive: per-bucket counts, total, per-bucket
    percentages, a sentiment score in [-1, 1], and the positive share. Empty
    input yields total=0 (not an error).
    """
    counts = {b: 0 for b in BUCKETS}
    conf_weighted = {b: 0.0 for b in BUCKETS}
    conf_n = {b: 0 for b in BUCKETS}

    for label, count, avg_conf in rows:
        bucket = LABEL_TO_BUCKET.get(label)
        if bucket is None:
            continue
        c = int(count or 0)
        counts[bucket] += c
        # Weight per-label average confidence by its count to combine labels.
        if avg_conf is not None and c:
            conf_weighted[bucket] += _num(avg_conf) * c
            conf_n[bucket] += c

    total = sum(counts.values())
    percentages = {
        b: (round(counts[b] / total * 100, 1) if total else 0.0) for b in BUCKETS
    }

    if total:
        score = round(
            sum(BUCKET_SCORE[b] * counts[b] for b in BUCKETS) / total, 4
        )
        positive_share = percentages["positive"]
    else:
        score = 0.0
        positive_share = 0.0

    avg_confidence = {
        b: (round(conf_weighted[b] / conf_n[b], 4) if conf_n[b] else None)
        for b in BUCKETS
    }

    return {
        "total": total,
        "counts": counts,
        "percentages": percentages,
        "avg_confidence": avg_confidence,
        "score": score,
        "positive_share": positive_share,
    }


def _shape_trend(rows: list[tuple]) -> list[dict]:
    """
    Turn [(day, raw_label, count)] into an ordered list of per-day objects:
    [{date, negative, neutral, positive, total}]. Days are already ordered by
    the query.
    """
    days: dict[str, dict] = {}
    order: list[str] = []
    for day, label, count in rows:
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        if key not in days:
            days[key] = {"date": key, **{b: 0 for b in BUCKETS}, "total": 0}
            order.append(key)
        bucket = LABEL_TO_BUCKET.get(label)
        if bucket:
            c = int(count or 0)
            days[key][bucket] += c
            days[key]["total"] += c
    return [days[key] for key in order]


class CommentSentimentService:
    """Aggregates and shapes comment sentiment for entities, posts and ranking."""

    @staticmethod
    def get_entity_sentiment(
        entity_id: int, start_date=None, end_date=None, example_limit: int = 3
    ) -> dict:
        """Full sentiment payload for one brand: summary + trend + examples."""
        summary = _shape_counts(
            CommentRepository.get_sentiment_counts_by_entity(
                entity_id, start_date, end_date
            )
        )
        summary["entity_id"] = entity_id
        summary["trend"] = _shape_trend(
            CommentRepository.get_sentiment_trend_by_entity(
                entity_id, start_date, end_date
            )
        )

        examples = {}
        for bucket in BUCKETS:
            if summary["counts"][bucket] == 0:
                examples[bucket] = []
                continue
            comments = CommentRepository.get_example_comments_by_entity(
                entity_id, BUCKET_LABELS[bucket], example_limit, start_date, end_date
            )
            examples[bucket] = [_comment_to_dict(c) for c in comments]
        summary["examples"] = examples
        return summary

    @staticmethod
    def get_post_sentiment(
        page_id: str, platform: str, post_id: str, example_limit: int = 3
    ) -> dict:
        """Sentiment payload for a single post: summary + examples."""
        summary = _shape_counts(
            CommentRepository.get_sentiment_counts_by_post(page_id, platform, post_id)
        )
        examples = {}
        for bucket in BUCKETS:
            if summary["counts"][bucket] == 0:
                examples[bucket] = []
                continue
            comments = CommentRepository.get_example_comments_by_post(
                page_id, platform, post_id, BUCKET_LABELS[bucket], example_limit
            )
            examples[bucket] = [_comment_to_dict(c) for c in comments]
        summary["examples"] = examples
        return summary

    @staticmethod
    def get_ranking(start_date=None, end_date=None) -> list[dict]:
        """
        One row per entity ranked by a volume-adjusted sentiment score (desc).
        Entities below RANKING_MIN_COMMENTS are excluded; each row carries the
        same summary shape as get_entity_sentiment (minus trend/examples) plus a
        `ranking_score` (the value actually used for ordering).
        """
        rows = CommentRepository.get_sentiment_ranking(start_date, end_date)
        if not rows:
            return []

        # Group (entity_id, name, type, label, count) rows by entity.
        entities: dict[int, dict] = {}
        for entity_id, name, entity_type, label, count in rows:
            entity = entities.setdefault(
                entity_id,
                {"entity_id": entity_id, "entity_name": name, "type": entity_type,
                 "_rows": []},
            )
            entity["_rows"].append((label, count, None))

        ranking = []
        for entity in entities.values():
            summary = _shape_counts(entity.pop("_rows"))
            summary.pop("avg_confidence", None)  # not meaningful in the ranking
            entity.update(summary)
            # Skip statistically insignificant brands.
            if entity["total"] < RANKING_MIN_COMMENTS:
                continue
            # Shrink the raw score toward neutral (0) for small samples so a
            # handful of glowing comments can't outrank a large, steady audience.
            entity["ranking_score"] = round(
                entity["score"] * entity["total"]
                / (entity["total"] + RANKING_SHRINKAGE_K),
                4,
            )
            ranking.append(entity)

        ranking.sort(key=lambda r: (r["ranking_score"], r["total"]), reverse=True)
        for idx, row in enumerate(ranking, start=1):
            row["rank"] = idx
        return ranking
