"""Check invoices against purchase orders and produce an Excel report.

Checks:
  1. Missing required fields
  2. Duplicate invoices (same vendor, PO, amount and date)
  3. Unknown purchase order
  4. Vendor does not match the purchase order
  5. Amount differs from the purchase order (tolerance configurable)
  6. Negative or zero amount
  7. Due date earlier than invoice date

Usage:  python check_invoices.py [--tolerance 0.02]
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REQUIRED = ["invoice_id", "po_number", "vendor", "amount", "currency",
            "invoice_date", "due_date"]


def load(data_dir: Path):
    inv = pd.read_csv(data_dir / "invoices.csv", parse_dates=["invoice_date", "due_date"])
    po = pd.read_csv(data_dir / "purchase_orders.csv", parse_dates=["po_date"])
    return inv, po


def run_checks(inv: pd.DataFrame, po: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    """Return one row per problem found (an invoice can appear several times)."""
    flags = []

    def flag(mask, issue, detail=None):
        for idx in inv.index[mask]:
            text = detail(inv.loc[idx]) if detail else ""
            flags.append({"invoice_id": inv.at[idx, "invoice_id"], "issue": issue, "detail": text})

    # 1. missing fields
    for col in REQUIRED:
        flag(inv[col].isna(), "Missing field", lambda r, c=col: f"{c} is empty")

    # 2. duplicates (keep first occurrence, flag the rest)
    key = ["vendor", "po_number", "amount", "invoice_date"]
    dup = inv.duplicated(subset=key, keep="first") & inv["po_number"].notna()
    flag(dup, "Possible duplicate", lambda r: "Same vendor, PO, amount and date as an earlier invoice")

    # join with POs
    merged = inv.merge(po, on="po_number", how="left", suffixes=("", "_po"))
    merged.index = inv.index
    has_po = inv["po_number"].notna()

    # 3. unknown PO
    flag(has_po & merged["po_amount"].isna(), "Unknown PO", lambda r: f"{r['po_number']} not found")

    known = merged["po_amount"].notna()
    # 4. vendor mismatch
    flag(known & (merged["vendor"] != merged["vendor_po"]), "Vendor mismatch",
         lambda r: f"Invoice vendor differs from PO vendor ({merged.at[r.name, 'vendor_po']})")

    # 5. amount mismatch
    diff = (merged["amount"] - merged["po_amount"]) / merged["po_amount"]
    flag(known & (diff.abs() > tolerance) & (merged["amount"] > 0), "Amount differs from PO",
         lambda r: f"{diff[r.name]:+.1%} vs PO ({merged.at[r.name, 'po_amount']:,.2f})")

    # 6. negative / zero amounts
    flag(inv["amount"] <= 0, "Negative or zero amount", lambda r: f"amount = {r['amount']:,.2f}")

    # 7. dates
    flag(inv["due_date"] < inv["invoice_date"], "Due date before invoice date",
         lambda r: f"{r['invoice_date']:%Y-%m-%d} -> {r['due_date']:%Y-%m-%d}")

    return pd.DataFrame(flags, columns=["invoice_id", "issue", "detail"])


def write_report(inv, flags, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    flagged_ids = set(flags["invoice_id"])
    clean = inv[~inv["invoice_id"].isin(flagged_ids)]
    flagged = inv[inv["invoice_id"].isin(flagged_ids)].merge(
        flags.groupby("invoice_id")["issue"].agg("; ".join).rename("issues"),
        on="invoice_id", how="left")

    by_issue = flags["issue"].value_counts().rename_axis("issue").reset_index(name="count")
    summary = pd.DataFrame({
        "metric": ["Invoices checked", "Invoices flagged", "Invoices clean",
                   "Clean rate", "Total value checked (SEK)", "Value flagged (SEK)"],
        "value": [len(inv), len(flagged), len(clean), f"{len(clean) / len(inv):.1%}",
                  f"{inv['amount'].sum():,.0f}", f"{flagged['amount'].sum():,.0f}"],
    })

    path = out_dir / "invoice_check_report.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False)
        by_issue.to_excel(xw, sheet_name="Summary", index=False, startrow=len(summary) + 3)
        flags.to_excel(xw, sheet_name="Flags", index=False)
        flagged.to_excel(xw, sheet_name="Flagged invoices", index=False)
        clean.to_excel(xw, sheet_name="Clean invoices", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(width + 3, 60)

    fig, ax = plt.subplots(figsize=(8, 4))
    by_issue.sort_values("count").plot.barh(x="issue", y="count", ax=ax, legend=False, color="#1d6b75")
    ax.set_title("Invoice problems by type")
    ax.set_xlabel("Number of flags")
    ax.set_ylabel("")
    plt.tight_layout()
    fig.savefig(out_dir / "issues_by_type.png", dpi=150)
    return path, summary, by_issue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="output")
    ap.add_argument("--tolerance", type=float, default=0.02,
                    help="allowed difference vs PO amount (0.02 = 2%%)")
    args = ap.parse_args()

    inv, po = load(Path(args.data))
    flags = run_checks(inv, po, args.tolerance)
    path, summary, by_issue = write_report(inv, flags, Path(args.out))

    print(summary.to_string(index=False, header=False))
    print("\nProblems by type:")
    print(by_issue.to_string(index=False))
    print(f"\nReport written to {path}")


if __name__ == "__main__":
    main()
