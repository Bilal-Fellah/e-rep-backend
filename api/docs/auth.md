# Auth Routes Documentation

All routes in this document are prefixed with `/api/auth`.

Token extraction in these routes uses the helper in `api/utils/auth.py`:
- `Authorization: Bearer <token>` is checked first
- if no bearer token is present, matching cookie is used (`access_token` or `refresh_token`)

---

## **POST /api/auth/register_mail**

Registers an email for temporary access.

### Request

```json
{
  "email": "user@example.com"
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "message": "Email user@example.com registered for temporary access"
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Invalid email" }
```

```json
{ "success": false, "error": "Email already exists" }
```

---

## **POST /api/auth/register_user**

Creates a verified user account and returns tokens.

### Request

```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "password": "secret123",
  "phone_number": "+15551234567",
  "profession": "marketing",
  "role": "registered"
}
```

`role` is optional and defaults to `registered`.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "access_token": "jwt_access_token_here",
    "refresh_token": "jwt_refresh_token_here",
    "user_role": "registered",
    "user_id": 1,
    "is_verified": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "missing required key: profession" }
```

```json
{ "success": false, "error": "Invalid email format" }
```

```json
{ "success": false, "error": "Invalid phone number format" }
```

```json
{ "success": false, "error": "Password must be at least 8 characters" }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/auth/register_entity_name**

Registers an entity name for temporary access.

### Request

```json
{
  "entity_name": "MyEntity"
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "message": "Entity MyEntity registered for temporary access"
  }
}
```

### Error Responses

```json
{ "success": false, "error": "entity name MyEntity already exists" }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/auth/register_entity**

Creates a new entity and maps it to a category. Requires authenticated user with role in `admin`, `registered`, `subscribed`.

### Request

```json
{
  "entity_name": "MyEntity",
  "type": "business",
  "category_id": 2,
  "pages": [
    {
      "platform": "instagram",
      "link": "https://instagram.com/myentity"
    }
  ]
}
```

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "id": 5,
    "name": "MyEntity",
    "type": "business",
    "category_id": 2,
    "pages": [
      {
        "page_id": "71b5dd66-6cc9-5dfc-88ae-bff8d2c9d483",
        "page_link": "https://instagram.com/myentity",
        "platform": "instagram"
      }
    ]
  }
}
```

### Error Responses

```json
{ "success": false, "error": "No valid token has been sent" }
```

```json
{ "success": false, "error": "Access denied" }
```

```json
{ "success": false, "error": "Missing required parameters" }
```

---

## **POST /api/auth/login**

Authenticates user credentials and returns token pair.

### Request

```json
{
  "email": "john@example.com",
  "password": "secret123"
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "access_token": "jwt_access_token_here",
    "refresh_token": "jwt_refresh_token_here",
    "user_role": "registered",
    "user_id": 1,
    "is_verified": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Invalid credentials" }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/auth/get_user_data**

Returns user profile data from authenticated access token.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "email": "john@example.com",
    "user_id": 1,
    "role": "registered",
    "is_verified": true,
    "profession": "marketing",
    "first_name": "John",
    "last_name": "Doe",
    "created_at": "2026-04-12T08:20:30+00:00"
  }
}
```

### Error Responses

```json
{ "error": "User not found" }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/auth/refresh_token**

Validates refresh token, returns a new access token, and sets a refreshed `access_token` cookie.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "access_token": "new_access_token"
  }
}
```

### Error Responses

```json
{ "error": "Missing refresh token" }
```

```json
{ "error": "Invalid refresh token" }
```

```json
{ "error": "Refresh token expired" }
```

---

## **POST /api/auth/logout**

Clears `access_token` and `refresh_token` cookies. If a user is identified from the provided token, the stored refresh token is revoked in the database.

### Request

No request body is required.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "message": "Logged out successfully"
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/auth/validate_user_role**

Updates the target user's role and sets them as verified. Caller must be authenticated and have role in `admin`, `registered`, `subscribed`.

### Request

```json
{
  "user_id": 9,
  "role": "admin"
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "user_id": 9,
    "role": "admin",
    "is_verified": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required key user_id" }
```

```json
{ "success": false, "error": "Access denied" }
```

---

## **POST /api/auth/complete_profile**

Updates current authenticated user's `phone_number` and `profession`.

### Request

```json
{
  "phone_number": "+15551234567",
  "profession": "marketing"
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "user_id": 1,
    "phone_number": "+15551234567",
    "profession": "marketing",
    "is_verified": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "User not found" }
```

```json
{ "success": false, "error": "Invalid phone number format" }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/auth/redirect_to_app**

Reissues fresh auth cookies and returns an HTTP redirect to the configured frontend app URL. Caller must be authenticated and have role in `admin`, `registered`, `subscribed`.

### Success Response (302)

Redirect to `FRONTEND_REDIRECT_URL` and set cookies:
- `access_token`
- `refresh_token`

### Error Responses

```json
{ "error": "User not found" }
```

```json
{ "success": false, "error": "User role doesnt has enough privilege" }
```

```json
{ "success": false, "error": "Invalid request data" }
```
