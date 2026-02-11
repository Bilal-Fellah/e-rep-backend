platform_metrics = {
    "instagram": {
        "id_key": "id",
        "date": "datetime",
        "weight": 1/4,
        "metrics": [
            {"name": "comments", "score": 0.6},
            {"name": "likes", "score": 0.4},
        ]
    },
    "linkedin": {
        "id_key": "post_id",
        "date": "date",
        "weight": 1/4,
        "metrics": [
            {"name": "comments_count", "score": 0.6},
            {"name": "likes_count", "score": 0.4},
        ]
    },
    "x": {
        "id_key": "post_id",
        "date": "date_posted",
        "weight": 1/4,
        "metrics": [
            {"name": "reposts", "score": 0.5},
            {"name": "likes", "score": 0.25},
            {"name": "replies", "score": 0.25},
        ]
    },
    "tiktok": {
        "id_key": "video_id",
        "date": "create_date",
        "weight": 1/4,
        "metrics": [
            {"name": "commentcount", "score": 0.4},
            {"name": "share_count", "score": 0.3},
            {"name": "favorites_count", "score": 0.3},
            # {"name": "playcount", "score": 0.1},
        ]
    }
}

def compute_score(post, metrics):
    score = 0
    post_gains={}

    for m in metrics:
        name = m["name"]
        weight = m.get("weight", 1.0)
        value = post.get(name)
        score += weight * float(value if value is not None else 0)
        post_gains[name] = value
    return score, post_gains


def summarize_days(data, platform_metrics):
    summary = []


    for day_block in data:
        day = day_block["day"]
        posts = day_block["posts"]

        day_total_score = 0
        platform_scores = {}
        day_gains = {}

        for post in posts:
            platform = post.get("platform")
            metrics = platform_metrics.get(platform, {}).get("metrics", [])

            # Compute score of this post
            post_score, post_gains = compute_score(post, metrics)

            # Add to total
            day_total_score += post_score

            # Add to platform-specific total
            if platform not in platform_scores:
                platform_scores[platform] = 0
            platform_scores[platform] += post_score

            for metric, value in post_gains.items():
                if platform not in day_gains:
                    day_gains[platform] = {}
                if metric not in day_gains[platform]:
                    day_gains[platform][metric] = 0
                day_gains[platform][metric] += value if value else 0

        summary.append({
            "date": day,
            "total_score": day_total_score,
            "platform_scores": platform_scores,
            "day_gains": day_gains
        })

    return summary
