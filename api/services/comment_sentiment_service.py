# Business logic for comment-sentiment aggregation.
#
# Sentiment is stored per comment as an integer `label` (0-4) + `confidence`.
# The 5-point scale is (by product convention, NOT encoded in the DB):
#   0 = Very Negative, 1 = Negative, 2 = Neutral, 3 = Positive, 4 = Very Positive
# This service turns the raw per-label counts produced by CommentRepository into
# stable, frontend-friendly shapes (percentages, a single sentiment score,
# positive share, trend series, and example comments).
from api.repositories.comment_repository import CommentRepository

# Labels considered "positive" for the positive-share metric.
POSITIVE_LABELS = (3, 4)
LABELS = range(5)

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
    Turn [(label, count, avg_confidence)] into a stable summary dict:
    per-label counts, total, per-label percentages, a sentiment score in
    [-1, 1], and the positive share. Empty input yields total=0 (not an error).
    """
    counts = {label: 0 for label in LABELS}
    confidence = {label: None for label in LABELS}

    for label, count, avg_conf in rows:
        if label is None or label not in counts:
            continue
        counts[label] = int(count or 0)
        confidence[label] = round(_num(avg_conf), 4) if avg_conf is not None else None

    total = sum(counts.values())
    percentages = {
        label: (round(counts[label] / total * 100, 1) if total else 0.0)
        for label in LABELS
    }

    if total:
        weighted = sum(label * counts[label] for label in LABELS)
        avg_label = weighted / total  # 0..4
        score = round((avg_label - 2) / 2, 4)  # map to [-1, 1]
        positive_share = round(
            sum(counts[label] for label in POSITIVE_LABELS) / total * 100, 1
        )
    else:
        score = 0.0
        positive_share = 0.0

    return {
        "total": total,
        "counts": {f"label_{label}": counts[label] for label in LABELS},
        "percentages": {f"label_{label}": percentages[label] for label in LABELS},
        "avg_confidence": {f"label_{label}": confidence[label] for label in LABELS},
        "score": score,
        "positive_share": positive_share,
    }


def _shape_trend(rows: list[tuple]) -> list[dict]:
    """
    Turn [(day, label, count)] into an ordered list of per-day objects:
    [{date, label_0..label_4, total}]. Days are already ordered by the query.
    """
    days: dict[str, dict] = {}
    order: list[str] = []
    for day, label, count in rows:
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        if key not in days:
            days[key] = {
                "date": key,
                **{f"label_{label_i}": 0 for label_i in LABELS},
                "total": 0,
            }
            order.append(key)
        if label in LABELS:
            days[key][f"label_{label}"] = int(count or 0)
            days[key]["total"] += int(count or 0)
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
        for label in LABELS:
            if summary["counts"][f"label_{label}"] == 0:
                examples[f"label_{label}"] = []
                continue
            comments = CommentRepository.get_example_comments_by_entity(
                entity_id, label, example_limit, start_date, end_date
            )
            examples[f"label_{label}"] = [_comment_to_dict(c) for c in comments]
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
        for label in LABELS:
            if summary["counts"][f"label_{label}"] == 0:
                examples[f"label_{label}"] = []
                continue
            comments = CommentRepository.get_example_comments_by_post(
                page_id, platform, post_id, label, example_limit
            )
            examples[f"label_{label}"] = [_comment_to_dict(c) for c in comments]
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
