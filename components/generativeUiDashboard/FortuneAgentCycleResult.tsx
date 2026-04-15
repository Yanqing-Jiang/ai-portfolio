import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * FortuneAgentCycleResult
 * 
 * Premium Cycle Reading (year/month luck timeline).
 * Redesigned for mobile-first vertical stack, no horizontal scroll.
 * Theme: Occasion Page (Dark Indigo, Gold, Chinese Serif).
 */

interface FortuneAgentCycleResultProps {
  onBack?: () => void;
}

// --- MOCK DATA ---
const MOCK_CURRENT = {
  month: "April 2026",
  pillar: "癸巳月",
  score: 68,
  bullets: [
    "Mood: Internal restlessness meeting strategic clarity.",
    "Opportunity: Harmonious Wood supports your Fire Day Master.",
    "Warning: Metal of the year brings pressure to consolidate."
  ],
  citation: { text: "水火既濟，君子以思患而豫防之。", source: "《易經》" },
  horizonPosition: 0.2, // position in 5-year view
};

const MOCK_DECADES = [
  { name: '己丑', range: '2012 - 2021', status: 'past' },
  { name: '庚寅', range: '2022 - 2031', status: 'current', analysis: "Metal shapes your Fire — a decade of material achievement through discipline." },
  { name: '辛卯', range: '2032 - 2041', status: 'future' },
];

const MOCK_YEARS = [
  { year: 2025, label: "2025 · 33 sui", pillar: "乙巳", score: 52, scores: [45, 38, 50, 55, 60, 58, 52, 48, 45, 50, 55, 62], summary: ["Consolidation phase.", "Watch health in early Q1.", "Family harmony improves."], citation: { text: "乙木生火，氣勢和平。", source: "《淵海子平》" } },
  { year: 2026, label: "2026 · 34 sui", pillar: "丙午", score: 78, scores: [60, 65, 68, 70, 75, 82, 85, 80, 78, 88, 92, 85], summary: ["Peak energy year.", "Career breakthrough in Oct/Nov.", "Yang-blade intensity requires focus."], citation: { text: "丙午之火，得地而強。", source: "《子平真詮》" } },
  { year: 2027, label: "2027 · 35 sui", pillar: "丁未", score: 54, scores: [65, 60, 55, 52, 50, 48, 45, 42, 50, 55, 60, 62], summary: ["Steady consolidation.", "Avoid high-risk pivots.", "Focus on internal growth."], citation: { text: "丁未土中，火氣收斂。", source: "《命理約言》" } },
  { year: 2028, label: "2028 · 36 sui", pillar: "戊申", score: 82, scores: [70, 75, 85, 88, 90, 85, 80, 78, 82, 85, 88, 85], summary: ["Surge in wealth affinity.", "Strategic investments favored.", "Travel brings opportunity."], citation: { text: "戊申之土，生金化火。", source: "《滴天髓》" } },
  { year: 2029, label: "2029 · 37 sui", pillar: "己酉", score: 62, scores: [60, 58, 55, 52, 58, 62, 65, 68, 70, 65, 62, 60], summary: ["Balanced flow.", "Partnership development.", "Creative output peaks."], citation: { text: "己酉金地，火入長生。", source: "《淵海子平》" } },
  { year: 2030, label: "2030 · 38 sui", pillar: "庚戌", score: 55, scores: [52, 50, 48, 45, 50, 55, 58, 62, 65, 60, 55, 52], summary: ["Earthly branch clash.", "Mindful communication.", "Routine brings stability."], citation: { text: "庚金劈甲，火勢方烈。", source: "《子平真詮》" } },
  { year: 2031, label: "2031 · 39 sui", pillar: "辛亥", score: 65, scores: [55, 58, 62, 65, 68, 72, 75, 70, 65, 62, 58, 60], summary: ["Fluid transition.", "Emotional intelligence key.", "Mentorship arrives."], citation: { text: "辛金之柔，亥水之深。", source: "《命理約言》" } },
  { year: 2032, label: "2032 · 40 sui", pillar: "壬子", score: 48, scores: [50, 48, 45, 42, 40, 38, 42, 45, 50, 55, 52, 48], summary: ["Low tide period.", "Rest and reflection.", "Avoid legal conflicts."], citation: { text: "壬子水旺，火受其克。", source: "《滴天髓》" } },
  { year: 2033, label: "2033 · 41 sui", pillar: "癸丑", score: 60, scores: [52, 55, 58, 62, 65, 60, 58, 55, 60, 65, 68, 62], summary: ["Recovery phase.", "Practical foundations.", "Patience rewarded."], citation: { text: "癸水滋木，火氣復萌。", source: "《淵海子平》" } },
  { year: 2034, label: "2034 · 42 sui", pillar: "甲寅", score: 85, scores: [75, 80, 88, 92, 95, 90, 85, 82, 85, 88, 90, 88], summary: ["Major upward cycle.", "Expansion and leadership.", "Lasting legacy built."], citation: { text: "甲寅木盛，火勢沖天。", source: "《子平真詮》" } },
];

const MOCK_WHY_CARDS = [
  { icon: "Decade", name: "Decade Pillar 庚寅 (2022-2031)", bullets: ["Metal shapes your Fire: discipline yields results.", "Growth in wood energy supports vitality.", "Resource accumulation through persistence."], citation: "滴天髓 · 庚金" },
  { icon: "Year", name: "Current Year 丙午 — 羊刃", bullets: ["Yang-blade intensity: high risk, high reward.", "Direct support to Day Master Bing Fire.", "Need for emotional grounding in summer."], citation: "淵海子平 · 羊刃" },
  { icon: "Window", name: "Luck Window: Late 2026", bullets: ["Triple Fire alignment in autumn months.", "Breakthrough period for career pivots.", "Social capital peaks in November."], citation: "子平真詮 · 運限" },
  { icon: "Consolidation", name: "2027 Strategy: Consolidation", bullets: ["Earth energy absorbs excess heat.", "Shift from expansion to stabilization.", "Ideal for property or family foundations."], citation: "命理約言" },
];

// --- COMPONENTS ---

const SparklineDots = ({ scores, activeMonth }: { scores: number[], activeMonth?: number }) => {
  return (
    <div className="flex gap-1 items-center">
      {scores.map((s, i) => {
        const color = s > 75 ? '#eab308' : s < 50 ? '#dc2626' : '#f8fafc';
        const opacity = s > 75 ? '1' : s < 50 ? '0.8' : '0.4';
        const isActive = activeMonth === i + 1;
        return (
          <div 
            key={i} 
            className="relative"
            style={{ 
              width: '6px', 
              height: '6px', 
              borderRadius: '50%', 
              backgroundColor: color,
              opacity: opacity
            }}
          >
            {isActive && (
              <motion.div 
                className="absolute inset-[-4px] border border-[#eab308] rounded-full"
                animate={{ scale: [1, 1.5, 1], opacity: [1, 0, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};

const ElementRingSmall = ({ position }: { position: number }) => (
  <div className="w-12 h-12 relative flex items-center justify-center">
    <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
      <circle cx="50" cy="50" r="45" fill="transparent" stroke="#eab308" strokeWidth="2" strokeDasharray="2 4" />
      <motion.circle 
        cx="50" cy="50" r="45" fill="transparent" stroke="#eab308" strokeWidth="6" 
        strokeDasharray="282.7" strokeDashoffset={282.7 * (1 - position)}
      />
    </svg>
    <div className="absolute text-[8px] font-bold text-[#eab308]">NOW</div>
  </div>
);

// --- MAIN COMPONENT ---

export const FortuneAgentCycleResult: React.FC<FortuneAgentCycleResultProps> = ({ onBack }) => {
  const [activeTab, setActiveTab] = useState<'Now' | 'Year' | 'Why' | 'Ask'>('Now');
  const [expandedYear, setExpandedYear] = useState<number | null>(2026);

  return (
    <div
      className="min-h-screen text-[#f8fafc] font-serif selection:bg-[#eab308]/30"
      style={{
        background:
          'linear-gradient(180deg, #200a06 0%, #4a1608 55%, #0c0a14 100%)',
      }}
    >
      {/* Fixed Header Shell */}
      <div className="fixed top-0 left-0 right-0 z-50 bg-[#0c0a14]/80 backdrop-blur-md border-b border-[#eab308]/10">
        <div className="max-w-2xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-[#eab308] rotate-45" />
              <h1 className="text-lg uppercase tracking-widest text-[#eab308] font-bold">Cycle Reading</h1>
            </div>
            <span className="text-[10px] text-[#f8fafc]/50 uppercase tracking-tighter">Year & Month Luck • Bing Fire</span>
          </div>
          <button 
            onClick={onBack}
            className="px-4 py-1 rounded-full border border-[#eab308]/30 text-[10px] uppercase tracking-widest text-[#eab308] hover:bg-[#eab308]/10 transition-colors"
          >
            Back
          </button>
        </div>
      </div>

      <main className="max-w-2xl mx-auto px-4 pt-24 pb-32">
        {/* Tab Bar */}
        <nav className="flex justify-between border-b border-[#eab308]/10 mb-8">
          {(['Now', 'Year', 'Why', 'Ask'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-3 text-xs font-bold uppercase tracking-[0.2em] transition-colors relative ${
                activeTab === tab ? 'text-[#eab308]' : 'text-[#f8fafc]/40'
              }`}
            >
              {tab}
              {activeTab === tab && (
                <motion.div layoutId="cycleTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#eab308]" />
              )}
            </button>
          ))}
        </nav>

        {/* Decade Strip Header (Visible on all tabs) */}
        <section className="mb-8 p-4 rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm">
          <div className="space-y-2">
            {MOCK_DECADES.map((d) => (
              <div key={d.name} className={`flex justify-between items-center py-1 px-2 rounded-lg ${d.status === 'current' ? 'bg-[#eab308]/10 border border-[#eab308]/40 shadow-[0_0_15px_rgba(234,179,8,0.1)]' : 'opacity-40'}`}>
                <div className="flex gap-4 items-center">
                  <span className={`text-sm font-bold ${d.status === 'current' ? 'text-[#eab308]' : ''}`}>{d.name}</span>
                  <span className="text-[10px] uppercase tracking-tighter">{d.range}</span>
                </div>
                {d.status === 'current' && <span className="text-[8px] border border-[#eab308] text-[#eab308] px-1 rounded uppercase font-bold">Current</span>}
                {d.status !== 'current' && <span className="text-[8px] uppercase font-bold opacity-50">{d.status}</span>}
              </div>
            ))}
          </div>
        </section>

        {/* Dynamic Content */}
        <AnimatePresence mode="wait">
          {activeTab === 'Now' && (
            <motion.div
              key="now"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="p-6 rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4">
                  <ElementRingSmall position={MOCK_CURRENT.horizonPosition} />
                </div>
                <h2 className="text-3xl font-bold mb-1">{MOCK_CURRENT.month}</h2>
                <div className="flex items-center gap-3 mb-6">
                  <span className="text-xl text-[#eab308] font-bold">{MOCK_CURRENT.pillar}</span>
                  <div className="h-4 w-px bg-[#eab308]/30" />
                  <div className="flex items-center gap-1">
                    <span className="text-2xl font-bold">{MOCK_CURRENT.score}</span>
                    <span className="text-[10px] uppercase tracking-widest opacity-40">Luck Score</span>
                  </div>
                </div>

                <ul className="space-y-3 mb-8">
                  {MOCK_CURRENT.bullets.map((b, i) => (
                    <li key={i} className="flex gap-3 text-sm leading-relaxed text-[#f8fafc]/80">
                      <span className="text-[#eab308]">✦</span>
                      {b}
                    </li>
                  ))}
                </ul>

                <div className="pt-4 border-t border-[#eab308]/20 flex justify-between items-end">
                  <div className="italic text-xs text-[#f8fafc]/40 font-serif max-w-[70%]">
                    "{MOCK_CURRENT.citation.text}"
                  </div>
                  <div className="text-[10px] text-[#eab308] font-bold uppercase tracking-widest">
                    {MOCK_CURRENT.citation.source}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'Year' && (
            <motion.div
              key="year"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              <div className="space-y-3">
                {MOCK_YEARS.map((y) => (
                  <div key={y.year} className="flex flex-col">
                    <button
                      onClick={() => setExpandedYear(expandedYear === y.year ? null : y.year)}
                      className={`flex items-center justify-between p-4 rounded-xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.3)] transition-all ${expandedYear === y.year ? 'border-[#eab308] bg-[#eab308]/5' : ''}`}
                    >
                      <div className="flex flex-col items-start gap-1">
                        <span className="text-sm font-bold">{y.label}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-[#eab308] font-bold uppercase tracking-widest">{y.pillar}</span>
                          <div className="w-1 h-1 bg-[#eab308]/30 rounded-full" />
                          <span className="text-[10px] font-bold opacity-60">SCORE {y.score}</span>
                        </div>
                      </div>
                      <SparklineDots scores={y.scores} activeMonth={y.year === 2026 ? 4 : undefined} />
                    </button>
                    
                    <AnimatePresence>
                      {expandedYear === y.year && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden bg-[#eab308]/5 border-x border-b border-[#eab308]/40 rounded-b-xl -mt-2 mb-2"
                        >
                          <div className="p-4 pt-6 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <span className="text-[9px] uppercase tracking-widest text-[#eab308]">Peak Months</span>
                                <div className="text-xs font-bold mt-1 opacity-80">Aug, Oct, Nov</div>
                              </div>
                              <div>
                                <span className="text-[9px] uppercase tracking-widest text-[#dc2626]">Trough Months</span>
                                <div className="text-xs font-bold mt-1 opacity-80">Feb, May</div>
                              </div>
                            </div>
                            <div className="space-y-2">
                              {y.summary.map((s, i) => (
                                <p key={i} className="text-xs leading-relaxed opacity-70">• {s}</p>
                              ))}
                            </div>
                            <div className="pt-3 border-t border-[#eab308]/20 italic text-[10px] text-[#eab308]/60 text-right">
                              "{y.citation.text}" — {y.citation.source}
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {activeTab === 'Why' && (
            <motion.div
              key="why"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              {MOCK_WHY_CARDS.map((card, idx) => (
                <div key={idx} className="p-4 rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-8 h-8 rounded-full bg-[#eab308]/10 border border-[#eab308]/30 flex items-center justify-center">
                      <span className="text-[#eab308] text-sm">✦</span>
                    </div>
                    <h3 className="text-sm font-bold uppercase tracking-widest text-[#eab308]">{card.name}</h3>
                  </div>
                  <ul className="space-y-2 mb-4 pl-11">
                    {card.bullets.map((b, i) => (
                      <li key={i} className="text-xs leading-relaxed opacity-80 text-[#f8fafc]/90">
                        {b}
                      </li>
                    ))}
                  </ul>
                  <div className="border border-[#eab308]/20 rounded p-2 text-right">
                    <span className="text-[10px] uppercase tracking-tighter text-[#eab308] font-bold italic opacity-60">
                      {card.citation}
                    </span>
                  </div>
                </div>
              ))}
            </motion.div>
          )}

          {activeTab === 'Ask' && (
            <motion.div
              key="ask"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-6"
            >
              <div className="p-4 rounded-2xl border border-[#eab308]/15 bg-white/5 space-y-4 mb-8">
                <div className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-[#eab308] flex-shrink-0" />
                  <div className="text-xs leading-relaxed opacity-80 bg-[#0c0a14] p-3 rounded-lg border border-[#eab308]/10">
                    What about my career in 2027?
                  </div>
                </div>
                <div className="flex gap-3 justify-end">
                  <div className="text-xs leading-relaxed opacity-90 bg-[#eab308]/10 p-3 rounded-lg border border-[#eab308]/30 max-w-[80%]">
                    In 2027 (Ding Wei year), your Fire energy is tempered by the Earth-Moistening influence. This is a time for stabilization. Avoid pivots; instead, master your current domain.
                  </div>
                  <div className="w-6 h-6 rounded-full bg-[#eab308]/40 flex-shrink-0" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {["What about 2027?", "Best career window?", "When will money flow?", "Pivot or hold?"].map(chip => (
                  <button key={chip} className="p-3 text-left rounded-xl border border-[#eab308]/20 bg-[#1e1b4b]/20 hover:border-[#eab308] transition-all">
                    <div className="text-[10px] text-[#eab308] font-bold uppercase tracking-widest mb-1">Inquiry</div>
                    <div className="text-xs opacity-70">{chip}</div>
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Floating Input Bar (Always bottom-fixed) */}
      <footer className="fixed bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-[#0c0a14] via-[#0c0a14] to-transparent z-50">
        <div className="max-w-2xl mx-auto">
          <div className="relative">
            <input
              type="text"
              placeholder="Ask about your destiny..."
              className="w-full bg-[#1e1b4b]/40 border border-[#eab308]/30 rounded-full py-4 pl-6 pr-14 text-sm focus:outline-none focus:border-[#eab308] transition-all placeholder:text-[#f8fafc]/30 backdrop-blur-xl"
            />
            <button className="absolute right-4 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-[#eab308] text-[#0c0a14] flex items-center justify-center hover:scale-105 transition-transform shadow-[0_0_10px_rgba(234,179,8,0.3)]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default FortuneAgentCycleResult;
