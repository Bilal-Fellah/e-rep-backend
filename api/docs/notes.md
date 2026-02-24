# Notes API

All routes are prefixed with `/data`.

Notes can be attached to a **post** (`target_type: "post"`) or to an entity graph (`target_type: "interactions_graph"` / `"followers_graph"`).

Visibility controls who can read a note:
- `"private"` — author only
- `"public"` — anyone with access to the target

`status` values: `active` | `archived` | `deleted` (soft-delete only).

---

## **POST /data/create_note**

Create a new note.

### Request Body

```json
{
  "user_id": 1,
  "content": "Engagement dropped after Feb 10.",
  "target_type": "interactions_graph",
  "target_id": 3,
  "title": "Q1 observation",
  "visibility": "private",
  "context_data": { "date_range": "2026-02-01/2026-02-20" }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_id` | integer | ✅ | Must exist in `users` |
| `content` | string | ✅ | |
| `target_type` | string | ✅ | `"post"`, `"interactions_graph"`, or `"followers_graph"` |
| `target_id` | integer | ✅ | `post.id` or `entity.id` depending on `target_type` |
| `title` | string | ❌ | |
| `visibility` | string | ❌ | Default: `"private"` |
| `context_data` | object | ❌ | Arbitrary JSON metadata |

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
    "target_id": 3,
    "context_data": { "date_range": "2026-02-01/2026-02-20" },
    "visibility": "private",
    "status": "active",
    "created_at": "2026-02-24T10:00:00",
    "updated_at": null
  }
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"<field> is required"` |
| 400 | `"Invalid target_type, must be 'post', 'interactions_graph', or 'followers_graph'"` |
| 404 | `"Target post not found"` |
| 404 | `"Target entity not found"` |
| 404 | `"User doesn't exist, can't create note"` |

---

## **GET /data/get_note/\<note_id\>**

Get a single note by its ID. Returns 403 if the note is private and `user_id` is not the author.

### Query Parameters

| Param | Type | Required |
|-------|------|----------|
| `user_id` | integer | ✅ |

### Success Response (200)

```json
{
  "success": true,
  "data": { ...note object... }
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 403 | `"Access denied"` |
| 404 | `"Note not found"` |

---

## **GET /data/get_notes_for_target**

Get all notes attached to a specific post or entity graph. Returns public notes plus the requesting user's own private notes.

### Query Parameters

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `target_type` | string | ✅ | `"post"`, `"interactions_graph"`, `"followers_graph"` |
| `target_id` | integer | ✅ | |
| `user_id` | integer | ✅ | Used to include the user's own private notes |
| `include_archived` | boolean | ❌ | Default: `false` |

### Success Response (200)

```json
{
  "success": true,
  "data": [ ...array of note objects... ]
}
```

---

## **GET /data/get_notes_by_author**

Get all notes written by a specific user.

### Query Parameters

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `author_id` | integer | ✅ | |
| `include_archived` | boolean | ❌ | Default: `false` |

### Success Response (200)

```json
{
  "success": true,
  "data": [ ...array of note objects... ]
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"author_id is required"` |

---

## **POST /data/update_note/\<note_id\>**

Update the content, title, context_data, or visibility of a note. Only the author can update.

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

All fields except `user_id` are optional — only provided fields are updated.

### Success Response (200)

```json
{
  "success": true,
  "data": { ...updated note object... }
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"user_id is required"` |
| 403 | `"Access denied — you are not the author"` |
| 404 | `"Note not found"` |

---

## **POST /data/archive_note/\<note_id\>**

Set a note's status to `"archived"`. Only the author can archive.

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

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"user_id is required"` |
| 403 | `"Access denied — you are not the author"` |
| 404 | `"Note not found"` |

---

## **POST /data/delete_note/\<note_id\>**

Soft-delete a note (sets status to `"deleted"`). Only the author can delete.

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

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"user_id is required"` |
| 403 | `"Access denied — you are not the author"` |
| 404 | `"Note not found"` |
