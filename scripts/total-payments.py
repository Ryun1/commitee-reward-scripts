#!/usr/bin/env python3
"""
Report stats on a committee rewards payment JSON file:
total entries, unique addresses, total ADA, and per-committee/month breakdowns.

Usage: total-payments.py <payment.json>
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

LOVELACE_PER_ADA = 1_000_000


def fmt_ada(lovelace):
    return f"{lovelace / LOVELACE_PER_ADA:,.6f} ADA"


def fmt_lovelace(lovelace):
    return f"{lovelace:,} lovelace"


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <payment.json>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r") as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        print("ERROR: Expected a JSON array at the top level", file=sys.stderr)
        sys.exit(1)

    total_lovelace = 0
    address_totals = defaultdict(int)
    address_counts = Counter()
    committee_totals = defaultdict(int)
    committee_counts = Counter()
    month_counts = Counter()
    amount_counts = Counter()
    amounts = []

    for entry in entries:
        amount = entry["lovelace_amount"]
        address = entry["address"]
        meta = entry.get("metadata", {})

        total_lovelace += amount
        address_totals[address] += amount
        address_counts[address] += 1
        amount_counts[amount] += 1
        amounts.append(amount)

        committee = meta.get("committee", "<no committee>")
        committee_totals[committee] += amount
        committee_counts[committee] += 1

        year = meta.get("reward_year", "?")
        month = meta.get("reward_month", "?")
        month_counts[f"{year} {month}"] += 1

    duplicates = {a: c for a, c in address_counts.items() if c > 1}

    print("=" * 80)
    print(f"PAYMENT STATS: {input_path}")
    print("=" * 80)

    print("\nTOTALS")
    print(f"  Entries:           {len(entries):,}")
    print(f"  Unique addresses:  {len(address_totals):,}")
    print(f"  Total:             {fmt_lovelace(total_lovelace)}  ({fmt_ada(total_lovelace)})")
    print(f"  Min payment:       {fmt_ada(min(amounts))}")
    print(f"  Max payment:       {fmt_ada(max(amounts))}")
    print(f"  Mean payment:      {fmt_ada(total_lovelace // len(entries))}")

    print(f"\nBY COMMITTEE ({len(committee_totals)})")
    for committee, total in sorted(committee_totals.items(), key=lambda kv: -kv[1]):
        count = committee_counts[committee]
        print(f"  {count:>3}  {fmt_ada(total):>22}  {committee}")

    print(f"\nBY PAYMENT AMOUNT ({len(amount_counts)})")
    for amount, count in sorted(amount_counts.items(), key=lambda kv: -kv[0]):
        print(f"  {count:>3}  {fmt_ada(amount):>22}")

    print(f"\nBY REWARD MONTH ({len(month_counts)})")
    for period, count in sorted(month_counts.items()):
        print(f"  {count:>3}  {period}")

    if duplicates:
        print(f"\nADDRESSES RECEIVING MULTIPLE PAYMENTS ({len(duplicates)})")
        for address, count in sorted(duplicates.items(), key=lambda kv: -kv[1]):
            total = address_totals[address]
            print(f"  {count}x  {fmt_ada(total):>22}  {address}")


if __name__ == "__main__":
    main()
