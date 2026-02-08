
## **POST /register\_entity**

Register a new entity under a category.

### Request

```json
{
  "entity_name": "MyCompany",
  "type": "business",
  "category_id": 2
}
```

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "id": 5,
    "name": "MyCompany",
    "type": "business",
    "category_id": 2
  }
}
```

### Error Response (400/500)

```json
{
  "error": "missing required keys"
}
```

```json
{
  "error": "wrong category_id"
}
```

```json
{
  "error": "entity name MyCompany already exists"
}
```

```json
{
  "error": "failed to insert entity data"
}
```

---

## **POST /login**

Authenticate user and return tokens.

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

### Error Response (401)

```json
{
  "error": "Invalid credentials"
}
```

---

## **POST /get\_user\_data**

Fetch user details from JWT access token.

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

## **POST /refresh\_token**

Generate a new access token using a refresh token.

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


## **POST /register\_entity**

Add a new entity with all related data in the database

####   allowed_roles = ["admin"]

### Headers

```
Authorization: Bearer <access_token>
```

### Success Response (200)

```json
{
  "data": {
    "category_id": 3,
    "id": 166,
    "name": "chopit2",
    "pages": [
      {
        "page_id": "71b5dd66-6cc9-5dfc-88ae-bff8d2c9d483",
        "page_link": "chopa.com",
        "platform": "instagram"
      }
    ],
    "type": "company"
  },
  "success": true
}
```

### Error Responses

```json
{
  "error": "Missing access token"
}
```

```json
{
  "error": "Invalid access token"
}
```

```json
{
  "error": "wrong category_id"
}
```

```json
{
  "error": "Missing required parameters"
}
```

## **POST /validate\_user\_role**

Update the role of a user

####   allowed_roles = ["admin"]

### Headers

```
Authorization: Bearer <access_token>
```

### Success Response (200)

```json
{
  "data": {
    "role": "admin",
    "user_id": 9
  },
  "success": true
}
```

### Error Responses

```json
{
  "error": "Missing access token"
}
```

```json
{
  "error": "Invalid access token"
}
```

```json
{
  "error": "Missing required parameters"
}
```

## **POST /register_mail**
Register an email for temporary access without creating a full user account.

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

**Invalid email (400)**
```json
{
  "error": "Invalid email"
}
```

**Email already exists (400)**
```json
{
  "error": "Email already exists"
}
```

---

## **POST /register_user**
Create a new user account and return authentication tokens. No need to login separately after registration.

### Request
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "password": "secret123",
  "role": "registered"
}
```

**Note:** `role` is optional and defaults to `"registered"`. Allowed roles: `"public"`, `"registered"`, `"anonymous"`, `"subscribed"`, `"admin"`

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

**Token Details:**
- Access token: Valid for 1 day
- Refresh token: Valid for 30 days

### Error Responses

**Missing required key (400)**
```json
{
  "error": "missing required key: first_name"
}
```

**Invalid role (400)**
```json
{
  "error": "role must be in ['public', 'registered', 'anonymous', 'subscribed', 'admin']"
}
```

**Email already exists (400)**
```json
{
  "error": "Email already exists"
}
```