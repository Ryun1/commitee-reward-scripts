#!/usr/bin/env python3
"""
Validate payment CSV or JSON against the tx view JSON.
Checks that every entry in the payment file is matched by exactly one output
in the tx JSON, including correct counts for addresses receiving multiple
payments.

Usage: validate.py <payment-file> <tx-json> [--change-address <addr>]
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


LOVELACE_PER_ADA = 1_000_000


def fmt_ada(lovelace):
    return f"{int(lovelace) / LOVELACE_PER_ADA:,.6f} ADA"


def load_tx_outputs(tx_json_path):
    """Return address -> list of lovelace amounts from the tx view JSON."""
    with open(tx_json_path, "r") as f:
        tx_json = json.load(f)
    outputs = defaultdict(list)
    for output in tx_json.get("outputs", []):
        amount = output["amount"]
        coin = amount.get("lovelace", amount.get("coin"))
        outputs[output["address"]].append(int(coin))
    return outputs


def load_payment_entries(path):
    """Return a list of (address, lovelace_amount, label) from a CSV or JSON file."""
    ext = path.suffix.lower()
    entries = []

    if ext == ".json":
        with open(path, "r") as f:
            raw = json.load(f)
        for i, entry in enumerate(raw, start=1):
            if "address" not in entry or "lovelace_amount" not in entry:
                entries.append((None, None, f"Entry {i}"))
                continue
            entries.append((
                entry["address"].strip(),
                int(entry["lovelace_amount"]),
                f"Entry {i}",
            ))
    elif ext == ".csv":
        with open(path, "r") as f:
            reader = csv.reader(f)
            # create-tx.sh skips 2 header rows for CSVs (tail -n +3) — match that.
            next(reader, None)
            next(reader, None)
            for row_num, row in enumerate(reader, start=3):
                if not row or len(row) < 2:
                    entries.append((None, None, f"Row {row_num}"))
                    continue
                entries.append((
                    row[0].strip(),
                    int(row[1].strip()),
                    f"Row {row_num}",
                ))
    else:
        raise ValueError(f"Unsupported file type '{ext}' (expected .csv or .json)")

    return entries


def validate(entries, tx_outputs):
    """Consume tx outputs to match payment entries. Returns (matches, errors, warnings, remaining)."""
    matches, errors, warnings = [], [], []
    # Copy so we can pop as we consume — leftover entries become the "extras" report.
    remaining = {addr: list(amounts) for addr, amounts in tx_outputs.items()}

    for address, amount, label in entries:
        if address is None:
            warnings.append(f"{label}: empty or missing fields, skipped")
            continue

        available = remaining.get(address)
        if not available:
            errors.append(
                f"{label}: address NOT FOUND (or already consumed) in tx — "
                f"{address}  expected {fmt_ada(amount)}"
            )
            continue

        if amount in available:
            available.remove(amount)
            matches.append(f"{label}: ✓ {address[:20]}... = {fmt_ada(amount)}")
            if not available:
                del remaining[address]
        else:
            errors.append(
                f"{label}: AMOUNT MISMATCH at {address}  "
                f"expected {fmt_ada(amount)}  available {[fmt_ada(a) for a in available]}"
            )

    return matches, errors, warnings, remaining


def parse_args():
    args = sys.argv[1:]
    change_address = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == "--change-address":
            if i + 1 >= len(args):
                usage()
            change_address = args[i + 1]
            i += 2
        elif args[i] in ("-h", "--help"):
            usage(exit_code=0)
        else:
            positional.append(args[i])
            i += 1

    if len(positional) != 2:
        usage()

    return Path(positional[0]), Path(positional[1]), change_address


def usage(exit_code=1):
    out = sys.stdout if exit_code == 0 else sys.stderr
    print(f"Usage: {sys.argv[0]} <payment-file> <tx-json> [--change-address <addr>]", file=out)
    print("  <payment-file>       Payment details file (.csv or .json)", file=out)
    print("  <tx-json>            cardano-cli tx view JSON (e.g. bulk-payment.tx.json)", file=out)
    print("  --change-address     Optional. Tx output to this address is treated as change,", file=out)
    print("                       not flagged as an unmatched extra.", file=out)
    sys.exit(exit_code)


def main():
    input_path, tx_path, change_address = parse_args()

    if not input_path.exists():
        print(f"❌ ERROR: Payment file not found: {input_path}")
        sys.exit(1)
    if not tx_path.exists():
        print(f"❌ ERROR: Tx JSON file not found: {tx_path}")
        sys.exit(1)

    print("=" * 80)
    print("PAYMENT VALIDATION REPORT")
    print("=" * 80)
    print(f"Payment file: {input_path}")
    print(f"Tx JSON:      {tx_path}")
    if change_address:
        print(f"Change addr:  {change_address}")
    print("=" * 80)

    try:
        tx_outputs = load_tx_outputs(tx_path)
        total_tx_outputs = sum(len(v) for v in tx_outputs.values())
        print(f"\n✓ Loaded {total_tx_outputs} tx outputs across {len(tx_outputs)} addresses")
    except Exception as e:
        print(f"❌ ERROR loading tx JSON: {e}")
        sys.exit(1)

    try:
        entries = load_payment_entries(input_path)
    except Exception as e:
        print(f"❌ ERROR loading payment file: {e}")
        sys.exit(1)
    print(f"✓ Loaded {len(entries)} payment entries")

    matches, errors, warnings, remaining = validate(entries, tx_outputs)

    # Split leftover tx outputs into expected change vs unexpected extras.
    change_outputs = {}
    extra_outputs = {}
    if change_address and change_address in remaining:
        change_outputs[change_address] = remaining.pop(change_address)
    extra_outputs = remaining

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    if matches:
        print(f"\n✓ MATCHES ({len(matches)}):")
        for m in matches:
            print(f"  {m}")

    if warnings:
        print(f"\n⚠ WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  {w}")

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  {e}")

    if change_outputs:
        print(f"\nℹ CHANGE OUTPUTS ({sum(len(v) for v in change_outputs.values())}):")
        for addr, amounts in change_outputs.items():
            for a in amounts:
                print(f"  {addr} = {fmt_ada(a)}")

    if extra_outputs:
        total_extra = sum(len(v) for v in extra_outputs.values())
        print(f"\n⚠ UNMATCHED TX OUTPUTS ({total_extra}):")
        for addr in sorted(extra_outputs):
            for a in extra_outputs[addr]:
                print(f"  {addr} = {fmt_ada(a)}")
        if not change_address and len(extra_outputs) == 1:
            only_addr = next(iter(extra_outputs))
            print(
                f"\n  Hint: if {only_addr[:20]}... is your change address, "
                f"re-run with --change-address {only_addr}"
            )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Payment entries:   {len(entries)}")
    print(f"Matches:           {len(matches)}")
    print(f"Errors:            {len(errors)}")
    print(f"Warnings:          {len(warnings)}")
    print(f"Change outputs:    {sum(len(v) for v in change_outputs.values())}")
    print(f"Unmatched extras:  {sum(len(v) for v in extra_outputs.values())}")

    if errors or extra_outputs:
        print("\n❌ VALIDATION FAILED")
        sys.exit(1)
    if warnings:
        print("\n⚠ VALIDATION PASSED WITH WARNINGS")
        sys.exit(0)
    print("\n✅ VALIDATION PASSED — all entries match")
    sys.exit(0)


if __name__ == "__main__":
    main()
