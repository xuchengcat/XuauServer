# Ubuntu 主硬盘灾难恢复

本文档用于主系统硬盘损坏、HDD6T 备份盘仍然完好的场景。恢复分区会覆盖目标硬盘；任何命令执行前都必须根据容量、序列号和型号重新确认设备，不能假定新盘仍是 `/dev/sda`。

## 1. 找到并验证备份集

从 Ubuntu Live USB 启动，挂载 HDD6T，然后选择最新且包含 `COMPLETE` 的目录：

```bash
ls -ld /mnt/HDD6T/commonbkp/backupset-*/
cd /mnt/HDD6T/commonbkp/backupset-主机名-日期-时间
sha256sum -c SHA256SUMS
gzip -t ./*.tgz
```

任何校验失败都不要继续恢复，应尝试上一代备份。

备份集中的 `system-metadata/` 保存原分区表、UUID、挂载关系、软件包和 Docker 清单。先阅读 `lsblk.txt`、`blkid.txt`、`findmnt.txt`、`root-device.txt` 和根盘的 `sfdisk-*.dump`。

## 2. 创建新硬盘分区

用 `lsblk -o NAME,SIZE,MODEL,SERIAL` 确认替换硬盘。可以参考原根盘的 sfdisk dump 重建 GPT，但新盘容量不同时应手工创建：

- 一个 FAT32 EFI System Partition，建议至少 1 GiB。
- 一个用于 `/` 的 ext4 根分区。

不要不经检查直接把 sfdisk dump 写入磁盘。记录新分区名称和 UUID：

```bash
sudo blkid
```

以下步骤用变量表示目标，示例值必须替换成现场确认后的设备：

```bash
TARGET=/mnt/restore-root
ROOT_PART=/dev/替换盘根分区
EFI_PART=/dev/替换盘EFI分区
```

格式化、挂载根分区和 EFI 分区后，确保 EFI 分区已经挂载到 `$TARGET/boot/efi`，再解压根归档；否则 EFI 文件会写到根分区而不是 EFI 分区。

## 3. 解压系统和服务数据

在备份集目录内执行。必须以 root 身份恢复数字 UID/GID、ACL 和全部扩展属性：

```bash
sudo tar --extract --gzip --preserve-permissions \
  --acls --xattrs --xattrs-include='*' --numeric-owner \
  --file ./Ubuntubkp-主机名.tgz --directory "$TARGET"

sudo tar --extract --gzip --preserve-permissions \
  --acls --xattrs --xattrs-include='*' --numeric-owner \
  --file ./Sdd128bkp-主机名.tgz --directory "$TARGET"
```

`Sdd128bkp` 的历史名称容易误解：当前 `/mnt/SDD128G` 实际是根文件系统上的服务数据目录，不是挂载于 `/mnt/temp` 的 128G Btrfs SSD。

照片和微信归档通常用于 HDD14T 数据恢复；仅主硬盘损坏时，不要无故覆盖仍然完好的 HDD14T 数据。

## 4. 更新 fstab 和引导

根据新分区的 `blkid` 修改 `$TARGET/etc/fstab` 中根分区和 EFI 分区的 UUID。HDD6T、HDD14T、camera1t 和 `/mnt/temp` 的条目只有在对应原磁盘仍然存在时才能保留。

为 chroot 挂载运行环境：

```bash
for path in /dev /dev/pts /proc /sys /run; do
  sudo mount --bind "$path" "$TARGET$path"
done
sudo chroot "$TARGET" /bin/bash
```

在 chroot 内确认 EFI 分区已挂载，然后重新安装和生成引导配置：

```bash
mount /boot/efi
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=ubuntu
update-initramfs -c -k all
update-grub
```

如果 `update-initramfs -c` 提示对应版本已经存在，可改用 `update-initramfs -u -k all`。完成后退出 chroot，按挂载顺序逆序卸载，再尝试启动。

## 5. 首次启动检查

启动后依次确认：

1. `findmnt` 与预期磁盘一致，尤其不能让 HDD6T/HDD14T 的挂载目录落到根盘。
2. `/home/xuau`、SSH 密钥和用户文件存在且所有者正确。
3. 用 `system-metadata/packages.tsv` 和 `apt-manual.txt` 补装或修复软件包。
4. Docker、Compose、网络和防火墙正常。
5. 再启动容器，并逐个检查 Home Assistant、Frigate、Nextcloud、Node-RED、MQTT、Nginx Proxy Manager 等服务。
6. 对恢复后的 SQLite 数据库执行 `PRAGMA integrity_check`，对 MariaDB 使用其原生检查工具。
7. 核对 `getcap -r /usr/bin /usr/sbin`；必要时通过重装相关软件包恢复 capability。

## 6. 已知限制

- 分区表和 UEFI NVRAM 启动项不能只靠 tar 自动恢复，需要人工重建。
- 备份运行时容器未暂停，活跃数据库可能存在事务一致性风险。
- `/mnt/temp` 上真正的 128G SSD未包含在这些归档中；主盘单独损坏时它应仍然存在。
- `/var/log`、缓存、Docker overlay2 和虚拟文件系统按设计不备份。
