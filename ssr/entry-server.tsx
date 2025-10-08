import React from 'react';
import { renderToString } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { HelmetProvider, type FilledContext } from 'react-helmet-async';
import { AppRoutes } from '../App';
import { PROJECT_DATA } from '../constants';

export interface RenderResult {
  html: string;
  headTags: string;
}

export const getRoutes = (): string[] => [
  '/',
  ...PROJECT_DATA.flatMap((year) => year.projects.map((project) => `/project/${project.id}`)),
];

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
  ].join('');

  return { html, headTags };
};
