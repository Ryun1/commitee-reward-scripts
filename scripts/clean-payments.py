#!/usr/bin/env python3
"""
Remove zero-lovelace entries from a payment JSON file and write a cleaned copy.

Usage: clean-payments.py <input.json> [output.json]

If output.json is omitted, writes alongside the input as <name>.clean.json.
"""

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} <input.json> [output.json]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(sys.argv[2]) if len(sys.argv) == 3 \
        else input_path.with_suffix(".clean.json")

    with open(input_path, "r") as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        print("ERROR: Expected a JSON array at the top level", file=sys.stderr)
        sys.exit(1)

    kept = [e for e in entries if e.get("lovelace_amount", 0) > 0]
    removed = len(entries) - len(kept)

    with open(output_path, "w") as f:
        json.dump(kept, f, indent=2)
        f.write("\n")

    print(f"Input:   {input_path}  ({len(entries)} entries)")
    print(f"Output:  {output_path}  ({len(kept)} entries)")
    print(f"Removed: {removed} zero-lovelace entries")


if __name__ == "__main__":
    main()
