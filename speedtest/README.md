# 家庭服务器网页测速

访问：https://speedtest.xuchengcat.cn:444/

用户自行配置域名解析；本服务不管理公网DNS。Nginx Proxy Manager中代理主机ID为34，转发到同一Docker网络的speedtest:80，使用已有通配证书。已关闭反代请求/响应缓冲和缓存。

网页为LibreSpeed 6.3.1官方源码中的单服务器仪表盘示例，补充中文标题、测速方向说明，关闭遥测和ISP查询。点击开始测速；下载是家庭服务器向浏览器发送，上传是浏览器向家庭服务器发送，速率单位Mbit/s。应在外网测试；服务器本机或局域网结果不能代表公网链路。

部署目录：/mnt/SDD128G/speedtest，启动：

```bash
docker compose -f /mnt/SDD128G/speedtest/compose.yaml up -d
```

镜像下载缓慢，因此复用本地已有PHP/Apache运行时镜像，固定别名local/php-apache-speedtest:20261118，直接启动apache2-foreground；文档根目录仅挂载LibreSpeed网页，不启动Nextcloud应用。网页代码只读挂载。未暴露额外宿主端口。容器自动重启并带HTTP健康检查。

本机以正确域名/SNI访问444验证页面200、1MiB随机数据下载200、1MiB上传200、Nginx配置验证通过。尚未通过用户外部设备验证公网访问与实际吞吐。

维护：Nginx代理可在现有管理界面修改；网页文件位于www，原始源码位于speedtest-master。源码来源https://github.com/librespeed/speedtest，归档位于/mnt/SDD128G/codex/web-speedtest-20261118/source.tar.gz。

Git 保存部署配置、定制后的 `www/` 源码与上游许可证；本地上游参考目录
`speedtest-master/` 以及可选的 `country_asn.mmdb`、`geoip2.phar` 下载文件不入库。
当前关闭 ISP 查询，不依赖这些 GeoIP 文件；以后启用时需从对应上游版本补齐。
`local/php-apache-speedtest:20261118` 是本机镜像别名，迁移主机时需另行准备兼容的
PHP/Apache 镜像，包含 `apache2-foreground` 入口；Git 不保存容器镜像。

本任务曾添加的DNS记录和speedtest-ddns自动任务已根据用户要求撤回。update_dns.py仅为停用的历史脚本，不属于当前服务。现有iperf3保持原样。
