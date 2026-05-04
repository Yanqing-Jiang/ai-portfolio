import React from 'react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: OssCard — Plan §8.0 (new section vs prior plan).
// The bridge between the case study and the github.com/<yanqing>/homer-lite repo
// that Sprint 4 builds. Until the repo is public the link is disabled and we
// signal that the public extraction lands May 15.

const REPO_URL = 'https://github.com/Yanqing-Jiang/homer-lite'; // populated end of Sprint 4
const REPO_LIVE = false;

export const OssCard: React.FC = () => (
  <SectionShell id="oss" eyebrow="Open source" title="Production private. Lite public.">
    <div
      className="rounded-lg border p-6 md:p-10"
      style={{
        borderColor: HOMER_THEME.divider,
        background: HOMER_THEME.bgSoft,
      }}
    >
      <p
        className="text-base md:text-lg leading-relaxed mb-8"
        style={{ fontFamily: HOMER_THEME.fontSerif, color: HOMER_THEME.text }}
      >
        Production Homer runs privately because it holds personal memory,
        communications, credentials, and confidential work context.{' '}
        <span style={{ color: HOMER_THEME.accent }}>homer-lite</span> is the
        sanitized open-source extraction — same architecture, mock
        integrations, generated sample data, MIT-licensed.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-6 mb-10">
        <div>
          <div className="text-[11px] tracking-[0.24em] uppercase mb-2" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}>
            Public
          </div>
          <ul className="space-y-1.5 text-sm" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
            <li>· state schema + migrations</li>
            <li>· FTS5 + vector hybrid search</li>
            <li>· scheduler core + sample jobs</li>
            <li>· executor abstraction + mock adapter</li>
            <li>· MCP safe subset</li>
          </ul>
        </div>
        <div>
          <div className="text-[11px] tracking-[0.24em] uppercase mb-2" style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}>
            Stays private
          </div>
          <ul className="space-y-1.5 text-sm" style={{ color: HOMER_THEME.textMuted, fontFamily: HOMER_THEME.fontMono }}>
            <li>· production database + backups</li>
            <li>· personal memory files</li>
            <li>· Telegram / Gmail / Voice integrations</li>
            <li>· proprietary skills + work context</li>
            <li>· anything touching real services</li>
          </ul>
        </div>
      </div>

      <a
        href={REPO_LIVE ? REPO_URL : '#'}
        aria-disabled={!REPO_LIVE}
        onClick={(e) => {
          if (!REPO_LIVE) e.preventDefault();
        }}
        className="inline-flex min-h-[44px] max-w-full items-center justify-center gap-2 px-4 md:px-5 py-3 rounded-full text-sm text-center transition-colors"
        style={{
          background: REPO_LIVE ? HOMER_THEME.accent : 'transparent',
          border: `1px solid ${REPO_LIVE ? HOMER_THEME.accent : HOMER_THEME.divider}`,
          color: REPO_LIVE ? '#1a160f' : HOMER_THEME.textMuted,
          fontFamily: HOMER_THEME.fontMono,
          letterSpacing: '0.05em',
        }}
      >
        {REPO_LIVE ? 'View homer-lite on GitHub →' : '[ public repo lands May 15 ]'}
      </a>
    </div>
  </SectionShell>
);

export default OssCard;
