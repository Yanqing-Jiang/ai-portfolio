# IndexNow setup

IndexNow notifies Bing (and any IndexNow-aware engine — DuckDuckGo, Yandex, Seznam, Naver) the moment we deploy new content, instead of waiting for the next crawl. Bing's index also powers Copilot, Perplexity's fallback, and many AI-search citations.

## One-time setup

1. Generate an API key at https://www.bing.com/indexnow (free; no Bing Webmaster account required, but we should set one up too).
2. Drop the key in this `public/` directory as `<KEY>.txt` containing only the key string. Cloudflare Pages serves it at `https://yanqing.app/<KEY>.txt` — IndexNow uses this file to verify domain ownership on each request.
3. Add the key to GitHub Actions secrets as `INDEXNOW_KEY`.
4. In `.github/workflows/deploy.yml`, set `INDEXNOW_KEY: ${{ secrets.INDEXNOW_KEY }}` in the env for the build step.

## How it fires

`scripts/prerender.mjs` reads `process.env.INDEXNOW_KEY` after writing `sitemap.xml` and POSTs all URLs to `https://api.indexnow.org/indexnow`. Skipped silently in local dev when the env var is unset.

## Verifying

After a deploy:
- Check the Actions log for `IndexNow ping succeeded: N URLs submitted`.
- In Bing Webmaster Tools → IndexNow tab, you'll see the submission count.
- New pages typically appear in Bing within minutes (vs hours/days from crawl).

## Reference

- IndexNow protocol: https://www.indexnow.org/documentation
- Bing's IndexNow guide: https://www.bing.com/indexnow

This file is informational and is fine to deploy publicly.
