#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 get_subscription.py

shopt -s nullglob
# pick most-recent subscription_* file by mtime (safe even when filenames don't match today)
latest_json="$(ls -1t subscription_*.json 2>/dev/null | head -n 1 || true)"

if [[ -z "$latest_json" ]]; then
  echo "Error: get_subscription.py did not produce any subscription_*.json" >&2
  exit 1
fi

# If the latest JSON is not from today, just warn and continue.
today="$(date +%Y%m%d)"
if [[ $latest_json != subscription_${today}_* ]]; then
  echo "Warning: Latest subscription file $latest_json is not from today ($today) - continuing with the latest available file" >&2
fi

python3 update_proxies_from_subscription.py

if [[ ! -f config.yaml ]]; then
  echo "Error: update_proxies_from_subscription.py did not produce config.yaml" >&2
  exit 1
fi

cp -f config.yaml /tmp/config.yaml

for json_file in subscription_*.json; do
  # Remove all subscription files except the one we used (latest_json)
  if [[ "$json_file" != "$latest_json" ]]; then
    rm -f "$json_file"
  fi
done
