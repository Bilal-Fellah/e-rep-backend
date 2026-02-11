
## ✅ FRONTEND FLOW (Google OAuth – correct way)

### 1️⃣ User clicks **“Login with Google”**

Frontend **redirects browser** (not fetch):

```js
window.location.href =
  "https://api.brendex.net/google/login?return_to=https://www.brendex.net";
```

---

### 2️⃣ User logs in with Google

Nothing to do here (Google UI).

---

### 3️⃣ Backend redirects user to frontend

User lands on:

```
https://www.brendex.net/auth/complete?code=TEMP_CODE
```

Frontend page: `/auth/complete`

---

### 4️⃣ Frontend finalizes login (VERY IMPORTANT)

On `/auth/complete` page:

```js
const params = new URLSearchParams(window.location.search);
const code = params.get("code");

await fetch("https://api.brendex.net/google/finalize", {
  method: "POST",
  credentials: "include",   // REQUIRED
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ code })
});
```

✅ Backend now sets **HttpOnly cookies**

---

### 5️⃣ Frontend redirects user inside app

```js
window.location.replace("/dashboard");
```

---

## 🔍 How frontend verifies login later

```js
fetch("https://api.brendex.net/me", {
  credentials: "include"
});
```

Cookies are sent automatically.

---

## ❌ Frontend must NOT do

* ❌ Do NOT store tokens
* ❌ Do NOT read cookies
* ❌ Do NOT redirect before finalize finishes

---

## 🧠 Summary (one screen)

1. Redirect to backend login
2. Google auth
3. Backend → `/auth/complete?code=...`
4. `POST /google/finalize`
5. Redirect user inside app

That’s it. Production-safe.

