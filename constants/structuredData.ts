import type { Project } from '../types';
import {
  DEFAULT_OG_IMAGE,
  DEFAULT_SAME_AS,
  DEFAULT_TWITTER_HANDLE,
  LANDING_METRICS,
  LANDING_SEO,
  LANDING_SERVICE_SUMMARY,
  SITE_BASE_URL,
  SITE_NAME,
} from './seo';

export interface MetricDefinition {
  name: string;
  description?: string;
  value: number;
  unitText?: string;
}

export interface ServiceDefinition {
  name: string;
  description: string;
  serviceType?: string;
  keywords?: string[];
  areaServed?: string;
}

export interface NavigationDefinition {
  name: string;
  url: string;
}

export interface FaqItem {
  question: string;
  answer: string;
}

const replaceFancyQuotes = (value: string) =>
  value
    .replace(/[\u2018\u2019\u2032\u2035]/g, "'")
    .replace(/[\u201C\u201D\u2033\u2036]/g, '"')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\u2026/g, '...');

const sanitizeText = (value?: string) => {
  if (!value) return '';
  const normalized = replaceFancyQuotes(value).replace(/[^\x09\x0A\x0D\x20-\x7E]/g, ' ');
  return normalized.replace(/\s+/g, ' ').trim();
};

const sanitizeStringList = (values?: string[]) =>
  values?.map((item) => sanitizeText(item)).filter(Boolean) ?? [];

const toQuantitativeValue = (metric: MetricDefinition) => ({
  '@type': 'QuantitativeValue',
  name: sanitizeText(metric.name),
  value: metric.value,
  unitText: metric.unitText ?? 'Unit',
  description: sanitizeText(metric.description),
});

export const buildWebsiteSchema = (projects: Project[]) => {
  const projectPages = projects.map((project, index) => ({
    '@type': 'WebPage',
    name: sanitizeText(project.seoTitle ?? project.title),
    url: `${SITE_BASE_URL}/project/${project.id}`,
    datePublished: project.datePublished ?? LANDING_SEO.updatedTime,
    dateModified: project.dateModified ?? LANDING_SEO.updatedTime,
    position: index + 1,
  }));

  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE_NAME,
    url: SITE_BASE_URL,
    description: sanitizeText(LANDING_SEO.description),
    inLanguage: 'en',
    publisher: {
      '@type': 'Person',
      name: sanitizeText(LANDING_SEO.author),
      sameAs: LANDING_SEO.sameAs ?? DEFAULT_SAME_AS,
    },
    sameAs: LANDING_SEO.sameAs ?? DEFAULT_SAME_AS,
    potentialAction: {
      '@type': 'SearchAction',
      target: `${SITE_BASE_URL}/?q={search_term_string}`,
      'query-input': 'required name=search_term_string',
    },
    hasPart: projectPages,
    metrics: LANDING_METRICS.map(toQuantitativeValue),
  };
};

export const buildServiceCatalogSchema = (services: ServiceDefinition[] = LANDING_SERVICE_SUMMARY) => ({
  '@context': 'https://schema.org',
  '@type': 'OfferCatalog',
  name: 'AI systems, analytics automation, and data services',
  url: SITE_BASE_URL,
  provider: {
    '@type': 'Person',
    name: sanitizeText(LANDING_SEO.author),
  },
  itemListElement: services.map((service, index) => ({
    '@type': 'Offer',
    position: index + 1,
    itemOffered: {
      '@type': 'Service',
      name: sanitizeText(service.name),
      description: sanitizeText(service.description),
      serviceType: sanitizeText(service.serviceType ?? service.name),
      keywords: sanitizeStringList(service.keywords),
      areaServed: service.areaServed ?? 'Global',
      provider: {
        '@type': 'Person',
        name: sanitizeText(LANDING_SEO.author),
      },
    },
  })),
});

export const buildSiteNavigationSchema = (routes: NavigationDefinition[]) => ({
  '@context': 'https://schema.org',
  '@type': 'SiteNavigationElement',
  name: sanitizeText(SITE_NAME),
  hasPart: routes.map((route) => ({
    '@type': 'SiteNavigationElement',
    name: sanitizeText(route.name),
    url: route.url,
  })),
});

export const buildStatsSchema = (metrics: MetricDefinition[] = LANDING_METRICS) => ({
  '@context': 'https://schema.org',
  '@type': 'Dataset',
  name: 'AI systems and analytics automation impact metrics',
  description: "Key performance metrics for Yanqing Jiang's AI systems, analytics automation, and experimentation programs.",
  creator: {
    '@type': 'Person',
    name: sanitizeText(LANDING_SEO.author),
  },
  includedInDataCatalog: sanitizeText(SITE_NAME),
  measurementTechnique: ['Automation Hours', 'Incremental Revenue', 'Agentic Trading Gains'],
  variableMeasured: metrics.map(toQuantitativeValue),
});

export const buildBreadcrumbList = (items: NavigationDefinition[]) => ({
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: items.map((item, index) => ({
    '@type': 'ListItem',
    position: index + 1,
    name: sanitizeText(item.name),
    item: item.url,
  })),
});

export const buildFaqSchema = (items: FaqItem[] = []) => ({
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: items.map((item) => ({
    '@type': 'Question',
    name: sanitizeText(item.question),
    acceptedAnswer: {
      '@type': 'Answer',
      text: sanitizeText(item.answer),
    },
  })),
});

const ensureKeywords = (project: Project) => {
  if (project.seoKeywords?.length) return project.seoKeywords;
  if (project.serviceTags?.length) return project.serviceTags;
  if (project.technologies?.length) return project.technologies;
  return LANDING_SEO.keywords;
};

const ensureDescription = (project: Project) => {
  if (project.seoDescription) return project.seoDescription;
  const description = project.description?.trim();
  if (description) return description.length > 320 ? `${description.slice(0, 317)}...` : description;
  return LANDING_SEO.description;
};

export const buildArticleSchema = (project: Project) => {
  const keywords = sanitizeStringList(ensureKeywords(project));
  const description = sanitizeText(ensureDescription(project));
  const headline = sanitizeText(project.seoTitle ?? `${project.title} | AI Systems Project`);
  const authorName = sanitizeText(LANDING_SEO.author);

  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline,
    description,
    author: {
      '@type': 'Person',
      name: authorName,
      url: SITE_BASE_URL,
      sameAs: LANDING_SEO.sameAs ?? DEFAULT_SAME_AS,
    },
    publisher: {
      '@type': 'Organization',
      name: sanitizeText(SITE_NAME),
      url: SITE_BASE_URL,
      logo: {
        '@type': 'ImageObject',
        url: DEFAULT_OG_IMAGE,
      },
    },
    mainEntityOfPage: `${SITE_BASE_URL}/project/${project.id}`,
    image: project.ogImage ?? project.coverUrl ?? project.imageUrl ?? DEFAULT_OG_IMAGE,
    datePublished: project.datePublished ?? LANDING_SEO.updatedTime,
    dateModified: project.dateModified ?? LANDING_SEO.updatedTime,
    about: sanitizeStringList(project.serviceTags),
    mentions: sanitizeStringList(project.statHighlights),
  };
};

export const buildLandingSchemas = (
  projects: Project[],
  navigation: NavigationDefinition[],
  faqItems: FaqItem[] = []
) => {
  const schemas = [
    buildWebsiteSchema(projects),
    buildServiceCatalogSchema(),
    buildSiteNavigationSchema(navigation),
    buildStatsSchema(),
  ];

  if (faqItems.length) {
    schemas.push(buildFaqSchema(faqItems));
  }

  return schemas;
};

export const toNavigationFromProjects = (projects: Project[]): NavigationDefinition[] => {
  const uniqueProjectsMap = new Map<string, NavigationDefinition>();
  projects.forEach((project) => {
    uniqueProjectsMap.set(project.id, {
      name: sanitizeText(project.title),
      url: `${SITE_BASE_URL}/project/${project.id}`,
    });
  });

  return [
    { name: 'Home', url: SITE_BASE_URL },
    ...Array.from(uniqueProjectsMap.values()),
  ];
};

export const buildAiFactsPayload = (projects: Project[]) =>
  projects.map((project) => ({
    id: project.id,
    title: sanitizeText(project.seoTitle ?? project.title),
    description: sanitizeText(ensureDescription(project)),
    url: `${SITE_BASE_URL}/project/${project.id}`,
    technologies: project.technologies,
    serviceTags: sanitizeStringList(project.serviceTags),
    statHighlights: sanitizeStringList(project.statHighlights),
    defaultPrompts: project.defaultPrompts,
    primaryMetricValue: project.primaryMetricValue,
  }));
