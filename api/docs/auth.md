
````
# Auth Routes Documentation

## **POST /signup**
Create a new user account.

### Request
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "password": "secret123",
  "role": "public"
}
````

### Success Response (201)

```json
{
  "message": "User created",
  "id": 1
}
```

### Error Response (400)

```json
{
  "error": "Email already exists"
}
```

---

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

