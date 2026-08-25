#!/bin/sh

set -u

config_file=/tmp/ShellCrash/config.yaml
log_file=/etc/ShellCrash/task/daily_group_test.log
lock_dir=/tmp/ShellCrash-daily-group-test.lock
provider=b

cleanup() {
  rmdir "$lock_dir" 2>/dev/null || true
}

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$*" >>"$log_file"
}

api() {
  method=$1
  path=$2
  if [ -n "$secret" ]; then
    curl -fsS --max-time 60 -X "$method" -H "Authorization: Bearer $secret" "$controller$path"
  else
    curl -fsS --max-time 60 -X "$method" "$controller$path"
  fi
}

if ! mkdir "$lock_dir" 2>/dev/null; then
  exit 0
fi
trap cleanup EXIT HUP INT TERM

if [ ! -r "$config_file" ]; then
  log "ERROR runtime config is unreadable"
  exit 1
fi

secret=$(sed -n 's/^[[:space:]]*secret:[[:space:]]*["'\'' ]*\([^"'\'' ]*\).*/\1/p' "$config_file" | head -n 1)
controller_value=$(sed -n 's/^[[:space:]]*external-controller:[[:space:]]*["'\'' ]*\([^"'\'' ]*\).*/\1/p' "$config_file" | head -n 1)
case "$controller_value" in
  :*) controller="http://127.0.0.1$controller_value" ;;
  0.0.0.0:*) controller="http://127.0.0.1:${controller_value##*:}" ;;
  '') controller=http://127.0.0.1:9999 ;;
  *) controller="http://$controller_value" ;;
esac

if api PUT "/providers/proxies/$provider" >/dev/null; then
  log "provider $provider refreshed"
else
  log "WARN provider $provider refresh failed; testing cached nodes"
fi

sleep 2

steam_path='/group/%F0%9F%8E%AE%20Steam/delay?url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204&timeout=10000'
gpt_path='/group/%F0%9F%A4%96%20ChatGPT/delay?url=https%3A%2F%2Fchatgpt.com%2Fcdn-cgi%2Ftrace&timeout=10000'

if api GET "$steam_path" >/dev/null; then
  log "Steam test completed"
else
  log "ERROR Steam test failed"
fi

if api GET "$gpt_path" >/dev/null; then
  log "ChatGPT test completed"
else
  log "ERROR ChatGPT test failed"
fi
