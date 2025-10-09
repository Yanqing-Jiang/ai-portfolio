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

const toQuantitativeValue = (metric: MetricDefinition) => ({
  '@type': 'QuantitativeValue',
  name: metric.name,
  value: metric.value,
  unitText: metric.unitText ?? 'Unit',
  description: metric.description,
});

export const buildWebsiteSchema = (projects: Project[]) => {
  const projectPages = projects.map((project, index) => ({
    '@type': 'WebPage',
    name: project.seoTitle ?? project.title,
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
    description: LANDING_SEO.description,
    inLanguage: 'en',
    publisher: {
      '@type': 'Person',
      name: LANDING_SEO.author,
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
    name: LANDING_SEO.author,
  },
  itemListElement: services.map((service, index) => ({
    '@type': 'Offer',
    position: index + 1,
    itemOffered: {
      '@type': 'Service',
      name: service.name,
      description: service.description,
      serviceType: service.serviceType ?? service.name,
      keywords: service.keywords,
      areaServed: service.areaServed ?? 'Global',
      provider: {
        '@type': 'Person',
        name: LANDING_SEO.author,
      },
    },
  })),
});

export const buildSiteNavigationSchema = (routes: NavigationDefinition[]) => ({
  '@context': 'https://schema.org',
  '@type': 'SiteNavigationElement',
  name: SITE_NAME,
  hasPart: routes.map((route) => ({
    '@type': 'SiteNavigationElement',
    name: route.name,
    url: route.url,
  })),
});

export const buildStatsSchema = (metrics: MetricDefinition[] = LANDING_METRICS) => ({
  '@context': 'https://schema.org',
  '@type': 'Dataset',
  name: 'AI systems and analytics automation impact metrics',
  description: 'Key performance metrics for Yanqing Jiang’s AI systems, analytics automation, and experimentation programs.',
  creator: {
    '@type': 'Person',
    name: LANDING_SEO.author,
  },
  includedInDataCatalog: SITE_NAME,
  measurementTechnique: ['Automation Hours', 'Incremental Revenue', 'Agentic Trading Gains'],
  variableMeasured: metrics.map(toQuantitativeValue),
});

export const buildBreadcrumbList = (items: NavigationDefinition[]) => ({
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: items.map((item, index) => ({
    '@type': 'ListItem',
    position: index + 1,
    name: item.name,
    item: item.url,
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
  const keywords = ensureKeywords(project);
  const description = ensureDescription(project);

  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: project.seoTitle ?? `${project.title} | AI Systems Project`,
    description,
    author: {
      '@type': 'Person',
      name: LANDING_SEO.author,
      url: SITE_BASE_URL,
      sameAs: LANDING_SEO.sameAs ?? DEFAULT_SAME_AS,
    },
    publisher: {
      '@type': 'Organization',
      name: SITE_NAME,
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
    about: project.serviceTags,
    mentions: project.statHighlights,
  };
};

export const buildLandingSchemas = (projects: Project[], navigation: NavigationDefinition[]) => [
  buildWebsiteSchema(projects),
  buildServiceCatalogSchema(),
  buildSiteNavigationSchema(navigation),
  buildStatsSchema(),
];

export const toNavigationFromProjects = (projects: Project[]): NavigationDefinition[] => {
  const uniqueProjectsMap = new Map<string, NavigationDefinition>();
  projects.forEach((project) => {
    uniqueProjectsMap.set(project.id, {
      name: project.title,
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
    title: project.seoTitle ?? project.title,
    description: ensureDescription(project),
    url: `${SITE_BASE_URL}/project/${project.id}`,
    technologies: project.technologies,
    serviceTags: project.serviceTags,
    statHighlights: project.statHighlights,
    defaultPrompts: project.defaultPrompts,
    primaryMetricValue: project.primaryMetricValue,
  }));
