# e-rep-backend

Flask REST API backend for the Brendex reputation analytics platform.

## Overview

This backend provides analytics data for social media entities (companies, influencers, small businesses), including followers history, interaction rankings, post metrics, and user authentication via both email/password and Google OAuth.

## Project Structure

```
api/
  routes/           # Flask Blueprints (auth, data, public, health, oauth)
    data/           # Data endpoints: entities, pages, categories, influence history, notes, posts
  services/         # Business logic layer
  repositories/     # Database access layer (SQLAlchemy)
  models/           # SQLAlchemy ORM models
  utils/            # Auth helpers, validators, logging, permissions
  docs/             # Markdown API documentation per feature area
migrations/         # Alembic database migrations
logs/               # Rotating JSONL log files (route, service, repository errors)
```

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | JWT signing secret |
| `FLASK_ENV` | `development`, `production`, or `testing` |
| `DB_USER` | PostgreSQL username |
| `DB_PWD` | PostgreSQL password |
| `DB_NAME` | PostgreSQL database name |
| `VPS_ADDRESS` | DB host (development only) |
| `VPS_DB_PORT` | DB port (development only) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `BACKEND_URL` | Public backend URL (used for OAuth callback) |
| `FRONTEND_REDIRECT_URL` | Frontend base URL for post-login redirects |
| `FRONTEND_COOKIE_DOMAIN` | Cookie domain (e.g. `.brendex.net`) |
| `COOKIE_SECURE` | Set to `true` in production |
| `ALLOWED_OAUTH_RETURN_URLS` | Comma-separated list of allowed OAuth return URLs |

## Running Locally

```bash
python -m venv flask-env
flask-env\Scripts\activate      # Windows
pip install -r requirements.txt

# Set environment variables, then:
python app.py --port 5000
```

The API is available at `http://localhost:5000`.

## Running with Docker

```bash
docker-compose up --build
```

## Running Tests

```bash
TESTING=true pytest
```

## API Documentation

See `api/docs/` for per-feature documentation:

| File | Coverage |
|---|---|
| `auth.md` | `/api/auth/*` — registration, login, logout, token refresh |
| `google_login.md` | `/api/oauth/*` — Google OAuth flow |
| `entities.md` | `/api/data/*` — entity CRUD and analytics |
| `page.md` | `/api/data/*` — page CRUD |
| `categories.md` | `/api/data/*` — category CRUD |
| `influence_history.md` | `/api/data/*` — followers and interaction rankings |
| `interaction_stats.md` | `/api/data/*` — per-entity/competitor interaction stats |
| `notes.md` | `/api/data/*` — user notes on posts and graphs |
| `posts.md` | `/api/data/*` — post data and history |
| `public.md` | `/api/public/*` — unauthenticated public endpoints |
| `health.md` | `/health/check` — liveness probe |
| `access_roles.md` | Role-based access summary |

## Auth Model

- **JWT** tokens — short-lived access token (1 day) + long-lived refresh token (30 days)
- Token is sent via `Authorization: Bearer <token>` header or `access_token` cookie
- Roles: `registered`, `subscribed`, `admin`
- Google OAuth users are created automatically on first login

## Supported Platforms

`facebook`, `instagram`, `x`, `tiktok`, `linkedin`, `youtube`
