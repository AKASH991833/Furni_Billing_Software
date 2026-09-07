# Furniture Bill — License Server

FastAPI + PostgreSQL backend for the commercial lifetime-license system of the
Furniture Bill desktop application.

## What it does

- Issues unique, cryptographically-strong license keys (`FB-XXXX-XXXX-XXXX`)
- Signs license/activation data with an **Ed25519 private key**
- Binds a license to one device (composite machine fingerprint)
- Provides admin APIs to create customers/licenses and manage activation state
- Stores **only licensing metadata** — never customer billing data

## Layout

```
license_server/
  app/
    main.py                 # FastAPI app + startup
    core/
      config.py             # Settings from .env
      rate_limit.py         # In-memory rate limiter
    crypto/
      ed25519.py            # Ed25519 sign/verify + base64 helpers
      license_keys.py       # Key generator (FB-XXXX-XXXX-XXXX)
      generate_keys.py      # CLI: produce a key pair
    models/
      database.py           # Engine / sessions / create_all
      models.py             # Customers, Licenses, ActivationLog
    schemas/schemas.py      # Pydantic request/response models
    services/
      license_service.py    # Core activation & management logic
    routes/
      activation.py         # POST /api/activate (client-facing)
      admin.py              # /admin/* endpoints (token auth)
  .env.example              # Template (copy to .env)
  requirements.txt
```

## Setup (development)

```bash
cd license_server
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 1. Create a PostgreSQL database (or point DATABASE_URL at an existing one)
createdb license_server

# 2. Generate your signing key pair (NEVER commit the private key)
python -m app.crypto.generate_keys
# → copy PRIVATE_KEY into .env as PRIVATE_SIGNING_KEY
# → copy PUBLIC_KEY into the client app config

# 3. Create a .env from the template
copy .env.example .env
# → fill DATABASE_URL, SECRET_KEY
# → set ADMIN_PASSWORD_HASH = sha256 of your admin password:
python -c "import hashlib;print(hashlib.sha256(b'YOUR_PASSWORD').hexdigest())"

# 4. Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`

## Admin API usage

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/admin/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_PASSWORD"}' | jq -r .token)

curl -X POST "http://localhost:8000/admin/customers" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Mahendra Vishwakarma","mobile":"98xxxxxxxx"}'

curl -X POST "http://localhost:8000/admin/licenses" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"customer_id":1,"product":"furniture_bill","license_type":"LIFETIME","device_limit":1}'
```

## Client-facing activation

```bash
curl -X POST "http://localhost:8000/api/activate" \
  -H "Content-Type: application/json" \
  -d '{
    "license_key":"FB-XXXX-XXXX-XXXX",
    "product":"furniture_bill",
    "app_version":"1.0.0",
    "device_fingerprint":"<hashed machine id>"
  }'
```

Successful response contains `license_data` + `signature`. The client verifies
the Ed25519 signature offline using the embedded **public key** before saving.

## Deployment (Docker + HTTPS)

The repo ships a production stack: PostgreSQL 16, the FastAPI server, the admin
web UI, and Caddy (automatic TLS). Requirements: a server with Docker +
Compose, a domain, and the private signing key.

```bash
# 1. On your machine, generate secrets once
python -m app.crypto.generate_keys        # -> PRIVATE_SIGNING_KEY / PUBLIC_KEY
python -c "import hashlib;print(hashlib.sha256(b'YourPassword').hexdigest())"
python -c "import secrets;print(secrets.token_hex(32))"

# 2. On the server
cp release.env.example release.env
# fill in APP_DOMAIN, POSTGRES_PASSWORD, PRIVATE_SIGNING_KEY, ADMIN_PASSWORD_HASH, SECRET_KEY

docker compose --env-file release.env up -d --build
```

Copy the matched **PUBLIC_KEY** into the desktop app (`app/config.py`) build.

### Admin web UI (optional browser tool)

```bash
uvicorn admin_web.main:app --host 0.0.0.0 --port 8080
```
Single-page dashboard to issue/revoke/deactivate licenses and manage customers.
It reuses the same admin token auth as the JSON API.

## Production checklist

- HTTPS enforced by Caddy automatically (`release.env.example` -> Caddyfile).
- PostgreSQL with strong credentials.
- `SECRET_KEY` and `PRIVATE_SIGNING_KEY` from secret management — never Git.
- Back up PostgreSQL (licenses are the product).