# Authentication & Entity Routes

This document describes the authentication and entity-related routes defined in `routes/auth_routes.py`.
```markdown
# Auth API Documentation

This document describes the authentication and entity registration API routes defined in `routes/auth_routes.py`.

---

## Base URL
All routes are prefixed with:  
```

/auth

```

---

## **1. Signup**
**Endpoint:**  
```

POST /auth/signup

````

**Description:**  
Creates a new user account.

**Request Body (JSON):**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "johndoe@example.com",
  "password": "securepassword",
  "role": "public"   // optional, defaults to "public"
}
````

**Responses:**

* **201 Created**

```json
{
  "message": "User created",
  "id": 1
}
```

* **400 Bad Request**
  Email already exists:

```json
{
  "error": "Email already exists"
}
```

---

## **2. Register Entity**

**Endpoint:**

```
POST /auth/register_entity
```

**Description:**
Registers a new entity and associates it with a category.

**Required Fields in Request Body (JSON):**

```json
{
  "entity_name": "MyEntity",
  "type": "organization",
  "category_id": 2
}
```

**Responses:**

* **201 Created**

```json
{
  "success": true,
  "data": {
    "id": 10,
    "name": "MyEntity",
    "type": "organization",
    "category_id": 2
  }
}
```

* **400 Bad Request**
  Missing required keys:

```json
{
  "error": "missing required keys"
}
```

Invalid category\_id:

```json
{
  "error": "wrong category_id"
}
```

Entity already exists:

```json
{
  "error": "entity name MyEntity already exists"
}
```

* **500 Internal Server Error**
  Failed to insert entity:

```json
{
  "error": "failed to insert entity data"
}
```

Failed to map entity to category:

```json
{
  "error": "failed to map entity to category"
}
```

---

## **3. Login**

**Endpoint:**

```
POST /auth/login
```

**Description:**
Authenticates a user and returns a JWT token valid for 2 hours.

**Request Body (JSON):**

```json
{
  "email": "johndoe@example.com",
  "password": "securepassword"
}
```

**Responses:**

* **200 OK**

```json
{
  "token": "JWT_TOKEN_HERE",
  "role": "public"
}
```

* **401 Unauthorized**
  Invalid credentials:

```json
{
  "error": "Invalid credentials"
}
```

---

## Notes

* The ` ` returned from login is a JWT signed with the server `SECRET_KEY` using `HS256`.
* The `exp` (expiration) field inside the JWT payload ensures tokens are valid only for 2 hours.


