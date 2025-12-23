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

GET /api/data/get_entity_interaction_stats
Retrieve the progress of interaction statistics for a specific entity.

Parameters:
entity_id (required): Identifier of the entity.
start_date (optional, ISO8601): Filter posts created on or after this date.


Response:
A list of days, in which day there are posts with total interactions 
and the gained interactions on that day.

Example request body:
  /api/data/get_entity_interaction_stats?entity_id=94


Example response:

---
{
  "data": [
    {
      "day": "2025-08-22",
      "posts": []
    },
    {
      "day": "2025-08-23",
      "posts": [
        {
          "comments_count": 6,
          "create_time": "2025-08-22T19:59:05.796Z",
          "gained_comments_count": 5,
          "gained_likes_count": 9,
          "likes_count": 26,
          "platform": "linkedin",
          "post_id": "7364704661401935873"
        },
        {
          "comments_count": 2,
          "create_time": "2025-08-21T19:59:05.799Z",
          "gained_comments_count": 1,
          "gained_likes_count": 5,
          "likes_count": 27,
          "platform": "linkedin",
          "post_id": "7364340544061227008"
        },
        {
          "comments_count": 9,
          "create_time": "2025-08-18T19:59:05.801Z",
          "gained_comments_count": 0,
          "gained_likes_count": 1,
          "likes_count": 29,
          "platform": "linkedin",
          "post_id": "7363253349141340161"
        }
      ]
    }
  ],
  "success": true
}
