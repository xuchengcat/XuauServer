#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (( EUID != 0 )); then
    case " $* " in
        *" --dry-run "*) ;;
        *) exec sudo -- "$SCRIPT_DIR/refresh_config.sh" "$@" ;;
    esac
fi
exec python3 "$SCRIPT_DIR/update_subscription.py" --env-file "$SCRIPT_DIR/.env" "$@"
