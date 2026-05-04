BARK_SERVER="xuau-bark-server.onrender.com"
BARK_TOKEN="iphone" # my device token

# 停止并删除原有容器，记得备份！
docker stop iptv
docker rm iptv
# 拉取最新的镜像并上线
docker compose pull youshandefeiyang/allinone:latest
docker compose up -d

# Send Bark notification with the list of files
curl -s "https://$BARK_SERVER/$BARK_TOKEN/iptv_update_succress?group=Server&level=passive"

echo "update iptv succress"
