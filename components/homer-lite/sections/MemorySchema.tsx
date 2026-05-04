import React from 'react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: MemorySchema — Plan §4.0.
// 2-tier model + annotated SQL + FTS/vector hybrid rationale.
// Sprint 1 stub renders the SQL excerpt and tier explainer; Sprint 2 adds
// syntax highlighting (rehype-pretty-code already in the repo) and the
// "why hybrid" callout that ties to Lesson 1.

const SQL_EXCERPT = `-- knowledge_claims: the canonical operational layer
CREATE TABLE knowledge_claims (
  id            TEXT PRIMARY KEY,
  kind          TEXT NOT NULL,        -- fact | decision | question | insight | commitment
  text          TEXT NOT NULL,
  confidence    REAL NOT NULL,
  source        TEXT,                 -- session id, file path, chat thread
  created_at    INTEGER NOT NULL,
  superseded_by TEXT REFERENCES knowledge_claims(id)
);

-- FTS5 mirror — keyword search at SQLite speed
CREATE VIRTUAL TABLE knowledge_claims_fts USING fts5(
  text, content='knowledge_claims', content_rowid='rowid'
);

-- memory_embeddings: the semantic layer, lazily populated
CREATE TABLE memory_embeddings (
  claim_id  TEXT PRIMARY KEY REFERENCES knowledge_claims(id),
  vector    BLOB NOT NULL,
  model     TEXT NOT NULL,
  dim       INTEGER NOT NULL
);`;

export const MemorySchema: React.FC = () => (
  <SectionShell
    id="memory-schema"
    eyebrow="Memory"
    title="Two tiers, hybrid retrieval."
    subtitle="Tier 1 is canonical ground truth — SQLite-backed claims with FTS5. Tier 2 is the live retrieval layer, a vector index lazily synced from Tier 1. Every answer Homer gives traces back to a claim row."
  >
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
      {[
        {
          tier: 'Tier 1 — Canonical',
          body: 'knowledge_claims (SQLite) + ~/memory/*.md. Source-of-truth for every fact. FTS5 keyword search, transactional integrity, never silently rewritten.',
        },
        {
          tier: 'Tier 2 — Live',
          body: 'memory_context MCP call: real-time freshness check before any status / goal / plan answer. Vector + FTS hybrid scoring; falls back to canonical on conflict.',
        },
      ].map((t) => (
        <div
          key={t.tier}
          className="p-4 md:p-6 rounded-md border"
          style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
        >
          <div
            className="text-xs tracking-[0.24em] uppercase mb-3"
            style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
          >
            {t.tier}
          </div>
          <div
            className="text-base leading-relaxed"
            style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
          >
            {t.body}
          </div>
        </div>
      ))}
    </div>

    <pre
      className="rounded-md p-5 overflow-x-auto text-xs md:text-sm leading-relaxed border"
      style={{
        background: 'rgba(20, 18, 16, 0.85)',
        borderColor: HOMER_THEME.divider,
        fontFamily: HOMER_THEME.fontMono,
        color: HOMER_THEME.text,
      }}
    >
      <code>{SQL_EXCERPT}</code>
    </pre>
  </SectionShell>
);

export default MemorySchema;
