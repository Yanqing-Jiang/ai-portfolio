import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const distDir = path.resolve(__dirname, '../dist');
const ssrEntryPath = path.resolve(__dirname, '../dist-ssr/entry-server.js');

const template = await readFile(path.join(distDir, 'index.html'), 'utf-8');

const { render, getRoutes, getSitemapEntries } = await import(pathToFileURL(ssrEntryPath).href);

const routes = getRoutes();

for (const route of routes) {
  const { html, headTags } = render(route);

  const withHead = template.replace('</head>', `${headTags}\n</head>`);
  const withAppHtml = withHead.replace(
    /<div id="root"><\/div>/,
    `<div id="root">${html}</div>`
  );

  const outputRelative =
    route === '/' ? 'index.html' : path.join(route.replace(/^\//, ''), 'index.html');
  const outputPath = path.join(distDir, outputRelative);

  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, withAppHtml, 'utf-8');

  console.log(`Prerendered ${route} -> ${outputRelative}`);
}

const { pages, projects } = getSitemapEntries();
const today = new Date().toISOString().split('T')[0];

const formatDate = (value) => {
  if (!value) return today;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return today;
  return date.toISOString().split('T')[0];
};

const buildUrlEntry = ({ loc, lastModified, changefreq, priority }) => {
  const pieces = [
    `  <url>`,
    `    <loc>${loc}</loc>`,
    `    <lastmod>${formatDate(lastModified)}</lastmod>`,
  ];

  if (changefreq) {
    pieces.push(`    <changefreq>${changefreq}</changefreq>`);
  }
  if (typeof priority === 'number') {
    pieces.push(`    <priority>${priority.toFixed(2)}</priority>`);
  }

  pieces.push('  </url>');
  return pieces.join('\n');
};

const buildUrlSet = (entries) => [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...entries.map(buildUrlEntry),
  '</urlset>',
].join('\n');

const sitemapPagesXml = buildUrlSet(pages);
const sitemapProjectsXml = buildUrlSet(projects);

const rootDir = path.resolve(__dirname, '..');
await writeFile(path.join(rootDir, 'sitemap-pages.xml'), sitemapPagesXml, 'utf-8');
await writeFile(path.join(rootDir, 'sitemap-projects.xml'), sitemapProjectsXml, 'utf-8');
await mkdir(distDir, { recursive: true });
await writeFile(path.join(distDir, 'sitemap-pages.xml'), sitemapPagesXml, 'utf-8');
await writeFile(path.join(distDir, 'sitemap-projects.xml'), sitemapProjectsXml, 'utf-8');

const siteOrigin = pages[0] ? `${new URL(pages[0].loc).origin}/` : 'https://ai.jiangyanqing.com/';
const sitemapIndexXml = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  `  <sitemap>`,
  `    <loc>${new URL('sitemap-pages.xml', siteOrigin).toString()}</loc>`,
  `    <lastmod>${formatDate(pages[0]?.lastModified)}</lastmod>`,
  '  </sitemap>',
  '  <sitemap>',
  `    <loc>${new URL('sitemap-projects.xml', siteOrigin).toString()}</loc>`,
  `    <lastmod>${formatDate(projects[0]?.lastModified)}</lastmod>`,
  '  </sitemap>',
  '</sitemapindex>',
].join('\n');

await writeFile(path.join(rootDir, 'sitemap.xml'), sitemapIndexXml, 'utf-8');
await writeFile(path.join(distDir, 'sitemap.xml'), sitemapIndexXml, 'utf-8');

console.log('Generated sitemap.xml, sitemap-pages.xml, and sitemap-projects.xml');

if (process.env.PING_SITEMAPS === '1') {
  const sitemapUrl = new URL('sitemap.xml', siteOrigin).toString();
  const endpoints = [
    `https://www.google.com/ping?sitemap=${encodeURIComponent(sitemapUrl)}`,
    `https://www.bing.com/ping?sitemap=${encodeURIComponent(sitemapUrl)}`,
  ];

  await Promise.all(
    endpoints.map(async (endpoint) => {
      try {
        const response = await fetch(endpoint, { method: 'GET' });
        if (!response.ok) {
          console.warn(`Sitemap ping failed for ${endpoint}: ${response.status}`);
        } else {
          console.log(`Sitemap ping succeeded for ${endpoint}`);
        }
      } catch (error) {
        console.warn(`Sitemap ping threw for ${endpoint}`, error);
      }
    })
  );
}
