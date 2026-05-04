export const SITE_BASE_URL = 'https://yanqing.app';
export const SITE_NAME = 'Yanqing Jiang AI & ML Portfolio';
export const DEFAULT_OG_IMAGE = 'https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png';
export const DEFAULT_THEME_COLOR = '#111827';
export const DEFAULT_TWITTER_HANDLE = '@yanqing_j';

export const DEFAULT_SAME_AS = [
  'https://www.linkedin.com/in/jiangyanqing/',
  'https://medium.com/@yanqing_j',
  'https://github.com/yanqingj',
];

export const LANDING_METRICS = [
  {
    name: 'AutomationHoursSaved',
    description: 'Estimated labor hours automated through AI workflow orchestration and reporting copilots.',
    value: 4000,
    unitText: 'Hours',
  },
  {
    name: 'IncrementalRevenueInfluenced',
    description: 'Business value from analytics automation, experimentation, and forecasting programs.',
    value: 150000000,
    unitText: 'USD',
  },
  {
    name: 'AgenticTradeGain',
    description: 'Peak realized gain produced by the LangGraph-powered agentic trading bot proof of concept.',
    value: 200,
    unitText: 'Percent',
  },
];

export const LANDING_SERVICE_SUMMARY = [
  {
    name: 'AI Agent Systems & Autonomy',
    description:
      'Design LangGraph and multi-agent orchestrations that blend retrieval, memory, and clarifications for analytics and trading workflows.',
    serviceType: 'AI Systems Engineering',
    keywords: ['LangGraph', 'Agent Orchestration', 'Retrieval-Augmented Generation'],
    areaServed: 'Global',
  },
  {
    name: 'Analytics Automation & Decision Ops',
    description:
      'Ship telemetry-rich analytics copilots, alerting workflows, and narrative insights that compress analyst turnaround across commerce and media.',
    serviceType: 'Analytics Automation',
    keywords: ['Analytics Automation', 'Telemetry', 'Insight Copilots'],
    areaServed: 'Global',
  },
  {
    name: 'Enterprise Data Activation',
    description:
      'Modernize Supabase, SQL Server, and Azure data stacks with governed views, vector indexes, and streaming pipelines that power AI copilots.',
    serviceType: 'Data Engineering & Governance',
    keywords: ['Supabase', 'SQL Server', 'Azure', 'Vector Indexes'],
    areaServed: 'Global',
  },
  {
    name: 'Experimentation & Forecasting Science',
    description:
      'Deploy experimentation scaffolding, causal models, and forecasting agents that inform investment and merchandising strategy.',
    serviceType: 'Applied Data Science',
    keywords: ['Experimentation', 'Forecasting', 'Causal Models'],
    areaServed: 'Global',
  },
];

export const LANDING_SEO = {
  title: 'Yanqing Jiang | AI Systems & Analytics Automation Portfolio',
  description:
    'AI Portfolio of Yanqing Jiang, senior Advanced Analytics Manager, specializing in Enterprise Agentic Workflows, GenAI production systems and Advanced Analytics solutions.',
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
