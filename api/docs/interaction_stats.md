**Interaction stats -- Routes documentation**

GET /api/data/get_page_interaction_stats
Returns interaction statistics for a specific page.

Parameters:
page_id (required): Unique identifier of the page.
start_date (optional, ISO8601): Filter posts created on or after this date.

Response:
A list of posts with their engagement metrics and computed score.
Each post includes:
post_id
platform
create_time
raw interaction metrics depending on the platform
computed score

Example response:
{
"success": true,
"data": [
{
"comments_count": 1,
"likes_count": 132,
"platform": "linkedin",
"post_id": "7387618805675610113",
"create_time": "2025-10-26T19:56:45.945Z",
"score": 53.4
}
]
}

---

GET /api/data/get_entity_interaction_stats
Returns aggregated interaction statistics for all pages belonging to an entity.

Parameters:
entity_id (required): Identifier of the entity.
start_date (optional, ISO8601): Filter posts created on or after this date.

Response:
A list of posts aggregated across all pages of the entity.
Each item contains:
post_id
platform
create_time
raw interaction metrics
computed score

Example response:
{
"success": true,
"data": [
{
"comments": 15,
"likes": 143,
"platform": "instagram",
"post_id": "3770189665996505307",
"create_time": "2025-11-20T18:01:12.000Z",
"score": 53.4
}
]
}

---

POST /api/data/get_competitors_interaction_stats
Returns interaction statistics for one or multiple competitor entities.

Body:
entity_ids (required): List of entity IDs to compare.
start_date (optional, ISO8601): Filter posts created on or after this date.

Response:
A list of posts for each competitor entity.
Each item includes:
post_id
platform
create_time
interaction metrics
computed score

Example request body:
{
"entity_ids": [94],
"start_date": "2025-11-27"
}

Example response:
{
"success": true,
"data": [
{
      "comments_count": 1,
      "create_time": "2025-11-27T09:02:46.232Z",
      "entity_id": 94,
      "likes_count": 54,
      "page_id": "89d53a4f-e978-5b46-8870-e7b70deee521",
      "platform": "linkedin",
      "post_id": "7399492135802277888",
      "score": 22.200000000000003
    },
    ]
}

---
