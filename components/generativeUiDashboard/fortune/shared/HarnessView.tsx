import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useFortuneStore } from '../../stores/fortuneStore';
import { Network, Shuffle, Target, TrendingUp, TriangleAlert, X } from 'lucide-react';
import type { FortuneFinding, ZiweiChart, ZiweiStar } from '../../lib/fortuneTypes';
const AGREEMENT_LABELS = {
  convergent: 'Both perspectives align', mixed: 'Mixed signals',
  bazi_only: 'Bazi perspective', ziwei_only: 'Zi Wei perspective',
};

/** `personLabel` names whose birthday ages these are (compatibility uses Person A). */
function findingWindow(f: FortuneFinding, personLabel?: string): string {
  if (f.start_year === null || f.end_year === null) return 'No calendar window';
  const years = f.start_year === f.end_year ? `${f.start_year}` : `${f.start_year}–${f.end_year}`;
  const ages = f.age_at_birthday;
  if (ages?.length !== 2) return years;
  const range = ages[0] === ages[1] ? `${ages[0]}` : `${ages[0]}–${ages[1]}`;
  return `${years} · ${personLabel ? `${personLabel} turning` : 'Turning'} ${range}`;
}

const PALACE_NAMES: Record<string, [string, string]> = {
  soulPalace: ['命宮', 'Life'], siblingsPalace: ['兄弟', 'Siblings'],
  spousePalace: ['夫妻', 'Partnership'], childrenPalace: ['子女', 'Children'],
  wealthPalace: ['財帛', 'Wealth'], healthPalace: ['疾厄', 'Health'],
  surfacePalace: ['遷移', 'Travel'], friendsPalace: ['交友', 'Friends'],
  careerPalace: ['官祿', 'Career'], propertyPalace: ['田宅', 'Home'],
  spiritPalace: ['福德', 'Wellbeing'], parentsPalace: ['父母', 'Parents'],
};
const STAR_NAMES: Record<string, string> = {
  ziweiMaj: 'Zi Wei', tianjiMaj: 'Tian Ji', taiyangMaj: 'Sun', wuquMaj: 'Wu Qu',
  tiantongMaj: 'Tian Tong', lianzhenMaj: 'Lian Zhen', tianfuMaj: 'Tian Fu',
  taiyinMaj: 'Moon', tanlangMaj: 'Tan Lang', jumenMaj: 'Ju Men',
  tianxiangMaj: 'Tian Xiang', tianliangMaj: 'Tian Liang', qishaMaj: 'Qi Sha', pojunMaj: 'Po Jun',
};
const TRANSFORMS: Record<string, string> = { '禄': 'Gain', '祿': 'Gain', '权': 'Drive', '權': 'Drive', '科': 'Recognition', '忌': 'Strain' };
// Branch order starts at Tiger; preserve the traditional 12-cell perimeter.
const POSITIONS = [[4, 1], [3, 1], [2, 1], [1, 1], [1, 2], [1, 3], [1, 4], [2, 4], [3, 4], [4, 4], [4, 3], [4, 2]];

function starName(star: ZiweiStar) { return STAR_NAMES[star.name] || star.name.replace(/(Maj|Min)$/, ''); }
function palaceName(palace: ZiweiChart['palaces'][number]) { return PALACE_NAMES[palace.key] || ['', palace.name]; }

export function HarnessView({ accent, children }: { accent: string; children: React.ReactNode }) {
  const [params, setParams] = useSearchParams();
  const [expanded, setExpanded] = useState(() => params.has('view'));
  const [workings, setWorkings] = useState(false);
  const model = useFortuneStore(s => s.dataModel);
  const trace = useFortuneStore(s => s.traceEvents);
  const status = useFortuneStore(s => s.status);
  const view = ['chart', 'pipeline'].includes(params.get('view') || '') ? params.get('view')! : 'findings';
  const brief = model?.harness?.brief;
  const selectedFinding = brief?.findings[Number(params.get('finding') || 0)];
  const person = params.get('person') === 'b' ? 'personB' : 'personA';
  const chart = model?.harness?.charts?.[person];
  // Birthday ages in the brief are always Person A's; only say so when there are two charts.
  const personLabel = model?.harness?.charts?.personB ? 'Person A' : undefined;
  const selectedIndex = Number(params.get('palace') ?? chart?.palaces.find(p => p.key === 'soulPalace')?.index ?? 0);
  const selected = chart?.palaces.find(p => p.index === selectedIndex);
  const linked = selectedFinding?.evidence_paths.flatMap(path => {
    const prefix = person === 'personB' ? /^\/person_b\/ziwei\/palaces\/(\d+)/ : /^\/ziwei\/palaces\/(\d+)/;
    const match = path.match(prefix);
    return match ? [Number(match[1])] : [];
  }) || [];
  const navigate = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([key, value]) => next.set(key, value));
    setParams(next, { replace: true });
  };
  const running = status === 'loading' || status === 'streaming';

  return (
    <>
    <div className="mb-4 flex justify-end">
      <button type="button" aria-expanded={expanded} aria-controls="fortune-harness"
        onClick={() => {
          setExpanded(!expanded);
          if (expanded) {
            const next = new URLSearchParams(params);
            ['view', 'finding', 'palace', 'person'].forEach(key => next.delete(key));
            setParams(next, { replace: true });
          }
        }}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-white/10 px-3 text-xs text-slate-400 hover:text-white">
        {expanded ? <X size={14} /> : <Network size={14} />}
        {expanded ? 'Close backend explorer' : 'Explore backend'}
      </button>
    </div>
    {!expanded ? children : <section id="fortune-harness" className="space-y-6 pb-8" aria-label="How this reading was made">
      <header>
        <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color: accent }}>Inside the reading</p>
        <h2 className="font-serif text-2xl text-[#f4e9c8]">From chart to life advice.</h2>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-400">Explore the evidence, the twelve palaces, and the steps that turn calculations into your reading.</p>
      </header>
      <nav className="flex border-b border-white/10" aria-label="Reading explanation views">
        {[['findings', 'What we found'], ['chart', '12 palaces'], ['pipeline', 'How it works']].map(([id, label]) => (
          <button type="button" key={id} aria-pressed={view === id} onClick={() => navigate({ view: id })}
            className="min-h-11 border-b-2 px-3 py-3 text-xs transition-colors sm:px-4" style={{ color: view === id ? accent : '#94a3b8', borderColor: view === id ? accent : 'transparent' }}>{label}</button>
        ))}
      </nav>

      {view === 'findings' && <>
        {!brief && <p className="border border-dashed border-white/15 p-4 text-sm leading-relaxed text-slate-400">
          {status === 'error' ? 'This reading stopped before its findings were ready. Start a new reading to try again.' : 'This older reading has no saved findings. Start a new reading to explore them.'}
        </p>}
        {!!brief?.findings.length && <label className="block text-xs text-slate-400">
          Finding
          <select aria-label="Finding" value={params.get('finding') || '0'} onChange={e => navigate({ finding: e.target.value })}
            className="mt-2 min-h-11 w-full min-w-0 rounded-lg border border-white/10 bg-[#0d1419] px-3 text-sm text-slate-200">
            {brief.findings.map((finding, index) => <option key={index} value={index}>{index + 1}. {finding.topic}</option>)}
          </select>
        </label>}
        {selectedFinding && <div className="space-y-3 border border-white/10 p-4 sm:p-5">
          <p className="text-xs" style={{ color: accent }}>{findingWindow(selectedFinding, personLabel)} · {AGREEMENT_LABELS[selectedFinding.agreement]}</p>
          <h3 className="font-serif text-xl text-[#f4e9c8]">{selectedFinding.topic}</h3>
          <ul className="space-y-2">
            {([
              [TrendingUp, 'Opportunity', selectedFinding.opportunity, '#94a3b8'],
              [TriangleAlert, 'Risk', selectedFinding.risk, '#f59e0b'],
              [Target, 'Action', selectedFinding.action, '#94a3b8'],
              [Shuffle, 'If it plays out differently', selectedFinding.alternative, '#94a3b8'],
            ] as const).filter(([, , text]) => !!text).map(([Icon, label, text, color]) => (
              <li key={label} className="flex gap-2 text-[13px] leading-relaxed text-slate-300">
                <Icon size={14} className="mt-1 flex-none" style={{ color }} aria-hidden />
                <span><b className="font-medium text-slate-200">{label}: </b>{text}</span>
              </li>
            ))}
          </ul>
          <details className="border-t border-white/10 pt-3">
            <summary className="inline-flex min-h-11 cursor-pointer items-center text-xs text-slate-400 hover:text-slate-200">Technical basis and chart references</summary>
            <p className="mt-2 text-[13px] leading-relaxed text-slate-300">{selectedFinding.technical_basis}</p>
            <p className="mt-3 text-[11px] text-slate-500">Tap a chart reference to open that palace.</p>
            <div className="mt-2 flex flex-wrap gap-2">{selectedFinding.evidence_paths.map(path => {
              const palace = path.match(/^(\/person_b)?\/ziwei\/palaces\/(\d+)/);
              return palace ? <button type="button" key={path} className="inline-flex min-h-11 items-center border border-white/10 px-2.5 font-mono text-[11px] hover:bg-white/5" style={{ color: accent }}
                aria-label={`Open palace ${palace[2]}${palace[1] ? ' for Person B' : ''}`}
                onClick={() => navigate({ view: 'chart', person: palace[1] ? 'b' : 'a', palace: palace[2] })}>{path}</button>
                : <span key={path} className="inline-flex min-h-11 items-center border border-white/10 px-2.5 font-mono text-[11px] text-slate-400">{path}</span>;
            })}</div>
          </details>
        </div>}
        {!!brief?.limitations?.length && <details className="border border-white/10 p-4">
          <summary className="min-h-11 cursor-pointer text-xs text-slate-300">What this reading cannot tell you</summary>
          <ul className="mt-2 space-y-2">
            {brief.limitations.map(limit => <li key={limit} className="text-[13px] leading-relaxed text-slate-400">{limit}</li>)}
            {brief.withheld_findings?.map(withheld => <li key={withheld.topic} className="text-[13px] leading-relaxed text-slate-400">Withheld: {withheld.topic} — {withheld.reason}</li>)}
          </ul>
        </details>}
        {children}
      </>}

      {view === 'chart' && <>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2">{model?.harness?.charts?.personB && ['a', 'b'].map(id => {
            const active = (person === 'personB' ? 'b' : 'a') === id;
            return <button key={id} type="button"
              onClick={() => navigate({ person: id })} aria-pressed={active}
              className="min-h-11 border px-3 text-xs"
              style={{ borderColor: active ? accent : 'rgba(255,255,255,0.1)', color: active ? accent : '#cbd5e1', background: active ? `${accent}14` : 'transparent' }}>Person {id.toUpperCase()}</button>;
          })}</div>
          <label className="flex min-h-11 items-center gap-2 text-xs text-slate-400"><input type="checkbox" className="h-4 w-4" checked={workings} onChange={e => setWorkings(e.target.checked)} />Show technical details</label>
        </div>
        {chart?.status === 'computed' ? <>
          <div className="grid grid-cols-4 gap-1.5 sm:gap-2" role="group" aria-label="Twelve palace chart">
            <div className="col-start-2 col-end-4 row-start-2 row-end-4 flex min-w-0 flex-col items-center justify-center px-2 text-center">
              <span className="font-serif text-3xl text-[#f4e9c8] sm:text-5xl">紫微</span>
              <h3 className="mt-2 font-serif text-sm text-[#f4e9c8] sm:text-xl">Twelve palaces</h3>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-400 sm:text-xs">Tap a life area to see its stars and links.</p>
              <p className="mt-4 hidden font-mono text-[9px] text-slate-500 sm:block">{chart.engine} {chart.version}<br />Locally computed chart</p>
            </div>
            {chart.palaces.map(p => {
              const [cjk, label] = palaceName(p);
              const active = selected?.index === p.index;
              const related = selected?.related_palace_indices.includes(p.index);
              const [row, col] = POSITIONS[p.index] || [1, 1];
              return <button key={p.index} type="button" aria-label={`${label} palace`} aria-pressed={active}
                onClick={() => navigate({ palace: String(p.index) })}
                className="relative flex min-h-[95px] min-w-0 flex-col items-start border p-2 text-left transition-colors sm:min-h-[125px] sm:p-3"
                style={{ gridRow: row, gridColumn: col, borderColor: active || related ? accent : '#263139', borderStyle: related && !active ? 'dashed' : 'solid', background: active ? `${accent}18` : '#0d1419' }}>
                <span className="font-serif text-sm text-[#f4e9c8] sm:text-lg">{cjk}</span>
                <span className="mb-2 text-[10px] leading-tight text-slate-300 sm:text-xs">{label}{p.is_body_palace ? ' · Body' : ''}</span>
                <span className="mt-auto text-[10px] leading-snug text-slate-400 sm:text-[11px]">{p.major_stars.map(starName).join(' · ') || 'No major star'}</span>
                {linked.includes(p.index) && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full" style={{ background: accent }} aria-label="Cited in selected finding" />}
                {workings && <span className="mt-1 font-mono text-[9px] text-slate-500">{p.decadal_nominal_ages.join('–')} nominal</span>}
              </button>;
            })}
          </div>
          <p className="text-[11px] leading-relaxed text-slate-500">Solid border: selected · Dashed: related palaces · Dot: cited in the selected finding</p>
          {selected && <div className="border border-white/10 p-5" aria-live="polite">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><h3 className="font-serif text-xl text-[#f4e9c8]">{palaceName(selected).join(' · ')}</h3><span className="font-mono text-[10px] text-slate-400">Traditional decade · {selected.decadal_nominal_ages.join('–')} nominal age</span></div>
            <p className="mb-4 text-[11px] leading-relaxed text-slate-400">Nominal ages are traditional chart labels, not birthday ages or exact calendar transition dates.</p>
            <div className="flex flex-wrap gap-3">{selected.major_stars.map(star => <div key={star.name} className="border border-white/10 px-3 py-2">
              <p className="text-sm text-slate-200">{starName(star)}</p><p className="mt-1 text-xs text-slate-400">{star.mutagen ? `${star.mutagen} · ${TRANSFORMS[star.mutagen] || star.mutagen}` : 'No natal transformation'}</p>
              {workings && <p className="mt-1 font-mono text-[10px] text-slate-500">Brightness: {star.brightness || 'not rated'}</p>}
            </div>)}</div>
            {!selected.major_stars.length && <p className="text-sm text-slate-400">No major star is placed here. Read this palace with its opposite and related palaces.</p>}
            <div className="mt-4 flex flex-wrap gap-2">{selected.related_palace_indices.map((index, order) => {
              const related = chart.palaces.find(p => p.index === index);
              return related && <button key={index} type="button" className="inline-flex min-h-11 items-center text-xs hover:underline" style={{ color: accent }} onClick={() => navigate({ palace: String(index) })}>{order === 2 ? 'Opposite' : 'Trine'}: {palaceName(related)[1]}</button>;
            })}</div>
            {workings && <div className="mt-4 space-y-2 border-t border-white/10 pt-4 font-mono text-[10px] leading-relaxed text-slate-400">
              <p>{selected.stem} / {selected.branch} · {selected.minor_stars.map(starName).join(', ') || 'No minor stars'}</p>
              <p>{person === 'personB' ? '/person_b' : ''}/ziwei/palaces/{selected.index}</p>
            </div>}
            {brief?.findings.filter(f => f.evidence_paths.some(path => path === `${person === 'personB' ? '/person_b' : ''}/ziwei/palaces/${selected.index}` || path.startsWith(`${person === 'personB' ? '/person_b' : ''}/ziwei/palaces/${selected.index}/`))).map((f, index) =>
              <div key={index} className="mt-4 border-t border-white/10 pt-4"><p className="text-xs" style={{ color: accent }}>{f.topic}</p><p className="mt-1 text-sm leading-relaxed text-slate-300">{f.technical_basis}</p></div>)}
          </div>}
        </> : <div className="border border-dashed border-white/15 p-8 text-center">
          <h3 className="font-serif text-xl text-[#f4e9c8]">{running ? 'Preparing the chart' : 'Twelve-palace chart unavailable'}</h3>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">{running ? 'The chart will appear when the local calculation finishes.' : chart?.reason === 'birth_time_unknown' ? 'A birth hour is needed to place the twelve palaces. This reading uses the available Bazi pillars.' : chart?.reason === 'gender_unknown' ? 'The selected chart convention requires gender. Available Bazi evidence still supports this reading.' : 'This reading was made before palace charts were saved. Start a new reading to explore them.'}</p>
        </div>}
        <div className="grid grid-cols-4 gap-2" aria-label="Bazi four pillars">{(['year', 'month', 'day', 'hour'] as const).map(key => {
          const pillar = person === 'personA' ? model?.pillars?.[key] : model?.compatibility?.personB?.pillars?.[key];
          return <div key={key} className="border-t border-white/10 py-3"><p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">{key}</p><p className="text-xs text-slate-300">{pillar ? `${pillar.stem} · ${pillar.branch}` : 'Not supplied'}</p></div>;
        })}</div>
      </>}

      {view === 'pipeline' && <div className="space-y-6">
        <div className="border border-white/10 p-5"><p className="font-serif text-xl text-[#f4e9c8]">Calculate → interpret → check → explain</p><p className="mt-2 text-sm leading-relaxed text-slate-400">The model interprets saved chart facts. A separate check verifies its evidence references and timing before the reading is written.</p></div>
        {[
          ['01', 'Calculate the charts', 'Deterministic', `Bazi pillars + ${chart?.status === 'computed' ? '12 Zi Wei palaces' : 'Zi Wei unavailable for this reading'}`],
          ['02', 'Find relevant passages', 'Local retrieval', model?.harness?.sources ? `${model.harness.sources.bazi_passages} passages from ${model.harness.sources.bazi_books} Bazi texts. ${model.harness.sources.ziwei_passages} Zi Wei passages attached.` : 'Bazi source passages are shown in Findings. No Zi Wei classical corpus is attached.'],
          ['03', 'Compare the evidence', 'Technical interpreter', 'Opportunities, tensions, alternative interpretations and supported timing.'],
          ['04', 'Check the findings', brief?.validation?.status === 'passed' ? 'Passed' : running ? 'Pending' : 'Not recorded', brief?.validation ? `${brief.validation.checks.join(' · ')}. Retained: ${brief.findings.length}. Withheld: ${brief.withheld_findings?.length || 0}. Repairs: ${brief.validation.repairs}.` : 'Evidence-path and timing checks run before presentation.'],
          ['05', 'Write the reading', 'Audience writer', 'Life themes, ages, possible events and actions in plain English.'],
          ['06', 'Review the output', model?.guardrail ? 'Reviewed' : 'Pending', 'The findings and final prose pass the same safety review before display.'],
        ].map(([number, title, badge, description]) => <div key={number} className="grid grid-cols-[32px_1fr] gap-3 border-b border-white/10 pb-4"><span className="font-mono text-xs" style={{ color: accent }}>{number}</span><div><div className="flex flex-wrap justify-between gap-2"><h3 className="text-sm text-slate-200">{title}</h3><span className="font-mono text-[10px] text-slate-400">{badge}</span></div><p className="mt-2 text-xs leading-relaxed text-slate-400">{description}</p></div></div>)}
        <p className="text-xs text-slate-400">{trace.length} trace events recorded. Expand the execution trace for measured durations and model names.</p>
        <details className="border border-white/10 p-4"><summary className="cursor-pointer text-xs text-slate-300">Calculation conventions and limits</summary><div className="mt-3 space-y-2 text-xs leading-relaxed text-slate-400">{Object.entries(chart?.conventions || {}).map(([key, value]) => <p key={key}><b>{key.replace(/_/g, ' ')}:</b> {value}</p>)}{chart?.limits?.map(limit => <p key={limit}>{limit}</p>)}<p>Evidence checks verify references and calendar coverage. They do not prove that a predicted event will occur.</p></div></details>
      </div>}
    </section>}
    </>
  );
}
