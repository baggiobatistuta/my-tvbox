import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

SRC = "sources.txt"
OUT = "output/multi.txt"
TIMEOUT = 6
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def load_sources():
    if not os.path.exists(SRC):
        return []
    with open(SRC, "r", encoding="utf-8") as f:
        lines = []
        for line in f:
            line = line.strip()
            if line and "," in line:
                lines.append(line)
        return lines

def check_one(item):
    name, url = item.split(",", 1)
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        # 尝试解析 JSON（TVBox 源通常是 JSON）
        try:
            data = r.json()
            if isinstance(data, dict) and "sites" in data:
                return f"{name},{url}"
        except Exception:
            # 非 JSON，但能访问，也保留（部分 txt 多仓）
            if "txt" in url or "m3u" in url:
                return f"{name},{url}"
            return None
    except Exception:
        return None
    return None

def main():
    sources = load_sources()
    alive = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(check_one, src) for src in sources]
        for future in as_completed(futures):
            result = future.result()
            if result:
                alive.append(result)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for line in alive:
            f.write(line + "\n")

    print(f"✅ 检测完成：{len(sources)} 个源，存活 {len(alive)} 个")

if __name__ == "__main__":
    main()
