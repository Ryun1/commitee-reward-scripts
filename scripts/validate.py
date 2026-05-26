#!/usr/bin/env python3
"""
Validate payment CSV or JSON against the tx view JSON.
Checks that each entry in the payment file matches an output in the tx JSON.

Usage: validate.py <payment-file> <tx-json>
"""

import json
import csv
import sys
from pathlib import Path


def load_outputs(json_path):
    """Load and index outputs.json by address, collecting all amounts per address"""
    with open(json_path, 'r') as f:
        tx_json = json.load(f)
    outputs = tx_json.get('outputs', [])
    # Map address -> list of amounts (an address can have multiple UTxOs)
    outputs_dict = {}
    for output in outputs:
        address = output['address']
        if 'coin' not in output['amount']:
            coin = output['amount']['lovelace']
        else:
            coin = output['amount']['coin']

        outputs_dict.setdefault(address, []).append(coin)

    return outputs_dict


def validate_csv(csv_path, outputs_dict):
    """Validate CSV entries against outputs dictionary"""
    errors = []
    warnings = []
    matches = []

    with open(csv_path, 'r') as f:
        # Skip the header row
        reader = csv.reader(f)
        header = next(reader)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 because of header
            if not row or len(row) < 2:
                warnings.append(f"Row {row_num}: Empty or incomplete row")
                continue

            wallet_address = row[0].strip()
            csv_amount = row[1].strip()

            # Check if address exists in outputs.json
            if wallet_address not in outputs_dict:
                errors.append(f"Row {row_num}: Address NOT FOUND in outputs.json")
                errors.append(f"  Address: {wallet_address}")
                errors.append(f"  CSV Amount: {csv_amount}")
            else:
                json_amounts = outputs_dict[wallet_address]

                # Check if amount matches any UTxO at this address
                if int(csv_amount) in [int(a) for a in json_amounts]:
                    matches.append(f"Row {row_num}: ✓ MATCH - {wallet_address[:20]}... = {csv_amount} lovelace")
                else:
                    errors.append(f"Row {row_num}: AMOUNT MISMATCH")
                    errors.append(f"  Address: {wallet_address}")
                    errors.append(f"  CSV Amount: {csv_amount}")
                    errors.append(f"  JSON Amounts: {json_amounts}")

    return matches, errors, warnings


def check_extra_entries(csv_path, outputs_dict):
    """Check if outputs.json has entries not in CSV"""
    csv_addresses = set()

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            if row and len(row) >= 1:
                csv_addresses.add(row[0].strip())

    json_addresses = set(outputs_dict.keys())
    extra_in_json = json_addresses - csv_addresses

    return extra_in_json


def validate_json(json_input_path, outputs_dict):
    """Validate JSON input entries against outputs dictionary"""
    errors = []
    warnings = []
    matches = []

    with open(json_input_path, 'r') as f:
        entries = json.load(f)

    for entry_num, entry in enumerate(entries, start=1):
        if 'address' not in entry or 'lovelace_amount' not in entry:
            warnings.append(f"Entry {entry_num}: Missing 'address' or 'lovelace_amount' field, skipping")
            continue

        wallet_address = entry['address'].strip()
        input_amount = entry['lovelace_amount']

        if wallet_address not in outputs_dict:
            errors.append(f"Entry {entry_num}: Address NOT FOUND in outputs.json")
            errors.append(f"  Address: {wallet_address}")
            errors.append(f"  Input Amount: {input_amount}")
        else:
            json_amounts = outputs_dict[wallet_address]

            if int(input_amount) in [int(a) for a in json_amounts]:
                matches.append(f"Entry {entry_num}: ✓ MATCH - {wallet_address[:20]}... = {input_amount} lovelace")
            else:
                errors.append(f"Entry {entry_num}: AMOUNT MISMATCH")
                errors.append(f"  Address: {wallet_address}")
                errors.append(f"  Input Amount: {input_amount}")
                errors.append(f"  JSON Amounts: {json_amounts}")

    return matches, errors, warnings


def check_extra_entries_json(json_input_path, outputs_dict):
    """Check if outputs.json has entries not in the JSON input file"""
    with open(json_input_path, 'r') as f:
        entries = json.load(f)

    input_addresses = {entry['address'].strip() for entry in entries if 'address' in entry}
    json_addresses = set(outputs_dict.keys())
    extra_in_json = json_addresses - input_addresses

    return extra_in_json


def usage():
    print(f"Usage: {sys.argv[0]} <payment-file> <tx-json>", file=sys.stderr)
    print("  <payment-file>  Payment details file (.csv or .json)", file=sys.stderr)
    print("  <tx-json>       cardano-cli tx view JSON (e.g. bulk-payment.tx.json)", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) != 3:
        usage()

    input_path = Path(sys.argv[1])
    json_path = Path(sys.argv[2])

    # Check if files exist
    if not input_path.exists():
        print(f"❌ ERROR: Payment file not found: {input_path}")
        sys.exit(1)

    if not json_path.exists():
        print(f"❌ ERROR: JSON file not found: {json_path}")
        sys.exit(1)

    # Detect input file type
    file_ext = input_path.suffix.lower()
    if file_ext not in ('.csv', '.json'):
        print(f"❌ ERROR: Unsupported file type '{file_ext}' (expected .csv or .json)")
        sys.exit(1)

    print("=" * 80)
    print("PAYMENT VALIDATION REPORT")
    print("=" * 80)
    print(f"Input File: {input_path}")
    print(f"JSON File:  {json_path}")
    print("=" * 80)

    # Load outputs.json
    try:
        outputs_dict = load_outputs(json_path)
        print(f"\n✓ Loaded {len(outputs_dict)} entries from outputs.json")
    except Exception as e:
        print(f"❌ ERROR loading outputs.json: {e}")
        sys.exit(1)

    # Validate input file
    try:
        if file_ext == '.json':
            print("Detected JSON input file")
            matches, errors, warnings = validate_json(input_path, outputs_dict)
            extra_in_json = check_extra_entries_json(input_path, outputs_dict)
        else:
            print("Detected CSV input file")
            matches, errors, warnings = validate_csv(input_path, outputs_dict)
            extra_in_json = check_extra_entries(input_path, outputs_dict)
    except Exception as e:
        print(f"❌ ERROR validating payment file: {e}")
        sys.exit(1)

    # Print results
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)

    if matches:
        print(f"\n✓ MATCHES ({len(matches)}):")
        for match in matches:
            print(f"  {match}")

    if warnings:
        print(f"\n⚠ WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  {warning}")

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"  {error}")

    if extra_in_json:
        print(f"\n⚠ EXTRA ENTRIES IN JSON NOT IN CSV ({len(extra_in_json)}):")
        for addr in sorted(extra_in_json):
            print(f"  {addr} = {outputs_dict[addr]} lovelace")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_input_rows = len(matches) + (len(errors) // 3)  # Approximate
    print(f"Entries Processed: {total_input_rows}")
    print(f"Matches: {len(matches)}")
    print(f"Errors: {len([e for e in errors if 'Row' in e or 'Entry' in e])}")
    print(f"Warnings: {len(warnings)}")
    print(f"Extra in JSON: {len(extra_in_json)}")

    # Exit code
    if errors:
        print("\n❌ VALIDATION FAILED - Errors found")
        sys.exit(1)
    elif warnings or extra_in_json:
        print("\n⚠ VALIDATION PASSED WITH WARNINGS")
        sys.exit(0)
    else:
        print("\n✅ VALIDATION PASSED - All entries match!")
        sys.exit(0)


if __name__ == "__main__":
    main()