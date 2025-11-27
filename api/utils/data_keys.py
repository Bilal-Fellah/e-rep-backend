platform_metrics = {
    "instagram": {
        "id_key": "id",
        "date": "datetime",
        "weight": 1/4,
        "metrics": [
            {"name": "comments", "score": 0.7},
            {"name": "likes", "score": 0.3},
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
            {"name": "favorites_count", "score": 0.2},
            {"name": "playcount", "score": 0.1},
        ]
    }
}
