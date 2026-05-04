import requests
import base64
import json
from datetime import datetime
import re

def get_subscription():
    # 订阅链接
    url = "https://msub.xn--bwwx30f.top/api/v1/client/subscribe?token=9e6ebe8c27d62e3025f0a7ae87be6589"
    
    try:
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
        }
        # 发送GET请求获取数据
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        
        # 获取订阅数据
        subscription_data = response.text
        
        # 将base64解码
        decoded_subscription = base64.b64decode(subscription_data).decode('utf-8')
        
        # 分割所有的vmess链接
        vmess_links = decoded_subscription.strip().split('\n')
        
        # 解析所有vmess链接
        configs = []
        for link in vmess_links:
            if link.startswith('vmess://'):
                # 移除vmess://前缀并解码
                vmess_data = link[8:]  # 移除 "vmess://"
                try:
                    decoded_config = base64.b64decode(vmess_data).decode('utf-8')
                    config = json.loads(decoded_config)
                    configs.append(config)
                except Exception as e:
                    print(f"Error parsing vmess link: {e}")
        
        # 将所有配置保存为一个JSON数组
        json_data = configs
        
        # 生成输出文件名（使用当前时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"subscription_{timestamp}.json"
        
        # 将JSON数据写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        print(f"Successfully saved subscription data to {output_file}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading subscription: {e}")
    except base64.binascii.Error as e:
        print(f"Error decoding base64 data: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON data: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    get_subscription()
