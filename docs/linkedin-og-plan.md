## Goal
Make every `/project/<projectId>` URL produce static HTML meta tags (title, description, hero image) so LinkedIn scrapers display the correct preview instead of the site-wide default image.

## Current Situation
- The router serves project pages via React (`BrowserRouter`) with client-side rendering only. The initial HTML that LinkedIn fetches is `index.html` with a single Open Graph image (`https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png`), so LinkedIn cannot see per-project metadata.
- The standard project branch in `components/ProjectView.tsx` injects `<Helmet>` tags that include `og:title`, `og:description`, `og:image`, `twitter:card`, etc. Two project branches (`next-gen-analytics-sql`, `next-gen-analytics-memory`) provide title/description but skip the image tags. Legacy projects rendered via `LegacyProjectPage` never mount `<Helmet>`, so they inherit only the global defaults.

## Plan
1. **Catalog Required Metadata**
   - For each project ensure `constants.ts` supplies the fields needed for social cards (`title`, `description`, `coverUrl`). Example: `coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Agent%20demo.gif'`.
   - Fill gaps for special projects (e.g., add `coverUrl` for `next-gen-analytics-memory`) and legacy items. Where only `imageUrl` exists, decide whether to reuse it or add a higher-resolution static PNG for better previews.

2. **Normalize Helmet Blocks**
   - Update `ProjectView.tsx` so every branch sets the same complete Open Graph / Twitter meta set. For example, add:
     ```tsx
     <meta property="og:image" content={project.coverUrl ?? FALLBACK_OG} />
     <meta name="twitter:image" content={project.coverUrl ?? FALLBACK_OG} />
     ```
   - Ensure legacy pages rendered through `LegacyProjectPage` call a shared `<ProjectHelmet project={project} />` component before returning their content.

3. **Introduce Static Prerendering**
   - Adopt Vite SSG or SSR to emit HTML snapshots with meta tags baked in. Options:
     - **vite-plugin-ssr** or **Vite SSG**: run at build time to generate `/project/<id>/index.html` files.
     - **Prerender script**: use `npm run build` followed by `node scripts/prerender-projects.mjs` which loads each route via `renderToString` and writes HTML.
   - Example with Vite SSG:
     ```ts
     // ssr.tsx
     export async function render(url, context) {
       return renderToString(<App url={url} />);
     }
     ```
     Then configure `vite-ssg.config.ts` to iterate over `PROJECT_DATA.map(p => `/project/${p.id}`)`.

4. **Serve Prerendered Pages**
   - Update deployment (e.g., Vercel/Netlify/Azure Static Web Apps) to publish the generated static routes. Confirm the server returns the prerendered HTML for GET `/project/<id>`.
   - If hosting on an object store (e.g., Azure Blob Static Website), upload the prerendered pages alongside the SPA assets and configure redirects so navigation still works.

5. **Add Build Verification**
   - Extend CI or local `npm run build` pipeline to fail if prerendering errors. Example workflow:
     1. `npm run build`
     2. `npm run prerender` (new script) — prints each route rendered.
     3. `node scripts/check-meta.js --route /project/agentic-trade-bot --expect og:image`
   - Include a Jest/Vitest snapshot test that renders `<ProjectHelmet>` and asserts the meta tags.

6. **Validate with LinkedIn Debugger**
   - After deploying, run `https://www.linkedin.com/post-inspector/inspect/<encoded-project-url>` to force a crawl and confirm the preview shows the project-specific hero image.
   - Document the validation checklist (route, image URL, timestamp) in `docs/social-sharing-validation.md` for future updates.

7. **Optional: Edge Rendering Fallback**
   - If full SSG is not feasible, configure a lightweight prerender proxy (e.g., Rendertron, Cloudflare Workers) to detect social bots (`User-Agent` contains `LinkedInBot`) and serve headless-rendered HTML with the correct meta.
   - Cache prerender responses for each project to avoid runtime costs; invalidate when `constants.ts` changes.

## Deliverables
- Normalized metadata component used by all project variants.
- Prerender pipeline producing HTML with embedded Open Graph/Twitter tags.
- Deployment instructions and validation checklist ensuring LinkedIn previews stay accurate.
