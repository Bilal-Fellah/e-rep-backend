# Pages History Monitoring Routes Documentation

All routes in this document are prefixed with `/api/data`.

These endpoints provide clean monitoring, filtering, and detail views for the `pages_history` database table for Web UIs.

Authentication is required (`admin`, `subscribed`, or `registered` role).

---

## **GET /api/data/pages_history** or **/api/data/get_pages_history**

Fetch paginated `pages_history` records with rich filtering capabilities.

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `start_date` | string | No | ISO date or timestamp (e.g. `2026-01-01`). Filters `recorded_at >= start_date`. |
| `end_date` | string | No | ISO date or timestamp (e.g. `2026-02-01`). Filters `recorded_at <= end_date`. |
| `brand_id` / `entity_id` | integer | No | Filter by specific entity / brand ID. |
| `brand` / `brand_name` | string | No | Filter by brand name (partial case-insensitive match). |
| `platform` | string | No | Filter by platform (`facebook`, `instagram`, `x`, `tiktok`, `linkedin`, `youtube`). |
| `page_id` | string (UUID) | No | Filter by specific page UUID. |
| `search` | string | No | Search keyword across page name, brand name, and page link. |
| `page` | integer | No | Page number (default: `1`). |
| `per_page` | integer | No | Number of records per page (default: `20`, max: `100`). |
| `sort_by` | string | No | Column to sort by: `recorded_at` or `id` (default: `recorded_at`). |
| `sort_order` | string | No | Sort direction: `desc` or `asc` (default: `desc`). |
| `include_data` | boolean | No | Set to `false` to exclude full JSON `data` payload for lightweight table rows (default: `true`). |

### Example Request

```
GET /api/data/pages_history?platform=instagram&brand_id=5&page=1&per_page=20&include_data=true
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 1452,
        "recorded_at": "2026-08-09T04:30:00+00:00",
        "page_id": "3f5d7c6a-8b10-54c3-a2b5-1c77d33f9e31",
        "page_name": "Nike Official",
        "page_link": "https://instagram.com/nike",
        "platform": "instagram",
        "brand_id": 5,
        "brand_name": "Nike",
        "data": {
          "followers": 305000000,
          "biography": "Just Do It.",
          "posts": [...]
        }
      }
    ],
    "total": 120,
    "page": 1,
    "per_page": 20,
    "total_pages": 6,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## **GET /api/data/pages_history/<id>** or **/api/data/get_pages_history_by_id**

Get a single `pages_history` record by ID with joined page and brand metadata.

### Query Parameters (when using `/get_pages_history_by_id`)

- `id` (integer, required)

### Example Request

```
GET /api/data/pages_history/1452
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "id": 1452,
    "recorded_at": "2026-08-09T04:30:00+00:00",
    "page_id": "3f5d7c6a-8b10-54c3-a2b5-1c77d33f9e31",
    "page_name": "Nike Official",
    "page_link": "https://instagram.com/nike",
    "platform": "instagram",
    "brand_id": 5,
    "brand_name": "Nike",
    "data": {
      "followers": 305000000,
      "biography": "Just Do It."
    }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "No pages_history record found with id 1452." }
```

---

## **GET /api/data/pages_history/options** or **/api/data/get_pages_history_options**

Get available filter options (distinct platforms, monitored brands, min/max recorded dates) for UI filter controls.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "platforms": ["facebook", "instagram", "linkedin", "tiktok", "x", "youtube"],
    "brands": [
      { "id": 5, "name": "Nike" },
      { "id": 12, "name": "Adidas" }
    ],
    "date_range": {
      "min_date": "2025-01-01T00:00:00+00:00",
      "max_date": "2026-08-09T04:30:00+00:00"
    },
    "total_records": 12500
  }
}
```

---

## **GET /api/data/pages_history/summary** or **/api/data/get_pages_history_summary**

Get monitoring summary statistics for the `pages_history` table.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "total_records": 12500,
    "records_today": 45,
    "records_last_7_days": 315,
    "records_last_30_days": 1350,
    "by_platform": {
      "facebook": 2000,
      "instagram": 3500,
      "linkedin": 1500,
      "tiktok": 2500,
      "x": 2000,
      "youtube": 1000
    },
    "active_pages_monitored": 150
  }
}
```
