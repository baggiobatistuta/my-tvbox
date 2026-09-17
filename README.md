# my-tvbox

自动检测并生成影视仓配置文件的 GitHub Actions 仓库。

## 文件说明

| 文件 | 用途 |
|---|---|
| `sources.txt` | 点播源列表（name,url），每行一个 |
| `iptv.txt` | 直播源列表（name,url），每行一个 |
| `check.py` | 核心检测脚本，抓取源→校验→生成配置 |
| `output/dancang.json` | **单仓配置**（影视仓 3.3.7 配置地址直填） |
| `output/multicang.json` | **多仓配置**（影视仓选仓库用） |
| `output/iptv.m3u` | 直播源 m3u 文件 |
| `output/multi.txt` | 存活的多仓 txt 列表 |

## 影视仓填法

### 推荐：单仓直填（搜索正常）

配置地址填：


https://fastly.jsdelivr.net/gh/baggiobatistuta/my-tvbox@main/output/dancang.json


> 3.3.7 版本单仓模式下搜索功能正常，这是最稳的用法。

### 备选：多仓模式（仅用于选仓库）

多仓地址填：


https://fastly.jsdelivr.net/gh/baggiobatistuta/my-tvbox@main/output/multicang.json


> ⚠️ 多仓模式下搜索有 bug（多仓套单仓搜不到），选完仓库后建议切回单仓模式使用。

## sources.txt 格式

txt
名字,https://example.com/tv.json
另一个源,https://xxx.com/api


规则：
- 一行一个，逗号分隔名字和地址
- 地址必须是 **https**（http 在某些网络下会被拦截）
- 地址打开后必须直接返回 `{ "sites": [...] }` 格式的 JSON
- 不要放导航页、域名出售页、README、中文域名主页
- `raw.githubusercontent.com` 原域名建议走 jsDelivr 镜像：
  
  https://fastly.jsdelivr.net/gh/用户名/仓库@分支/路径.json


## check.py 做了什么

1. **检测存活**：并发请求 `sources.txt` 里每个源，超时 6 秒
2. **过滤垃圾**：自动丢弃返回 HTML 导航页、域名出售页、非 JSON 内容的地址
3. **清洗站点**：从存活源里提取 `sites`，自动过滤掉：
   - `csp_*` 本地爬虫站
   - `./lib/` `./jar/` `./js/` 本地依赖
   - `127.0.0.1` / `socks5` 本机服务
   - `file://` 本地文件
4. **生成配置**：
   - `dancang.json`：只含远程 API 站，影视仓直填可用
   - `multicang.json`：只含 json 单仓入口，用于多仓选源
   - `iptv.m3u`：存活直播源合并

## 自动运行

- **每日自动**：GitHub Actions 每天定时跑一次，自动更新 `output/` 下所有文件
- **手动触发**：仓库 → Actions → 选工作流 → Run workflow

## 维护须知

> TVBox 免费源的平均寿命以周/月计。如果某天突然搜不到或首页空了：
> 1. 打开 `sources.txt` 里的地址，看是否还能返回 JSON
> 2. 死了的删掉，换新的进去
> 3. 重新跑 Actions 即可

找新源可以去：TVBox 相关 Telegram 群、GitHub 搜索 `tvbox json`、`TVBox源`、`FongMi` 等关键词。

## 版本兼容

| 影视仓版本 | 单仓 | 多仓搜索 |
|---|---|---|
| 3.3.7 | ✅ 正常 | ❌ 有 bug |
| 其他版本 | 视情况 | 视情况 |

当前仓库按 **3.3.7 单仓直填** 最优路径维护。


要不要我再帮你写一个 .github/workflows/update.yml 的 Actions 配置（定时每天跑 + 自动 commit push），这样你仓库就全自动了，不用手动触发？
