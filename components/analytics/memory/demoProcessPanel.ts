import type {
  AgentEvidence,
  AgentTurnTelemetry,
  FollowUpBanner,
  ProcessStep,
} from '../types';

const supervisorTurn: AgentTurnTelemetry = {
  id: 'supervisor-turn-1',
  role: 'supervisor_agent',
  status: 'complete',
  lane: 'coordination',
  summary: 'Supervisor routed AMD vs NVDA follow-up to web + narrative lanes.',
  ts: '2025-11-17T18:12:40.000Z',
};

const webTurn: AgentTurnTelemetry = {
  id: 'web-turn-1',
  role: 'web_research_agent',
  status: 'complete',
  lane: 'web',
  summary: 'Gemini bundle pulled AMD AI roadmap + NVDA earnings commentary.',
  ts: '2025-11-17T18:12:50.000Z',
};

const analysisTurn: AgentTurnTelemetry = {
  id: 'analysis-turn-1',
  role: 'analysis_writer',
  status: 'complete',
  lane: 'analysis',
  summary: 'Merged Gemini snippets into the NVDA vs AMD comparison narrative.',
  ts: '2025-11-17T18:13:07.000Z',
};

export const demoProcessSteps: ProcessStep[] = [
  {
    id: 'agent_coordination',
    name: 'Supervisor Routing',
    status: 'completed',
    thinking: [
      'Supervisor reviewed the NVDA vs AMD revision request.',
      'Selected the web and narrative lanes to refresh targeted insights.',
    ],
    details: {
      summary: 'Delegated revision request to web + analysis specialists without replaying planner steps.',
    },
    elapsed_ms: 6200,
    timestamp: '2025-11-17T18:12:41.120Z',
    sequence: 1,
    parallelGroup: 'coordination',
    flowMode: 'multi-agent',
    lane: 'coordination',
    toolCallId: 'sup-call-001',
    specialistRole: 'supervisor_agent',
    specialistLabel: 'Supervisor Agent',
    schemaVersion: 'analytics_tool_schema/2025-11-19',
    cacheAgeSeconds: 42,
    fastPathLatencyMs: 38,
  },
  {
    id: 'web_research_agent',
    name: 'Web Research Agent',
    status: 'completed',
    thinking: [
      'Fetched AMD AI roadmap commentary.',
      'Captured NVDA earnings excerpts covering H100 supply and hyperscaler demand.',
    ],
    details: {
      summary: 'Gemini WebRefresh captured user + industry focus topics for the revision bundle.',
      topics: ['AMD AI data center roadmap', 'NVDA earnings call supply signals'],
    },
    elapsed_ms: 11800,
    timestamp: '2025-11-17T18:12:52.884Z',
    sequence: 2,
    parallelGroup: 'web',
    flowMode: 'multi-agent',
    lane: 'web',
    toolCallId: 'web-call-992',
    specialistRole: 'web_specialist',
    specialistLabel: 'Web Research Specialist',
    schemaVersion: 'analytics_tool_schema/2025-11-19',
    guardrail: {
      status: 'pass',
      thresholds: { p50_ms: 800, p95_ms: 1500 },
    },
    cacheSource: 'web_cache',
  },
  {
    id: 'analysis_revision',
    name: 'Analysis Revision',
    status: 'completed',
    thinking: [
      'Applied refreshed Gemini snippets to NVDA vs AMD paragraph.',
      'Updated citations and highlighted AI accelerator TAM outlook.',
    ],
    details: {
      summary: 'Narrative merged Gemini bundle and marked the card as an agent-led revision.',
      status: 'applied',
    },
    elapsed_ms: 9600,
    timestamp: '2025-11-17T18:13:07.133Z',
    sequence: 3,
    parallelGroup: 'analysis',
    flowMode: 'multi-agent',
    lane: 'analysis',
    toolCallId: 'analysis-call-447',
    specialistRole: 'analysis_specialist',
    specialistLabel: 'Analysis Specialist',
    schemaVersion: 'analytics_tool_schema/2025-11-19',
    retryCount: 1,
    guardrail: {
      status: 'recovered',
      violations: ['latency_spike'],
      thresholds: { p50_ms: 900, p95_ms: 2000 },
    },
  },
];

export const demoAgentEvidence: AgentEvidence = {
  status: 'agent_run',
  summary: [
    'Supervisor agent rehydrated the prior NVDA vs AMD plan and routed the revision request.',
    'Web + Analysis specialists executed the targeted refresh without replaying deterministic SQL.',
  ],
  turns: [supervisorTurn, webTurn, analysisTurn],
  updatedAt: '2025-11-17T18:13:07.133Z',
};

export const demoFollowUpBanner: FollowUpBanner = {
  title: 'Revision: Analysis updated',
  message: 'Agent runtime refreshed the AMD vs NVDA comparison with new Gemini snippets.',
  route: 'analysis_only',
  reason: 'revision_request',
  flowMode: 'multi-agent',
  summary: 'Supervisor constrained the revision to analysis + web lanes.',
};
