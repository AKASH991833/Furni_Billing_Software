"""Developer seed script - adds realistic demo data.

Adds:
- A proper business/shop profile (editable via Settings later)
- 5 furniture/interior customers
- 6 invoices across areas with measurements, LS rows and custom items
- Payments against some invoices

Run:  python seed_demo.py
Data is written to the live app data folder so the running application
shows the demo content immediately.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault(
    "FURNITURE_BILL_DATA",
    os.path.join(os.environ.get("APPDATA", ""), "FurnitureBill", "data"),
)

from app.database.seed import init_app_data  # noqa: E402
from app.services import (  # noqa: E402
    business_service,
    customer_service,
    invoice_service,
    payment_service,
)
from app.utils.calculations import amount_in_words  # noqa: E402

init_app_data()


def seed_shop():
    business_service.save_profile({
        "business_name": "Shree Balaji Furniture Works",
        "owner_name": "Mr. Suresh Kumar Gupta",
        "business_type": "Furniture Contractor & Interior Works",
        "mobile": "+91 98765 43210",
        "alternate_mobile": "+91 98220 11223",
        "email": "contact@balajifurniture.in",
        "address": "Shop No. 12, Main Market Road,\nNear Bus Stand,",
        "city": "Raipur",
        "state": "Chhattisgarh",
        "pincode": "492001",
        "gstin": "22AABCB1234F1Z5",
        "invoice_prefix": "SBFW",
        "terms_conditions": (
            "1. 50% advance payment required to confirm the order.\n"
            "2. Balance payment due on completion of work.\n"
            "3. Delivery 15-20 days from confirmation.\n"
            "4. Fitting & installation charges included.\n"
            "5. Warranty of 1 year on workmanship.\n"
            "6. GST as applicable will be charged extra."
        ),
        "show_gst": True,
        "default_gst_rate": 18.0,
        "currency": "₹",
    })
    print("Shop profile updated.")


CUSTOMERS = [
    {
        "name": "Ramesh Patel",
        "mobile": "9876512346",
        "alternate_mobile": "9822012345",
        "email": "ramesh.patel@gmail.com",
        "address": "House No. 45, Shankar Nagar",
        "city": "Raipur",
        "state": "Chhattisgarh",
        "notes": "Prefers teak wood finish.",
    },
    {
        "name": "Sunita Sharma",
        "mobile": "9829034578",
        "email": "sunita.sharma@yahoo.com",
        "address": "Flat 302, Green Heights, VIP Road",
        "city": "Raipur",
        "state": "Chhattisgarh",
        "notes": "Interior design for new apartment.",
    },
    {
        "name": "Amit Verma Constructions",
        "mobile": "9000098765",
        "alternate_mobile": "9000012345",
        "email": "accounts@amitverma.in",
        "address": "Plot 7, Industrial Area, Urla",
        "city": "Raipur",
        "state": "Chhattisgarh",
        "gstin": "22AAACV1234G1Z1",
        "notes": "Commercial contractor - bulk orders.",
    },
    {
        "name": "Priya Deshmukh",
        "mobile": "9898987878",
        "email": "priya.deshmukh@outlook.com",
        "address": "Ward 12, Pandri",
        "city": "Raipur",
        "state": "Chhattisgarh",
        "notes": "Kitchen remodeling.",
    },
    {
        "name": "Vikram Singh Rathore",
        "mobile": "9595951414",
        "email": "vikram.rathore@gmail.com",
        "address": "Villa 9, Civil Lines",
        "city": "Raipur",
        "state": "Chhattisgarh",
        "notes": "Furniture for bedroom & hall.",
    },
]


def make_items(pairs):
    """Convert (area, desc, size, qty, rate, manual) -> list of item dicts.
    If rate is 'LS', amount is treated as manual LS value (qty/rate LS)."""
    items = []
    for area, desc, size, qty, rate, manual in pairs:
        if rate == "LS":
            items.append({
                "area": area, "description": desc, "size": size,
                "qty_raw": "LS", "rate_raw": "LS", "amount": str(manual),
            })
        else:
            items.append({
                "area": area, "description": desc, "size": size,
                "qty_raw": str(qty), "rate_raw": str(rate), "amount": None,
            })
    return items


def seed_invoices():
    today = date.today()

    demo = [
        # customer_name, days_ago, due_days, discount, gst, status, items
        ("Ramesh Patel", 25, 20, 0, 18, "SAVED", make_items([
            ("HALL", "TV Unit", "9' x 6'6\"", 35, 800, None),
            ("HALL", "Crockery Unit", "8' x 2'", 12, 750, None),
            ("HALL", "Shoe Cabinet", "4' x 2'", 4, 900, None),
            ("HALL", "Loft", "10' x 2'", 6, 800, None),
            ("DINING ROOM", "Dining Table", "6' x 3'", 1, 18500, None),
            ("DINING ROOM", "Dining Chair", "-", 6, 2200, None),
        ])),
        ("Sunita Sharma", 18, 25, 500, 18, "SAVED", make_items([
            ("MASTER BEDROOM", "Bed with Storage", "6' x 6'6\"", 1, 32000, None),
            ("MASTER BEDROOM", "Wardrobe", "7' x 6'", 1, "LS", 38500),
            ("MASTER BEDROOM", "Dressing Table", "4' x 2'", 1, 12500, None),
            ("MASTER BEDROOM", "Bedside Table", "2' x 2'", 2, 4500, None),
            ("MASTER BEDROOM", "Headboard", "6' x 4'", 1, 6800, None),
        ])),
        ("Amit Verma Constructions", 40, 15, 0, 18, "SAVED", make_items([
            ("OFFICE", "Workstation Desk", "8' x 2'6\"", 10, 9500, None),
            ("OFFICE", "Office Chair", "-", 12, 3500, None),
            ("OFFICE", "File Cabinet", "3' x 2'", 6, 7800, None),
            ("OFFICE", "Partition Wall", "12' x 8'", 1, "LS", 62000),
            ("SHOP", "Counter", "6' x 3'", 2, 16500, None),
            ("SHOP", "Display Rack", "8' x 2'", 4, 7200, None),
        ])),
        ("Priya Deshmukh", 10, 30, 1000, 18, "SAVED", make_items([
            ("KITCHEN", "Kitchen Cabinet", "10' x 2'", 1, 18500, None),
            ("KITCHEN", "Base Cabinet", "8' x 2'2\"", 1, 16400, None),
            ("KITCHEN", "Wall Cabinet", "9' x 1'8\"", 1, 14200, None),
            ("KITCHEN", "Tall Unit", "7' x 2'", 1, 15800, None),
            ("KITCHEN", "Sink Unit", "6' x 2'", 1, "LS", 21000),
        ])),
        ("Vikram Singh Rathore", 5, 15, 0, 18, "SAVED", make_items([
            ("HALL", "TV Unit", "10' x 2'", 1, 22500, None),
            ("HALL", "Wall Panel", "12' x 4'", 1, 14800, None),
            ("HALL", "Loft", "9' x 2'", 2, 18000, None),
            ("MASTER BEDROOM", "Bed", "6'6\" x 6'", 1, 34500, None),
            ("MASTER BEDROOM", "Wardrobe", "8' x 6'6\"", 1, 41000, None),
            ("MASTER BEDROOM", "TV Unit", "5' x 2'", 1, 9200, None),
        ])),
        ("Ramesh Patel", 2, 30, 0, 18, "DRAFT", make_items([
            ("BATHROOM", "Cabinet", "3' x 2'", 1, "LS", 11500),
            ("BATHROOM", "Mirror", "2' x 3'", 1, 3800, None),
            ("DRESSING ROOM", "Dressing Table", "5' x 2'", 1, 13600, None),
        ])),
    ]

    for customer_name, days_ago, due_days, discount, gst, status, items in demo:
        cust = customer_service.search_customers(customer_name, limit=1)
        if not cust:
            print(f"  !! customer '{customer_name}' not found, skipping")
            continue
        cust = cust[0]

        inv_date = today - timedelta(days=days_ago)
        due_date = inv_date + timedelta(days=due_days)

        created = invoice_service.create_invoice({
            "customer_id": cust.id,
            "invoice_date": inv_date,
            "due_date": None if status == "DRAFT" else due_date,
            "site_address": cust.address or "",
            "discount": discount,
            "gst_rate": gst if status == "SAVED" else 0,
            "status": status,
            "invoice_prefix": business_service.get_invoice_prefix(),
        }, items)
        print(f"  {created.invoice_number}  {customer_name:<22} "
              f"subtotal={float(created.subtotal):>12,.2f} "
              f"grand={float(created.grand_total):>12,.2f}  [{status}]")

    print("Invoices created.")


def seed_payments():
    session_data = [
        # invoice_number, amount, days_ago, mode, reference
        ("SBFW-0001", 40000, 20, "Cash", "Cash-001"),
        ("SBFW-0001", 15000, 5, "UPI", "UPI-889122"),
        ("SBFW-0002", 50000, 10, "Bank Transfer", "NEFT-22931"),
        ("SBFW-0003", 150000, 8, "Cheque", "CHQ-00412"),
        ("SBFW-0004", 30000, 3, "UPI", "UPI-990011"),
    ]
    for number, amount, days_ago, mode, ref in session_data:
        invoices = invoice_service.search_invoices(number, limit=1)
        if not invoices:
            continue
        inv = invoices[0]
        payment_service.add_payment(inv.id, amount, date.today() - timedelta(days=days_ago),
                                    mode, ref)
        print(f"  payment {number:>10}  {amount:>10,.2f}  [{mode}]")
    print("Payments created.")


def main():
    print("Seeding demo data into:", os.environ["FURNITURE_BILL_DATA"])
    seed_shop()
    print("\nAdding customers...")
    for c in CUSTOMERS:
        customer_service.add_customer(c)
        print(f"  + {c['name']}")
    print("\nAdding invoices...")
    seed_invoices()
    print("\nAdding payments...")
    seed_payments()

    totals = customer_service.search_customers(limit=100)
    print(f"\nDone. {len(totals)} customers now in database.")


if __name__ == "__main__":
    main()
