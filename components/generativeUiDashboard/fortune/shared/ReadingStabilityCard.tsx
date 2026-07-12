/**
 * ReadingStabilityCard — birth-hour uncertainty simulator for unknown times.
 *
 * Calls POST /simulate and renders stability score/label, branch hypotheses
 * grouped by whether day-master / dominant element stay modal, and the most
 * sensitive chart elements.
 */

import React, { useMemo, useState } from 'react';
import { Loader2, ShieldAlert } from 'lucide-react';
import { fortuneClient } from '../../lib/fortuneClient';
import { GLASS } from '../designTokens';

interface StabilityField {
  value?: string;
  count?: number;
  total?: number;
  distribution?: Record<string, number>;
}

interface BranchHypothesis {
  branch?: string;
  repHour?: string;
  window?: string;
  dayMaster?: string;
  dominantElement?: string;
  weakestElement?: string;
  seasonalStrength?: string;
  harmonyScore?: number;
}

interface SimulatePayload {
  branches?: BranchHypothesis[];
  stability?: {
    dayMaster?: StabilityField;
    dominantElement?: StabilityField;
    seasonalStrength?: StabilityField;
    hourBranchDiversity?: number;
  } | null;
  completedBranches?: number;
  expectedBranches?: number;
  partial?: boolean;
  error?: string;
}

function fieldScore(field?: StabilityField): number {
  if (!field || !field.total || !field.count) return 0;
  return field.count / field.total;
}

function stabilityLabel(score: number): string {
  if (score >= 11 / 12) return 'High';
  if (score >= 8 / 12) return 'Moderate';
  if (score >= 0.5) return 'Mixed';
  return 'Low';
}

function stabilityColor(score: number): string {
  if (score >= 11 / 12) return '#34d399';
  if (score >= 8 / 12) return '#fbbf24';
  if (score >= 0.5) return '#fb923c';
  return '#f87171';
}

export interface ReadingStabilityCardProps {
  fortuneId: string | null;
  accent?: string;
}

export const ReadingStabilityCard: React.FC<ReadingStabilityCardProps> = ({
  fortuneId,
  accent = '#f59e0b',
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<SimulatePayload | null>(null);

  const run = async () => {
    if (!fortuneId || loading) return;
    setLoading(true);
    setError(null);
    try {
      const data = (await fortuneClient.simulateBirthTime(fortuneId)) as SimulatePayload;
      setPayload(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const analysis = useMemo(() => {
    if (!payload?.stability) return null;
    const { dayMaster, dominantElement, seasonalStrength } = payload.stability;
    const scores = [fieldScore(dayMaster), fieldScore(dominantElement), fieldScore(seasonalStrength)];
    const overall = scores.reduce((a, b) => a + b, 0) / Math.max(scores.length, 1);

    const modalDay = dayMaster?.value;
    const modalDom = dominantElement?.value;
    const stable: BranchHypothesis[] = [];
    const shifting: BranchHypothesis[] = [];
    for (const b of payload.branches || []) {
      const dayOk = !modalDay || b.dayMaster === modalDay;
      const domOk = !modalDom || b.dominantElement === modalDom;
      if (dayOk && domOk) stable.push(b);
      else shifting.push(b);
    }

    const sensitive: string[] = [];
    const pushIfWeak = (label: string, field?: StabilityField) => {
      if (!field?.total || !field.count) return;
      if (field.count < field.total) {
        const alt = Object.entries(field.distribution || {})
          .filter(([k]) => k !== field.value)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 2)
          .map(([k, n]) => `${k} (${n})`)
          .join(', ');
        sensitive.push(
          alt
            ? `${label} can shift to ${alt}`
            : `${label} is not unanimous across hours`,
        );
      }
    };
    pushIfWeak('Day master', dayMaster);
    pushIfWeak('Dominant element', dominantElement);
    pushIfWeak('Seasonal strength', seasonalStrength);

    return { overall, stable, shifting, sensitive, dayMaster, dominantElement, seasonalStrength };
  }, [payload]);

  return (
    <div className={`${GLASS} border-amber-500/15 bg-amber-500/[0.03] p-4`}>
      <div className="flex items-start gap-3">
        <div
          className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-xl"
          style={{ background: `${accent}18`, color: accent }}
        >
          <ShieldAlert size={15} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-300">
            Reading Stability
          </h3>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
            Birth hour was unknown, so this reading used a noon hypothesis.
            Simulate all 12 earthly-branch hours to see what stays stable.
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={run}
        disabled={!fortuneId || loading}
        className="mt-3 inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-[11px] font-semibold transition-colors disabled:opacity-50"
        style={{
          borderColor: `${accent}55`,
          color: accent,
          background: `${accent}12`,
        }}
      >
        {loading ? <Loader2 size={12} className="animate-spin" /> : null}
        {loading ? 'Simulating 12 hours…' : payload ? 'Re-run stability check' : 'How stable is this reading?'}
      </button>

      {error && (
        <p className="mt-2 text-[11px] text-rose-400">{error}</p>
      )}

      {analysis && payload?.stability && (
        <div className="mt-4 space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-slate-500">
                Stability score
              </div>
              <div
                className="text-lg font-semibold"
                style={{ color: stabilityColor(analysis.overall) }}
              >
                {Math.round(analysis.overall * 100)}% · {stabilityLabel(analysis.overall)}
              </div>
            </div>
            <div className="text-right text-[10px] text-slate-500">
              {payload.completedBranches}/{payload.expectedBranches || 12} branches
              {payload.partial ? ' (partial)' : ''}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            {[
              ['Day master', analysis.dayMaster],
              ['Dominant element', analysis.dominantElement],
              ['Seasonal strength', analysis.seasonalStrength],
            ].map(([label, field]) => {
              const f = field as StabilityField | undefined;
              return (
                <div
                  key={String(label)}
                  className="rounded-lg border border-white/5 bg-black/20 px-3 py-2"
                >
                  <div className="text-[9px] uppercase tracking-wider text-slate-500">
                    {label as string}
                  </div>
                  <div className="mt-0.5 truncate text-[12px] text-slate-200">
                    {f?.value || '—'}
                  </div>
                  <div className="font-mono text-[10px] text-slate-500">
                    {f?.count ?? 0}/{f?.total ?? 0} agree
                  </div>
                </div>
              );
            })}
          </div>

          <div className="space-y-2">
            <BranchGroup
              title="Stable across hours"
              hint="Day master + dominant element match the modal reading"
              branches={analysis.stable}
              tone="#34d399"
            />
            <BranchGroup
              title="Shifts the chart conclusions"
              hint="Hour changes day-master or dominant-element outcome"
              branches={analysis.shifting}
              tone="#fb923c"
            />
          </div>

          {analysis.sensitive.length > 0 && (
            <p className="text-[11px] leading-relaxed text-slate-400">
              Most sensitive: {analysis.sensitive.join('; ')}.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

function BranchGroup({
  title,
  hint,
  branches,
  tone,
}: {
  title: string;
  hint: string;
  branches: BranchHypothesis[];
  tone: string;
}) {
  if (branches.length === 0) return null;
  return (
    <div className="rounded-lg border border-white/5 bg-black/15 px-3 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: tone }}>
          {title} · {branches.length}
        </div>
        <div className="text-[9px] text-slate-600">{hint}</div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {branches.map((b) => (
          <span
            key={`${b.branch}-${b.repHour}`}
            className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 font-mono text-[10px] text-slate-300"
            title={`${b.window || ''} · ${b.dayMaster || ''} · ${b.dominantElement || ''}`}
          >
            {b.branch}
            {b.repHour ? ` ${b.repHour}` : ''}
          </span>
        ))}
      </div>
    </div>
  );
}

export default ReadingStabilityCard;
