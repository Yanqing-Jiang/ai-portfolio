import React from 'react';
import { renderToString } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { HelmetProvider, type FilledContext } from 'react-helmet-async';
import { AppRoutes } from '../App';
import { PROJECT_DATA } from '../constants';
import { LANDING_SEO, SITE_BASE_URL } from '../constants/seo';

export interface RenderResult {
  html: string;
  headTags: string;
}

export const getRoutes = (): string[] => [
  '/',
  ...PROJECT_DATA.flatMap((year) => year.projects.map((project) => `/project/${project.id}`)),
];

interface SitemapUrl {
  loc: string;
  lastModified?: string;
  changefreq?: string;
  priority?: number;
}

const toIsoDate = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toISOString();
};

export const getSitemapEntries = (): { pages: SitemapUrl[]; projects: SitemapUrl[] } => {
  const projects: SitemapUrl[] = PROJECT_DATA.flatMap((year) =>
    year.projects.map((project) => ({
      loc: `${SITE_BASE_URL}/project/${project.id}`,
      lastModified: toIsoDate(project.dateModified ?? project.datePublished ?? LANDING_SEO.updatedTime),
      changefreq: 'monthly',
      priority: 0.85,
    }))
  );

  const pages: SitemapUrl[] = [
    {
      loc: `${SITE_BASE_URL}/`,
      lastModified: toIsoDate(LANDING_SEO.updatedTime),
      changefreq: 'weekly',
      priority: 1.0,
    },
  ];

  return { pages, projects };
};

export const render = (url: string): RenderResult => {
  const helmetContext: FilledContext = {};

  const app = (
    <HelmetProvider context={helmetContext}>
      <StaticRouter location={url}>
        <AppRoutes />
      </StaticRouter>
    </HelmetProvider>
  );

  const html = renderToString(app);
  const helmet = helmetContext.helmet;

  const headTags = [
    helmet?.title?.toString() ?? '',
    helmet?.meta?.toString() ?? '',
    helmet?.link?.toString() ?? '',
    helmet?.script?.toString() ?? '',
    helmet?.noscript?.toString() ?? '',
  ].join('');

  return { html, headTags };
};
