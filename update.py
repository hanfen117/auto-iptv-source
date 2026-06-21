import requests
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor

# 配置参数
SOURCE_FILE = "sources.txt"
OUTPUT_M3U = "tv.m3u"
TIMEOUT = 4
THREAD_NUM = 15

# 读取本地频道源（兼容 名称,链接 单行格式）
def load_sources():
    channel_list = []
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "," in line:
                name, url = line.split(",", 1)
                channel_list.append((name, url))
    return channel_list

# 测速过滤失效链接
def test_stream(item):
    name, url = item
    try:
        start = time.time()
        resp = requests.head(url, timeout=TIMEOUT)
        delay = round((time.time() - start)*1000)
        if resp.status_code in (200, 302) and delay < 1000:
            return (name, url, delay)
    except Exception:
        return None

def main():
    all_channels = load_sources()
    print(f"读取原始频道总数：{len(all_channels)}")

    # 并发测速
    valid_list = []
    with ThreadPoolExecutor(max_workers=THREAD_NUM) as pool:
        result = pool.map(test_stream, all_channels)
        for res in result:
            if res:
                valid_list.append(res)
    print(f"测速后可用频道：{len(valid_list)}")

    # 生成标准M3U文件
    m3u_header = "#EXTM3U\n"
    m3u_content = m3u_header
    for name, url, delay in valid_list:
        m3u_content += f'#EXTINF:-1 tvg-name="{name}",{name}\n{url}\n'
    
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print("tv.m3u 文件生成完成")

if __name__ == "__main__":
    main()
