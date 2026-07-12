/**
 * fortuneTypes — shared TypeScript interfaces for the fortune agent system.
 *
 * Matches backend Pydantic schemas in backend/fortune/schemas.py and
 * SSE patch shapes verified from backend/fortune/stream_bridge.py.
 *
 * CRITICAL: Many SSE paths emit wrapped objects ({ items: [...] },
 * { references: [...] }), NOT bare arrays. Selectors must unwrap.
 */

// ---------------------------------------------------------------------------
// Core enums & primitives
// ---------------------------------------------------------------------------

export type FortuneFunctionId = 'wish' | 'luck-cycle' | 'compatibility' | 'lucky-day';
export type ElementType = 'Wood' | 'Fire' | 'Earth' | 'Metal' | 'Water';
export type FortuneStatus = 'idle' | 'loading' | 'streaming' | 'complete' | 'error';

// ---------------------------------------------------------------------------
// Birth profile (shared across all create requests)
// ---------------------------------------------------------------------------

export interface BirthProfileInput {
  name?: string;
  birthISO: string;
  timezone: string;
  birthTimeUnknown?: boolean;
  gender?: string;
}

// ---------------------------------------------------------------------------
// Per-function create requests
// ---------------------------------------------------------------------------

export interface WishCreateRequest {
  kind: 'wish';
  profile: BirthProfileInput;
  question: string;
  focus?: string;
  tone?: string;
}

export interface LuckCycleCreateRequest {
  kind: 'luck-cycle';
  profile: BirthProfileInput;
  horizon: '12m' | '36m' | '10y';
  focus: 'career' | 'wealth' | 'relationship' | 'health' | 'general';
}

export interface CompatibilityCreateRequest {
  kind: 'compatibility';
  relationship: string;
  personA: BirthProfileInput;
  personB: BirthProfileInput;
  question?: string;
}

export interface LuckyDayCreateRequest {
  kind: 'lucky-day';
  profile: BirthProfileInput;
  occasion: string;
  windowStartISO: string;
  windowEndISO: string;
  constraints?: string[];
}

export type FortuneCreateRequest =
  | WishCreateRequest
  | LuckCycleCreateRequest
  | CompatibilityCreateRequest
  | LuckyDayCreateRequest;

// ---------------------------------------------------------------------------
// SSE envelope (backend wraps every event in this shape)
// ---------------------------------------------------------------------------

export interface FortuneStreamEnvelope {
  run_id: string;
  fortune_id: string;
  seq: number;
  payload: string; // raw A2UI line
}

// ---------------------------------------------------------------------------
// Citation (backend-emitted via /data/classics)
// ---------------------------------------------------------------------------

export interface Citation {
  id: string;
  source: string;        // Chinese book title: "滴天髓"
  sourceEnglish?: string; // "Dripping Heavenly Marrow"
  chapter?: string;
  quote: string;         // Original Chinese
  translation?: string;  // English translation
  rationale?: string;    // Why this quote applies here
  scope?: 'foundation' | FortuneFunctionId;
}

// ---------------------------------------------------------------------------
// Replay response from GET /api/fortune/{id}
// ---------------------------------------------------------------------------

export interface FortuneReplayResponse {
  fortune_id: string;
  run_id: string;
  function_id: FortuneFunctionId;
  status: 'pending' | 'streaming' | 'complete' | 'error';
  last_seq: number;
  metadata: {
    created_at: string;
    persistence_degraded?: boolean;
    birth_time_unknown?: boolean;
  };
  data_model: FortuneDataModel;
  ask_history: AskTurn[];
}

// ---------------------------------------------------------------------------
// Ask turn (matches fortuneStore.ts AskTurn)
// ---------------------------------------------------------------------------

export interface AskTurn {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestampISO: string;
  runId?: string;
  narrative?: unknown;
  degradedMemory?: boolean;
}

// ---------------------------------------------------------------------------
// Unified data model — matches both live stream accumulation and replay
// ---------------------------------------------------------------------------

export interface FortuneDataModel {
  meta?: {
    status?: string;
    progress?: { stage?: string; message?: string; percent?: number };
    error_message?: string;
  };
  kpi?: Record<string, unknown>;
  pillars?: PillarSet;
  hiddenStems?: Record<string, HiddenStem[]>;
  tenGods?: { items?: TenGod[] };
  elements?: ElementCounts;
  elementBySource?: Record<string, unknown>;
  seasonalStrength?: SeasonalStrength;
  interactions?: { items?: Interaction[] };
  luckPillars?: { items?: LuckPillar[] };
  annualPillars?: { items?: AnnualPillar[] };
  narrative?: NarrativeModel;
  classics?: { references?: Citation[] };
  trace?: { steps?: Record<string, unknown>; summary?: unknown };
  guardrail?: GuardrailPayload;
  retrodictions?: { items?: Retrodiction[] };
  // Function-specific subtrees
  wish?: WishModel;
  luckCycle?: LuckCycleModel;
  compatibility?: CompatibilityModel;
  occasion?: OccasionModel;
}

// ---------------------------------------------------------------------------
// Pillar types
// ---------------------------------------------------------------------------

export interface Pillar {
  stem: string;        // e.g. "Jia" / "甲"
  branch: string;      // e.g. "Zi" / "子"
  stemChinese?: string;
  branchChinese?: string;
  element?: ElementType;
  branchElement?: ElementType;
  naYin?: string;
  hiddenStems?: HiddenStem[];
}

export interface PillarSet {
  year: Pillar;
  month: Pillar;
  day: Pillar;
  hour?: Pillar;
}

export interface HiddenStem {
  stem: string;
  element: ElementType;
  strength: 'dominant' | 'residual' | 'trace';
}

// ---------------------------------------------------------------------------
// Elements & seasonal
// ---------------------------------------------------------------------------

export interface ElementCounts {
  Wood: number;
  Fire: number;
  Earth: number;
  Metal: number;
  Water: number;
}

export interface SeasonalStrength {
  season: string;
  dayMasterElement: ElementType;
  strength: 'strong' | 'moderate' | 'weak';
  score: number;
  description?: string;
}

// ---------------------------------------------------------------------------
// Ten Gods & Interactions
// ---------------------------------------------------------------------------

export interface TenGod {
  pillar: string;       // "year" | "month" | "day" | "hour"
  position: string;     // "stem" | "branch"
  god: string;          // "Direct Wealth", "Indirect Officer", etc.
  godChinese?: string;  // "正财"
  element?: ElementType;
  description?: string;
}

export interface Interaction {
  type: string;         // "combination", "clash", "harm", "punishment"
  from: string;
  to: string;
  description?: string;
  effect?: string;
}

// ---------------------------------------------------------------------------
// Luck pillars & annual pillars
// ---------------------------------------------------------------------------

export interface LuckPillar {
  startAge: number;
  endAge: number;
  startYear?: number;
  endYear?: number;
  stem: string;
  branch: string;
  stemChinese?: string;
  branchChinese?: string;
  stemElement?: ElementType;
  branchElement?: ElementType;
  element?: ElementType;
  score?: number;
  description?: string;
  isCurrent?: boolean;
}

export interface AnnualPillar {
  year: number;
  stem: string;
  branch: string;
  stemChinese?: string;
  branchChinese?: string;
  element?: ElementType;
  score?: number;
  prediction?: string;
  confidence?: number;
  isCurrent?: boolean;
}

// ---------------------------------------------------------------------------
// Narrative
// ---------------------------------------------------------------------------

export interface NarrativeModel {
  streamingText?: string;
  isComplete?: boolean;
  tldr?: string;
  insights?: NarrativeInsight[];
  yearPredictions?: YearPrediction[];
}

export interface NarrativeInsight {
  id: string;
  icon: string;
  heading: string;
  tagline: string;
  bullets: Array<{ icon: string; text: string }>;
  citations?: string[];
}

export interface YearPrediction {
  year: number;
  prediction: string;
  confidence: number;
  evidenceRefs?: string[];
}

// ---------------------------------------------------------------------------
// Retrodictions
// ---------------------------------------------------------------------------

export interface Retrodiction {
  year: number;
  prediction: string;
  confidence: number;
  evidenceRefs?: string[];
  correction?: { user_note: string; corrected_at: string };
}

// ---------------------------------------------------------------------------
// Guardrail
// ---------------------------------------------------------------------------

export interface GuardrailPayload {
  message: string;
  /** Frontend convention */
  severity?: 'info' | 'warning' | 'error';
  /** Backend emits `level` — normalized to `severity` on ingest */
  level?: 'info' | 'warning' | 'error';
}

// ---------------------------------------------------------------------------
// Function-specific models
// ---------------------------------------------------------------------------

export interface WishModel {
  verdict?: {
    title: string;
    score?: number;
    summary: string;
    caution?: string;
    conditions?: Array<{ type: 'check' | 'warn' | 'cross'; text: string }>;
  };
  anchors?: Array<{
    id: string;
    label: string;
    symbol: string;
    element?: ElementType;
    relevance: number;
    bullets: string[];
  }>;
  mechanisms?: Mechanism[];
}

export interface LuckCycleModel {
  currentWindow?: {
    decade: string;
    score: number;
    summary: string;
    element?: ElementType;
  };
  timeline?: {
    decades?: LuckPillar[];
    years?: AnnualPillar[];
    months?: unknown[];
  };
  mechanisms?: Mechanism[];
}

export interface CompatibilityModel {
  overview?: {
    score: number;
    summary: string;
    relationship: string;
    strengths: string[];
    frictions: string[];
  };
  personA?: PersonChart;
  personB?: PersonChart;
  pairInteractions?: PairInteraction[];
  mechanisms?: Mechanism[];
}

export interface PersonChart {
  name?: string;
  dayMaster?: string;
  dayMasterElement?: ElementType;
  pillars?: PillarSet;
  elements?: ElementCounts;
  tenGods?: TenGod[];
  hiddenStems?: Record<string, HiddenStem[]>;
}

export interface PairInteraction {
  type: 'combination' | 'clash' | 'harm' | 'support' | 'punishment';
  from: string;
  to: string;
  personA: string;
  personB: string;
  description?: string;
  effect?: string;
}

export interface OccasionModel {
  topPicks?: OccasionPick[];
  calendar?: { month: string; year: number; days: OccasionDay[] };
  analysis?: {
    occasionType: string;
    keyElements: ElementType[];
    avoidElements: ElementType[];
    description: string;
  };
  mechanisms?: Mechanism[];
}

export interface OccasionPick {
  rank: number;
  date: string;
  dayPillar: { stem: string; branch: string };
  score: number;
  oneLineReason: string;
  bestHours?: string[];
  mechanisms?: Mechanism[];
}

export interface OccasionDay {
  date: string;
  pillar?: { stem: string; branch: string };
  score: number;
  isClash?: boolean;
  officer?: string; // 12 Day Officer name
}

// ---------------------------------------------------------------------------
// Shared mechanism (used by all function-specific models)
// ---------------------------------------------------------------------------

export interface Mechanism {
  id?: string;
  title: string;
  type?: string;
  bullets: string[];
  citationIds?: string[];
  icon?: string;
}
