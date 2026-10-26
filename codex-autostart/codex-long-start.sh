#!/usr/bin/env bash
set -euo pipefail

export HOME=/home/xuau
export PATH=/home/xuau/.local/bin:/usr/local/bin:/usr/bin:/bin
session=codex_long
workdir=/mnt/SDD128G/codex
codex=/home/xuau/.local/bin/codex
env_file="$HOME/.config/codex-long/environment"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

log() { printf '%s %s\n' "$(date --iso-8601=seconds)" "$*"; }
if [[ -f "$env_file" ]]; then
    # Private, user-owned shell exports; never stored in this repository.
    source "$env_file"
fi

case "${1:-}" in
    --run)
        cd -- "$workdir"
        exec "$codex" --yolo
        ;;
    ''|--probe-only) ;;
    *) printf 'Usage: %s [--probe-only|--run]\n' "$0" >&2; exit 2 ;;
esac

install -d -m 700 "$HOME/.cache/codex-long"
exec 9>"$HOME/.cache/codex-long/start.lock"
flock -n 9 || { log 'Another startup check is running; skipping.'; exit 0; }

if [[ "${1:-}" != --probe-only ]] && tmux has-session -t "=$session" 2>/dev/null; then
    log "Session $session already exists; leaving it untouched."
    exit 0
fi
[[ -d "$workdir" && -x "$codex" ]] || { log 'Working directory or Codex executable unavailable.'; exit 1; }

# Probe in an empty directory so project instructions are not loaded.
probe_dir=$(mktemp -d "$HOME/.cache/codex-long/probe.XXXXXX")
trap 'rm -rf -- "$probe_dir"' EXIT
log 'Checking model access using the existing Codex login (timeout: 120 seconds).'
if ! timeout --kill-after=10s 120s "$codex" exec \
    --ephemeral --skip-git-repo-check --sandbox read-only \
    -C "$probe_dir" --color never \
    -c 'developer_instructions="This is a connectivity probe. Do not use tools or read files. Reply with exactly CODEX_READY."' \
    -o "$probe_dir/reply" 'Reply with exactly CODEX_READY. Do not use tools.' \
    >"$probe_dir/output" 2>&1; then
    log 'Model probe failed or timed out; systemd will retry in 60 seconds.'
    exit 1
fi
if [[ ! -f "$probe_dir/reply" ]] || [[ "$(tr -d '[:space:]' < "$probe_dir/reply")" != CODEX_READY ]]; then
    log 'Model probe did not return the expected reply; systemd will retry in 60 seconds.'
    exit 1
fi
log 'Model access confirmed.'
[[ "${1:-}" != --probe-only ]] || exit 0

# Another client may have created the session while the probe was running.
if tmux has-session -t "=$session" 2>/dev/null; then
    log "Session $session now exists; leaving it untouched."
    exit 0
fi
# Load the private environment inside the pane too, even if the tmux server
# was started earlier with a different environment. Close the lock in children.
tmux new-session -d -s "$session" -c "$workdir" \
    "/bin/bash '$script_dir/codex-long-start.sh' --run" 9>&-
log "Created $session in $workdir and launched codex --yolo."
