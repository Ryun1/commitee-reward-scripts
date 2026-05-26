#!/usr/bin/env python3
"""
Report stats and sanity checks on a committee rewards payment JSON file:
sanity findings (unusual amounts, zero entries, duplicates), totals,
per-committee/month breakdowns, and addresses receiving multiple payments.

Usage: total-payments.py <payment.json>
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LOVELACE_PER_ADA = 1_000_000

EXPECTED_AMOUNTS_ADA = (499, 500, 999, 1000)
EXPECTED_AMOUNTS_LOVELACE = frozenset(a * LOVELACE_PER_ADA for a in EXPECTED_AMOUNTS_ADA)


def fmt_ada(lovelace):
    return f"{lovelace / LOVELACE_PER_ADA:,.6f} ADA"


def fmt_lovelace(lovelace):
    return f"{lovelace:,} lovelace"


def period_str(meta):
    return f"{meta.get('reward_year', '?')} {meta.get('reward_month', '?')}"


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

    unusual_amounts = []      # (idx, amount, committee, period)
    zero_lovelace = []        # (idx, committee, period)
    claim_id_index = defaultdict(list)              # claim_id -> [idx, ...]
    period_address_index = defaultdict(list)        # (addr, committee, year, month) -> [idx, ...]

    for i, entry in enumerate(entries, start=1):
        amount = entry["lovelace_amount"]
        address = entry["address"]
        meta = entry.get("metadata", {})
        committee = meta.get("committee", "<no committee>")
        period = period_str(meta)

        total_lovelace += amount
        address_totals[address] += amount
        address_counts[address] += 1
        amount_counts[amount] += 1
        amounts.append(amount)

        committee_totals[committee] += amount
        committee_counts[committee] += 1
        month_counts[period] += 1

        if amount == 0:
            zero_lovelace.append((i, committee, period))
        elif amount not in EXPECTED_AMOUNTS_LOVELACE:
            unusual_amounts.append((i, amount, committee, period))

        claim_id = meta.get("claim_id")
        if claim_id is not None:
            claim_id_index[claim_id].append(i)

        year = meta.get("reward_year")
        month = meta.get("reward_month")
        if committee and year is not None and month is not None:
            period_address_index[(address, committee, year, month)].append(i)

    duplicates = {a: c for a, c in address_counts.items() if c > 1}
    duplicate_claim_ids = {cid: ixs for cid, ixs in claim_id_index.items() if len(ixs) > 1}
    duplicate_periods = {key: ixs for key, ixs in period_address_index.items() if len(ixs) > 1}

    nonzero_amounts = [a for a in amounts if a > 0]
    expected_str = ", ".join(str(a) for a in EXPECTED_AMOUNTS_ADA)

    print("=" * 80)
    print(f"PAYMENT STATS: {input_path}")
    print("=" * 80)

    print("\nSANITY CHECK")

    def mark(count, level):
        # Pad [OK] to the same width as [WARN]/[FAIL] so labels line up.
        return f"[{level}]" if count > 0 else "[OK]  "

    checks = [
        ("[OK]  ", "Entries",                                       len(entries),               ""),
        (mark(len(unusual_amounts), "WARN"),    "Unusual amounts",  len(unusual_amounts),       f"     (expected: {expected_str} ADA)"),
        (mark(len(zero_lovelace), "WARN"),      "Zero-lovelace entries",                len(zero_lovelace),         ""),
        (mark(len(duplicate_claim_ids), "FAIL"), "Duplicate claim_ids",                  len(duplicate_claim_ids),   ""),
        (mark(len(duplicate_periods), "FAIL"),   "Duplicate (address, committee, month) tuples", len(duplicate_periods), ""),
    ]
    label_width = max(len(label) for _, label, _, _ in checks)
    for marker, label, count, suffix in checks:
        print(f"  {marker} {label:<{label_width}}  {count:>4}{suffix}")

    if unusual_amounts:
        print("\n  Unusual amounts:")
        for idx, amount, committee, period in unusual_amounts:
            print(f"    #{idx:<4} {fmt_ada(amount):>22}  {period}  {committee}")

    if zero_lovelace:
        print("\n  Zero-lovelace entries:")
        for idx, committee, period in zero_lovelace:
            print(f"    #{idx:<4} {period}  {committee}")

    if duplicate_claim_ids:
        print("\n  Duplicate claim_ids:")
        for cid, ixs in sorted(duplicate_claim_ids.items()):
            print(f"    claim_id={cid}  entries: {', '.join('#' + str(i) for i in ixs)}")

    if duplicate_periods:
        print("\n  Duplicate (address, committee, month) tuples:")
        for (addr, committee, year, month), ixs in duplicate_periods.items():
            print(f"    entries: {', '.join('#' + str(i) for i in ixs)}")
            print(f"      address:   {addr}")
            print(f"      committee: {committee}")
            print(f"      period:    {year} {month}")

    print("\nTOTALS")
    print(f"  Entries:           {len(entries):,}")
    print(f"  Unique addresses:  {len(address_totals):,}")
    print(f"  Total:             {fmt_lovelace(total_lovelace)}  ({fmt_ada(total_lovelace)})")
    print(f"  Min payment:       {fmt_ada(min(amounts))}")
    print(f"  Max payment:       {fmt_ada(max(amounts))}")
    print(f"  Mean payment:      {fmt_ada(total_lovelace // len(entries))}")
    if zero_lovelace and nonzero_amounts:
        nonzero_mean = sum(nonzero_amounts) // len(nonzero_amounts)
        print(f"  Mean (excl. 0):    {fmt_ada(nonzero_mean)}")
    print(f"  Median payment:    {fmt_ada(int(median(amounts)))}")

    print(f"\nBY COMMITTEE ({len(committee_totals)})")
    for committee, total in sorted(committee_totals.items(), key=lambda kv: -kv[1]):
        count = committee_counts[committee]
        print(f"  {count:>3}  {fmt_ada(total):>22}  {committee}")

    print(f"\nBY PAYMENT AMOUNT ({len(amount_counts)})")
    for amount, count in sorted(amount_counts.items(), key=lambda kv: -kv[0]):
        tag = "  (unusual)" if amount not in EXPECTED_AMOUNTS_LOVELACE else ""
        print(f"  {count:>3}  {fmt_ada(amount):>22}{tag}")

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
