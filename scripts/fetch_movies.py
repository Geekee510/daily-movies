#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日新片 + 豆瓣评分汇总
- 增量更新：新片追加到 movies.json，不重复抓已有条目
- 重新渲染 index.html（固定路径，书签永久有效）
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
from datetime import datetime, timedelta
from urllib.parse import quote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "movies.json")
HTML_FILE = os.path.join(ROOT, "index.html")


# ──────────────────────────────────────────
# 1. 抓取电影港新片
# ──────────────────────────────────────────
def fetch_new_movies(days=2):
    url = "https://www.dygangs.net/ys/index.htm"
    print(f"📡 抓取电影港首页...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = "gb2312"
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return []

    date_prefixes = set()
    for i in range(days):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        date_prefixes.add(d)

    movies, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/ys/(\d{8})/(\d+)\.htm", href)
        if not m:
            continue
        date_str = m.group(1)
        if date_str not in date_prefixes:
            continue
        title = (a.get("title") or a.get_text()).strip()
        if not title or title in seen:
            continue
        seen.add(title)
        full_url = href if href.startswith("http") else "https://www.dygangs.net" + href
        movies.append({"title": title, "date": date_str, "source_url": full_url})

    movies.sort(key=lambda x: x["date"], reverse=True)
    print(f"✅ 找到 {len(movies)} 部新片")
    return movies


# ──────────────────────────────────────────
# 2. 查豆瓣评分
# ──────────────────────────────────────────
def search_douban(title):
    search_url = f"https://www.douban.com/search?cat=1002&q={quote(title)}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        result = soup.select_one(".result-list .result")
        if not result:
            return None, None, None, None

        rating_tag = result.select_one(".rating_nums")
        rating = rating_tag.get_text(strip=True) if rating_tag else None

        count_tag = result.select_one(".subject-cast")
        count = None
        if count_tag:
            cm = re.search(r"([\d,]+)人", count_tag.get_text())
            if cm:
                count = cm.group(1).replace(",", "") + "人"

        link_tag = result.select_one("a[href*='douban.com/subject']")
        link = link_tag["href"].split("?")[0] if link_tag else None

        name_tag = result.select_one(".title a")
        found_name = name_tag.get_text(strip=True) if name_tag else ""

        return rating, count, link, found_name
    except Exception as e:
        print(f"  ⚠️  豆瓣搜索失败 [{title}]: {e}")
        return None, None, None, None


# ──────────────────────────────────────────
# 3. 增量更新 movies.json
# ──────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_movies(existing, new_movies):
    existing_titles = {m["title"] for m in existing}
    added = []
    for m in new_movies:
        if m["title"] not in existing_titles:
            added.append(m)
    return added


# ──────────────────────────────────────────
# 4. 渲染 index.html
# ──────────────────────────────────────────
def render_html(all_movies):
    updated_at = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    rows = ""
    for i, m in enumerate(all_movies, 1):
        rating    = m.get("rating") or "—"
        count     = m.get("count") or ""
        db_link   = m.get("douban_link") or ""
        found     = m.get("found_name") or ""
        date_fmt  = f"{m['date'][:4]}-{m['date'][4:6]}-{m['date'][6:]}"

        try:
            r = float(rating)
            rc = "high" if r >= 8 else ("mid" if r >= 6 else "low")
        except:
            rc = "none"

        if db_link:
            hint = f' <span class="fn">({found})</span>' if found and found != m["title"] else ""
            db_cell = f'<a href="{db_link}" target="_blank" class="dbl">豆瓣{hint}</a>'
        else:
            db_cell = '<span class="na">暂无</span>'

        rows += f"""
      <tr>
        <td class="idx">{i}</td>
        <td class="tt"><a href="{m['source_url']}" target="_blank">{m['title']}</a></td>
        <td class="dt">{date_fmt}</td>
        <td class="rt {rc}">{rating}</td>
        <td class="ct">{count}</td>
        <td class="db">{db_cell}</td>
      </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日新片豆瓣评分</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f4f4f8;color:#333}}
.wrap{{max-width:980px;margin:32px auto;padding:0 16px}}
h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
.sub{{color:#999;font-size:13px;margin-bottom:22px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 14px rgba(0,0,0,.08)}}
thead{{background:#1a1a2e;color:#fff}}
thead th{{padding:13px 11px;text-align:left;font-size:13px;font-weight:600}}
tbody tr{{border-bottom:1px solid #f0f0f0;transition:background .12s}}
tbody tr:last-child{{border-bottom:none}}
tbody tr:hover{{background:#fafafa}}
td{{padding:11px;font-size:14px;vertical-align:middle}}
.idx{{color:#ccc;width:32px;text-align:center}}
.tt a{{color:#1a73e8;text-decoration:none;font-weight:500}}
.tt a:hover{{text-decoration:underline}}
.dt{{color:#aaa;font-size:13px;white-space:nowrap}}
.rt{{font-size:18px;font-weight:700;text-align:center;width:64px}}
.rt.high{{color:#e06c00}}.rt.mid{{color:#27ae60}}.rt.low{{color:#e74c3c}}.rt.none{{color:#ccc;font-size:14px}}
.ct{{color:#bbb;font-size:12px;white-space:nowrap}}
.dbl{{color:#06be6b;text-decoration:none;font-size:13px}}
.dbl:hover{{text-decoration:underline}}
.na{{color:#ccc;font-size:13px}}
.fn{{color:#bbb;font-size:11px}}
.legend{{display:flex;gap:14px;margin-top:14px;font-size:12px;color:#aaa}}
.dot{{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:3px}}
.dot.high{{background:#e06c00}}.dot.mid{{background:#27ae60}}.dot.low{{background:#e74c3c}}
footer{{text-align:center;color:#ccc;font-size:12px;margin-top:18px;padding-bottom:32px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>🎬 每日新片豆瓣评分</h1>
  <p class="sub">数据来源：电影港 · 豆瓣 &nbsp;|&nbsp; 最后更新：{updated_at} &nbsp;|&nbsp; 共 {len(all_movies)} 部</p>
  <table>
    <thead>
      <tr><th>#</th><th>电影名称</th><th>更新日期</th><th>豆瓣评分</th><th>评分人数</th><th>豆瓣页面</th></tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
  <div class="legend">
    <span><span class="dot high"></span>8分及以上</span>
    <span><span class="dot mid"></span>6~8分</span>
    <span><span class="dot low"></span>6分以下</span>
  </div>
  <footer>每天自动更新 · 收藏此页书签永久有效</footer>
</div>
</body>
</html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html 已更新（{len(all_movies)} 部电影）")


# ──────────────────────────────────────────
# main
# ──────────────────────────────────────────
def main():
    print(f"\n{'='*52}")
    print(f"  新片豆瓣汇总  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    new_movies = fetch_new_movies(days=2)
    existing   = load_data()
    to_add     = merge_movies(existing, new_movies)

    if not to_add:
        print("📭 没有新增电影，重新渲染页面...")
        render_html(existing)
        return

    print(f"\n🆕 新增 {len(to_add)} 部，开始查豆瓣评分...\n")
    for m in to_add:
        rating, count, link, found = search_douban(m["title"])
        m["rating"]      = rating
        m["count"]       = count
        m["douban_link"] = link
        m["found_name"]  = found
        m["added_at"]    = datetime.now().strftime("%Y-%m-%d")
        print(f"  🎬 {m['title']:<20} 豆瓣: {rating or '暂无'}")
        time.sleep(1.5)

    all_movies = to_add + existing          # 新的排前面
    save_data(all_movies)
    render_html(all_movies)

    print(f"\n{'─'*60}")
    print(f"{'#':<4}{'电影名称':<22}{'日期':<12}{'豆瓣'}")
    print(f"{'─'*60}")
    for i, m in enumerate(to_add, 1):
        d = f"{m['date'][:4]}-{m['date'][4:6]}-{m['date'][6:]}"
        print(f"{i:<4}{m['title']:<22}{d:<12}{m.get('rating') or '—'}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
