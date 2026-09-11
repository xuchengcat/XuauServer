# 服务器备份

本目录集中管理 Ubuntu 系统及服务数据的备份文件。

## 文件

- `backup.sh`：由 root 定时执行的备份脚本。
- `exclude-root.txt`：Ubuntu 根文件系统归档的排除规则。
- `backup.conf.example`：可选配置模板。
- `RESTORE.md`：主硬盘故障后的恢复步骤；每次成功备份也会复制到 HDD6T。

## 备份位置

完整备份集位于：

```text
/mnt/HDD6T/commonbkp/backupset-<主机名>-<年月日>-<时分秒>/
```

每个备份集包含四个压缩包、系统恢复信息、`SHA256SUMS` 和完成标记。创建过程中使用同一文件系统内的 `.partial-*` 目录，只有全部压缩包通过 gzip 和 SHA-256 校验后才原子发布。

`/mnt/HDD6T/commonbkp/RESTORE.md` 始终保存最近成功版本的恢复文档。

## 配置

脚本内置当前机器的挂载点和 UUID。需要修改时：

```bash
cd /mnt/SDD128G/server-backup
cp backup.conf.example backup.conf
chmod 600 backup.conf
```

不要把包含 Bark token 的 `backup.conf` 提交到 Git。

## 手动运行

只执行挂载、UUID、权限、依赖和空间检查，不创建备份：

```bash
sudo /mnt/SDD128G/server-backup/backup.sh --check
```

完整备份数据量较大，应在业务低峰执行：

```bash
sudo /mnt/SDD128G/server-backup/backup.sh
```

脚本退出码为 0 才表示完整成功。失败的 `.partial-*` 会保留用于排查，但不会触发旧备份清理。

## 保留规则

- 保留最近 3 个完整的新格式备份集。
- 新备份完整发布前绝不清理旧备份。
- 原有顶层 `*.tgz` 归档会一直保留到至少产生 3 个新格式完整备份集。
- 超过 7 天的失败 `.partial-*` 只会在一次新备份成功后清理。

## 一致性边界

脚本按文件读取正在运行的 Docker 服务数据。gzip 和 SHA-256 可以确认归档没有传输或存储损坏，但不能保证正在写入的 SQLite、MariaDB 等数据库具备事务一致性。关键数据库应另行增加应用级导出、容器暂停或文件系统快照。
