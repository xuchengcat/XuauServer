#!/usr/bin/env bash
set -Eeuo pipefail

umask 027
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
CONFIG_FILE="$SCRIPT_DIR/backup.conf"
EXCLUDE_FILE="$SCRIPT_DIR/exclude-root.txt"

BACKUP_ROOT="/mnt/HDD6T/commonbkp"
BACKUP_MOUNT="/mnt/HDD6T"
BACKUP_MOUNT_UUID="00a8921e-3ee3-4664-907c-d15bcfea6782"
MEDIA_MOUNT="/mnt/HDD14T"
MEDIA_MOUNT_UUID="986e4336-57c3-487b-a19b-c9fc54dee560"
KEEP_GENERATIONS=3
MIN_FREE_GIB=100
BARK_SERVER="xuau-bark-server.onrender.com"
BARK_TOKEN=""

if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
fi

HOST_SHORT=$(hostname -s)
SAFE_HOST=${HOST_SHORT//[^a-zA-Z0-9_.-]/_}
BACKUP_ID=$(date +"%Y%m%d-%H%M%S")
SET_NAME="backupset-${SAFE_HOST}-${BACKUP_ID}"
STAGING_DIR="$BACKUP_ROOT/.partial-${SAFE_HOST}-${BACKUP_ID}"
FINAL_DIR="$BACKUP_ROOT/$SET_NAME"
BACKUP_STARTED=0
CHECK_ONLY=0

case "${1:-}" in
    --check)
        CHECK_ONLY=1
        ;;
    "")
        ;;
    *)
        printf '用法：%s [--check]\n' "$0" >&2
        exit 2
        ;;
esac

log() {
    printf '%s %s\n' "$(date --iso-8601=seconds)" "$*"
}

notify_bark() {
    local title=$1
    local body=$2
    [[ -n "$BARK_SERVER" && -n "$BARK_TOKEN" ]] || return 0
    curl --fail --silent --show-error --max-time 20 \
        "https://${BARK_SERVER}/${BARK_TOKEN}/${title}/${body}?group=Server" >/dev/null
}

on_error() {
    local rc=$?
    local line=${BASH_LINENO[0]:-unknown}
    trap - ERR INT TERM
    if (( BACKUP_STARTED )); then
        log "备份失败：退出码=$rc，行=$line；旧备份未清理，临时目录保留：$STAGING_DIR" >&2
        notify_bark "ServerBackupFailed" "${SAFE_HOST}-${BACKUP_ID}-exit-${rc}" || true
    else
        log "备份在前置检查阶段失败：退出码=$rc，行=$line；尚未写入备份数据" >&2
    fi
    exit "$rc"
}
on_signal() {
    if (( BACKUP_STARTED )); then
        log "备份被信号中断；旧备份未清理，临时目录保留：$STAGING_DIR" >&2
        notify_bark "ServerBackupFailed" "${SAFE_HOST}-${BACKUP_ID}-interrupted" || true
    else
        log "备份在前置检查阶段被中断；尚未写入备份数据" >&2
    fi
    exit 130
}
trap on_error ERR
trap on_signal INT TERM

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        log "缺少必需命令：$1" >&2
        return 1
    }
}

mounted_uuid() {
    findmnt -rn -o UUID -T "$1"
}

require_exact_mount() {
    local path=$1
    local expected_uuid=$2
    local actual_target actual_uuid
    actual_target=$(findmnt -rn -o TARGET -T "$path")
    actual_uuid=$(mounted_uuid "$path")
    [[ "$actual_target" == "$path" ]] || {
        log "$path 不是独立挂载点，实际落在 $actual_target" >&2
        return 1
    }
    [[ "$actual_uuid" == "$expected_uuid" ]] || {
        log "$path UUID 不符：期望 $expected_uuid，实际 $actual_uuid" >&2
        return 1
    }
    [[ -w "$path" ]] || {
        log "$path 不可写" >&2
        return 1
    }
}

require_path_on_mount() {
    local path=$1
    local expected_target=$2
    local expected_uuid=$3
    local actual_target actual_uuid
    actual_target=$(findmnt -rn -o TARGET -T "$path")
    actual_uuid=$(mounted_uuid "$path")
    [[ "$actual_target" == "$expected_target" && "$actual_uuid" == "$expected_uuid" ]] || {
        log "$path 不在预期文件系统上：目标=$actual_target，UUID=$actual_uuid" >&2
        return 1
    }
}

validate_configuration() {
    [[ "$KEEP_GENERATIONS" =~ ^[1-9][0-9]*$ ]] || {
        log "KEEP_GENERATIONS 必须是大于 0 的整数" >&2
        return 1
    }
    [[ "$MIN_FREE_GIB" =~ ^[1-9][0-9]*$ ]] || {
        log "MIN_FREE_GIB 必须是大于 0 的整数" >&2
        return 1
    }
    [[ "$BACKUP_ROOT" != "$BACKUP_MOUNT" ]] || {
        log "BACKUP_ROOT 不能直接等于 BACKUP_MOUNT" >&2
        return 1
    }
    case "$BACKUP_ROOT/" in
        "$BACKUP_MOUNT"/*) ;;
        *)
            log "BACKUP_ROOT 必须位于 BACKUP_MOUNT 内" >&2
            return 1
            ;;
    esac
}

check_free_space() {
    local available required minimum_bytes reference_bytes=0 newest_set
    available=$(df --output=avail -B1 "$BACKUP_MOUNT" | awk 'NR==2 {print $1}')
    minimum_bytes=$((MIN_FREE_GIB * 1024 * 1024 * 1024))

    newest_set=$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
        -name "backupset-${SAFE_HOST}-*" -printf '%f\n' | sort -r | head -n 1 || true)
    if [[ -n "$newest_set" && -f "$BACKUP_ROOT/$newest_set/COMPLETE" ]]; then
        reference_bytes=$(du -sb "$BACKUP_ROOT/$newest_set" | awk '{print $1}')
    else
        reference_bytes=$(find "$BACKUP_ROOT" -maxdepth 1 -type f \
            \( -name 'Ubuntubkp-*.tgz' -o -name 'Sdd128bkp-*.tgz' \
               -o -name 'Photosbkp-*.tgz' -o -name 'wechat-*.tgz' \) \
            -printf '%s\n' | awk '{sum += $1} END {print sum + 0}')
    fi

    required=$((reference_bytes + reference_bytes / 5))
    (( required < minimum_bytes )) && required=$minimum_bytes
    (( available >= required )) || {
        log "HDD6T 空间不足：可用 $available 字节，要求至少 $required 字节" >&2
        return 1
    }
    log "空间检查通过：可用 $available 字节，最低要求 $required 字节"
}

save_required_output() {
    local output=$1
    shift
    "$@" >"$output"
    [[ -s "$output" ]] || {
        log "必需的恢复信息为空：$output" >&2
        return 1
    }
}

save_optional_output() {
    local output=$1
    shift
    if ! "$@" >"$output" 2>"${output}.stderr"; then
        log "警告：可选恢复信息采集失败：$*" >&2
    fi
}

collect_metadata() {
    local metadata=$STAGING_DIR/system-metadata
    local root_source root_parent root_disk disk disk_name
    mkdir -p "$metadata"

    root_source=$(readlink -f "$(findmnt -rn -o SOURCE -T /)")
    root_parent=$(lsblk -ndo PKNAME "$root_source")
    [[ -n "$root_parent" ]] || {
        log "无法识别根分区 $root_source 的父磁盘" >&2
        return 1
    }
    root_disk="/dev/$root_parent"

    {
        printf 'backup_id=%s\n' "$BACKUP_ID"
        printf 'hostname=%s\n' "$HOST_SHORT"
        printf 'root_source=%s\n' "$root_source"
        printf 'root_disk=%s\n' "$root_disk"
        printf 'services_path_source=%s\n' "$(findmnt -rn -o SOURCE -T /mnt/SDD128G)"
        printf 'services_path_mount_target=%s\n' "$(findmnt -rn -o TARGET -T /mnt/SDD128G)"
    } >"$metadata/root-device.txt"

    save_required_output "$metadata/sfdisk-root.dump" sfdisk --dump "$root_disk"
    save_required_output "$metadata/lsblk.txt" lsblk -O
    save_required_output "$metadata/lsblk.json" lsblk -J -O
    save_required_output "$metadata/blkid.txt" blkid
    save_required_output "$metadata/findmnt.txt" findmnt --all
    cp --preserve=all /etc/fstab "$metadata/fstab"
    cp --preserve=all /etc/os-release "$metadata/os-release"
    cp --preserve=all "$SCRIPT_DIR/RESTORE.md" "$metadata/RESTORE.md"
    cp --archive /etc/apt "$metadata/etc-apt"

    dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' \
        >"$metadata/packages.tsv"
    [[ -s "$metadata/packages.tsv" ]]
    dpkg --get-selections >"$metadata/dpkg-selections.txt"
    apt-mark showmanual >"$metadata/apt-manual.txt"
    uname -a >"$metadata/uname.txt"
    hostnamectl >"$metadata/hostnamectl.txt"

    while read -r disk; do
        [[ "$disk" == "$root_disk" ]] && continue
        disk_name=${disk#/dev/}
        save_optional_output "$metadata/sfdisk-${disk_name}.dump" sfdisk --dump "$disk"
    done < <(lsblk -dnpo NAME,TYPE | awk '$2 == "disk" {print $1}')

    save_optional_output "$metadata/efibootmgr.txt" efibootmgr -v
    save_optional_output "$metadata/root-crontab.txt" crontab -l
    save_optional_output "$metadata/docker-version.txt" docker version
    save_optional_output "$metadata/docker-info.txt" docker info
    save_optional_output "$metadata/docker-containers.txt" docker ps -a --no-trunc
    save_optional_output "$metadata/docker-images.txt" docker image ls --digests --no-trunc
    save_optional_output "$metadata/docker-volumes.txt" docker volume ls
    save_optional_output "$metadata/docker-mounts.txt" docker inspect \
        --format '{{.Name}}{{range .Mounts}}{{printf "\\n  %s <- %s (%s)" .Destination .Source .Type}}{{end}}{{println}}' \
        $(docker ps -aq)

    log "系统恢复信息已采集到 $metadata"
}

create_archive() {
    local source=$1
    local archive_base=$2
    local exclude=${3:-}
    local partial="$STAGING_DIR/${archive_base}.tgz.partial"
    local final="$STAGING_DIR/${archive_base}.tgz"
    local -a args=(
        --create --gzip --preserve-permissions --numeric-owner
        --acls --xattrs --xattrs-include='*'
        --file "$partial"
    )

    [[ -n "$exclude" ]] && args+=(--exclude-from "$exclude")
    log "开始归档 $source -> $partial"
    tar "${args[@]}" "$source"
    sync -f "$partial"
    gzip -t "$partial"
    mv -- "$partial" "$final"
    sync -f "$final"
    log "归档及 gzip 校验通过：$final"
}

write_and_verify_checksums() {
    (
        cd "$STAGING_DIR"
        {
            sha256sum -- ./*.tgz
            find ./system-metadata -type f -print0 | sort -z | xargs -0 sha256sum
        } >SHA256SUMS.partial
        sync -f SHA256SUMS.partial
        mv -- SHA256SUMS.partial SHA256SUMS
        sha256sum -c SHA256SUMS
        sync -f SHA256SUMS
    )
    log "全部 SHA-256 校验通过"
}

publish_restore_document() {
    local partial="$BACKUP_ROOT/.RESTORE.md.partial-${BACKUP_ID}"
    cp --preserve=mode,timestamps "$SCRIPT_DIR/RESTORE.md" "$partial"
    sync -f "$partial"
    mv -- "$partial" "$BACKUP_ROOT/RESTORE.md"
    sync -f "$BACKUP_ROOT/RESTORE.md"
}

prune_old_backups() {
    local -a sets=()
    local set path i
    while read -r set; do
        [[ -n "$set" && -f "$BACKUP_ROOT/$set/COMPLETE" ]] && sets+=("$set")
    done < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
        -name "backupset-${SAFE_HOST}-????????-??????" -printf '%f\n' | sort -r)

    for ((i=KEEP_GENERATIONS; i<${#sets[@]}; i++)); do
        path="$BACKUP_ROOT/${sets[i]}"
        [[ -f "$path/COMPLETE" && ! -L "$path" ]] || continue
        log "清理旧的完整备份集：$path"
        rm -rf -- "$path"
    done

    if (( ${#sets[@]} >= KEEP_GENERATIONS )); then
        find "$BACKUP_ROOT" -maxdepth 1 -type f \
            \( -name 'Ubuntubkp-*.tgz' -o -name 'Sdd128bkp-*.tgz' \
               -o -name 'Photosbkp-*.tgz' -o -name 'wechat-*.tgz' \) \
            -print -delete
    fi

    find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
        -name ".partial-${SAFE_HOST}-????????-??????" -mtime +7 \
        -print -exec rm -rf -- {} +
}

main() {
    local command
    (( EUID == 0 )) || {
        log "必须以 root 身份运行" >&2
        return 1
    }

    for command in tar gzip sha256sum findmnt lsblk blkid sfdisk dpkg-query \
        dpkg apt-mark sync curl; do
        require_command "$command"
    done
    validate_configuration
    [[ -r "$EXCLUDE_FILE" ]] || {
        log "排除文件不存在或不可读：$EXCLUDE_FILE" >&2
        return 1
    }

    require_exact_mount "$BACKUP_MOUNT" "$BACKUP_MOUNT_UUID"
    require_exact_mount "$MEDIA_MOUNT" "$MEDIA_MOUNT_UUID"
    mkdir -p "$BACKUP_ROOT"
    require_path_on_mount "$BACKUP_ROOT" "$BACKUP_MOUNT" "$BACKUP_MOUNT_UUID"
    check_free_space
    if (( CHECK_ONLY )); then
        log "前置检查全部通过；未创建备份"
        return 0
    fi
    [[ ! -e "$STAGING_DIR" && ! -e "$FINAL_DIR" ]]
    mkdir -- "$STAGING_DIR"
    BACKUP_STARTED=1

    log "/mnt/SDD128G 当前位于 $(findmnt -rn -o SOURCE -T /mnt/SDD128G)，挂载目标为 $(findmnt -rn -o TARGET -T /mnt/SDD128G)"
    collect_metadata
    create_archive "/" "Ubuntubkp-${SAFE_HOST}" "$EXCLUDE_FILE"
    create_archive "/mnt/HDD14T/Pictures" "Photosbkp-${SAFE_HOST}"
    create_archive "/mnt/SDD128G" "Sdd128bkp-${SAFE_HOST}"
    create_archive "/mnt/HDD14T/wechat" "wechat-${SAFE_HOST}"
    write_and_verify_checksums

    printf 'backup_id=%s\ncompleted_at=%s\n' \
        "$BACKUP_ID" "$(date --iso-8601=seconds)" >"$STAGING_DIR/COMPLETE"
    sync -f "$STAGING_DIR/COMPLETE"
    sync -f "$STAGING_DIR"
    mv -- "$STAGING_DIR" "$FINAL_DIR"
    sync -f "$BACKUP_ROOT"
    publish_restore_document
    prune_old_backups
    log "完整备份集发布成功：$FINAL_DIR"
    notify_bark "ServerBackupFinished" "$SET_NAME" || \
        log "警告：备份成功，但 Bark 通知失败" >&2
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
