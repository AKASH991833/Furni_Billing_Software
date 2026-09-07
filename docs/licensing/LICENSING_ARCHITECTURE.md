# Commercial Software Licensing System Architecture & Operations Manual

> **Product Suite**: Furniture Bill Software, AC Service Billing, Future Commercial Desktop Applications  
> **Classification**: Production Architecture & Operations Runbook  
> **Version**: 2.0.0 (Multi-Product & Asymmetric Ed25519 Cryptography)

---

## 1. High-Level Architecture

The commercial licensing system follows an **asymmetric, offline-first, zero-knowledge** architecture. The Central License Server manages customer identities, issued licenses, and hardware bindings. The Desktop Application activates once over the internet, stores a cryptographically signed license file locally, and operates **100% offline indefinitely** thereafter.

```mermaid
graph TD
    subgraph "Desktop Client (Machine A)"
        UI[PySide6 Activation Window / Login Page]
        HW[Hardware Fingerprint Collector (UUID + CPU + MAC)]
        LS[app/services/license_service.py]
        PUB[(Embedded Ed25519 Public Key)]
        LIC[(Local license.json: AppData/FurnitureBill/license.json)]
        BIZ_DB[(Local SQLite DB: furniture.db)]
        PIN[Local Business PIN Auth]
    end

    subgraph "Public Internet"
        HTTPS[TLS / HTTPS Encrypted Channel]
    end

    subgraph "Central License Server (Cloud / VPS)"
        FASTAPI[FastAPI Gateway :8000]
        RATE[In-Memory Sliding-Window Rate Limiter]
        SEC[Admin Auth JWT / Bearer]
        SIGN[Ed25519 Asymmetric Signer]
        PRIV[(Server Private Key - SECURE)]
        PG[(PostgreSQL / SQLite Database)]
        ADMIN_WEB[Admin Web Dashboard SPA]
    end

    UI --> LS
    HW --> LS
    LS -->|1. One-Time Activation| HTTPS
    HTTPS --> FASTAPI
    FASTAPI --> RATE
    RATE --> SIGN
    PRIV --> SIGN
    FASTAPI --> PG
    ADMIN_WEB --> SEC --> FASTAPI

    SIGN -->|2. Signed License Envelope| HTTPS
    HTTPS --> LS
    LS -->|3. Save Verified Envelope| LIC
    PUB -->|4. Offline Verification on Every Launch| LS
    LS -->|5. License Valid -> Allow PIN Login| UI
    PIN -->|6. Business Access Only| BIZ_DB
```

---

## 2. Commercial Lifecycle of a Customer & License

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Business Owner
    actor Admin as Software Vendor / Admin
    participant AdminUI as Vendor Admin Portal
    participant Server as Central License Server
    participant Desktop as Desktop Application

    Admin->>AdminUI: Create customer record (Name, Company, Contact)
    AdminUI->>Server: POST /api/v1/admin/customers
    Admin->>AdminUI: Generate license for product (e.g. furniture_bill, 1 seat)
    AdminUI->>Server: POST /api/v1/admin/licenses
    Server-->>AdminUI: Returns FB-XXXX-XXXX-XXXX-XXXX
    Admin->>Customer: Delivers License Key via Invoice / Email / WhatsApp

    Customer->>Desktop: Installs software & enters License Key
    Desktop->>Desktop: Collects stable hardware fingerprint
    Desktop->>Server: POST /api/v1/license/activate (Key, Product, Fingerprint)
    Server->>Server: Validate product match, active status, and seat limit
    Server->>Server: Sign license payload with Ed25519 private key
    Server->>Server: Record activation event in audit trail
    Server-->>Desktop: 200 OK + Signed Envelope (payload + Base64 signature)
    Desktop->>Desktop: Verify signature against embedded public key
    Desktop->>Desktop: Write local license.json

    Customer->>Desktop: Daily usage (100% Offline)
    Desktop->>Desktop: Reads license.json, verifies signature & device fingerprint
    Desktop-->>Customer: Business PIN prompt displays; Invoices generated offline

    Note over Customer,Admin: Hardware Upgrade / Migration Workflow
    Customer->>Admin: "Old laptop broke, need to activate on new PC"
    Admin->>AdminUI: Locate license & click "Reset Device Binding"
    AdminUI->>Server: POST /api/v1/admin/licenses/{id}/reset-device
    Server->>Server: Clear current_device, reset activated_devices count, log event
    Customer->>Desktop: Enters key on new PC -> Activation succeeds!
```

---

## 3. First-Time Activation Flow

1. **User Launches Unactivated Application**:
   - The desktop bootstrapper (`run.py`) executes `license_service.is_activated()`.
   - `license_service` looks for `license.json` in the OS application data path (`%APPDATA%\FurnitureBill\license.json` on Windows, or overridden by `FURNITURE_BILL_LICENSE`).
   - If missing or invalid, the desktop application displays the **Software Activation** window.
   - The user cannot proceed past activation to the PIN login or billing database.
2. **Key Submission**:
   - User inputs their assigned license key (e.g., `FB-7B29-4D1E-8F3A`).
   - Clicking **ACTIVATE** triggers `license_service.activate_online(key)`.
3. **Hardware Fingerprint Generation**:
   - `license_service.machine_id()` collects the local motherboard UUID, CPU processor ID, and primary MAC address.
   - Computes a stable SHA-256 hash formatted as an uppercase alphanumeric device fingerprint.
4. **Server Validation**:
   - Desktop sends `POST /api/v1/license/activate` with:
     ```json
     {
       "license_key": "FB-7B29-4D1E-8F3A",
       "product": "furniture_bill",
       "device_fingerprint": "8F9B2C4D1E3A5F7091B2C3D4E5F60718",
       "machine_name": "DESKTOP-ACCOUNTS-01"
     }
     ```
   - Server checks:
     - Is the key valid and registered in the database?
     - Does the key's target product match `"furniture_bill"`?
     - Is the license status `ACTIVE` (not `REVOKED`, `EXPIRED`, or `BLOCKED`)?
     - Is the device already registered to this license, or is `activated_devices < max_devices`?
5. **Asymmetric Signing**:
   - The server constructs the canonical verification payload:
     ```json
     {
       "license_key": "FB-7B29-4D1E-8F3A",
       "product": "furniture_bill",
       "customer_id": "cust_9012",
       "device_fingerprint": "8F9B2C4D1E3A5F7091B2C3D4E5F60718",
       "issued_at": "2026-09-07T00:00:00Z",
       "expires_at": null,
       "features": ["all"],
       "max_devices": 1
     }
     ```
   - Server signs the canonical UTF-8 JSON bytes using its **Ed25519 private key**.
   - Encodes the 64-byte raw signature as a Base64 string.
   - Records an `ACTIVATE` audit event with timestamp, IP address, and machine name.
6. **Local Storage & Public Key Verification**:
   - Client receives the payload and signature.
   - Client verifies the signature using the **Ed25519 public key** compiled directly into the client code (`app/crypto/public_key.py`).
   - If verification succeeds, client writes atomic JSON to `license.json` with permissions restricted to the local user.

---

## 4. Offline Verification Model

The desktop software never requires an internet connection during day-to-day operations.

```
+-------------------------------------------------------------------------+
|                         APPLICATION STARTUP                             |
|                                                                         |
| 1. Read AppData/FurnitureBill/license.json                              |
| 2. Extract {"license_data": {...}, "signature": "..."}                  |
| 3. Ed25519 Verify: Verify(signature, canonical_json(license_data), PUB) |
|    - If BAD: Corrupted/tampered -> Show activation window.              |
| 4. Device Binding Check:                                                |
|    - Compute current machine fingerprint.                               |
|    - Compare with license_data["device_fingerprint"].                   |
|    - If MISMATCH: Machine cloned/moved -> Show activation window.       |
| 5. Expiry Check (if not lifetime):                                      |
|    - Compare license_data["expires_at"] with system date.               |
| 6. Product Check:                                                       |
|    - Verify license_data["product"] == "furniture_bill".                |
| 7. ALL CHECKS PASS -> Launch Business PIN Login Screen.                 |
+-------------------------------------------------------------------------+
```

### Why Ed25519?
- **Speed**: Signature verification completes in under 0.1 milliseconds.
- **Security**: 128-bit security level resilient against chosen-ciphertext and side-channel attacks.
- **Asymmetric**: The private signing key resides strictly on the vendor's central server. The desktop app only contains the public verification key. An attacker inspecting, decompiling, or modifying the desktop executable cannot forge valid license signatures.

---

## 5. Machine Binding & Hardware Fingerprinting

### Hardware Components Sampled
The desktop client collects stable platform telemetry using WMI (Windows Management Instrumentation) and OS system queries:
1. Motherboard BIOS UUID (`wmic csproduct get uuid` or PowerShell equivalent)
2. CPU Processor ID (`wmic cpu get processorid`)
3. Primary Network Interface MAC Address (`getnode()`)

### Mitigations & Limitations
- **NIC changes / VPN adapters**: Hardware hashing prioritizes motherboard UUID and processor ID. Network interface changes or USB dongle removals do not invalidate the fingerprint.
- **Admin Reset Protocol**: When a user purchases a new machine or upgrades their motherboard, the vendor admin uses the Admin Portal to click **Reset Device**. This disassociates the previous hardware hash and allows a single new machine to claim the license.

---

## 6. Multi-Product Architecture

The server natively supports multiple software products in a single unified licensing infrastructure.

| Product Code | Prefix Pattern | Application Name |
|---|---|---|
| `furniture_bill` | `FB-XXXX-XXXX-XXXX` | Furniture Billing & Invoicing Desktop |
| `ac_service` | `AC-XXXX-XXXX-XXXX` | Air Conditioner Service & Maintenance ERP |
| `future_product` | `FP-XXXX-XXXX-XXXX` | Custom Enterprise Products |

### Cross-Product Isolation
- A valid license generated for `furniture_bill` will be **strictly rejected** if an AC Service desktop client attempts to activate it (HTTP 400: `"License key is not valid for this product."`).
- The desktop client supplies its registered product code during activation and offline verification.

---

## 7. Server REST API Reference

All v1 APIs are prefixed with `/api/v1/`. Legacy aliases (`/api/activate`, `/api/deactivate`) are preserved for backward compatibility.

### 7.1 Client Endpoints

#### `POST /api/v1/license/activate`
Activates a license key for a given machine fingerprint.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "license_key": "FB-A1B2-C3D4-E5F6",
    "product": "furniture_bill",
    "device_fingerprint": "8F9B2C4D1E3A5F7091B2C3D4E5F60718",
    "machine_name": "ACCOUNTS-PC"
  }
  ```
- **Responses**:
  - `200 OK`:
    ```json
    {
      "success": true,
      "message": "Activation successful.",
      "license_data": {
        "license_key": "FB-A1B2-C3D4-E5F6",
        "product": "furniture_bill",
        "customer_id": "cust_123",
        "device_fingerprint": "8F9B2C4D1E3A5F7091B2C3D4E5F60718",
        "issued_at": "2026-09-07T00:00:00Z",
        "expires_at": null,
        "features": ["all"],
        "max_devices": 1
      },
      "signature": "base64-encoded-64-byte-ed25519-signature"
    }
    ```
  - `400 Bad Request`: Device limit exceeded, product mismatch, or invalid key.
  - `403 Forbidden`: License revoked or blocked.
  - `429 Too Many Requests`: Rate limit exceeded (more than 30 attempts per minute per IP).

#### `POST /api/v1/license/deactivate`
Relinquishes an activation from a device.
- **Request Body**:
  ```json
  {
    "license_key": "FB-A1B2-C3D4-E5F6",
    "product": "furniture_bill",
    "device_fingerprint": "8F9B2C4D1E3A5F7091B2C3D4E5F60718"
  }
  ```

#### `POST /api/v1/license/validate`
Online check for desktop clients performing an optional periodic integrity check.
- **Request Body**: Same as activate.
- **Response**: Returns current validity and status (`ACTIVE`, `REVOKED`, `EXPIRED`, `BLOCKED`).

#### `GET /api/v1/license/status?key={key}`
Public check returning high-level status of a key without revealing customer details.

---

### 7.2 Admin Endpoints (Requires `Authorization: Bearer <JWT_TOKEN>`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/admin/login` | Authenticate vendor admin and receive JWT access token |
| `GET` | `/api/v1/admin/customers` | List all registered customers with license counts |
| `POST` | `/api/v1/admin/customers` | Register a new business customer |
| `GET` | `/api/v1/admin/licenses` | List all issued licenses across all products |
| `POST` | `/api/v1/admin/licenses` | Issue a new license for a customer with product and seat limit |
| `GET` | `/api/v1/admin/licenses/{id}` | Inspect a single license, bound device, and status |
| `POST` | `/api/v1/admin/licenses/{id}/reset-device` | Unbind current device and reset activation count |
| `POST` | `/api/v1/admin/licenses/{id}/revoke` | Revoke a license (marks invalid immediately) |
| `POST` | `/api/v1/admin/licenses/{id}/block` | Block a compromised or fraudulent license |
| `POST` | `/api/v1/admin/licenses/{id}/reactivate` | Re-enable a revoked or blocked license |
| `GET` | `/api/v1/admin/licenses/{id}/events` | View complete audit trail of all activations, resets, and status changes |

---

## 8. Database Schema Documentation

The license server database uses standard SQLAlchemy models compatible with PostgreSQL, MySQL, and SQLite.

```mermaid
erDiagram
    CUSTOMERS ||--o{ LICENSES : owns
    LICENSES ||--o{ ACTIVATION_LOGS : records

    CUSTOMERS {
        int id PK
        string name
        string email
        string company
        string phone
        datetime created_at
    }

    LICENSES {
        int id PK
        int customer_id FK
        string license_key UK
        string license_key_hash UK "Indexed SHA-256"
        string product "furniture_bill / ac_service"
        string status "ACTIVE / REVOKED / EXPIRED / BLOCKED"
        int max_devices "Default: 1"
        int activated_devices "Default: 0"
        string current_device "Hardware fingerprint"
        string machine_name "Reported computer name"
        datetime issued_at
        datetime expires_at "Nullable for lifetime"
        datetime activated_at
        datetime updated_at
        text features_metadata "JSON metadata"
    }

    ACTIVATION_LOGS {
        int id PK
        int license_id FK
        string action "CREATE / ACTIVATE / DEACTIVATE / RESET_DEVICE / REVOKE / BLOCK / REACTIVATE"
        string device_fingerprint
        string machine_name
        string ip_address
        text note
        datetime timestamp
    }
```

---

## 9. Security Model & Data Privacy

### Zero-Knowledge Data Boundary
1. **Financial and Invoicing Data**: The desktop application stores all customers, items, prices, tax records, invoice history, payments, and business settings in a local SQLite database (`furniture.db`) located in `%APPDATA%\FurnitureBill\data`.
2. **Zero Ingestion**: The License Server **never receives, processes, or stores** invoice numbers, line items, customer addresses, monetary amounts, GST numbers, or billing reports.
3. **Network Isolation**: The desktop billing pipeline (PDF generation, ledger calculation, GST summary) is 100% self-contained and executes with zero network I/O.

### Cryptographic Key Hierarchy
- **Private Key**: 32-byte Ed25519 private seed stored only on the license server host. Never exposed via any API endpoint. Never packaged into the desktop client installer.
- **Public Key**: 32-byte Ed25519 public key embedded in the desktop client source code (`app/crypto/public_key.py`). Used exclusively for offline signature verification.
- **Key Storage**: On production servers, the private key is loaded from the environment variable `ED25519_PRIVATE_KEY` or an encrypted vault path (`SERVER_KEY_PATH`).

---

## 10. Production Server Deployment Guide

### Deployment via Docker Compose

```yaml
version: '3.8'

services:
  license_db:
    image: postgres:16-alpine
    container_name: license_db
    restart: always
    environment:
      POSTGRES_DB: license_system
      POSTGRES_USER: license_admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - internal_net

  license_server:
    build:
      context: ./license_server
      dockerfile: Dockerfile
    container_name: license_server
    restart: always
    environment:
      DATABASE_URL: postgresql://license_admin:${DB_PASSWORD}@license_db:5432/license_system
      SECRET_KEY: ${ADMIN_JWT_SECRET}
      ED25519_PRIVATE_KEY: ${ED25519_PRIVATE_KEY}
      ALLOWED_ORIGINS: "https://licensing.yourdomain.com"
    depends_on:
      - license_db
    networks:
      - internal_net
      - web_net
    expose:
      - "8000"

  nginx:
    image: nginx:alpine
    container_name: license_proxy
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - license_server
    networks:
      - web_net

volumes:
  pgdata:

networks:
  internal_net:
  web_net:
```

### Environment Variables
| Variable | Description | Default / Example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `postgresql://user:pass@localhost:5432/license_db` |
| `SECRET_KEY` | JWT secret for admin portal tokens | Secure random 64-char hex string |
| `ED25519_PRIVATE_KEY` | Base64-encoded 32-byte Ed25519 seed | Generated via `python -m app.crypto.keygen` |
| `ADMIN_USERNAME` | Master administrator username | `admin` |
| `ADMIN_PASSWORD` | Master administrator password | `ChangeThisPasswordInProduction!` |
| `RATE_LIMIT_PER_MINUTE` | Max activations per minute per IP | `30` |

### Database Backup & Recovery
```bash
# Backup PostgreSQL License DB
docker exec -t license_db pg_dump -U license_admin license_system > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260907.sql | docker exec -i license_db psql -U license_admin -d license_system
```

---

## 11. Troubleshooting Runbook

| Failure Mode | Symptoms | Root Cause | Solution |
|---|---|---|---|
| **Network Timeout During Activation** | "Could not reach the activation server" | Client has no active internet connection or firewall is blocking outbound HTTPS. | Verify client can reach `https://licensing.yourdomain.com/health`. Connect machine to internet once to complete activation. |
| **Device Mismatch** | "License is already bound to another machine" | User reinstalled Windows, changed motherboard, or copied installation folder. | Vendor admin logs into Admin Web Portal, locates license, and clicks **Reset Device**. User re-enters key. |
| **Tampered License File** | "License signature verification failed" | `license.json` was manually modified or corrupted by disk failure. | User deletes corrupted `%APPDATA%\FurnitureBill\license.json` and runs activation again using their key. |
| **Clock Skew Error** | "License expired" (on non-expired key) | Client machine system clock was rolled back or set years into the future. | Synchronize client system time with internet time (NTP). |
| **Rate Limit 429** | "Too many activation attempts" | User or script submitted repeated invalid keys in rapid succession. | Wait 60 seconds for the sliding rate-limiter window to reset. |

---

## 12. How to Add a New Desktop Product to this Ecosystem

Adding a new product (e.g., `electrician_billing` with prefix `EL-`) requires zero architectural changes:

1. **Server Configuration**:
   - In `license_server/app/crypto/license_keys.py`, add the product prefix mapping:
     ```python
     PRODUCT_PREFIXES["electrician_billing"] = "EL"
     ```
2. **Admin Web Portal**:
   - In `license_server/admin_web/static/index.html`, add the new product option to the `<select id="productSelect">`:
     ```html
     <option value="electrician_billing">Electrician Billing (EL-)</option>
     ```
3. **New Desktop Application**:
   - In the new application's `app/config/config.py`:
     ```python
     PRODUCT_NAME = "electrician_billing"
     LICENSE_SERVER_URL = "https://licensing.yourdomain.com"
     ```
   - Copy `app/services/license_service.py` and `app/crypto/public_key.py` to the new desktop application.
   - Embed the identical Ed25519 public key.
4. **Issue License**:
   - In the Admin Portal, select "Electrician Billing", specify seats, and click **Generate License**.
   - Output: `EL-9B2F-81A4-320C-4E1D`.
   - The new application will activate cleanly and operate with complete offline autonomy.
