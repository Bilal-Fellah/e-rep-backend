# Shared helper functions for data keys.
platform_metrics = {
    "instagram": {
        "id_key": "id",
        "date": "datetime",
        "weight": 1/5,
        "metrics": [
            {"name": "comments", "score": 1},
            {"name": "likes", "score": 1},
        ]
    },
    "linkedin": {
        "id_key": "post_id",
        "date": "date",
        "weight": 1/5,
        "metrics": [
            {"name": "comments_count", "score": 1},
            {"name": "likes_count", "score": 1},
        ]
    },
    "x": {
        "id_key": "post_id",
        "date": "date_posted",
        "weight": 1/5,
        "metrics": [
            {"name": "reposts", "score": 1},
            {"name": "likes", "score": 1},
            # {"name": "replies", "score": 1},
        ]
    },
    "tiktok": {
        "id_key": "video_id",
        "date": "create_date",
        "weight": 1/5,
        "metrics": [
            {"name": "commentcount", "score": 1},
            {"name": "share_count", "score": 1},
            # {"name": "favorites_count", "score": 1},
            # {"name": "playcount", "score": 1},
        ]
    }, 
    "facebook":{
        "id_key": "post_id",
        "date": "date_posted",
        "weight": 1/5,
        "metrics": [
            {"name": "num_comments", "score": 1},
            {"name": "likes", "score": 1},
            # {"name": "num_shares", "score": 1},
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

