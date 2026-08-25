# PulseBoard — Design Notes & Decision Log

A running record of *why* the schema looks the way it does. Plan lives in
`PULSEBOARD.md`; long-term vision in `ARCHITECTURE.md`. This file captures the
reasoning behind decisions so we (and reviewers) never have to reconstruct it.

Last updated: 2026-08-25

---

## Where we are

- ✅ `users` table + first Alembic migration (Week 1).
- ✅ `sources` table + migration (Week 2 schema landed early).
- ✅ `/health` endpoint.
- ✅ Password hashing — `app/core/security.py`, Argon2 via `pwdlib`.
- ✅ `sessions` table + migration (`4bf420e833e7`). Replaces the JWT plan.
- ✅ `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me` + the
  `get_current_user` dependency — Week 1. **Verified against Postgres
  2026-08-25:** register 201 → login 200 + `Set-Cookie` → me 200 → logout 204
  → me 401. Confirmed in the DB that `sessions.session_id` is the SHA-256 of
  the cookie value (never the raw token), and that logout deletes the row —
  revocation demonstrated, not just asserted. Error paths: wrong password 401,
  unknown email 401 (identical body), duplicate register 409, no cookie 401,
  forged token 401, short password 422.
- ⬜ **W1 remaining:** no automated tests. The loop above was curl-by-hand and
  will rot the moment auth changes. pytest is scheduled W6 — moved up to W2 if
  roles touch `get_current_user`.
- 🔜 Roles (admin/viewer) as a dependency + sources CRUD/API keys — Week 2, next.
- 🔜 `metrics` table (time-series readings — Week 3). Design decided below;
  not yet written.

### Why Argon2 and not SHA-256

A password hash must be **slow** on purpose. SHA-256 is fast — a GPU does
billions/sec, so a leaked table gets brute-forced against a common-password
list in minutes. Argon2 is tuned so one hash takes ~100ms: invisible to a human
logging in once, ruinous to someone trying ten million guesses. It also salts
automatically (random value mixed in per password), so two users with the same
password get different hashes and cracking one doesn't crack the other. The
salt lives inside the `$argon2id$v=19$m=...$<salt>$<hash>` string — nothing
extra to store. Used `PasswordHash.recommended()` rather than naming Argon2
explicitly, so the choice tracks the library's current best practice.

---

## Sessions, not JWT (decided 2026-08-03)

**What a JWT is:** the server signs a small JSON blob
(`{"user_id":42,"role":"admin","exp":...}`) and hands it to the client, which
sends it back on every request. The server checks the signature and stores
**nothing** — that's "stateless." It's a concert wristband: it carries its own
proof, so no bouncer's clipboard is needed. (The payload is signed, not
encrypted — anyone holding it can read it. Never put secrets in one.)

**The catch:** a wristband can't be taken back. The role printed on it was true
when it was issued and never updates — that's **staleness**, a copy that was
correct when made and doesn't know the original changed. So with stateless JWT:

- logout only deletes the client's copy; the token itself stays valid until `exp`
- a stolen token can't be killed
- demoting or deleting a user has no effect until expiry

**Our requirement:** logout must take effect immediately, and we must be able to
kill access from the server (stolen laptop). That is **revocation**, and
revocation needs a server-side list we can delete a row from. → **sessions**.

**Cost we accepted:** one extra `SELECT` per request. It's a primary-key lookup
on a pooled connection, ~0.2–1 ms, well under 1% of a request. Statelessness
solves a many-servers / high-QPS problem we do not have — same reasoning as
partitioning below.

Rejected middle path: short-lived JWT + refresh token. Buys back partial
revocation at real complexity cost. Right at scale, wrong for a one-user
dashboard.

*Done (`a768813`): dropped `pyjwt` from `pyproject.toml` — it was a dependency
for a design we rejected, and the manifest should describe what we actually built.*

**Told the neighbor (2026-08-16).** He specified JWT; this is a deliberate
deviation, raised with him rather than swapped quietly.
<!-- TODO(Ace): one line on what he actually said back — that's the bit an
interviewer will ask about. -->

### `sessions` table (draft)

| column       | why it's there                                                     |
| ------------ | ------------------------------------------------------------------ |
| `session_id` | PK. The random secret the browser sends back on every request.      |
| `user_id`    | FK → `users.id`, `ON DELETE CASCADE` — deleting a user kills their sessions. |
| `expires_at` | Checked in the SQL `WHERE`, not only in Python (see below).         |
| `created_at` | Audit/debugging only; no auth logic reads it.                       |

Expiry is enforced in the query (`WHERE session_id = ... AND expires_at > now()`),
not by a cleanup job. A job that deletes old rows every hour still leaves an
expired session usable until it runs — same lesson as `event_id`: the database
*enforces*, a background task only *tidies up*. A cleanup job is still wanted so
the table doesn't grow forever, but it is housekeeping, not a security control.

*Resolved — yes, hashed at rest with **SHA-256, not Argon2**.* `hash_session_token`
in `app/core/security.py`; the raw token exists only in the browser cookie, so a
dump of the `sessions` table yields no usable tickets. Argon2 is slow *on purpose* because passwords are
guessable from a wordlist. A 256-bit random token can't be guessed at all, so
there's nothing to slow down, and this lookup runs on every single request.

---

## The four tables and why

The system has **four different kinds of thing**, each with its own lifecycle,
so each gets its own table (this is *normalization* — every fact lives in exactly
one place):

| Table      | Represents          | Lifecycle                                    |
| ---------- | ------------------- | -------------------------------------------- |
| `users`    | a human             | registers, logs in, has a role. Changes rarely. |
| `sources`  | a machine           | admin adds it, owns an API key, revocable. Few rows. |
| `sessions` | one active login    | created at login, deleted at logout/expiry. Short-lived. |
| `metrics`  | a single reading    | append-only, millions of rows, never updated. |

Chain: a **user** (admin) creates a **source** → gets an API key → the machine
posts **metrics** using that key.

`sessions` was a *consequence* of choosing sessions over JWT (above), not extra
scope: a JWT keeps the login on the client and needs no table, a session keeps it
on the server and therefore needs one. That table is the price of revocation.

Every table has its **own** primary key — `users.id`, `sources.id`,
`sessions.session_id`, `metrics.(event_id, event_time)`. "Primary key" is a
per-table job (*what identifies a row in this table*), not one global thing.

---

## API keys (machine authentication)

- **Problem:** humans log in with password + JWT. A server posting readings every
  few seconds can't "log in and click a button." Machines need a different proof.
- **What it is:** a long random secret string, e.g. `pb_live_9f8a3c2e...`,
  generated with Python's `secrets.token_hex(32)`.
- **Lifecycle:** admin creates a source → server generates the key → shown to the
  user **once** → the machine sends it in a header on every metric POST.
- **Storage:** store a **hash** of the key, not the raw key (same as a password),
  so a DB leak doesn't expose usable keys. *(Week 2 refinement.)*
- Lives on the `sources` table.

---

## Idempotency — the core decision behind the `metrics` table

**Requirement (the actual business problem):** *if the same reading is retried,
don't store it twice.* Network hiccups → agent retries → the same reading can
arrive twice → duplicate rows → graphs lie.

Reasoning chain:

```
Network retries
  → need idempotency
  → need a stable identifier that survives retries   → event_id
  → the CLIENT (sensor) must generate it (server-generated can't recognize a retry)
  → database rejects duplicates via a UNIQUE constraint
  → partitioning (later) changes how that constraint is written
```

### Decisions

1. **The sensor generates `event_id`, not the server.** A server-generated id
   would differ on each retry, so it couldn't detect duplicates. We control the
   sensors (we write the generator in Week 6), so we can mandate this.
2. **`event_id` is a UUID (`uuid4`) → globally unique.** Alternative was a
   per-sensor counter, which would force `(source_id, event_id)` for uniqueness.
   UUID is simpler: `event_id` alone identifies one logical reading.
3. **API contract:** *every metric producer MUST send a UUID `event_id` per
   reading.* No two sensors can collide (UUID guarantees this).

---

## Uniqueness vs. lookup — two different jobs, two different objects

A CRUD app solves both with one primary key because it fetches rows by their key.
A time-series table never fetches a metric by its `event_id`, so we split the jobs:

- **Uniqueness (idempotency):** handled by the **primary key** (see below) —
  a PK *is* a UNIQUE + NOT NULL constraint, so it already forbids duplicates.
  No separate `UNIQUE` constraint needed.
- **Fast dashboard lookup:** an index on `(source_id, metric, event_time)` —
  order matches the query's WHERE (always know the source, then the metric, then
  narrow by time). The order is what makes it usable.

### Primary key = `(event_id, event_time)` — one object, both jobs

A table has exactly **one** primary key, but it can span multiple columns
(a *composite* PK). We use a composite PK on `metrics`:

```
PRIMARY KEY (event_id, event_time)
```

- It is **one** primary key whose identity is the *pair* taken together — not
  "two PKs."
- Because a PK is a UNIQUE + NOT NULL constraint, this single object does **both**
  jobs: (1) official row identity, and (2) the idempotency guard (rejects retries).
  So we do **not** add a separate `UNIQUE (event_id, event_time)` — that would
  enforce the same rule twice and cost a redundant index on every insert.
- **No surrogate `id` column.** An auto-increment PK would add a column + index we
  never query by, on an insert-only table. The natural composite PK is enough.

---

## Partitioning — decision: prepare for it, don't build it yet

- **Postgres does NOT partition automatically.** You declare it by hand and must
  create each monthly partition (or use `pg_partman` to automate creation).
  Nothing is free or automatic.
- **Why partition (eventually):** (1) time-bounded dashboard queries touch only
  the relevant month(s) — *partition pruning*; (2) retention becomes
  `DROP TABLE metrics_2026_04` (instant) instead of a slow, bloating `DELETE`.
- **Why not now:** at Phase-1 scale (one neighbor, a few sources) neither problem
  exists. Partitioning is a solution to a volume problem we don't have. → Phase 3.
- **Decision:** **plain (non-partitioned) `metrics` table in Phase 1**, but shape
  the **primary key** as **`(event_id, event_time)`** now so switching on
  partitioning in Phase 3 is a switch-flip, not a live-table rebuild.
  - `event_id` alone is what actually guarantees uniqueness (it's a global UUID).
  - `event_time` is in the PK **only** because a future partition-by-`event_time`
    requires the partition key to be in every unique constraint — and the PK is a
    unique constraint (each partition is a physically separate table with its own
    index, so Postgres can only guarantee global uniqueness if a duplicate is
    forced into the same partition). It adds nothing to correctness today — pure
    future-proofing.

---

## The five things called "key" (they are unrelated)

| Term              | Job                                          | In PulseBoard                              |
| ----------------- | -------------------------------------------- | ------------------------------------------ |
| API key           | machine proves it may post data              | secret string on `sources`                 |
| Primary key       | official row identity (= UNIQUE + NOT NULL)   | `(event_id, event_time)` — also the idempotency guard |
| Unique constraint | prevent duplicate logical readings           | absorbed into the PK — no separate one     |
| Foreign key       | point at another table's row                 | `source_id → sources.id`                   |
| Partition key     | which physical partition stores the row      | `event_time` (Phase 3)                     |
| Index             | make queries fast                            | `(source_id, metric, event_time)`          |

None of these exists because "every table needs one." Each solves a distinct problem.

---

## Open (W2): registration is currently public

Anyone can `POST /auth/register`. This is **deliberate for W1** — roles don't
exist yet, so there is nothing to check a caller against.

When roles land in W2, registration becomes admin-only. That creates a
**bootstrap problem**: only an admin may create users, but a fresh database has
zero users, so no admin exists to create the first admin — deadlock. Every
system with logins hits this; the fix is always that the first row arrives from
*outside* the API.

Three real options: a CLI seed command (Django's `createsuperuser`), env-var
bootstrap at startup (Grafana, most self-hosted Docker apps), or first-user-wins
(Gitea, Jellyfin). First-user-wins assumes the operator registers during a
trusted window right after install — our W7 deploy is a public AWS URL, which
breaks exactly that assumption.

Leaning env-var (`BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD`): fits Docker Compose,
reuses the existing `Settings` pattern, needs no shell into a running container.
It's also idempotent for free — creating a *specific* email means a second run
(or two workers racing at startup) hits the existing `UNIQUE` on `users.email`
and fails harmlessly, instead of producing a second admin. Same lesson as
`event_id` below: the database *enforces*, the application can only *check*.

Decision deferred to W2 — not forgotten.

---

## Open questions (still to pin down for the `metrics` table)

- `metric` name — text for Phase 1; labels/tags parked pending the neighbor question.
- `value` type — **not float** (floating-point can't represent e.g. a CPU % or
  money exactly). Decide the exact numeric type when writing the column list.
- `ingest_time` — server receipt time; `clock_timestamp()` vs `now()` matters.

*Resolved:* `metrics` primary key = composite `(event_id, event_time)` — natural,
no surrogate `id`, and it absorbs the uniqueness/idempotency job (no separate
`UNIQUE` constraint).

---

## Known trade-off: login timing leak (W1, accepted)

`POST /auth/login` skips Argon2 entirely when the email doesn't exist, so a miss
returns faster than a wrong password. **Measured 2026-08-25: ~50 ms (hit, Argon2
runs) vs ~0 ms (miss, short-circuited)** — Argon2 params are `m=65536,t=3,p=4`.
That gap is measurable, and it leaks **which emails have accounts** — user
enumeration.

Fix is to always run a hash, even on the miss (verify against a dummy hash), so
both paths cost the same. Not done: at one-neighbor scale the exposure is a list
of emails that isn't secret anyway. Recorded because it's a deliberate choice,
not an oversight — revisit before the W7 public deploy.
