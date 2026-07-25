import type { Project } from '../types';
import {
  DEFAULT_OG_IMAGE,
  DEFAULT_SAME_AS,
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
  // Set only where a price is actually published on the site (the free intro
  // call). Omitted => the Offer carries no price claim.
  price?: string;
  priceCurrency?: string;
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

// Phase C — exported so components (ProjectHelmet, future BlogHelmet utils)
// can reuse instead of duplicating. Net-negative diff per refactor discipline.
export const sanitizeText = (value?: string) => {
  if (!value) return '';
  const normalized = replaceFancyQuotes(value).replace(/[^\x09\x0A\x0D\x20-\x7E]/g, ' ');
  return normalized.replace(/\s+/g, ' ').trim();
};

export const sanitizeStringList = (values?: string[]) =>
  values?.map((item) => sanitizeText(item)).filter(Boolean) ?? [];

export const toAbsoluteUrl = (value?: string) => {
  if (!value || !value.trim()) return undefined;
  try {
    return new URL(value, SITE_BASE_URL).toString();
  } catch {
    return value;
  }
};

// Phase C — emit a Thing list (entity graph density) instead of bare strings.
// schema.org accepts strings on Article.about/mentions, but AI Overviews show
// stronger entity-recognition signals when given typed Thing nodes.
const toThingList = (values?: string[]) =>
  sanitizeStringList(values).map((name) => ({ '@type': 'Thing', name }));

const toQuantitativeValue = (metric: MetricDefinition) => ({
  '@type': 'QuantitativeValue',
  name: sanitizeText(metric.name),
  value: metric.value,
  unitText: metric.unitText ?? 'Unit',
  description: sanitizeText(metric.description),
});

export const buildWebsiteSchema = (projects: Project[]) => {
  const seenSlugs = new Set<string>();
  const projectPages = projects.reduce((pages, project) => {
    const slug = project.canonicalId ?? project.id;
    if (seenSlugs.has(slug)) {
      return pages;
    }
    seenSlugs.add(slug);
    pages.push({
    '@type': 'WebPage',
    name: sanitizeText(project.seoTitle ?? project.title),
      url: `${SITE_BASE_URL}/project/${slug}`,
    datePublished: project.datePublished ?? LANDING_SEO.updatedTime,
    dateModified: project.dateModified ?? LANDING_SEO.updatedTime,
      position: pages.length + 1,
    });
    return pages;
  }, [] as any[]);

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
  name: 'AI agent systems, workflow automation, and agentic-stack training',
  url: SITE_BASE_URL,
  provider: {
    '@type': 'Person',
    name: sanitizeText(LANDING_SEO.author),
  },
  itemListElement: services.map((service, index) => ({
    '@type': 'Offer',
    position: index + 1,
    ...(service.price !== undefined
      ? { price: service.price, priceCurrency: service.priceCurrency ?? 'USD', url: `${SITE_BASE_URL}/consult` }
      : {}),
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
  measurementTechnique: ['Automation Hours', 'Decisions Influenced', 'Analyst Hours Saved', 'Late Payment Reduction'],
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

const ensureDescription = (project: Project) => {
  if (project.seoDescription) return project.seoDescription;
  const description = project.description?.trim();
  if (description) return description.length > 320 ? `${description.slice(0, 317)}...` : description;
  return LANDING_SEO.description;
};

// Function: buildPersonSchema — called from LandingPageFlow to embed Person JSON-LD for SEO and LLM discoverability; returns schema.org Person with stable @id, job title, skills, and social links.
// jobTitle uses hybrid wording (current internal + public positioning) per GEO audit 2026-05-03 to align with Director-of-Agents narrative without misrepresenting current employer role.
// Phase C — added alumniOf + worksFor (entity grounding to a real org accelerates
// Google Knowledge Graph attachment) and expanded knowsAbout to 15 entries for
// the 4.8x entity-density boost in AI Overviews citation selection.
export const buildPersonSchema = () => ({
  '@context': 'https://schema.org',
  '@type': 'Person',
  '@id': `${SITE_BASE_URL}/#person`,
  name: sanitizeText(LANDING_SEO.author),
  jobTitle: 'AI Agent System Builder',
  description:
    'AI Agent System Builder. Builds enterprise agent workflows that cut up to 90% of the work time from database to delivered dashboard or deck, personal agent systems with durable memory, and hands-on training on the agentic stack (Claude Code, Codex, Copilot). Covers the full AI service stack on Azure, GCP and AWS. Enterprise perspective from Advanced Analytics at P&G.',
  url: SITE_BASE_URL,
  image: DEFAULT_OG_IMAGE,
  sameAs: LANDING_SEO.sameAs ?? DEFAULT_SAME_AS,
  worksFor: {
    '@type': 'Organization',
    name: 'Procter & Gamble',
  },
  alumniOf: [
    {
      '@type': 'Organization',
      name: 'Procter & Gamble',
    },
  ],
  knowsAbout: [
    'AI Agent System Design',
    'Enterprise Agentic Pipelines',
    'LangGraph Agent Orchestration',
    'Claude Agent SDK',
    'Claude Code',
    'OpenAI Codex',
    'Agent Harness Training',
    'A2UI Protocol',
    'Generative UI',
    'Multi-Agent Workflows',
    'Analytics Automation',
    'RAG Systems',
    'Production LLM Pipelines',
    'Model Context Protocol (MCP)',
    'FastAPI',
    'Supabase pgvector',
    'Cloudflare Tunnel',
    'Prompt Engineering',
  ],
});

// Function: buildSoftwareSchema — called from ProjectHelmet to add SoftwareSourceCode JSON-LD for code projects; references Person @id as author.
// Phase C — added codeRepository (only when project.link is a github.com URL,
// per refactor discipline: don't advertise non-repo URLs as source code) and
// softwareRequirements (from technologies) for richer entity grounding.
const isGithubUrl = (value?: string) => {
  if (!value) return false;
  try {
    return new URL(value, SITE_BASE_URL).host === 'github.com';
  } catch {
    return false;
  }
};

export const buildSoftwareSchema = (project: Project) => {
  const slug = project.canonicalId ?? project.id;
  const description = sanitizeText(ensureDescription(project));
  const resolvedImage =
    toAbsoluteUrl(project.ogImage ?? project.coverUrl ?? project.imageUrl ?? DEFAULT_OG_IMAGE) ??
    DEFAULT_OG_IMAGE;
  const codeRepository = isGithubUrl(project.link) ? toAbsoluteUrl(project.link) : undefined;

  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareSourceCode',
    '@id': `${SITE_BASE_URL}/project/${slug}#source-code`,
    name: sanitizeText(project.seoTitle ?? project.title),
    description,
    url: `${SITE_BASE_URL}/project/${slug}`,
    image: resolvedImage,
    datePublished: project.datePublished ?? LANDING_SEO.updatedTime,
    dateModified: project.dateModified ?? LANDING_SEO.updatedTime,
    programmingLanguage: sanitizeStringList(project.technologies),
    softwareRequirements: sanitizeStringList(project.technologies),
    ...(codeRepository ? { codeRepository } : {}),
    author: {
      '@id': `${SITE_BASE_URL}/#person`,
    },
    keywords: sanitizeStringList(project.seoKeywords ?? project.serviceTags ?? project.technologies),
  };
};

export const buildSoftwareApplicationSchema = (project: Project) => {
  const slug = project.canonicalId ?? project.id;
  const description = sanitizeText(ensureDescription(project));
  const resolvedImage =
    toAbsoluteUrl(project.ogImage ?? project.coverUrl ?? project.imageUrl ?? DEFAULT_OG_IMAGE) ??
    DEFAULT_OG_IMAGE;
  const keywords = sanitizeStringList(project.seoKeywords ?? project.serviceTags ?? project.technologies);
  const featureList = sanitizeStringList(project.serviceTags ?? project.technologies);

  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    '@id': `${SITE_BASE_URL}/project/${slug}#software-application`,
    name: sanitizeText(project.title),
    alternateName: sanitizeText(project.seoTitle ?? project.title),
    description,
    url: `${SITE_BASE_URL}/project/${slug}`,
    image: resolvedImage,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    author: {
      '@id': `${SITE_BASE_URL}/#person`,
    },
    creator: {
      '@id': `${SITE_BASE_URL}/#person`,
    },
    datePublished: project.datePublished ?? LANDING_SEO.updatedTime,
    dateModified: project.dateModified ?? LANDING_SEO.updatedTime,
    softwareRequirements: sanitizeStringList(project.technologies),
    ...(featureList.length ? { featureList } : {}),
    ...(keywords.length ? { keywords } : {}),
  };
};

// Phase C — buildArticleSchema is the single highest-impact schema for AI
// citation. 2026 research (digitalapplied, stackmatix): +73% AI selection rate
// for explicit schema, +156% for multi-modal (text+image+video). Changes:
//   - image now an ImageObject array with explicit dimensions (was bare URL)
//   - VideoObject embed when project.videoUrl present
//   - about + mentions promoted from string lists to typed Thing nodes
//     (`project.about` falls back to serviceTags; `project.mentions` is
//     opt-in canonical-entity list and replaces the prior incorrect use of
//     statHighlights as mentions — those were metrics, not entities)
export const buildArticleSchema = (project: Project) => {
  const slug = project.canonicalId ?? project.id;
  const description = sanitizeText(ensureDescription(project));
  const headline = sanitizeText(project.seoTitle ?? `${project.title} | AI Systems Project`);
  const authorName = sanitizeText(LANDING_SEO.author);
  const resolvedImage =
    toAbsoluteUrl(project.ogImage ?? project.coverUrl ?? project.imageUrl ?? DEFAULT_OG_IMAGE) ??
    DEFAULT_OG_IMAGE;

  const imageObjects = [
    {
      '@type': 'ImageObject',
      url: resolvedImage,
      width: 1200,
      height: 630,
      caption: sanitizeText(project.title),
    },
  ];

  const videoUrl = toAbsoluteUrl(project.videoUrl);
  const videoThumb = toAbsoluteUrl(project.videoThumbnailUrl ?? project.posterUrl) ?? resolvedImage;
  const videoObject = videoUrl
    ? {
        '@type': 'VideoObject',
        name: sanitizeText(project.title),
        description,
        thumbnailUrl: videoThumb,
        contentUrl: videoUrl,
        uploadDate: project.datePublished ?? LANDING_SEO.updatedTime,
        ...(project.videoDurationISO ? { duration: project.videoDurationISO } : {}),
      }
    : undefined;

  const aboutThings = toThingList(project.about ?? project.serviceTags ?? []);
  const mentionThings = toThingList(project.mentions ?? []);

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
    mainEntityOfPage: `${SITE_BASE_URL}/project/${slug}`,
    image: imageObjects,
    ...(videoObject ? { video: videoObject } : {}),
    datePublished: project.datePublished ?? LANDING_SEO.updatedTime,
    dateModified: project.dateModified ?? LANDING_SEO.updatedTime,
    ...(aboutThings.length ? { about: aboutThings } : {}),
    ...(mentionThings.length ? { mentions: mentionThings } : {}),
  };
};

export const buildLandingSchemas = (
  projects: Project[],
  navigation: NavigationDefinition[],
  // FAQPage schema intentionally NOT included on landing per Tw93 GEO playbook
  // (2026-05-03): Princeton/IIT Delhi GEO research finds pure FAQ format hurts
  // AI citations. The faqItems param is accepted for backward compatibility but
  // is not emitted into landing-page schemas. Use buildFaqSchema() directly only
  // for non-landing routes (e.g. /ask) where FAQ-shape powers a product feature.
  _faqItems: FaqItem[] = []
) => {
  return [
    buildWebsiteSchema(projects),
    buildServiceCatalogSchema(),
    buildSiteNavigationSchema(navigation),
    buildStatsSchema(),
  ];
};

