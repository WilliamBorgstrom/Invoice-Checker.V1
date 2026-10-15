"""Generate fictional purchase orders and invoices with deliberate errors.

All data is made up. Run this once to create data/purchase_orders.csv
and data/invoices.csv, then run check_invoices.py.
"""
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)
OUT = Path("data")
OUT.mkdir(exist_ok=True)

VENDORS = ["Nordic Parts AB", "Lindholmen Logistics", "Harbour IT Services",
           "Scandi Tooling", "BlueWave Consulting", "Gothia Office Supply"]
START = date(2026, 1, 5)

# 1. Purchase orders ---------------------------------------------------------
pos = []
for i in range(1, 81):
    pos.append({
        "po_number": f"PO-{1000 + i}",
        "vendor": random.choice(VENDORS),
        "po_amount": round(random.uniform(800, 45000), 2),
        "po_date": START + timedelta(days=random.randint(0, 120)),
    })
po_df = pd.DataFrame(pos)

# 2. Clean invoices (one per PO, paid within terms) ---------------------------
rows = []
for n, po in enumerate(pos, start=1):
    inv_date = po["po_date"] + timedelta(days=random.randint(3, 25))
    rows.append({
        "invoice_id": f"INV-{5000 + n}",
        "po_number": po["po_number"],
        "vendor": po["vendor"],
        "amount": po["po_amount"],
        "currency": "SEK",
        "invoice_date": inv_date,
        "due_date": inv_date + timedelta(days=30),
    })

# 3. Inject errors on purpose -------------------------------------------------
def pick(k):
    return random.sample(range(len(rows)), k)

for i in pick(5):                       # amount differs from PO
    rows[i]["amount"] = round(rows[i]["amount"] * random.choice([1.08, 1.15, 0.9]), 2)
for i in pick(3):                       # missing PO number
    rows[i]["po_number"] = None
for i in pick(3):                       # vendor does not match PO
    rows[i]["vendor"] = random.choice([v for v in VENDORS if v != rows[i]["vendor"]])
for i in pick(2):                       # negative amount
    rows[i]["amount"] = -abs(rows[i]["amount"])
for i in pick(2):                       # due date before invoice date
    rows[i]["due_date"] = rows[i]["invoice_date"] - timedelta(days=5)
for i in pick(2):                       # unknown PO
    rows[i]["po_number"] = f"PO-{9000 + i}"
for i in pick(2):                       # missing currency
    rows[i]["currency"] = None

dupes = [dict(rows[i]) for i in pick(4)]  # exact duplicates, new invoice id
for k, d in enumerate(dupes):
    d["invoice_id"] = f"INV-{6000 + k}"
rows.extend(dupes)

random.shuffle(rows)
pd.DataFrame(rows).to_csv(OUT / "invoices.csv", index=False)
po_df.to_csv(OUT / "purchase_orders.csv", index=False)
print(f"Created {len(rows)} invoices and {len(po_df)} purchase orders in ./data")
