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
    'Yanqing Jiang architects LangGraph-powered AI systems, analytics automation, and enterprise data workflows for commerce, retail media, and operations teams.',
  keywords: [
    'AI systems engineer',
    'analytics automation',
    'LangGraph developer',
    'agentic workflows',
    'data platform modernization',
    'FastAPI Supabase stack',
    'enterprise analytics copilots',
    'forecasting automation',
  ],
  author: 'Yanqing Jiang',
  subject: 'AI systems, analytics automation, and enterprise data workflows',
  category: 'AI Consulting & Analytics Automation',
  canonical: `${SITE_BASE_URL}/`,
  locale: 'en_US',
  sameAs: DEFAULT_SAME_AS,
  updatedTime: '2025-10-01T00:00:00Z',
};

export const LANDING_FAQ = [
  {
    question: 'What types of AI systems do you build?',
    answer:
      'I ship LangGraph-powered copilots, memory-augmented workflows, and analytics agents that automate research, SQL generation, and decision support for commercial teams.',
  },
  {
    question: 'Which industries have you supported?',
    answer:
      'Commerce, retail media, finance, and operations groups rely on my platforms for experimentation, procurement automation, and revenue forecasting.',
  },
  {
    question: 'How do you approach data governance and infrastructure?',
    answer:
      'I modernize Supabase and SQL Server foundations with governed views, vector indexes, and telemetry so AI agents and BI tools stay compliant and fast.',
  },
  {
    question: 'Can you integrate with existing analytics stacks?',
    answer:
      'Yes. I have integrated FastAPI services, Supabase, Power BI, and bespoke APIs to orchestrate workflows that work alongside the tools teams already use.',
  },
];

export const AI_CRAWLER_ALLOWLIST = [
  'GPTBot',
  'ChatGPT-User',
  'Google-Extended',
  'ClaudeBot',
  'Ai2Bot',
  'CCBot',
  'PerplexityBot',
  'Amazonbot',
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
