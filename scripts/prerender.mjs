import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const distDir = path.resolve(__dirname, '../dist');
const ssrEntryPath = path.resolve(__dirname, '../dist-ssr/entry-server.js');

const template = await readFile(path.join(distDir, 'index.html'), 'utf-8');

const { render, getRoutes } = await import(pathToFileURL(ssrEntryPath).href);

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
