# Furniture Billing Software

Desktop billing application for a furniture business, written in Python. Includes product and customer management, GST invoice generation with PDF export, Excel export, and a separate FastAPI-based license server for activating paid installations.

## Components

- `app/` - desktop application (GUI, billing, database, PDF invoices)
- `license_server/` - FastAPI license server with admin web panel, Docker support and tests
- `run.py` - launches the desktop app
- `BUILD.md` - reproducible build and packaging guide for the Windows installer

## Run locally

```bash
python -m pip install -r requirements.txt
python run.py
```

See `BUILD.md` for building the standalone Windows executable and installer, and `license_server/README.md` for running the license server.
