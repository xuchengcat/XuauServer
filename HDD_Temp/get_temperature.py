import subprocess
import requests
import re

# 配置
DISKS = ["/dev/sdb", "/dev/sdc"]  # 你的硬盘列表
HA_URL = "http://127.0.0.1:8123/api/services/input_number/set_value"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIwOWY0YjRlNzU4Yjg0ZWQ5YTFhMzgxMjZkMDAwM2U1MyIsImlhdCI6MTc0NzAzNzE5OSwiZXhwIjoyMDYyMzk3MTk5fQ.uXp09j04-TV3ueksbBWG9ZntX-svP_fJXLeC-21E4nw"  # 在HA用户界面profile页面生成

def get_disk_temp(disk):
    try:
        result = subprocess.run(
            ["smartctl", "-A", disk],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            if "Temperature_Celsius" in line:
                # 先移除括号及其内容
                line_no_bracket = re.sub(r'\(.*?\)', '', line)
                parts = line_no_bracket.split()
                if parts and parts[-1].isdigit():
                    return int(parts[-1])
    except Exception as e:
        print(f"Error reading {disk}: {e}")
    return None

def send_to_ha(disk, temp):
    entity_id = f"input_number.disk_temp_{disk.split('/')[-1]}"
    url = HA_URL
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "entity_id": entity_id,
        "value": temp
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Set {entity_id}: {temp}°C, status: {response.status_code}, resp: {response.text}")

if __name__ == "__main__":
    for disk in DISKS:
        temp = get_disk_temp(disk)
        if temp is not None:
            send_to_ha(disk, temp)
        else:
            print(f"未能获取 {disk} 的温度") 
