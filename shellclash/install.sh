#!/bin/sh

set -eu

if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' '请使用 sudo 运行此脚本。' >&2
  exit 1
fi

source_dir=/mnt/SDD128G/shellclash
backup_dir="/etc/ShellCrash/backups/codex-$(date '+%Y%m%d-%H%M%S')"

mkdir -p "$backup_dir"
install -m 0644 /etc/ShellCrash/yamls/config.yaml "$backup_dir/config.yaml"
install -m 0644 /etc/ShellCrash/yamls/rules.yaml "$backup_dir/rules.yaml"
if [ -f /tmp/ShellCrash/config.yaml ]; then
  install -m 0644 /tmp/ShellCrash/config.yaml "$backup_dir/runtime-config.yaml"
fi

/tmp/ShellCrash/CrashCore -t -d /etc/ShellCrash -f "$source_dir/config.yaml"

install -o root -g shellcrash -m 0644 "$source_dir/config.yaml" /etc/ShellCrash/yamls/config.yaml
install -o root -g shellcrash -m 0644 "$source_dir/rules.yaml" /etc/ShellCrash/yamls/rules.yaml
install -o root -g root -m 0755 "$source_dir/daily_group_test.sh" /etc/ShellCrash/task/daily_group_test.sh
install -o root -g root -m 0644 "$source_dir/shellcrash-daily-group-test.cron" /etc/cron.d/shellcrash-daily-group-test

printf '安装完成，备份位于：%s\n' "$backup_dir"
printf '%s\n' '尚未重启 ShellCrash，请通过 ShellCrash 菜单重启核心。'
