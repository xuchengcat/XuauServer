#!/bin/bash
####################################
#
# Backup to NFS mount script.
#
####################################

excludefile="/mnt/SDD128G/exclude.txt"

backup_ubuntu="/"
backup_sdd128="/mnt/SDD128G"
backup_photos="/mnt/HDD14T/Pictures"
backup_wechat="/mnt/HDD14T/wechat"

# Set a common destination for all backups
common_dest="/mnt/HDD6T/commonbkp"

BARK_SERVER="xuau-bark-server.onrender.com"
BARK_TOKEN="iphone" # my device token

day=$(date +"%Y-%m-%d")
hostname=$(hostname -s)

# Function to perform backup
backup() {
    # Parameters:
    # $1 - source: The directory to be backed up
    # $2 - dest: The destination directory where the backup will be stored
    # $3 - archive_name: The name of the backup archive file
    # $4 - exclude: Optional parameter for a file containing patterns to exclude from the backup

    local source=$1
    local dest=$2
    local archive_name=$3
    local exclude=$4

    # Print start message with source and destination details
    echo "Start Backing up $source to $dest/$archive_name-$day.tgz"
    date
    echo

    # Perform the backup using tar
    # -c: Create a new archive
    # -p: Preserve permissions
    # -z: Compress the archive with gzip
    # -f: Use archive file
    # --exclude-from: Exclude files matching patterns in the specified file
    if [ -n "$exclude" ]; then
        tar -cpzf "$dest/$archive_name-$day.tgz" --exclude-from="$exclude" "$source"
    else
        tar -cpzf "$dest/$archive_name-$day.tgz" "$source"
    fi

    # Print completion message
    echo
    echo "Backup finished for $source"
    date

    # Remove old backups of the same type
    # Find files in the destination directory that match the pattern
    # ${archive_name%-*}*.tgz: Matches files with the same prefix as the current archive
    # ! -name "$archive_name": Excludes the current archive from deletion
    # -exec rm {} \;: Executes the rm command to delete each matched file
    find "$dest" -type f -name "${archive_name%-*}*.tgz" ! -name "$archive_name-$day.tgz" -exec rm {} \;
    echo "Removed old backups for $source"
}

# Perform backups to the common destination
backup "$backup_ubuntu" "$common_dest" "Ubuntubkp-$hostname" "$excludefile"
backup "$backup_photos" "$common_dest" "Photosbkp-$hostname" ""
backup "$backup_sdd128" "$common_dest" "Sdd128bkp-$hostname" ""
backup "$backup_wechat" "$common_dest" "wechat-$hostname" ""

# List all files in common_dest and store in a variable
files_list=$(ls "$common_dest" | tr '\n' ',')

# Send Bark notification with the list of files
curl -s "https://$BARK_SERVER/$BARK_TOKEN/ServerBackupFinished/$files_list?group=Server"

echo "back up succress"


