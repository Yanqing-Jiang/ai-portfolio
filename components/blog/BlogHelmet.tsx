import React from 'react';
// @ts-ignore — react-helmet-async types not bundled cleanly with ESM
import { Helmet } from 'react-helmet-async';
import type { BlogPost } from '../../lib/blog/mdx';
import { buildFaqSchema } from '../../constants/structuredData';

const SITE = 'https://yanqing.app';
const SITE_NAME = 'Yanqing Jiang';
const TWITTER_HANDLE = '@yanqing_j';
const PERSON_SAMEAS = [
  'https://medium.com/@yanqing_j',
  'https://www.linkedin.com/in/yanqingjiang/',
  'https://twitter.com/yanqing_j',
  'https://github.com/Yanqing-Jiang',
];

/** Pretty labels for tags shown in user-facing places (article:section etc.). */
const TAG_LABELS: Record<string, string> = {
  agents: 'Agents',
  'llm-eng': 'LLM Engineering',
  a2ui: 'Agent-to-UI',
  claude: 'Claude',
  rag: 'RAG',
  evals: 'Evals',
  finance: 'Finance',
  infra: 'Infra',
  devops: 'DevOps',
  analytics: 'Analytics',
  skills: 'Skills',
  'personal-ai': 'Personal AI',
  philosophy: 'Philosophy',
  career: 'Career',
  'vibe-coding': 'Vibe Coding',
};
function tagLabel(t: string): string {
  return TAG_LABELS[t] ?? t.replace(/(^|-)(\w)/g, (_, _s, c) => ` ${c.toUpperCase()}`).trim();
}

interface Props {
  post: BlogPost;
}

/**
 * SEO + JSON-LD for individual blog posts.
 *
 * Why this looks the way it does:
 *   - Self-canonical by default. Imported Medium posts no longer set
 *     `canonical: 'https://medium.com/...'`. Sending Google to Medium would
 *     bleed all of yanqing.app's link equity to medium.com — opposite of what
 *     we want. The Medium URL lives in `mediumUrl` and is referenced via
 *     `sameAs` on the Author, which tells Google "same entity" without
 *     transferring authority.
 *   - Title pattern: "Title | <PrimaryTag> — Yanqing Jiang" gives the SERP
 *     row a topic chip Google often promotes to a sitelink.
 *   - article:section uses the human-readable label for the LEAD tag (the one
 *     shown in the on-page "Field Notes · X" eyebrow), so social embeds and
 *     Google's category attribution match what the user sees.
 *   - BreadcrumbList JSON-LD enables the "Home › Field Notes › Title"
 *     breadcrumb in Google SERP cards.
 *   - publisher.logo is required by Google Rich Results for Article — we
 *     point to the 512px profile favicon until a dedicated logo lands.
 *   - inLanguage: 'en' tells crawlers + screen readers explicitly.
 */
const BlogHelmet: React.FC<Props> = ({ post }) => {
  const { frontmatter, slug, readingMinutes, wordCount } = post;
  const url = `${SITE}/blog/${slug}`;
  const ogImage = absoluteUrl(
    frontmatter.ogImage ?? frontmatter.hero?.src ?? '/og-default.png'
  );
  const datePublished = new Date(frontmatter.publishedAt).toISOString();
  const dateModified = frontmatter.updatedAt
    ? new Date(frontmatter.updatedAt).toISOString()
    : datePublished;
  const leadTag = frontmatter.tags[0];
  const sectionLabel = leadTag ? tagLabel(leadTag) : 'Field Notes';

  // Self-canonical unless a frontmatter override is set explicitly.
  const canonical = frontmatter.canonical ?? url;
  const isSelfCanonical = canonical === url;

  // ---- JSON-LD: Article ----
  const articleSchema = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: frontmatter.title,
    description: frontmatter.description,
    image: [ogImage],
    datePublished,
    dateModified,
    inLanguage: 'en',
    articleSection: sectionLabel,
    author: {
      '@type': 'Person',
      name: SITE_NAME,
      url: SITE,
      sameAs: PERSON_SAMEAS,
    },
    publisher: {
      '@type': 'Person',
      name: SITE_NAME,
      url: SITE,
      logo: {
        '@type': 'ImageObject',
        url: `${SITE}/favicon-512.png`,
      },
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': url,
    },
    keywords: frontmatter.tags.join(', '),
    wordCount,
    timeRequired: `PT${readingMinutes}M`,
    url,
    // If this is a mirror, advertise the Medium copy as a related work — but
    // keep canonical local. Search engines treat `sameAs` on Article as "same
    // content elsewhere" without redirecting authority.
    ...(frontmatter.mediumUrl ? { sameAs: [frontmatter.mediumUrl] } : {}),
  };

  // ---- JSON-LD: BreadcrumbList ----
  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: SITE },
      { '@type': 'ListItem', position: 2, name: 'Field Notes', item: `${SITE}/blog` },
      { '@type': 'ListItem', position: 3, name: frontmatter.title, item: url },
    ],
  };

  // SEO-friendly title: Title | Topic — Yanqing Jiang (≤ ~70 chars when possible).
  const browserTitle = leadTag
    ? `${frontmatter.title} | ${tagLabel(leadTag)} — ${SITE_NAME}`
    : `${frontmatter.title} — ${SITE_NAME}`;

  return (
    <Helmet>
      <title>{browserTitle}</title>
      <meta name="description" content={frontmatter.description} />
      <meta name="author" content={SITE_NAME} />
      <meta name="keywords" content={frontmatter.tags.join(', ')} />
      <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
      <link rel="canonical" href={canonical} />
      {/* Discoverable RSS for crawlers + readers */}
      <link rel="alternate" type="application/rss+xml" title={`${SITE_NAME} — Field Notes`} href={`${SITE}/rss.xml`} />

      {/* Open Graph */}
      <meta property="og:type" content="article" />
      <meta property="og:title" content={frontmatter.title} />
      <meta property="og:description" content={frontmatter.description} />
      <meta property="og:url" content={url} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:alt" content={frontmatter.hero?.alt ?? frontmatter.title} />
      <meta property="og:locale" content="en_US" />
      <meta property="article:published_time" content={datePublished} />
      <meta property="article:modified_time" content={dateModified} />
      <meta property="article:author" content={SITE_NAME} />
      <meta property="article:section" content={sectionLabel} />
      {frontmatter.tags.map((t) => (
        <meta key={t} property="article:tag" content={t} />
      ))}

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={TWITTER_HANDLE} />
      <meta name="twitter:creator" content={TWITTER_HANDLE} />
      <meta name="twitter:title" content={frontmatter.title} />
      <meta name="twitter:description" content={frontmatter.description} />
      <meta name="twitter:image" content={ogImage} />
      <meta name="twitter:image:alt" content={frontmatter.hero?.alt ?? frontmatter.title} />
      <meta name="twitter:label1" content="Reading time" />
      <meta name="twitter:data1" content={`${readingMinutes} min`} />
      <meta name="twitter:label2" content="Topic" />
      <meta name="twitter:data2" content={sectionLabel} />

      {/* When THIS page is canonical, tell Google to consider Medium duplicates
          a syndication via sameAs in the Article schema above (no link rel here). */}
      {!isSelfCanonical && frontmatter.mediumUrl && (
        <link rel="alternate" href={frontmatter.mediumUrl} hrefLang="x-default" />
      )}

      <script type="application/ld+json">{JSON.stringify(articleSchema)}</script>
      <script type="application/ld+json">{JSON.stringify(breadcrumbSchema)}</script>
      {/* Phase C — selective FAQPage schema. Pure FAQ format hurts AI citation
          per geo-citation-lab; opt-in (emitFaqSchema=true) keeps schema
          reserved for posts that are genuinely Q&A-shaped, satisfying the
          March-2026 core update demotion of abused FAQ markup. */}
      {frontmatter.emitFaqSchema === true && (frontmatter.faqItems?.length ?? 0) >= 3 && (
        <script type="application/ld+json">
          {JSON.stringify(buildFaqSchema(frontmatter.faqItems))}
        </script>
      )}
    </Helmet>
  );
};

/** Resolve a path-or-url to an absolute URL on SITE. */
function absoluteUrl(srcOrPath: string): string {
  if (/^https?:\/\//i.test(srcOrPath)) return srcOrPath;
  return `${SITE}${srcOrPath.startsWith('/') ? '' : '/'}${srcOrPath}`;
}

export default BlogHelmet;
