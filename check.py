import json
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SRC = "sources.txt"
IPTV = "iptv.txt"
OUT_TXT = "output/multi.txt"
OUT_JSON = "output/dancang.json"
OUT_M3U = "output/iptv.m3u"
OUT_MULTI_JSON = "output/multicang.json" 

TIMEOUT = 6
MAX_WORKERS = 8
TOO_SLOW = 5.0
MAX_SITES = 80
PRIORITY_KEYWORDS = ["4K", "4k", "UHD", "豆瓣", "高清", "热播", "网盘", "旗舰"]

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

def load_sources_from(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "," not in line:
                continue
            name, url = line.split(",", 1)
            out.append((name.strip(), url.strip()))
    return out


def looks_like_html(text):
    t = text.lstrip().lower()
    return t.startswith("<!doctype") or t.startswith("<html")


def check_iptv(item):
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

        if ".m3u" in url.lower() or text.startswith("#EXTM3U"):
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("http"):
                    return {
                        "name": name,
                        "cost": round(cost, 3),
                        "channel": {
                            "name": name,
                            "urls": [line]
                        }
                    }
            return None

        if url.lower().endswith(".json") or text.startswith("{"):
            try:
                data = r.json()
            except Exception:
                return None
            channels = data.get("channels") if isinstance(data, dict) else data
            if isinstance(channels, list) and len(channels) > 0:
                ch = channels[0]
                urls = ch.get("urls") or [ch.get("url")]
                return {
                    "name": name,
                    "cost": round(cost, 3),
                    "channel": {
                        "name": name,
                        "urls": [u for u in urls if u]
                    }
                }
            return None

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("http") and (".m3u" in line or "live" in line):
                return {
                    "name": name,
                    "cost": round(cost, 3),
                    "channel": {
                        "name": name,
                        "urls": [line]
                    }
                }
        return None

    except Exception:
        return None


def check_one(item):
    name, url = item
    start = time.time()
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        cost = time.time() - start
        if r.status_code != 200:
            return None
        text = r.text.strip()
        if not text or looks_like_html(text):
            return None

        # JSON 单仓 / 配置仓
        if url.lower().endswith(".json") or text.startswith("{") or text.startswith("["):
            try:
                data = r.json()
            except Exception:
                return None
            sites = data.get("sites") if isinstance(data, dict) else None
            store = data.get("store", {}) if isinstance(data, dict) else {}
            store_sites = store.get("sites") if isinstance(store, dict) else None
            ok = (
                isinstance(sites, list) and len(sites) > 0
            ) or (
                isinstance(store_sites, list) and len(store_sites) > 0
            )
            if not ok:
                return None
            return {"name": name, "url": url, "cost": round(cost, 3), "kind": "json"}

        # 多仓 txt
        if url.lower().endswith(".txt") or "\n" in text:
            lines = [x.strip() for x in text.splitlines() if x.strip() and "," in x]
            if len(lines) >= 1:
                return {"name": name, "url": url, "cost": round(cost, 3), "kind": "txt"}
            return None

        return {"name": name, "url": url, "cost": round(cost, 3), "kind": "other"}

    except Exception:
        return None


def is_remote_site(s):
    """只保留 api 是完整 http(s) 的远程站点"""
    api = s.get("api", "")
    if not api.startswith("http"):
        return False
    bad = ("127.0.0.1", "socks5", "./", "csp_", "file://")
    return not any(b in api for b in bad)


def site_priority(s):
    name = (s.get("name") or s.get("key") or "")
    score = 0
    for kw in PRIORITY_KEYWORDS:
        if kw.lower() in name.lower():
            score += 1
    return score


def build_single_json(alive):
    sites = []
    seen_keys = set()

    json_sources = [a for a in alive if a["kind"] == "json"]

    ranked = []
    for src in json_sources:
        try:
            r = requests.get(src["url"], headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
        except Exception:
            continue

        top = data.get("sites") or {}
        store = data.get("store", {}) if isinstance(data, dict) else {}
        store_sites = store.get("sites") if isinstance(store, dict) else None
        src_sites = top if isinstance(top, list) else []
        if not src_sites and isinstance(store_sites, list):
            src_sites = store_sites

        for s in src_sites:
            key = s.get("key") or s.get("name")
            if not key or key in seen_keys:
                continue
            if not is_remote_site(s):
                continue
            seen_keys.add(key)
            ranked.append({
                "site": s,
                "src_cost": src["cost"],
                "prio": site_priority(s),
            })

    ranked.sort(key=lambda x: (-x["prio"], x["src_cost"]))

    for item in ranked[:MAX_SITES]:
        sites.append(item["site"])

    lives = []
    parses = []
    spider = ""
    for item in json_sources:
        try:
            data = requests.get(item["url"], headers=HEADERS, timeout=TIMEOUT).json()
        except Exception:
            continue
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


def build_multirepo_json(alive):
    """
    多仓 JSON：只放 json 单仓，不放 txt/other/导航页
    """
    urls = []
    myurl = r"https://fastly.jsdelivr.net/gh/baggiobatistuta/my-tvbox@main/output/dancang.json"
    urls.append({"name": r"Alex的影视仓", "url": myurl})
    urls.append({"name": r"小盒子", "url": "http://xhztv.top/xhz"})
    seen = set()
    for r in alive:
        if r["kind"] != "json":
            continue
        url = r["url"]
        if url in seen:
            continue
        seen.add(url)
        urls.append({"name": r["name"], "url": url})
    return {"urls": urls}


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

    results.sort(key=lambda x: x["cost"])

    os.makedirs("output", exist_ok=True)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        for r in results:
            if r["kind"] in ("txt", "other"):
                f.write(f"{r['name']},{r['url']}\n")

    single = build_single_json(results)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(single, f, ensure_ascii=False, indent=2)

    multirepo = build_multirepo_json(results)
    with open(OUT_MULTI_JSON, "w", encoding="utf-8") as f:
        json.dump(multirepo, f, ensure_ascii=False, indent=2)

    # ========== 直播源处理 ==========
    iptv_results = []
    if os.path.exists(IPTV):
        iptv_sources = load_sources_from(IPTV)
        log(f"读取直播候选源：{len(iptv_sources)} 个")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(check_iptv, s) for s in iptv_sources]
            for f in as_completed(futures):
                res = f.result()
                if res:
                    iptv_results.append(res)

        iptv_results.sort(key=lambda x: x["cost"])

        single["lives"] = [r["channel"] for r in iptv_results]

        with open(OUT_M3U, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for r in iptv_results:
                f.write(f"#EXTINF:-1 group-title=\"{r['channel']['name']}\",{r['channel']['name']}\n")
                f.write(f"{r['channel']['urls'][0]}\n")

        log(f"存活直播源：{len(iptv_results)} 个")
        for r in iptv_results:
            log(f"  {r['cost']}s  {r['name']}")

    log(f"存活源：{len(results)} 个")
    for r in results:
        log(f"  {r['cost']}s  {r['name']}  [{r['kind']}]")
    log(f"单仓 sites 数量：{len(single['sites'])}")


if __name__ == "__main__":
    main()
