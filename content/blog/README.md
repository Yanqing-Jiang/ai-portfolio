# Blog Authoring Guide

Self-hosted MDX blog at `/blog`. Each post is one `.mdx` file in this folder
plus an image folder under `public/blog/<slug>/`. No CMS, no database — just
files in git.

```
content/blog/<slug>.mdx           ← prose + frontmatter
public/blog/<slug>/img-01.png     ← hero + body images (served at /blog/<slug>/img-N.ext)
public/blog/<slug>/img-02.jpg
```

Posts are loaded at build time by `lib/blog/mdx.ts` via Vite's
`import.meta.glob('/content/blog/*.mdx')` — drop a file in, it shows up.

---

## Three ways to publish

### 1. Mirror an existing Medium post → local

```bash
node scripts/medium-import.mjs                    # all posts from default RSS
node scripts/medium-import.mjs --slug some-slug   # one post only
node scripts/medium-import.mjs --force            # overwrite existing MDX
node scripts/medium-import.mjs --dry              # parse only, write nothing
node scripts/medium-import.mjs --feed ./rss.xml   # use cached RSS (avoid 403s)
node scripts/medium-import.mjs --handle other     # different author
```

The script:

1. Fetches `https://medium.com/feed/@<handle>` (10 most recent posts).
2. For each post, downloads every `<img>` into `public/blog/<slug>/img-NN.<ext>`.
3. Rewrites image URLs to local paths.
4. Maps Medium categories → `BlogTag` enum (see `TAG_MAP` in the script).
5. Emits `content/blog/<slug>.mdx` with frontmatter matching `_schema.ts`.

Re-running is safe: existing MDX is skipped, missing images are still
downloaded. Add `--force` to re-overwrite.

> **403 from Medium?** Their feed/CDN occasionally rate-limits. The script
> falls through `cdn-images-1.medium.com → miro.medium.com/v2/...` for images.
> If the feed itself 403s, save it once via `curl https://medium.com/feed/@yanqing_j -o /tmp/medium-rss.xml`
> and pass `--feed /tmp/medium-rss.xml`.

### 2. Write a new post from scratch

```bash
SLUG=intent-custody-is-the-next-moat
mkdir -p public/blog/$SLUG
cp scripts/post-template.mdx content/blog/$SLUG.mdx
# then: edit slug in frontmatter, drop hero into public/blog/$SLUG/img-01.png, write
```

(Template lives in `scripts/` rather than `content/blog/` so the MDX glob
in `lib/blog/mdx.ts` doesn't try to load it as a post.)

Then update the frontmatter (slug **must** match the filename) and reload
`http://localhost:5173/blog`.

### 3. Cross-post local → Medium (manual, Medium-side)

The frontmatter `canonical` field points back to the Medium URL when this
local copy is the mirror. When the **local** post is the canonical and you
later cross-post to Medium, do this on Medium's side via Story Settings →
Advanced → Customize canonical link → paste `https://yanqing.app/blog/<slug>`.

---

## Frontmatter reference

```ts
export const frontmatter = {
  title: 'Display title',                   // required
  slug: 'matches-filename',                 // required, lowercase-kebab
  description:                              // required, 1–2 sentences (~155 char target — Google snippet)
    'Why X beats Y: a field report from shipping AI in production.',
  publishedAt: '2026-05-03',                // required, ISO YYYY-MM-DD
  updatedAt: '2026-05-04',                  // optional — bumps Article.dateModified
  tags: ['agents', 'llm-eng'],              // ≥1 tag, see _schema.ts BlogTag.
                                            // FIRST tag drives the "Field Notes · X" eyebrow,
                                            // article:section meta, and SERP topic chip.
  // canonical: 'https://other.com/...',    // OMIT for self-canonical (default).
                                            // Only set when another URL should be the SEO source.
  mediumUrl: 'https://medium.com/...',      // optional — added by importer; renders the
                                            // "Originally on Medium" courtesy link in the footer
                                            // and shows up in Article.sameAs (no SEO hand-off).
  wordCount: 944,                           // optional — baked in by importer; Article.wordCount
  readingMinutes: 5,                        // optional — baked in by importer; Article.timeRequired
  ogImage: '/blog/<slug>/og.png',           // optional — overrides hero for OG card
  draft: false,                             // optional — true hides from index/sitemap/RSS
  series: { name: 'Director of Agents', order: 2 }, // optional
  author: 'yanqing-jiang',                  // required (only author for now)
  hero: {
    src: '/blog/<slug>/img-01.png',         // local now; can be Azure Blob URL later
    alt: 'Topology diagram of bounded agents',  // ALSO used for og:image:alt
    caption: 'Bounded agents with explicit tool budgets.',
  },
};
```

### SEO baked in (per post)

Each post automatically ships:

- Self-canonical (`https://yanqing.app/blog/<slug>`) unless `canonical` is set
- Title pattern `Title | <PrimaryTag> — Yanqing Jiang`
- Open Graph + Twitter `summary_large_image` cards with absolute image URLs
- `article:section` (human-readable lead tag), `article:tag` per tag
- JSON-LD `Article` (with `wordCount`, `timeRequired`, `inLanguage`, `articleSection`,
  `author.sameAs` to Medium/LinkedIn/X/GitHub, `publisher.logo`, and
  `sameAs: [mediumUrl]` when mirrored)
- JSON-LD `BreadcrumbList` (Home › Field Notes › Title)
- `<link rel="alternate" type="application/rss+xml">` discovery
- `robots: index, follow, max-image-preview:large, max-snippet:-1`
- First body image: raw `<img>` with explicit `width`/`height`,
  `loading="eager"`, `fetchPriority="high"`, `decoding="async"` — pre-loaded
  via `<link rel="preload">` from the rendered `<img>` (LCP optimization)
- Other body images: explicit `width`/`height`, `loading="lazy"`, `decoding="async"` (CLS prevention)
- Top-level Medium `<h3>` is rewritten to `<h2>` so the document hierarchy is
  semantically valid (the article title is the only `<h1>`) and the right-rail
  TOC populates correctly.

Validation lives in `content/blog/_schema.ts` (`isValidFrontmatter`). Posts
that fail the check log a warning at build time and are dropped from the
index.

### Available tags

`agents`, `llm-eng`, `a2ui`, `claude`, `rag`, `evals`, `finance`, `infra`,
`devops`, `analytics`, `skills`, `personal-ai`, `philosophy`, `career`,
`vibe-coding`. Add more in `_schema.ts` when you start a new editorial lane —
they auto-surface as `/blog/tag/<tag>` filter pages.

---

## Image conventions

- **Local first.** Images live under `public/blog/<slug>/`. Vite serves them
  at `/blog/<slug>/<file>` in dev and bakes them into `dist/blog/<slug>/`
  during `npm run build`.
- **Naming.** Importer uses `img-01.png`, `img-02.jpg`, … in source order.
  When authoring by hand, anything goes — `hero.png`, `arch-diagram.svg`,
  whatever. Just reference them with the absolute path `/blog/<slug>/...`.
- **Hero image.** First image becomes `frontmatter.hero` automatically when
  importing. For hand-authored posts set it explicitly — the index page
  thumbnail falls back to a topic-seeded picsum if missing.
- **Future Azure Blob sync.** When ready to offload bandwidth, run a sync
  step (TBD: `scripts/blog-sync-blob.mjs`) that uploads every
  `public/blog/<slug>/` folder to
  `yanqinghot.blob.core.windows.net/public/blog/<slug>/...` and rewrites the
  `hero.src` + body image refs to the blob URLs. Until then, local hosting
  is fine — Cloudflare Pages serves them.

---

## Local preview

```bash
npm run dev                 # http://localhost:5173/blog
npm run build               # full prerender — emits /blog/<slug>/index.html
                            # PLUS dist/sitemap.xml and dist/rss.xml
npx tsc --noEmit            # type check
```

Watch for `[blog]` warnings in the dev console — they flag invalid
frontmatter or slug ↔ filename mismatches.

### Build artifacts that matter for SEO

After `npm run build`:

- `dist/blog/<slug>/index.html` — fully prerendered post (body + Helmet head
  + JSON-LD), single `<title>` and `<meta description>` per page (the
  prerender script dedupes Helmet's output)
- `dist/sitemap.xml` — every post + project + page with `<lastmod>`
- `dist/rss.xml` — full RSS 2.0 feed with `content:encoded` for each post
  (root-relative image URLs are absolutized to `https://yanqing.app/...`)
- `dist/blog/tag/<tag>/index.html` — one filtered index per active tag

---

## Editorial lanes (Yanqing's three angles)

When picking tags or pitching a new post, anchor to one of:

1. **Intent Custody** → `agents`, `personal-ai`, `claude`
2. **Harness Engineering for Analytics** → `analytics`, `a2ui`, `evals`
3. **Skills as the new SaaS** → `skills`, `agents`, `claude`

Plus the open lanes: `philosophy`, `career`, `vibe-coding`, `finance`.
