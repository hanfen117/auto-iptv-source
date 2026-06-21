import requests
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor

# 配置参数
SOURCE_FILE = "sources.txt"
OUTPUT_M3U = "tv.m3u"
TIMEOUT = 8
THREAD_NUM = 8

# 读取本地频道源（兼容 名称,链接 单行格式）
def load_sources():
    channel_list = []
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            # 跳过空行和注释行
            if not line or line.startswith("#"):
                continue
            # 按第一个逗号分割频道名和链接
            if "," in line:
                name, url = line.split(",", 1)
                channel_list.append((name.strip(), url.strip()))
    return channel_list

# 单链接测速函数
def test_stream(item):
    name, url = item
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        start = time.time()
        resp = requests.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        delay = round((time.time() - start) * 1000)
        # 200/302 视为可用，延迟低于1000ms
        if resp.status_code in (200, 302) and delay < 1000:
            return (name, url, delay)
    except Exception:
        pass
    return None

def main():
    # 读取全部频道
    all_channels = load_sources()
    print(f"读取原始频道总数：{len(all_channels)}")

    valid_channels = []
    # 多线程并发测速
    with ThreadPoolExecutor(max_workers=THREAD_NUM) as pool:
        results = pool.map(test_stream, all_channels)
        for res in results:
            if res:
                valid_channels.append(res)

    print(f"测速后可用频道：{len(valid_channels)}")

    # 生成标准m3u播放列表
    m3u_content = "#EXTM3U\n"
    for name, url, delay in valid_channels:
        m3u_content += f'#EXTINF:-1 tvg-name="{name}",{name}\n{url}\n'

    # 写入文件
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(m3u_content)
    print(f"{OUTPUT_M3U} 文件生成完成")

if __name__ == "__main__":
    main()
