# Notes API

All routes in this document are prefixed with `/api/data`.

Notes can target:
- a post: `target_type = "post"`
- an entity graph: `target_type = "interactions_graph"` or `"followers_graph"`

Visibility:
- `private`: author only
- `public`: visible to others with access to the target

Status values:
- `active`
- `archived`
- `deleted` (soft delete)

---

## **POST /api/data/create_note**

Create a new note.

### Request Body

```json
{
  "user_id": 1,
  "content": "Engagement dropped after Feb 10.",
  "target_type": "interactions_graph",
  "target_id": "3",
  "title": "Q1 observation",
  "visibility": "private",
  "context_data": { "date_range": "2026-02-01/2026-02-20" }
}
```

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "id": 1,
    "author_id": 1,
    "title": "Q1 observation",
    "content": "Engagement dropped after Feb 10.",
    "target_type": "interactions_graph",
    "target_id": "3",
    "context_data": { "date_range": "2026-02-01/2026-02-20" },
    "visibility": "private",
    "status": "active",
    "created_at": "2026-02-24T10:00:00",
    "updated_at": null
  }
}
```

### Error Responses

```json
{ "success": false, "error": "user_id is required" }
```

```json
{ "success": false, "error": "Invalid target_type, must be 'post', 'interactions_graph', or 'followers_graph'" }
```

```json
{ "success": false, "error": "Target post not found" }
```

```json
{ "success": false, "error": "Target entity not found" }
```

```json
{ "success": false, "error": "User doesn't exist, can't create note" }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_note/<note_id>**

Get a single note by id.

### Query Parameters

- `user_id` (optional, integer)

If note visibility requires ownership and `user_id` does not match author, returns 403.

### Error Responses

```json
{ "success": false, "error": "Note not found" }
```

```json
{ "success": false, "error": "Access denied" }
```

---

## **GET /api/data/get_notes_for_target**

Get notes for one target.

### Query Parameters

- `target_type` (required)
- `target_id` (required)
- `user_id` (optional)
- `include_archived` (optional, `true`/`false`, default `false`)

### Error Responses

```json
{ "success": false, "error": "target_type and target_id are required" }
```

---

## **GET /api/data/get_notes_by_author**

Get all notes for a user author.

### Query Parameters

- `user_id` (required)
- `include_archived` (optional, `true`/`false`, default `false`)

### Error Responses

```json
{ "success": false, "error": "user_id is required" }
```

---

## **POST /api/data/update_note/<note_id>**

Update note fields. Author only.

### Request Body

```json
{
  "user_id": 1,
  "title": "Updated title",
  "content": "Updated observation.",
  "visibility": "public",
  "context_data": { "date_range": "2026-02-01/2026-02-24" }
}
```

### Error Responses

```json
{ "success": false, "error": "user_id is required" }
```

```json
{ "success": false, "error": "Note not found" }
```

```json
{ "success": false, "error": "Access denied — you are not the author" }
```

---

## **POST /api/data/archive_note/<note_id>**

Archive note. Author only.

### Request Body

```json
{ "user_id": 1 }
```

### Success Response (200)

```json
{
  "success": true,
  "data": { "message": "Note archived" }
}
```

---

## **POST /api/data/delete_note/<note_id>**

Soft-delete note. Author only.

### Request Body

```json
{ "user_id": 1 }
```

### Success Response (200)

```json
{
  "success": true,
  "data": { "message": "Note deleted" }
}
```
