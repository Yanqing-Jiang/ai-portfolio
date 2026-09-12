import React from 'react';
import { Helmet } from 'react-helmet-async';
import { SITE_BASE_URL } from '../constants/seo';

const PAGE_URL = `${SITE_BASE_URL}/supreme-metric`;
const EMBED_SRC = '/embed/supreme-metric/index.html';
const TITLE = 'Supreme Metric — Governed Metric Topology for Business Questions | Yanqing Jiang';
const DESCRIPTION =
  'A spec and linter that gives every business question one score metric, one owner, and a review before any number ships. Databricks stays the semantic layer; Supreme Metric governs the topology.';

// Component: SupremeMetricPage - mounted at /supreme-metric inside the site shell so
// the header and project menu stay on top. The landing page itself is a set of
// static films under public/embed/supreme-metric (no build step); this route
// frames it full-height in the main content area and owns the page's SEO tags.
const SupremeMetricPage: React.FC = () => (
  <div className="h-full w-full bg-black">
    <Helmet>
      <title>{TITLE}</title>
      <meta name="description" content={DESCRIPTION} />
      <link rel="canonical" href={PAGE_URL} />
      <meta property="og:title" content="Supreme Metric — One metric per question sits above the rest" />
      <meta property="og:description" content={DESCRIPTION} />
      <meta property="og:type" content="website" />
      <meta property="og:url" content={PAGE_URL} />
      <meta property="og:image" content={`${SITE_BASE_URL}/embed/supreme-metric/cover.png`} />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="theme-color" content="#000000" />
    </Helmet>
    <iframe
      src={EMBED_SRC}
      title="Supreme Metric"
      className="block h-full w-full border-0"
      allow="fullscreen"
    />
  </div>
);

export default SupremeMetricPage;
