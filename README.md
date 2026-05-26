# Committee Reward Scripts

Tooling for preparing, validating, and reporting on Cardano committee reward
payouts. Used to build a single bulk-payment transaction from a list of
recipients (CSV or JSON) and verify the built transaction matches the source
data before signing.

## Repository layout

- `scripts/` — the tooling (see below).
- `payments/<YYYY-MM-DD>/` — one folder per payout. Holds the source payment
  file, the transaction artefacts, and a payout-specific README with the
  submitted txid.

## Scripts

All scripts accept `-h` / `--help`.

### `scripts/total-payments.py`

Reports stats and sanity checks on a payment JSON file. Flags amounts outside
the expected set (499, 500, 999, 1000 ADA), zero-lovelace rows, duplicate
`claim_id`s, and duplicate `(address, committee, reward_month)` tuples. Useful
to eyeball the source file before building a tx. Always exits 0.

```
python3 scripts/total-payments.py <payment.json>
```

### `scripts/remove-zero-lovelace-outputs.py`

Strips zero-lovelace rows from a payment JSON file and writes
`<name>.clean.json` alongside the input. Run this before `create-tx.sh` if
`total-payments.py` reports zero-lovelace entries.

```
python3 scripts/remove-zero-lovelace-outputs.py <input.json> [output.json]
```

### `scripts/create-tx.sh`

Builds the bulk-payment transaction. Queries UTxOs for the source wallet,
prompts for which to spend, then writes `bulk-payment.tx`,
`bulk-payment.tx.json`, and a hardware-wallet-transformed variant
(`bulk-payment-transformed.tx`) alongside the payment file.

```
./scripts/create-tx.sh <payment-address> <payment-file> [--metadata-file <jsonld>]
```

### `scripts/validate.py`

Cross-checks every row in the payment file against the built tx outputs (from
`bulk-payment.tx.json`). Errors out if any address or amount is missing,
mismatched, or appears in the tx but not in the source file. Pass
`--change-address` so the change output is not flagged as an unmatched extra.

```
python3 scripts/validate.py <payment-file> <tx-json> --change-address <addr>
```

## Typical workflow

1. Drop the payment file into `payments/<date>/committee-rewards.json`.
2. Review sanity findings:
   `python3 scripts/total-payments.py payments/<date>/committee-rewards.json`
3. If any zero-lovelace rows are reported, clean them:
   `python3 scripts/remove-zero-lovelace-outputs.py payments/<date>/committee-rewards.json`
4. Build the transaction:
   `./scripts/create-tx.sh <payment-addr> payments/<date>/committee-rewards.clean.json --metadata-file payments/<date>/metadata.json`
5. Validate the built tx against the cleaned payment file:
   `python3 scripts/validate.py payments/<date>/committee-rewards.clean.json payments/<date>/bulk-payment.tx.json --change-address <payment-addr>`
6. Sign `bulk-payment-transformed.tx` with the hardware wallet and submit.
7. Record the resulting txid in `payments/<date>/README.md`.

## Requirements

- `cardano-cli` (Conway era)
- `cardano-hw-cli` (for the hardware-wallet transaction transform step)
- `jq`
- Python 3
- A running cardano-node, with `CARDANO_NODE_SOCKET_PATH` set
