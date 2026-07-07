import React from 'react';
import { Link } from 'react-router-dom';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: CTA — final section.
// Consulting framing: Homer is the proof I know how to build production agent
// systems; if you need that, here's how to talk to me. Primary CTA goes to the
// existing /consult page (ConsultingPage component). No GitHub, no Calendly,
// no recruiter framing — just consulting + email + LinkedIn.

const LINKS = [
  { label: 'Email', href: 'mailto:jiangyanqing91@gmail.com' },
  { label: 'LinkedIn', href: 'https://www.linkedin.com/in/yanqing-jiang/' },
];

export const CTA: React.FC = () => (
  <SectionShell
    id="cta"
    eyebrow="Talk"
    title="Need help shipping AI agents in production?"
  >
    <p
      className="text-lg md:text-xl mb-10 max-w-2xl leading-relaxed"
      style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.textMuted }}
    >
      Homer is what I built for myself. The same patterns — durable memory,
      multi-CLI orchestration, scheduled jobs, MCP tools — work for production
      teams. If your team is stuck somewhere between &ldquo;cool prototype&rdquo;
      and &ldquo;reliable in production,&rdquo; I can help.
    </p>

    <div className="flex flex-col sm:flex-row gap-4 mb-12 items-start sm:items-center">
      <Link
        to="/consult"
        className="inline-flex min-h-[44px] items-center justify-center px-7 py-3.5 rounded-full text-sm transition-transform hover:-translate-y-0.5"
        style={{
          background: HOMER_THEME.accent,
          color: '#1a160f',
          fontFamily: HOMER_THEME.fontMono,
          letterSpacing: '0.05em',
          fontWeight: 600,
        }}
      >
        Book a consulting session →
      </Link>

      <div className="flex items-center gap-3 sm:gap-6">
        {LINKS.map((l) => (
          <a
            key={l.label}
            href={l.href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-[44px] items-center p-2 text-sm transition-colors hover:opacity-80"
            style={{
              color: HOMER_THEME.text,
              fontFamily: HOMER_THEME.fontMono,
              letterSpacing: '0.05em',
            }}
          >
            {l.label} →
          </a>
        ))}
      </div>
    </div>

    <div
      className="text-xs pt-12 border-t"
      style={{
        borderColor: HOMER_THEME.divider,
        color: HOMER_THEME.textMuted,
        fontFamily: HOMER_THEME.fontMono,
      }}
    >
      Homer runs privately on a Mac Mini. The architecture extraction
      (homer-lite, MIT) is in the works.
    </div>
  </SectionShell>
);

export default CTA;
