## **POST /google/login**

Redirects the user to Google's OAuth 2.0 authorization endpoint.

### Request

No request body is required.

### Success Response (302)

Redirects to the Google OAuth 2.0 authorization URL.

---

## **GET /google/callback**

Handles the callback from Google after user authorization.

### Query Parameters

- `code`: Authorization code from Google.
- `state`: State parameter to prevent CSRF attacks.

### Success Response (302)

Redirects to the `return_to` URL with a temporary login code.

### Error Responses

```json
{
  "error": "Missing code or state"
}
```

```json
{
  "error": "Invalid or expired state"
}
```

---

## **POST /google/finalize**

Finalizes the Google login process and issues JWT tokens.

### Request

```json
{
  "code": "temporary_login_code"
}
```

### Success Response (200)

```json
{
  "success": true
}
```

### Error Responses

```json
{
  "error": "Invalid or expired code"
}
```

---

## **POST /register_mail**

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
{
  "error": "Invalid email"
}
```

```json
{
  "error": "Email already exists"
}
```

---

## **POST /register_user**

Creates a new user account and returns authentication tokens.

### Request

```json
{
  "full_name": "John Doe",
  "email": "john@example.com",
  "password": "secret123",
  "phone_number": "1234567890",
  "role": "registered"
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
    "user_id": 1
  }
}
```

### Error Responses

```json
{
  "error": "missing required key: full_name"
}
```

```json
{
  "error": "role must be in ['public', 'registered', 'anonymous', 'subscribed', 'admin']"
}
```

```json
{
  "error": "Email already exists"
}
```

---

## **POST /register_entity_name**

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
{
  "error": "entity name MyEntity already exists"
}
```

---

## **POST /register_entity**

Registers a new entity with optional pages.

### Headers

```
Authorization: Bearer <access_token>
```

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
{
  "error": "Missing required parameters"
}
```

```json
{
  "error": "wrong category_id"
}
```

```json
{
  "error": "entity name MyEntity already exists"
}
```

---

## **POST /login**

Authenticates a user and returns JWT tokens.

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
    "user_role": "public",
    "user_id": 1
  }
}
```

### Error Responses

```json
{
  "error": "Invalid credentials"
}
```

---

## **POST /get_user_data**

Fetches user details from the JWT access token.

### Headers

```
Authorization: Bearer <access_token>
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "email": "john@example.com",
    "user_id": 1,
    "role": "public",
    "first_name": "John",
    "last_name": "Doe",
    "created_at": "2025-09-15T08:20:30Z"
  }
}
```

### Error Responses

```json
{
  "error": "User not found"
}
```

```json
{
  "error": "Token has expired"
}
```

```json
{
  "error": "Invalid token"
}
```

---

## **POST /refresh_token**

Generates a new access token using a refresh token.

### Headers

```
Authorization: Bearer <refresh_token>
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "access_token": "new_jwt_access_token_here"
  }
}
```

### Error Responses

```json
{
  "error": "Missing refresh token"
}
```

```json
{
  "error": "Invalid refresh token"
}
```

```json
{
  "error": "Refresh token expired"
}
```

---

## **POST /validate_user_role**

Updates the role of a user.

### Headers

```
Authorization: Bearer <access_token>
```

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
    "role": "admin"
  }
}
```

### Error Responses

```json
{
  "error": "Missing required key user_id"
}
```

```json
{
  "error": "Access denied"
}
```