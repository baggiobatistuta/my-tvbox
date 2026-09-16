import json
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SRC = "sources.txt"
OUT_TXT = "output/multi.txt"
OUT_JSON = "output/tvbox.json"

TIMEOUT = 6
MAX_WORKERS = 8
TOO_SLOW = 5.0  # 响应超过 5 秒，虽然活但排最后/可丢弃

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def log(msg):
    print(msg, flush=True)


def load_sources():
    if not os.path.exists(SRC):
        return []
    out = []
    with open(SRC, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "," not in line:
                continue
            name, url = line.split(",", 1)
            out.append((name.strip(), url.strip()))
    return out


def check_one(item):
    name, url = item
    start = time.time()
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        cost = time.time() - start
        if r.status_code != 200:
            return None
        text = r.text.strip()
        if not text:
            return None

        # 情况 1：JSON 单仓 / 多仓
        if url.lower().endswith(".json") or text.startswith("{") or text.startswith("["):
            try:
                data = r.json()
            except Exception:
                return None
            # 有 sites 才是真点播源
            sites = data.get("sites") if isinstance(data, dict) else None
            store = data.get("store", {}) if isinstance(data, dict) else {}
            store_sites = store.get("sites") if isinstance(store, dict) else None
            if (isinstance(sites, list) and len(sites) > 0) or \
               (isinstance(store_sites, list) and len(store_sites) > 0):
                return {
                    "name": name,
                    "url": url,
                    "cost": round(cost, 3),
                    "kind": "json",
                }
            return None

        # 情况 2：多仓 txt（一行一个源）
        if url.lower().endswith(".txt") or "\n" in text:
            lines = [x.strip() for x in text.splitlines() if x.strip() and "," in x]
            if len(lines) >= 1:
                return {
                    "name": name,
                    "url": url,
                    "cost": round(cost, 3),
                    "kind": "txt",
                }
            return None

        # 情况 3：其他能访问的也保留
        return {
            "name": name,
            "url": url,
            "cost": round(cost, 3),
            "kind": "other",
        }

    except Exception:
        return None


def build_single_json(alive):
    """
    把每个活着的 JSON 源里的 sites 合并进来
    按 key 去重，保留第一次出现的
    """
    sites = []
    seen_keys = set()
    lives = []
    parses = []
    spider = ""

    for item in alive:
        if item["kind"] != "json":
            continue
        try:
            r = requests.get(item["url"], headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
        except Exception:
            continue

        # store.sites 也兼容
        top_sites = data.get("sites") if isinstance(data, dict) else None
        store = data.get("store", {}) if isinstance(data, dict) else {}
        store_sites = store.get("sites") if isinstance(store, dict) else None
        src_sites = top_sites or store_sites or []

        for s in src_sites:
            key = s.get("key") or s.get("name")
            if not key:
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)
            sites.append(s)

        for lv in data.get("lives", []) or []:
            lives.append(lv)
        for p in data.get("parses", []) or []:
            parses.append(p)
        if not spider and data.get("spider"):
            spider = data.get("spider")

    return {
        "spider": spider,
        "sites": sites,
        "parses": parses,
        "lives": lives,
    }


def main():
    sources = load_sources()
    log(f"读取候选源：{len(sources)} 个")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(check_one, s) for s in sources]
        for f in as_completed(futures):
            res = f.result()
            if res:
                results.append(res)

    # 按响应时间排序：快的在前
    results.sort(key=lambda x: x["cost"])

    # 输出多仓 txt
    os.makedirs("output", exist_ok=True)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        for r in results:
            f.write(f"{r['name']},{r['url']}\n")

    # 输出单仓 json
    single = build_single_json(results)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(single, f, ensure_ascii=False, indent=2)

    log(f"存活源：{len(results)} 个")
    for r in results:
        log(f"  {r['cost']}s  {r['name']}  [{r['kind']}]")
    log(f"单仓 sites 数量：{len(single['sites'])}")


if __name__ == "__main__":
    main()
