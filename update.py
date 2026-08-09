import requests
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ====================== 可配置参数 ======================
SOURCE_FILE = "sources.txt"
OUTPUT_M3U = "tv.m3u"
LOG_FILE = "speed_log.txt"
TIMEOUT = 8          # 单次请求超时(秒)
THREAD_NUM = 12      # 并发线程数
MAX_DELAY_MS = 1000  # 最大允许延迟(毫秒)
RETRY_COUNT = 1      # 失败重试次数
# =======================================================

# 全局统计
stat = {
    "total": 0,
    "valid": 0,
    "timeout": 0,
    "slow": 0,
    "error": 0,
    "duplicate": 0
}

def write_log(msg: str):
    """写入日志+控制台打印"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_sources():
    """读取源文件，去重URL，清洗数据"""
    channel_list = []
    url_set = set()
    if not os.path.exists(SOURCE_FILE):
        write_log(f"错误：源文件 {SOURCE_FILE} 不存在！")
        return []
    
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    for idx, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        # 跳过空行、注释行
        if not line or line.startswith("#"):
            continue
        if "," not in line:
            write_log(f"第{idx}行格式错误，跳过：{line}")
            continue
        
        # 仅分割第一个逗号，频道名允许带逗号
        name, url = line.split(",", 1)
        name = name.strip()
        url = url.strip()
        
        if not name or not url:
            write_log(f"第{idx}行名称/链接为空，跳过")
            continue
        if url in url_set:
            stat["duplicate"] += 1
            continue
        
        url_set.add(url)
        channel_list.append((name, url))
    
    stat["total"] = len(channel_list)
    write_log(f"原始源去重后待检测总数：{stat['total']}，重复链接过滤：{stat['duplicate']}")
    return channel_list

def test_single_stream(item):
    """单链接测速，支持重试"""
    name, url = item
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": url
    }
    delay = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            start = time.perf_counter()
            resp = requests.head(
                url,
                headers=headers,
                timeout=TIMEOUT,
                allow_redirects=True,
                stream=False
            )
            delay = round((time.perf_counter() - start) * 1000)
            # 正常状态码
            if resp.status_code in (200, 206, 301, 302, 304):
                if delay < MAX_DELAY_MS:
                    write_log(f"✅ 有效 | {name} | 延迟:{delay}ms | {url}")
                    return (name, url, delay)
                else:
                    stat["slow"] += 1
                    write_log(f"⏱️ 延迟过高({delay}ms>{MAX_DELAY_MS}) | {name}")
            else:
                write_log(f"❌ 状态码异常{resp.status_code} | {name}")
            break
        except requests.exceptions.Timeout:
            stat["timeout"] += 1
            write_log(f"⏳ 超时重试{attempt}/{RETRY_COUNT} | {name}")
            time.sleep(0.3)
        except Exception as e:
            stat["error"] += 1
            write_log(f"💥 请求异常 {str(e)[:60]} | {name}")
            break
    return None

def generate_m3u(valid_list):
    """生成M3U文件，按延迟升序排序"""
    # 按延迟从小到大排序
    valid_list.sort(key=lambda x: x[2])
    content = "#EXTM3U\n"
    for name, url, delay in valid_list:
        content += f'#EXTINF:-1 tvg-name="{name}" delay="{delay}",{name}\n{url}\n'
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)
    write_log(f"✅ M3U文件 {OUTPUT_M3U} 生成完成")

def main():
    write_log("=" * 50)
    write_log("IPTV 直播源测速工具启动")
    write_log("=" * 50)
    # 清空日志
    open(LOG_FILE, "w", encoding="utf-8").close()
    channels = load_sources()
    if not channels:
        write_log("无有效频道可检测，程序退出")
        return
    
    valid_channels = []
    with ThreadPoolExecutor(max_workers=THREAD_NUM) as pool:
        task_map = {pool.submit(test_single_stream, ch): ch for ch in channels}
        for task in as_completed(task_map):
            res = task.result()
            if res:
                valid_channels.append(res)
                stat["valid"] += 1
    
    # 输出统计汇总
    write_log("\n========== 测速统计汇总 ==========")
    write_log(f"待检测总数: {stat['total']}")
    write_log(f"重复链接过滤: {stat['duplicate']}")
    write_log(f"有效可用频道: {stat['valid']}")
    write_log(f"延迟超标丢弃: {stat['slow']}")
    write_log(f"连接超时数量: {stat['timeout']}")
    write_log(f"请求异常失效: {stat['error']}")
    write_log("==================================\n")
    
    generate_m3u(valid_channels)
    write_log("测速任务全部结束！")

if __name__ == "__main__":
    main()
