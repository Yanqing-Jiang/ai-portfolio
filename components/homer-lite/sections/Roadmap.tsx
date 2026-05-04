import React from 'react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: Roadmap — "What's next" section.
// Forward-looking — Homer is live, here's what's coming. Each item has a status
// pill (in progress / next / soon / shipped) so the page stays honest about
// where each capability actually is.

type Status = 'in-progress' | 'next' | 'soon' | 'shipped';

const STATUS_COLOR: Record<Status, { bg: string; text: string; label: string }> = {
  shipped: { bg: 'rgba(34, 197, 94, 0.15)', text: '#86efac', label: 'shipped' },
  'in-progress': { bg: 'rgba(212, 160, 86, 0.18)', text: '#f5cf94', label: 'in progress' },
  next: { bg: 'rgba(56, 189, 248, 0.15)', text: '#7dd3fc', label: 'next' },
  soon: { bg: 'rgba(168, 85, 247, 0.15)', text: '#d8b4fe', label: 'soon' },
};

const ITEMS: { title: string; body: string; status: Status }[] = [
  {
    title: 'Public Try-Homer console',
    body: 'A sandboxed terminal on this page so visitors can run real Homer commands (status, memory_search, schedule) against a public-safe view of the system. Same MCP tools, sanitized data.',
    status: 'in-progress',
  },
  {
    title: 'Voice agent v2 — interruption + barge-in',
    body: 'Upgrade the ElevenLabs Managed Agent flow with full-duplex barge-in so I can interrupt mid-sentence. Re-tunes the call routing layer in src/voice/.',
    status: 'in-progress',
  },
  {
    title: 'homer-lite — MIT-licensed architecture extraction',
    body: 'A clean public repo containing the state schema, scheduler, executor abstraction, and MCP safe subset. No personal data, no production secrets — just the architecture.',
    status: 'next',
  },
  {
    title: 'Self-pruning skills harness',
    body: 'Today the skills layer self-prunes by usage. Next: have it propose merges and consolidations, not just deletions. Closes the meta-harness loop.',
    status: 'next',
  },
  {
    title: 'Cross-device memory sync',
    body: 'Homer currently lives on the Mac Mini. Next iteration: a thin remote client (mobile + work laptop) that pushes claims into the same memory layer over an encrypted tunnel.',
    status: 'soon',
  },
  {
    title: 'Marketplace of agent recipes',
    body: 'A registry of named agent flows (job-hunt, content, research, ops) that anyone can install into their own Homer instance via a single CLI command. Probably gated behind homer-lite v1.',
    status: 'soon',
  },
];

export const Roadmap: React.FC = () => (
  <SectionShell
    id="roadmap"
    eyebrow="What's next"
    title="The plans I'm working through right now."
    subtitle="Homer is live, but never finished. Each item below is real work in progress — pulled straight from my plan tracker."
  >
    <div className="space-y-3 md:space-y-4">
      {ITEMS.map((item, i) => {
        const c = STATUS_COLOR[item.status];
        return (
          <article
            key={i}
            className="grid md:grid-cols-[140px_1fr] gap-3 md:gap-8 p-5 md:p-6 rounded-md border transition-colors hover:bg-white/[0.02]"
            style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
          >
            <div>
              <span
                className="inline-block text-[10px] tracking-[0.24em] uppercase px-2.5 py-1 rounded-full"
                style={{ background: c.bg, color: c.text, fontFamily: HOMER_THEME.fontMono }}
              >
                {c.label}
              </span>
            </div>
            <div>
              <h3
                className="text-lg md:text-xl mb-2"
                style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
              >
                {item.title}
              </h3>
              <p className="text-sm md:text-base leading-relaxed" style={{ color: HOMER_THEME.textMuted }}>
                {item.body}
              </p>
            </div>
          </article>
        );
      })}
    </div>
  </SectionShell>
);

export default Roadmap;
