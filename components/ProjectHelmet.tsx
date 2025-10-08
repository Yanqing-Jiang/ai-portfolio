import React from 'react';
import { Helmet } from 'react-helmet-async';
import type { HelmetProps } from 'react-helmet-async';
import type { Project } from '../types';
import {
  DEFAULT_OG_IMAGE,
  DEFAULT_THEME_COLOR,
  DEFAULT_TWITTER_HANDLE,
  SITE_BASE_URL,
  SITE_NAME,
} from '../constants/seo';

interface ProjectHelmetProps {
  project: Project;
}

const truncate = (value: string, maxLength = 160) => {
  if (!value) return '';
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 3).trimEnd()}...`;
};

export const ProjectHelmet: React.FC<ProjectHelmetProps> = ({ project }) => {
  const title = project.seoTitle ?? `${project.title} - Yanqing Jiang | AI ML Portfolio`;
  const description = truncate(project.seoDescription ?? project.description);
  const keywords = project.seoKeywords?.length ? project.seoKeywords : project.technologies;
  const image = project.ogImage ?? project.coverUrl ?? project.imageUrl ?? DEFAULT_OG_IMAGE;
  const canonicalUrl = `${SITE_BASE_URL}/project/${project.id}`;

  const meta: HelmetProps['meta'] = [
    { name: 'author', content: 'Yanqing Jiang' },
    { name: 'robots', content: 'index, follow' },
    { name: 'theme-color', content: DEFAULT_THEME_COLOR },
    { property: 'og:type', content: 'article' },
    { property: 'og:title', content: title },
    { property: 'og:url', content: canonicalUrl },
    { property: 'og:site_name', content: SITE_NAME },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:site', content: DEFAULT_TWITTER_HANDLE },
    { name: 'twitter:creator', content: DEFAULT_TWITTER_HANDLE },
    { name: 'twitter:title', content: title },
    { property: 'article:author', content: 'Yanqing Jiang' },
  ];

  if (description) {
    meta.push({ name: 'description', content: description });
    meta.push({ property: 'og:description', content: description });
    meta.push({ name: 'twitter:description', content: description });
  }

  if (keywords?.length) {
    const keywordList = keywords.join(', ');
    meta.push({ name: 'keywords', content: keywordList });
    meta.push({ property: 'article:tag', content: keywordList });
  }

  if (image) {
    meta.push({ property: 'og:image', content: image });
    meta.push({ property: 'og:image:width', content: '1200' });
    meta.push({ property: 'og:image:height', content: '630' });
    meta.push({
      property: 'og:image:alt',
      content: `${project.title} - AI/ML project by Yanqing Jiang`,
    });
    meta.push({ name: 'twitter:image', content: image });
    meta.push({
      name: 'twitter:image:alt',
      content: `${project.title} - AI/ML project by Yanqing Jiang`,
    });
  }

  const link: HelmetProps['link'] = [{ rel: 'canonical', href: canonicalUrl }];

  return <Helmet title={title} meta={meta} link={link} />;
};

export default ProjectHelmet;
