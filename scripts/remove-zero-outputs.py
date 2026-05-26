#!/usr/bin/env python3
"""
Remove zero-lovelace entries from a payment JSON file and write a cleaned copy.
"""

import json
import sys
from pathlib import Path


def usage(exit_code=1):
    out = sys.stdout if exit_code == 0 else sys.stderr
    print(f"Usage: {sys.argv[0]} <input.json> [output.json]", file=out)
    print("  <input.json>      (Required) Payment JSON file to clean", file=out)
    print("  [output.json]     (Optional) Output path. Defaults to <input>.clean.json", file=out)
    print("                    written alongside the input file.", file=out)
    print("  -h, --help        Show this help message and exit", file=out)
    sys.exit(exit_code)


def parse_args():
    positional = []
    for arg in sys.argv[1:]:
        if arg in ("-h", "--help"):
            usage(exit_code=0)
        positional.append(arg)

    if len(positional) < 1 or len(positional) > 2:
        usage()

    input_path = Path(positional[0])
    output_path = Path(positional[1]) if len(positional) == 2 \
        else input_path.with_suffix(".clean.json")
    return input_path, output_path


def main():
    input_path, output_path = parse_args()

    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

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
