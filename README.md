# 每周新片豆瓣评分

每周自动抓取 [电影港](https://www.dygangs.net/ys/index.htm) 最新电影，查询豆瓣评分，更新到 GitHub Pages。

**👉 访问地址：`https://<你的用户名>.github.io/<仓库名>/`**

---

## 文件结构

```
├── index.html          # 展示页面（固定地址，书签永久有效）
├── movies.json         # 所有电影数据（增量累积）
├── scripts/
│   └── fetch_movies.py # 爬虫脚本
└── .github/
    └── workflows/
        └── daily-update.yml  # 每周一 09:30 自动运行
```

## 部署步骤

1. 在 GitHub 新建一个 **公开仓库**（如 `daily-movies`）
2. 把这个文件夹的所有内容推送上去：
   ```bash
   cd gh-deploy
   git init
   git remote add origin https://github.com/<你的用户名>/daily-movies.git
   git add .
   git commit -m "init"
   git push -u origin main
   ```
3. 进入仓库 → **Settings → Pages**
   - Source 选 `Deploy from a branch`
   - Branch 选 `main`，目录选 `/ (root)`
   - 点 Save
4. 等 1~2 分钟，访问 `https://<你的用户名>.github.io/daily-movies/` 即可

> 之后每周一早上 09:30 GitHub Actions 会自动运行，更新 `index.html` 和 `movies.json`，刷新页面即可看到新内容。也可以在 Actions 页面点 **Run workflow** 手动触发。
