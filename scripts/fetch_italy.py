#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取电影港意大利电影
- 遍历最新电影列表，筛选产地包含意大利的电影
- 获取详情和豆瓣评分
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
from datetime import datetime
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
DATA_FILE = os.path.join(ROOT, "italy_movies.json")


# ──────────────────────────────────────────
# 1. 获取意大利电影
# ──────────────────────────────────────────
def fetch_italy_movies(limit=10):
    """从电影港首页及分页获取意大利相关电影"""
    movies = []
    seen = set()
    page = 1
    max_pages = 50  # 增加到50页
    
    while len(movies) < limit and page <= max_pages:
        if page == 1:
            url = "https://www.dygangs.net/ys/index.htm"
        else:
            url = f"https://www.dygangs.net/ys/index_{page}.htm"
        
        print(f"📡 检查第 {page} 页...")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.encoding = "gb2312"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  ❌ 抓取失败: {e}")
            page += 1
            continue
        
        found_italy = False
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # 只获取电影详情页链接
            if not re.search(r"/ys/\d{8}/\d+\.htm", href):
                continue
            
            title = (a.get("title") or a.get_text()).strip()
            if not title or title in seen:
                continue
            seen.add(title)
            
            full_url = href if href.startswith("http") else "https://www.dygangs.net" + href
            
            # 检查产地是否包含意大利
            country = check_country(full_url)
            if country and "意大利" in country:
                print(f"  ✅ 找到意大利电影: {title} ({country})")
                movies.append({
                    "title": title,
                    "source_url": full_url,
                    "country": country,
                })
                if len(movies) >= limit:
                    break
                found_italy = True
            time.sleep(0.3)  # 减少延迟
        
        if found_italy:
            print(f"  本页找到 {len([m for m in movies])} 部")
        
        page += 1
        time.sleep(0.5)
    
    print(f"✅ 共找到 {len(movies)} 部意大利电影")
    return movies


def check_country(url):
    """检查电影详情页的产地"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "gb2312"
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()
        
        # 匹配产地字段（中文冒号）
        match = re.search(r"◎产　　地[：:]\s*(.+?)(?:\n|$)", text)
        if match:
            return match.group(1).strip()
        return None
    except:
        return None


# ──────────────────────────────────────────
# 2. 抓取电影详情
# ──────────────────────────────────────────
def fetch_movie_detail(url):
    """从电影详情页抓取完整信息"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "gb2312"
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()
        
        # 产地
        country_match = re.search(r"◎产　　地[：:]\s*(.+?)(?:\n|$)", text)
        country = country_match.group(1).strip() if country_match else ""
        
        # 类别
        category_match = re.search(r"◎类　　别[：:]\s*(.+?)(?:\n|$)", text)
        category = category_match.group(1).strip() if category_match else ""
        
        # 导演
        director_match = re.search(r"◎导　　演[：:]\s*(.+?)(?:\n◎|$)", text)
        director = director_match.group(1).strip() if director_match else ""
        director = director.replace("&middot;", "·")
        director = director.split(" ")[0].replace("·", "") if director else ""
        
        # 主演
        actor_match = re.search(r"◎主　　演[：:]\s*(.+?)(?:\n◎|$)", text, re.DOTALL)
        actors_raw = actor_match.group(1).strip() if actor_match else ""
        actors_raw = re.sub(r"<br\s*/?>", "\n", actors_raw, flags=re.I)
        actors_raw = actors_raw.replace("&middot;", "·")
        actor_lines = actors_raw.split("\n")
        actor_list = []
        for line in actor_lines:
            line = line.lstrip("　 ").strip()
            if not line:
                continue
            parts = line.split(" ")
            if parts:
                name = parts[0].replace("·", "").strip()
                if name and name not in actor_list:
                    actor_list.append(name)
                    if len(actor_list) >= 5:
                        break
        actors = " / ".join(actor_list) if actor_list else ""
        
        # 简介
        intro_match = re.search(r"◎简　　介[：:]\s*\n?　*(.+?)(?:\n【|$)", text, re.DOTALL)
        intro = intro_match.group(1).strip() if intro_match else ""
        intro = re.sub(r"\s+", " ", intro).strip()
        intro = intro[:100] + "..." if len(intro) > 100 else intro
        
        return {
            "country": country,
            "category": category,
            "director": director,
            "actors": actors,
            "intro": intro
        }
    except Exception as e:
        print(f"  ⚠️ 详情页抓取失败: {e}")
        return {"country": "", "category": "", "director": "", "actors": "", "intro": ""}


# ──────────────────────────────────────────
# 3. 查豆瓣评分
# ──────────────────────────────────────────
def search_douban(title):
    """搜索豆瓣评分（严格匹配）"""
    search_url = f"https://www.douban.com/search?cat=1002&q={quote(title)}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select(".result-list .result")
        
        if not results:
            return None, None, None, None
        
        for result in results:
            name_tag = result.select_one(".title a")
            found_name = name_tag.get_text(strip=True) if name_tag else ""
            
            if found_name and title in found_name:
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
                
                print(f"    ✅ 匹配: {found_name}")
                return rating, count, link, found_name
        
        # 无精确匹配，返回第一个
        result = results[0]
        name_tag = result.select_one(".title a")
        found_name = name_tag.get_text(strip=True) if name_tag else ""
        print(f"    ⚠️ 未精确匹配 [{title}] → {found_name}")
        
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
        
        return rating, count, link, found_name
    except Exception as e:
        print(f"  ⚠️ 豆瓣搜索失败 [{title}]: {e}")
        return None, None, None, None


# ──────────────────────────────────────────
# 4. 保存和加载
# ──────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────
# 5. 渲染 HTML
# ──────────────────────────────────────────
PAGE_SIZE = 10

def render_html(all_movies):
    """渲染意大利电影页面"""
    updated_at = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    total_pages = max(1, (len(all_movies) + PAGE_SIZE - 1) // PAGE_SIZE)
    
    # 分页导航
    pagination_html = ""
    if total_pages > 1:
        for p in range(1, total_pages + 1):
            pagination_html += f'<button class="page-btn" onclick="showPage({p})">{p}</button>'
        pagination_html = f'<div class="pagination">{pagination_html}</div>'
    
    cards = ""
    for i, m in enumerate(all_movies, 1):
        page_num = (i - 1) // PAGE_SIZE + 1
        rating = m.get("rating") or "—"
        count = m.get("count") or ""
        db_link = m.get("douban_link") or ""
        found = m.get("found_name") or ""
        
        country = m.get("country") or ""
        category = m.get("category") or ""
        director = m.get("director") or ""
        actors = m.get("actors") or ""
        intro = m.get("intro") or ""
        
        # 评分颜色
        try:
            r = float(rating)
            rc = "high" if r >= 8 else ("mid" if r >= 6 else "low")
        except:
            rc = "none"
        
        # 豆瓣链接
        if db_link:
            hint = f' <span class="fn">({found})</span>' if found and found != m["title"] else ""
            db_cell = f'<a href="{db_link}" target="_blank" class="dbl">豆瓣{hint}</a>'
        else:
            db_cell = '<span class="na">暂无</span>'
        
        # 导演链接
        director_html = ""
        if director:
            director_link = f"https://www.baidu.com/s?wd={quote(director)}"
            director_html = f'🎬 <a href="{director_link}" target="_blank" class="search-link">{director}</a>'
        
        # 主演链接
        actors_html = ""
        if actors:
            actor_links = []
            for a in actors.split(" / "):
                if a:
                    link = f"https://www.baidu.com/s?wd={quote(a)}"
                    actor_links.append(f'<a href="{link}" target="_blank" class="search-link">{a}</a>')
            actors_html = "🎬 " + " / ".join(actor_links)
        
        # 详情
        info_parts = []
        if country:
            info_parts.append(f"📍 {country}")
        if category:
            info_parts.append(f"🎭 {category}")
        if director_html:
            info_parts.append(director_html)
        if actors_html:
            info_parts.append(actors_html)
        info_html = "".join([f'<p class="info">{p}</p>' for p in info_parts])
        intro_html = f'<p class="intro">{intro}</p>' if intro else ''
        
        cards += f"""
      <div class="card page-{page_num}">
        <div class="card-header">
          <span class="num">{i}</span>
          <span class="title"><a href="{m['source_url']}" target="_blank">{m['title']}</a></span>
        </div>
        <div class="card-body">
          {info_html}
          {intro_html}
        </div>
        <div class="card-footer">
          <span class="rating {rc}">{rating}</span>
          <span class="count">{count}</span>
          {db_cell}
        </div>
      </div>"""
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>意大利电影 - 豆瓣评分</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#f4f4f8;color:#333}}
.wrap{{max-width:900px;margin:32px auto;padding:0 16px}}
.nav-link{{margin-bottom:16px}}
.nav-link a{{color:#1a73e8;text-decoration:none;font-size:14px}}
.nav-link a:hover{{text-decoration:underline}}
h1{{font-size:22px;font-weight:700;margin-bottom:4px;display:flex;align-items:center;gap:8px}}
.sub{{color:#999;font-size:13px;margin-bottom:22px}}
.cards{{display:flex;flex-direction:column;gap:16px}}
.card{{background:#fff;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,.08);overflow:hidden}}
.card.hidden{{display:none}}
.card-header{{display:flex;align-items:center;padding:14px 16px;background:#1a1a2e;color:#fff;gap:10px}}
.card-header .num{{background:rgba(255,255,255,.2);width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px}}
.card-header .title{{flex:1;font-size:16px;font-weight:600}}
.card-header .title a{{color:#fff;text-decoration:none}}
.card-header .title a:hover{{text-decoration:underline}}
.card-body{{padding:14px 16px}}
.info{{font-size:13px;color:#666;line-height:1.6;margin-bottom:4px}}
.info:first-child{{margin-top:0}}
.search-link{{color:#1a73e8;text-decoration:none}}
.search-link:hover{{text-decoration:underline}}
.intro{{font-size:13px;color:#888;line-height:1.5;margin-top:8px;padding-top:8px;border-top:1px solid #eee}}
.card-footer{{display:flex;align-items:center;padding:12px 16px;background:#fafafa;border-top:1px solid #f0f0f0;gap:12px}}
.rating{{font-size:20px;font-weight:700}}
.rating.high{{color:#e06c00}}.rating.mid{{color:#27ae60}}.rating.low{{color:#e74c3c}}.rating.none{{color:#ccc;font-size:16px}}
.count{{color:#bbb;font-size:12px}}
.dbl{{color:#06be6b;text-decoration:none;font-size:13px;margin-left:auto}}
.dbl:hover{{text-decoration:underline}}
.na{{color:#ccc;font-size:13px;margin-left:auto}}
.pagination{{display:flex;justify-content:center;gap:8px;margin:24px 0}}
.page-btn{{padding:8px 14px;border:1px solid #ddd;border-radius:6px;background:#fff;color:#333;cursor:pointer;font-size:14px}}
.page-btn:hover{{background:#f0f0f0}}
.page-btn.active{{background:#1a1a2e;color:#fff;border-color:#1a1a2e}}
.legend{{display:flex;gap:14px;margin-top:20px;font-size:12px;color:#aaa}}
.dot{{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:3px}}
.dot.high{{background:#e06c00}}.dot.mid{{background:#27ae60}}.dot.low{{background:#e74c3c}}
footer{{text-align:center;color:#ccc;font-size:12px;margin-top:24px;padding-bottom:32px}}
.contact{{text-align:center;margin-top:16px;font-size:13px;color:#888}}
.contact a{{color:#1a73e8;text-decoration:none}}
.contact a:hover{{text-decoration:underline}}
.counter{{text-align:center;margin-top:12px;font-size:13px;color:#666;background:#f8f8fa;padding:10px;border-radius:8px}}
</style>
</head>
<body>
<div class="wrap">
  <nav class="nav-link">← <a href="index.html">返回首页</a></nav>
  <h1>🇮🇹 意大利电影</h1>
  <p class="sub">数据来源：电影港 · 豆瓣 &nbsp;|&nbsp; 最后更新：{updated_at} &nbsp;|&nbsp; 共 {len(all_movies)} 部</p>
  <div class="cards">{cards}
  </div>
  {pagination_html}
  <div class="legend">
    <span><span class="dot high"></span>8分及以上</span>
    <span><span class="dot mid"></span>6~8分</span>
    <span><span class="dot low"></span>6分以下</span>
  </div>
  <footer>每周自动更新 · 收藏此页书签永久有效</footer>
  <div class="contact">📧 联系邮箱：<a href="mailto:james_tx7878@163.com">james_tx7878@163.com</a></div>
  <div class="counter">
    <span id="busuanzi_value_site_pv"></span>
    <span id="busuanzi_value_site_uv"></span>
  </div>
</div>
<script>
function showPage(n){{
  document.querySelectorAll('.card').forEach(c=>c.classList.add('hidden'));
  document.querySelectorAll('.card.page-'+n).forEach(c=>c.classList.remove('hidden'));
  document.querySelectorAll('.page-btn').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.page-btn')[n-1]&&document.querySelectorAll('.page-btn')[n-1].classList.add('active');
}}
showPage(1);
</script>
<script async src="//busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js"></script>
<script>
window.onload = function() {{
  setTimeout(function() {{
    var pv = document.getElementById('busuanzi_value_site_pv');
    var uv = document.getElementById('busuanzi_value_site_uv');
    if (pv && uv) {{
      document.querySelector('.counter').innerHTML =
        '🎉 你是今日第 <strong>' + pv.innerText + '</strong> 个来访者，网站共计 <strong>' + uv.innerText + '</strong> 次访问';
    }}
  }}, 500);
}};
</script>
</body>
</html>"""
    
    with open(os.path.join(ROOT, "italy.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ italy.html 已更新（{len(all_movies)} 部电影）")


# ──────────────────────────────────────────
# main
# ──────────────────────────────────────────
def main():
    print(f"\n{'='*52}")
    print(f"  意大利电影获取  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")
    
    # 加载已有数据
    existing = load_data()
    
    # 如果没有数据，从电影港获取
    if not existing:
        print("📡 从电影港获取意大利电影...")
        new_movies = fetch_italy_movies(limit=10)
        existing = new_movies
    else:
        print(f"📂 已有 {len(existing)} 部意大利电影")
    
    # 处理每部电影的详情和评分
    for m in existing:
        if not m.get("category"):  # 如果没有详情，抓取
            print(f"  📄 抓取详情: {m['title']}")
            detail = fetch_movie_detail(m["source_url"])
            m["category"] = detail.get("category", "")
            m["director"] = detail.get("director", "")
            m["actors"] = detail.get("actors", "")
            m["intro"] = detail.get("intro", "")
            time.sleep(0.5)
        
        if not m.get("rating"):  # 如果没有评分，获取
            rating, count, link, found = search_douban(m["title"])
            m["rating"] = rating
            m["count"] = count
            m["douban_link"] = link
            m["found_name"] = found
            print(f"  🎬 {m['title']:<20} 豆瓣: {rating or '暂无'}")
            time.sleep(1)
        
        m["added_at"] = datetime.now().strftime("%Y-%m-%d")
    
    save_data(existing)
    render_html(existing)
    
    print(f"\n{'─'*60}")
    for i, m in enumerate(existing, 1):
        print(f"{i:<4}{m['title']:<20}{m.get('country', '')[:15]:<15}{m.get('rating') or '—'}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
