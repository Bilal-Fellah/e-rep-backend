# Client ↔ Company Links API

Which client accounts belong to which company. A client asks from the app;
an admin approves in Brendex Admin.

- Client routes: `/api/data/company-links` — JWT, roles `registered`,
  `subscribed`, `admin`
- Admin routes: `/api/admin/company-links` — JWT, role `admin`

Backed by `api/services/client_entity_link_service.py` and the
`client_entity_links` table.

---

## The rule

**A request is a claim, not a link.** Anyone can ask to be added to any
brand, so nothing takes effect until an admin approves it. There is no
automatic linking anywhere — not on signup, not by email domain, not by
entity name.

**Many-to-many.** One client can hold several companies (an agency or
community manager handling multiple brands) and one company can have
several client accounts (colleagues with their own logins). One row per
`(user_id, entity_id)` pair, enforced by a unique constraint.

**A pair has one row, reused.** Asking again after a rejection reopens the
same request and clears the old review, rather than stacking duplicates.
This matters for the admin list: it stays one line per client/company, not
a history of every attempt.

## Statuses

| status | meaning |
|---|---|
| `pending` | asked, waiting on an admin |
| `approved` | linked — appears in `clients_for_entity` |
| `rejected` | refused; `review_note` says why, and the client can see it |

`role` is `owner` or `member`. It is advisory today — nothing reads it to
make a decision — but it's the field an access rule would need later, and
recording it at approval time costs nothing.

---

## Client routes

### `GET /api/data/company-links`

Every company this client is linked to or has asked to join, including
rejected requests and the reason given.

```json
{ "success": true, "data": { "links": [
  { "id": 3, "entity_id": 42, "entity_name": "djezzy", "entity_type": "company",
    "status": "pending", "role": "member", "note": "I'm the CM for this page",
    "review_note": null, "requested_at": "2026-09-05T09:12:00+00:00",
    "reviewed_at": null }
]}}
```

### `POST /api/data/company-links`

Body: `{"entity_id": 42, "note": "I'm the CM for this page"}` — `note`
optional, 500 chars max.

Creates a pending request. `201`. Returns `400` if the company doesn't
exist or the client is already linked to it. Posting again while pending
updates the note instead of erroring.

### `DELETE /api/data/company-links/<id>`

Withdraws a request that hasn't been answered. Refuses on an approved link
— leaving a company is an admin action, not a self-service delete.

---

## Admin routes

### `GET /api/admin/company-links`

Query: `status` (`pending`/`approved`/`rejected`), `limit` (default 200).
**Pending sort first regardless of age** — those are the ones waiting on a
decision.

```json
{ "success": true, "data": {
  "counts": { "pending": 2, "approved": 5 },
  "links": [
    { "id": 3, "user_id": 12, "user_email": "cm@djezzy.dz",
      "user_name": "Sara B", "user_role": "subscribed",
      "entity_id": 42, "entity_name": "djezzy", "entity_type": "company",
      "status": "pending", "role": "member",
      "note": "I'm the CM for this page", "review_note": null,
      "requested_at": "…", "reviewed_at": null, "reviewed_by": null }
  ]
}}
```

### `POST /api/admin/company-links`

Body: `{"user_id": 12, "entity_id": 42, "role": "owner", "review_note": "…"}`

Links directly without waiting for a request — the usual case when it was
agreed off-platform. If a pending request already exists for that pair it
is approved rather than duplicated (the unique constraint would reject a
second row).

### `POST /api/admin/company-links/<id>/approve`

Body: `{"role": "owner", "review_note": "…"}` — both optional.

### `POST /api/admin/company-links/<id>/reject`

Body: `{"review_note": "couldn't verify"}`. The note is shown to the
client, so it's worth filling in.

### `DELETE /api/admin/company-links/<id>`

Removes the link outright. This is how an approval is undone — rejecting
would leave a row implying the client asked and was refused, which isn't
what happened.

### `GET /api/admin/entities/<entity_id>/clients`

The approved client accounts on one company.

---

## What this does not do (yet)

Nothing consumes the link. It does not change what a client sees in Erup,
does not gate any endpoint, and does not affect scraping. It records who
belongs to which company so that decision can be made later, deliberately,
rather than being implied by a schema.
