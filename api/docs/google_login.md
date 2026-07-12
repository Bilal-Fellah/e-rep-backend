# Google OAuth Routes Documentation

All routes in this document are prefixed with `/api/oauth`.

---

## **GET /api/oauth/google/login**

Starts Google OAuth by redirecting the browser to Google authorization.

### Query Parameters

- `return_to` (optional): frontend base URL to redirect back to after callback.

`return_to` must be in the backend allowlist (`ALLOWED_OAUTH_RETURN_URLS`), otherwise request fails with 400.

### Success Response (302)

Redirects to Google OAuth URL.

### Error Responses

```json
{ "success": false, "error": "Invalid return_to" }
```

---

## **GET /api/oauth/google/callback**

Handles Google callback, validates state, exchanges auth code, gets user profile, and issues a temporary login code.

### Query Parameters

- `code` (required)
- `state` (required)

### Success Response (302)

Redirects to:

```
<return_to>/auth/complete?code=<temporary_login_code>
```

### Error Responses

```json
{ "success": false, "error": "Missing code or state" }
```

```json
{ "success": false, "error": "Invalid or expired state" }
```

```json
{ "success": false, "error": "Google authentication failed" }
```

---

## **POST /api/oauth/google/finalize**

Consumes the temporary login code and returns JWT tokens plus user data.

### Request

```json
{
  "code": "temporary_login_code"
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
    "user": {
      "id": 1,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "role": "registered",
      "is_verified": false,
      "profession": "other",
      "created_at": "2026-04-12T08:20:30+00:00"
    }
  }
}
```

Notes:
- Refresh token is persisted in database.
- Current implementation returns tokens in JSON response body.

### Error Responses

```json
{ "success": false, "error": "Missing code" }
```

```json
{ "success": false, "error": "Invalid or expired code" }
```

```json
{ "success": false, "error": "User not found" }
```
