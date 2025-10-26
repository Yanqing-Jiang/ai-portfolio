import React, { useMemo } from 'react';
import { Helmet } from 'react-helmet-async';
import type { Project } from '../types';
import {
  DEFAULT_OG_IMAGE,
  DEFAULT_THEME_COLOR,
  DEFAULT_TWITTER_HANDLE,
  LANDING_SEO,
  SITE_BASE_URL,
  SITE_NAME,
} from '../constants/seo';
import {
  buildArticleSchema,
  buildBreadcrumbList,
} from '../constants/structuredData';

interface ProjectHelmetProps {
  project: Project;
}

const truncate = (value: string, maxLength = 160) => {
  if (!value) return '';
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 3).trimEnd()}...`;
};

export const ProjectHelmet: React.FC<ProjectHelmetProps> = ({ project }) => {
  const title = project.seoTitle ?? `${project.title} - ${SITE_NAME}`;
  const description = truncate(project.seoDescription ?? project.description);
  const keywords = project.seoKeywords?.length ? project.seoKeywords : project.technologies;
  const keywordList = keywords?.join(', ');
  const image = project.ogImage ?? project.coverUrl ?? project.imageUrl ?? DEFAULT_OG_IMAGE;
  const canonicalUrl = `${SITE_BASE_URL}/project/${project.id}`;
  const datePublished = project.datePublished ?? LANDING_SEO.updatedTime;
  const dateModified = project.dateModified ?? LANDING_SEO.updatedTime;
  const serviceTags = project.serviceTags ?? [];
  const breadcrumbSchema = useMemo(
    () =>
      buildBreadcrumbList([
        { name: 'Home', url: SITE_BASE_URL },
        { name: project.title, url: canonicalUrl },
      ]),
    [project.title, canonicalUrl]
  );
  const articleSchema = useMemo(() => buildArticleSchema(project), [project]);

  return (
    <Helmet>
      <title>{title}</title>
      {description && <meta name="description" content={description} />}
      {keywordList && <meta name="keywords" content={keywordList} />}
      <meta name="author" content={LANDING_SEO.author} />
      <meta name="subject" content={LANDING_SEO.subject} />
      <meta name="robots" content="index, follow" />
      <meta name="theme-color" content={DEFAULT_THEME_COLOR} />

      <link rel="canonical" href={canonicalUrl} />
      <link rel="alternate" hrefLang="en-us" href={canonicalUrl} />

      <meta property="og:type" content="article" />
      <meta property="og:title" content={title} />
      {description && <meta property="og:description" content={description} />}
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:locale" content={LANDING_SEO.locale} />
      <meta property="og:updated_time" content={dateModified} />
      {image && <meta property="og:image" content={image} />}
      {image && <meta property="og:image:width" content="1200" />}
      {image && <meta property="og:image:height" content="630" />}
      {image && <meta property="og:image:alt" content={`${project.title} - AI systems project by Yanqing Jiang`} />}

      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={DEFAULT_TWITTER_HANDLE} />
      <meta name="twitter:creator" content={DEFAULT_TWITTER_HANDLE} />
      <meta name="twitter:title" content={title} />
      {description && <meta name="twitter:description" content={description} />}
      {image && <meta name="twitter:image" content={image} />}
      {image && (
        <meta
          name="twitter:image:alt"
          content={`${project.title} - AI systems and analytics automation showcase`}
        />
      )}

      <meta property="article:author" content={LANDING_SEO.author} />
      <meta property="article:published_time" content={datePublished} />
      <meta property="article:modified_time" content={dateModified} />
      {serviceTags?.map((tag) => (
        <meta key={`article-tag-${tag}`} property="article:tag" content={tag} />
      ))}

      <script type="application/ld+json">{JSON.stringify(articleSchema)}</script>
      <script type="application/ld+json">{JSON.stringify(breadcrumbSchema)}</script>
    </Helmet>
  );
};

export default ProjectHelmet;
