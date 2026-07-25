export const SITE_BASE_URL = 'https://yanqing.app';
export const SITE_NAME = 'Yanqing Jiang';
export const DEFAULT_OG_IMAGE = 'https://yanqinghot.blob.core.windows.net/public-access/og-agent-builder.png';
export const DEFAULT_THEME_COLOR = '#12110F';

// Visible commercial-front-door navigation (mirrors the on-page nav). Emitted
// as SiteNavigationElement so structured nav matches what users see — the old
// project chronology stays in WebSite.hasPart, not in navigation.
// Every url here must resolve to something that exists: #build / #proof /
// #process were advertised for months after those sections were removed.
export const LANDING_NAV = [
  { name: 'The work', url: `${SITE_BASE_URL}/#work` },
  { name: 'Pre-AI projects', url: `${SITE_BASE_URL}/#pre-ai` },
  { name: 'Writing', url: `${SITE_BASE_URL}/blog` },
  { name: 'Start a booking', url: `${SITE_BASE_URL}/consult` },
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

// The three offers shown on the landing page, plus the free intro call that is
// the only conversion path. Names and framing track the visible cards — a
// service catalog that lists offers the page doesn't sell is a mismatch signal.
export const LANDING_SERVICE_SUMMARY = [
  {
    name: 'Enterprise workflow',
    description:
      'Cut up to 90% of the work time out of an operating process with an AI agent workflow - from the database through to the delivered PowerPoint or dashboard. Every build starts from a baseline (hours, cost, cycle time, error rate) and ships with telemetry around the result.',
    serviceType: 'AI Workflow Automation',
    keywords: ['Agentic Pipelines', 'Workflow Automation', 'Reporting Automation', 'Telemetry', 'Function Calling'],
    areaServed: 'Global',
  },
  {
    name: 'Personal Agent OS',
    description:
      'A personal agent that remembers how you work: short-term context, long-term memory, scheduled work, and controlled access to your tools, running on infrastructure you own. Includes agent-managed personal websites that publish, deploy, and monitor themselves.',
    serviceType: 'Personal AI Systems',
    keywords: ['Personal Agent', 'Long-Term Memory', 'MCP Tools', 'Scheduled Jobs', 'Agent-Managed Website'],
    areaServed: 'Global',
  },
  {
    name: 'Hands on training',
    description:
      'Learn the agentic stack on your own toolset - GitHub Copilot, Claude Code, Codex, Pi, OpenClaw, Hermes - for yourself, a team, or an org. Working sessions on real repositories, not slideware.',
    serviceType: 'AI Training',
    keywords: ['Claude Code Training', 'Codex Training', 'Agent Harness', 'AI Enablement', 'Team Training'],
    areaServed: 'Global',
  },
  {
    name: 'Free 30-minute intro call',
    description:
      'A free first call to scope the work: what should change, what happens today, and whether an agent system is the right answer. Booked directly at /consult - no sign-in, no payment.',
    serviceType: 'Consultation',
    keywords: ['Free Consultation', 'AI Scoping Call', 'Discovery Call'],
    areaServed: 'Global',
    price: '0',
    priceCurrency: 'USD',
  },
];

export const LANDING_SEO = {
  title: 'AI Agent System Builder · Book with me | Yanqing Jiang',
  description:
    'AI agent system builder. Cut up to 90% of the work time in an enterprise workflow, build a personal agent OS, or train your team on the agentic stack. Free 30-minute call.',
  // Social share framing (overrides title/description for og: and twitter:).
  ogTitle: 'What It Takes to Make Agents Work in Production',
  ogDescription:
    'Case studies in agent memory, orchestration, analytics copilots, and end-to-end automation—from prototypes to production.',
  // Lead with the positioning the site actually sells against; the stack terms
  // stay because they are what technical buyers search for.
  keywords: [
    'AI agent system builder',
    'AI agent workflow automation',
    'agentic AI consultant',
    'personal agent OS',
    'Claude Code training',
    'Codex training',
    'AI systems engineer',
    'analytics automation',
    'LangGraph developer',
    'agentic workflows',
    'enterprise analytics copilots',
    'Context Engineering',
    'RAG Systems',
    'Multi-Agent Systems',
    'AI Orchestration',
    'A2UI',
    'Generative UI',
    'FastAPI Supabase stack',
  ],
  author: 'Yanqing Jiang',
  subject: 'AI agent systems, workflow automation, and agentic-stack training',
  category: 'AI Agent Systems & Workflow Automation',
  canonical: `${SITE_BASE_URL}/`,
  locale: 'en_US',
  updatedTime: '2026-07-24T00:00:00Z',
  sameAs: DEFAULT_SAME_AS,
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
