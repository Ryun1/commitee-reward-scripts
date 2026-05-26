#!/bin/bash
##################################################

# Default configuration values

##################################################

# Exit immediately if a command exits with a non-zero status,
# treat unset variables as an error, and fail if any command in a pipeline fails
set -euo pipefail

# Colors
#BLACK='\033[0;30m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BRIGHTWHITE='\033[0;37;1m'
NC='\033[0m'

# Check if cardano-cli is installed
if ! command -v cardano-cli >/dev/null 2>&1; then
  echo "Error: cardano-cli is not installed or not in your PATH." >&2
  exit 1
fi

# Check if jq is installed (required for JSON input)
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is not installed or not in your PATH." >&2
  exit 1
fi

# Usage message

usage() {
    echo "Usage: $0 <payment address> <payment details file> [--metadata-file <jsonld-file>]"
    echo "Options:"
    echo "  <payment address>                   (Required) Cardano payment address in Bech32"
    echo "  <payment details file>              (Required) Path to a CSV or JSON file with payment details"
    echo "                                        CSV format: address,lovelace_amount,..."
    echo "                                        JSON format: [{\"address\": \"...\", \"lovelace_amount\": 123, ...}]"
    echo "  --metadata-file <jsonld-file>       (Optional) Path to the JSON metadata file"
    echo "  -h, --help                           Show this help message and exit"
    exit 1
}

# Initialize variables with defaults
payment_address_input=""
payment_details_list_file=""
script_dir=$(dirname "$(realpath "$0")")
# Optional variables
metadata_file_input=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --metadata-file)
            if [ -n "${2:-}" ]; then
                metadata_file_input="$2"
                echo -e "${BLUE}Using metadata file: ${NC}$metadata_file_input"
                shift 2
            else
                echo -e "${RED}Error: --metadata-file requires a value${NC}" >&2
                usage
            fi
            ;;
        -h|--help)
            usage
            ;;
        *)
            if [ -z "$payment_address_input" ]; then
                payment_address_input="$1"
                echo -e "${BLUE}Using payment address:${NC} $payment_address_input"
            elif [ -z "$payment_details_list_file" ]; then
                payment_details_list_file="$1"
                echo -e "${BLUE}Using payment details file:${NC} $payment_details_list_file"
            else
                echo -e "${RED}Error: Unexpected argument: $1${NC}" >&2
                usage
            fi
            shift
            ;;
    esac
done

# If no payment address provided, show usage
# if [ -z "$payment_address_input" ]; then
#     echo -e "${RED}Error: No payment address specified${NC}" >&2
#     usage
# fi

# If no payment details file provided, show usage
if [ -z "$payment_details_list_file" ]; then
    echo -e "${RED}Error: No payment details file specified${NC}" >&2
    usage
fi

# Check if payment details file exists
if [ ! -f "$payment_details_list_file" ]; then
    echo -e "${RED}Error: Payment details file not found: $payment_details_list_file${NC}" >&2
    exit 1
fi

# Check if optional metadata file exists
if [ "$metadata_file_input" != "" ] && [ ! -f "$metadata_file_input" ]; then
    echo -e "${RED}Error: Metadata file not found: $metadata_file_input${NC}" >&2
    exit 1
fi


export PAYMENT_ADDR='addr1qx93k28kzzu4fng49cfcj8w7m8px36wf9z8j94638lu8cw574gazl7xgwlxg4uxe4ytwnttj8qw489waumt82gx5jdtqwh8hn0'

utxo_list=$(cardano-cli conway query utxo \
  --mainnet \
  --socket-path "$CARDANO_NODE_SOCKET_PATH" \
  --address "$PAYMENT_ADDR" )

echo "UTxO list for address $PAYMENT_ADDR:$utxo_list"

read -p "Which utxo you want to use for the transaction? (format: txhash#txix): " selected_utxo_1
read -p "Select a second utxo" selected_utxo_2

# Extract wallet address and lovelace amount to build --tx-out args
# Supports CSV and JSON input files
file_ext="${payment_details_list_file##*.}"

if [[ "$file_ext" == "json" ]]; then
    echo -e "${BLUE}Detected JSON input file${NC}"
    export TX_OUT=$(jq -r '.[] | "--tx-out " + .address + "+" + (.lovelace_amount | tostring)' "$payment_details_list_file" | tr '\n' ' ' | sed 's/^ *//;s/ *$//')
elif [[ "$file_ext" == "csv" ]]; then
    echo -e "${BLUE}Detected CSV input file${NC}"
    export TX_OUT=$(tail -n +3 "$payment_details_list_file" | tr -d '\r\t' | awk -F',' '{print "--tx-out " $1 "+" $2}' | tr '\n' ' ' | sed 's/^ *//;s/ *$//')
else
    echo -e "${RED}Error: Unsupported file type: .$file_ext (expected .csv or .json)${NC}" >&2
    exit 1
fi

# Calculate total sum of output amounts
if [[ "$file_ext" == "json" ]]; then
    total_lovelace=$(jq '[.[].lovelace_amount] | add' "$payment_details_list_file")
elif [[ "$file_ext" == "csv" ]]; then
    total_lovelace=$(tail -n +3 "$payment_details_list_file" | tr -d '\r\t' | awk -F',' '{sum += $2} END {printf "%.0f", sum}')
fi
total_ada=$(echo "scale=6; $total_lovelace / 1000000" | bc)

# Display what will be sent
echo "Transaction outputs:"
echo "$TX_OUT"
echo -e "${GREEN}Total output amount: ${BRIGHTWHITE}$total_lovelace lovelace ${NC}(${BRIGHTWHITE}$total_ada ADA${NC})"

# Build and execute the transaction
metadata_args=""
if [ -n "$metadata_file_input" ]; then
    metadata_args="--metadata-json-file $metadata_file_input"
fi

output_dir=$(dirname "$(realpath "$payment_details_list_file")")
tx_file="$output_dir/bulk-payment.tx"
tx_view_file="$output_dir/bulk-payment.tx.json"
transformed_tx_file="$output_dir/bulk-payment-transformed.tx"
echo -e "${BLUE}Writing tx files to:${NC} $output_dir"

cardano-cli conway transaction build \
  --socket-path "$CARDANO_NODE_SOCKET_PATH" \
  --mainnet \
  --tx-in "$selected_utxo_1" \
  --tx-in "$selected_utxo_2" \
  $TX_OUT \
  --change-address "$PAYMENT_ADDR" \
  $metadata_args \
  --out-file "$tx_file"


cardano-cli debug transaction  view \
    --tx-file "$tx_file" \
    --out-file "$tx_view_file"

echo -e "${BLUE}Transforming tx for hardware wallet signing:${NC} $transformed_tx_file"
cardano-hw-cli transaction transform \
    --tx-file "$tx_file" \
    --out-file "$transformed_tx_file"