export const SITE_BASE_URL = 'https://yanqing.app';
export const SITE_NAME = 'Yanqing Jiang';
export const DEFAULT_OG_IMAGE = 'https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png';
export const DEFAULT_THEME_COLOR = '#12110F';

// Visible commercial-front-door navigation (mirrors the on-page nav). Emitted
// as SiteNavigationElement so structured nav matches what users see — the old
// project chronology stays in WebSite.hasPart, not in navigation.
export const LANDING_NAV = [
  { name: 'What I build', url: `${SITE_BASE_URL}/#build` },
  { name: 'Proof', url: `${SITE_BASE_URL}/#proof` },
  { name: 'Process', url: `${SITE_BASE_URL}/#process` },
  { name: 'Writing', url: `${SITE_BASE_URL}/blog` },
  { name: 'Start a project', url: `${SITE_BASE_URL}/consult` },
];
export const DEFAULT_TWITTER_HANDLE = '@yanqing_j';

export const DEFAULT_SAME_AS = [
  'https://www.linkedin.com/in/jiangyanqing/',
  'https://medium.com/@yanqing_j',
  'https://github.com/Yanqing-Jiang',
];

// Human-visible AND JSON-LD metrics (D4 approved). The "200% trading gain"
// was dropped from landing per the refactor plan (risk-sensitive, off-offer);
// it survives on the project page with its shutdown context.
export const LANDING_METRICS = [
  {
    name: 'AutomationHoursSaved',
    description: 'Labor hours automated through AI workflow orchestration and reporting copilots in production systems.',
    value: 4000,
    unitText: 'Hours',
  },
  {
    name: 'DecisionsInfluenced',
    description: 'Business decisions influenced by analytics automation, experimentation, and forecasting programs.',
    value: 150000000,
    unitText: 'USD',
  },
  {
    name: 'AnalystHoursSaved',
    description: 'Analyst hours saved annually by the LLM invoice reconciliation pipeline.',
    value: 1000,
    unitText: 'Hours',
  },
  {
    name: 'LatePaymentReduction',
    description: 'Reduction in late payments after the invoice reconciliation workflow shipped to production.',
    value: 90,
    unitText: 'Percent',
  },
];

// The four visible offers, verbatim to the landing page's two-path offers.
export const LANDING_SERVICE_SUMMARY = [
  {
    name: 'Enterprise agentic pipelines',
    description:
      'Automate document-heavy, analytical, or multi-system work. Every build starts with a baseline - hours, cost, cycle time, error rate - and ships with telemetry around the result.',
    serviceType: 'AI Systems Engineering',
    keywords: ['Agentic Pipelines', 'Workflow Automation', 'Telemetry', 'Function Calling'],
    areaServed: 'Global',
  },
  {
    name: 'Embedded AI delivery team',
    description:
      'A five-person team across AI, data, product, and interface delivery that builds, instruments, launches, and hands over the system once the plan is agreed.',
    serviceType: 'AI Delivery',
    keywords: ['AI Delivery Team', 'Product', 'Data Engineering', 'Interface Design'],
    areaServed: 'Global',
  },
  {
    name: 'Personal agent OS',
    description:
      'Short-term context, long-term memory, scheduled work, and controlled access to your tools - running on infrastructure you own. A system that compounds context over months.',
    serviceType: 'Personal AI Systems',
    keywords: ['Personal Agent', 'Long-Term Memory', 'MCP Tools', 'Scheduled Jobs'],
    areaServed: 'Global',
  },
  {
    name: 'Zero-maintenance personal website',
    description:
      'Designed, built, hosted, maintained. Publishing, metadata, deployment, and monitoring are automated, while the site and content remain yours.',
    serviceType: 'Web Systems',
    keywords: ['Personal Website', 'Automated Publishing', 'Hosting', 'Monitoring'],
    areaServed: 'Global',
  },
];

export const LANDING_SEO = {
  title: 'Yanqing Jiang - AI Agent System Builder',
  description:
    'Yanqing Jiang designs and ships enterprise agentic pipelines, personal AI systems with durable memory, and zero-maintenance personal websites, backed by a five-person delivery team.',
  // Social share framing (overrides title/description for og: and twitter:).
  ogTitle: 'What It Takes to Make Agents Work in Production',
  ogDescription:
    'Case studies in agent memory, orchestration, analytics copilots, and end-to-end automation—from prototypes to production.',
  keywords: [
    'AI systems engineer',
    'analytics automation',
    'LangGraph developer',
    'agentic workflows',
    'data platform modernization',
    'FastAPI Supabase stack',
    'enterprise analytics copilots',
    'forecasting automation',
    'Context Engineering',
    'RAG Systems',
    'Multi-Agent Systems',
    'AI Orchestration',
    'Claude Code Production',
    'A2UI',
    'Generative UI',
    'Skills.md management',
  ],
  author: 'Yanqing Jiang',
  subject: 'AI systems, analytics automation, and enterprise data workflows',
  category: 'AI Consulting & Analytics Automation',
  canonical: `${SITE_BASE_URL}/`,
  locale: 'en_US',
  sameAs: DEFAULT_SAME_AS,
  updatedTime: '2026-01-05T00:00:00Z',
};

// FAQ content kept as a constant for reuse in non-landing surfaces ONLY.
// Per Tw93 GEO playbook (2026-05-03): pure FAQ format hurts AI citations
// (Princeton/IIT Delhi research). Do NOT emit this onto the landing page or
// into FAQPage JSON-LD. Intended re-use: feed as RAG context to the
// "Ask My Resume" agent at /project/ask-my-resume so the same Q&A content
// powers a product feature instead of a GEO anti-pattern.
export const LANDING_FAQ = [
  {
    question: 'What types of AI systems do you build?',
    answer:
      'Enterprise agent systems: LangGraph and Claude Agent SDK orchestrations, generative UI (A2UI protocol), production LLM pipelines, and personal AI infrastructure (Homer). Built end-to-end with FastAPI + Supabase + React, instrumented for governance and telemetry.',
  },
  {
    question: 'Which industries have you supported?',
    answer:
      'Commerce, retail media, finance, and operations. Production work at P&G (Amazon team) covers experimentation, procurement automation, AP reconciliation, and revenue forecasting.',
  },
  {
    question: 'How do you approach data governance and infrastructure?',
    answer:
      'Governed views, vector indexes (Supabase pgvector), audit trails, and telemetry so agents and BI workloads stay compliant. Backend on FastAPI with SSE streaming, Cloudflare Pages frontend, Docker for daemons.',
  },
  {
    question: 'Can you integrate with existing analytics stacks?',
    answer:
      'Yes. Production integrations include FastAPI, Supabase, Power BI, SQL Server, and bespoke APIs. The agentic layer composes existing tools rather than replacing them.',
  },
];

// Search/retrieval + user-triggered crawlers ONLY.
// Training crawlers (GPTBot, ClaudeBot, Google-Extended, CCBot, Meta-ExternalAgent)
// are intentionally NOT allowlisted per Tw93 GEO playbook (2026-05-03).
export const AI_CRAWLER_ALLOWLIST = [
  // Search & retrieval
  'OAI-SearchBot',
  'Claude-SearchBot',
  'PerplexityBot',
  // User-triggered fetchers
  'ChatGPT-User',
  'Claude-User',
  'Perplexity-User',
  'Google-Agent',
];

export const AI_CRAWLER_MONITORED_PATTERNS = [
  'GPTBot',
  'PerplexityBot',
  'Claude',
  'anthropic-ai',
  'Google-Extended',
  'Amazonbot',
  'CCBot',
  'DataForSeoBot',
  'facebookexternalhit',
];
