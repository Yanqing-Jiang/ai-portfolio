import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  Sparkles,
  ShieldCheck,
  Zap,
  Star,
} from 'lucide-react';
import {
  FortuneAgentResultShell,
  type FortuneTab,
} from './FortuneAgentResultShell';
import {
  FortuneAgentAskTab,
  type AskTurn,
} from './FortuneAgentAskTab';

/**
 * FortuneAgentOccasionResult — 擇 Auspicious Date reading.
 *
 * Theme: Gold (#eab308) — the flagship accent, which also happens to be
 * the shared "classical anchor" color. The rest of the shell (tabs, back
 * button, glyph) comes from FortuneAgentResultShell via purpose="lucky-day".
 *
 * Tabs: Top Picks · Calendar · Why · Ask.
 * Mobile-first with safe-area aware layout.
 */

interface Mechanism {
  icon: React.ReactNode;
  name: string;
  bullets: string[];
  citation: {
    source: string;
    content: string;
  };
}

interface DatePick {
  id: string;
  day: number;
  dateStr: string;
  weekday: string;
  pillar: string;
  score: number;
  oneLineReason: string;
  mechanisms: Mechanism[];
}

interface FortuneAgentOccasionResultProps {
  onBack?: () => void;
  inputPayload?: {
    occasion: string;
    profile: { birthDate: string; birthTime: string | null; gender: string };
    windowStart: string;
    windowEnd: string;
  } | null;
}

// Mock Data matching the Backend Data Contract
const MOCK_TOP_PICKS: DatePick[] = [
  {
    id: '1',
    day: 12,
    dateStr: "May 12, 2026",
    weekday: "Tuesday",
    pillar: "甲子",
    score: 92,
    oneLineReason: "Wood nourishes your Fire; Earth anchors the contract.",
    mechanisms: [
      {
        icon: <Star className="w-4 h-4 text-[#eab308]" />,
        name: "Celestial Nobleman",
        bullets: [
          "Jia-Zi pairing attracts influential mentors",
          "Protective energy against hidden legal clauses",
          "Harmonizes with your Natal Year Pillar"
        ],
        citation: {
          source: "渊海子平 · 贵人",
          content: "甲戊庚牛羊，此是贵人方。| Jia, Wu, and Geng stems find their Nobleman in the Ox and Goat."
        }
      },
      {
        icon: <Zap className="w-4 h-4 text-[#eab308]" />,
        name: "Wood-Fire Synergy",
        bullets: [
          "Wood (Jia) fuels your Bing Fire Day Master",
          "Creates sustainable growth for the partnership",
          "Ideal for long-term equity agreements"
        ],
        citation: {
          source: "滴天髓 · 甲木",
          content: "甲木参天，脱胎要火。| Jia Wood reaches for the heavens; it needs Fire to transform."
        }
      }
    ]
  },
  {
    id: '2',
    day: 20,
    dateStr: "May 20, 2026",
    weekday: "Wednesday",
    pillar: "壬申",
    score: 88,
    oneLineReason: "Water-Metal flow smooths negotiation friction.",
    mechanisms: [
      {
        icon: <ShieldCheck className="w-4 h-4 text-[#eab308]" />,
        name: "Resource Star Activation",
        bullets: [
          "Ren Water provides wisdom in decision making",
          "Metal (Shen) provides the structure and logic",
          "Prevents emotional overspending"
        ],
        citation: {
          source: "子平真诠 · 合冲",
          content: "申子辰合水局，主智。| The Shen-Zi-Chen combination forms a Water frame, favoring wisdom."
        }
      }
    ]
  },
  {
    id: '3',
    day: 7,
    dateStr: "May 7, 2026",
    weekday: "Thursday",
    pillar: "己卯",
    score: 85,
    oneLineReason: "Earth-Wood balance; day master supported.",
    mechanisms: [
      {
        icon: <Sparkles className="w-4 h-4 text-[#eab308]" />,
        name: "Peach Blossom Vitality",
        bullets: [
          "Mao Wood adds charm to your presentation",
          "Ji Earth grounds the initial excitement",
          "Good for creative industry contracts"
        ],
        citation: {
          source: "渊海子平 · 桃花",
          content: "寅午戌见卯，为桃花。| Yin-Wu-Xu sees Mao as the Peach Blossom star."
        }
      }
    ]
  }
];

const HEATMAP_SCORES = [
  { day: 1, score: 55, pillar: "癸丑" }, { day: 2, score: 58, pillar: "甲寅" }, 
  { day: 3, score: 35, pillar: "乙卯", isClash: true }, { day: 4, score: 62, pillar: "丙辰" },
  { day: 5, score: 65, pillar: "丁巳" }, { day: 6, score: 68, pillar: "戊午" },
  { day: 7, score: 85, pillar: "己卯" }, { day: 8, score: 72, pillar: "庚申" },
  { day: 9, score: 75, pillar: "辛酉" }, { day: 10, score: 60, pillar: "壬戌" },
  { day: 11, score: 58, pillar: "癸亥" }, { day: 12, score: 92, pillar: "甲子" },
  { day: 13, score: 70, pillar: "乙丑" }, { day: 14, score: 65, pillar: "丙寅" },
  { day: 15, score: 60, pillar: "丁卯" }, { day: 16, score: 55, pillar: "戊辰" },
  { day: 17, score: 52, pillar: "己巳" }, { day: 18, score: 32, pillar: "庚午", isClash: true },
  { day: 19, score: 78, pillar: "辛未" }, { day: 20, score: 88, pillar: "壬申" },
  { day: 21, score: 70, pillar: "癸酉" }, { day: 22, score: 65, pillar: "甲戌" },
  { day: 23, score: 60, pillar: "乙亥" }, { day: 24, score: 55, pillar: "丙子" },
  { day: 25, score: 50, pillar: "丁丑" }, { day: 26, score: 45, pillar: "戊寅" },
  { day: 27, score: 25, pillar: "己卯", isClash: true }, { day: 28, score: 60, pillar: "庚辰" },
  { day: 29, score: 65, pillar: "辛巳" }, { day: 30, score: 70, pillar: "壬午" },
  { day: 31, score: 75, pillar: "癸未" }
];

const SUGGESTED_CHIPS = [
  "Any dates after May 20?",
  "Best time of day on May 12?",
  "What if weather is bad?",
  "Should we pick Tuesday vs Wednesday?"
];

// Helper for heatmap colors
const getHeatmapColor = (score: number, isClash?: boolean) => {
  if (isClash) return 'bg-[#dc2626]/40 border-[#dc2626]/60 text-white';
  if (score >= 90) return 'bg-[#eab308] text-[#0c0a14] font-bold';
  if (score >= 70) return 'bg-[#eab308]/60 text-[#0c0a14]';
  if (score >= 50) return 'bg-[#1e1b4b] text-white/70 border-[#eab308]/10';
  return 'bg-[#450a0a] text-white/40 border-red-900/20';
};

const TABS: FortuneTab[] = [
  { id: 'Top Picks', label: 'Picks' },
  { id: 'Calendar', label: 'Calendar' },
  { id: 'Why', label: 'Why' },
  { id: 'Ask', label: 'Ask' },
];

export const FortuneAgentOccasionResult: React.FC<FortuneAgentOccasionResultProps> = ({ onBack, inputPayload }) => {
  const _occasionLabel = inputPayload?.occasion
    ? inputPayload.occasion.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    : 'Business Signing';
  const _birthLabel = inputPayload?.profile?.birthDate || '1991-09-05';
  void _occasionLabel; void _birthLabel;
  const [activeTab, setActiveTab] = useState<string>('Top Picks');
  const [selectedDay, setSelectedDay] = useState<number | null>(12);
  const [activeWhyDate, setActiveWhyDate] = useState<number>(12);
  const [askInput, setAskInput] = useState('');
  const [askHistory, setAskHistory] = useState<AskTurn[]>([
    {
      id: 'a1',
      role: 'agent',
      content:
        "May 12 stands out as the premium window for your contract. The real question under the question: do you want the deal signed, or signed and lasting? If the latter, anchor to the hour Wu 午 (11–13h).",
    },
  ]);

  const selectedDayData = useMemo(() => 
    HEATMAP_SCORES.find(d => d.day === selectedDay), 
  [selectedDay]);

  const whyDateData = useMemo(() => 
    MOCK_TOP_PICKS.find(p => p.day === activeWhyDate) || MOCK_TOP_PICKS[0], 
  [activeWhyDate]);

  const handleSend = () => {
    if (!askInput.trim()) return;
    const msg = askInput.trim();
    setAskHistory((h) => [
      ...h,
      { id: String(Date.now()), role: 'user', content: msg },
    ]);
    setAskInput('');
    // Mock response — backend will replace
    setTimeout(() => {
      setAskHistory((h) => [
        ...h,
        {
          id: String(Date.now() + 1),
          role: 'agent',
          content:
            "After May 20 the Shen–Zi cycle enters a clash phase for your Day Master. The mid-month window (12–20) is the cleanest. One thing to do this week: get the notary pre-booked for May 12 morning.",
        },
      ]);
    }, 900);
  };

  return (
    <FortuneAgentResultShell
      purpose="lucky-day"
      eyebrow="Occasion"
      subtitle="擇日 · Auspicious Date"
      tabs={TABS}
      activeTabId={activeTab}
      onTabChange={setActiveTab}
      onBack={onBack}
    >
      <AnimatePresence mode="wait">
          
          {/* TOP PICKS TAB */}
          {activeTab === 'Top Picks' && (
            <motion.div
              key="picks"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="w-6 h-px bg-[#eab308]/30"></span>
                <p className="text-[10px] uppercase tracking-[0.2em] text-[#eab308]">Recommended Windows</p>
              </div>

              {MOCK_TOP_PICKS.map((pick, idx) => (
                <motion.div
                  key={pick.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className="rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm p-5 relative overflow-hidden group"
                >
                  {/* Score Ring Background Arc */}
                  <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/2 w-32 h-32 rounded-full border-[12px] border-[#eab308]/5 pointer-events-none group-hover:border-[#eab308]/10 transition-colors" />
                  
                  <div className="flex justify-between items-start mb-4 relative z-10">
                    <div className="flex gap-4">
                      <div className="text-4xl font-serif text-[#eab308] leading-none">{pick.day}</div>
                      <div>
                        <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">{pick.weekday}</div>
                        <div className="text-lg font-serif font-bold text-white/90 leading-none tracking-wide">{pick.pillar} 日</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-[#eab308] leading-none">{pick.score}</div>
                      <div className="text-[8px] uppercase tracking-widest text-white/30 mt-1">Match</div>
                    </div>
                  </div>
                  
                  <div className="pl-4 border-l-2 border-[#eab308]/20 py-1">
                    <p className="text-sm text-white/80 leading-relaxed italic">
                      {pick.oneLineReason}
                    </p>
                  </div>
                  
                  <div className="mt-4 flex justify-between items-center">
                    <div className="flex gap-1.5">
                      {['Wood', 'Fire', 'Earth'].map(el => (
                        <span key={el} className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[8px] uppercase tracking-tighter text-white/40">
                          {el}
                        </span>
                      ))}
                    </div>
                    <button 
                      onClick={() => { setActiveWhyDate(pick.day); setActiveTab('Why'); }}
                      className="text-[10px] font-bold uppercase tracking-widest text-[#eab308] flex items-center gap-1 group-hover:gap-2 transition-all"
                    >
                      Why this date <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}

          {/* CALENDAR TAB */}
          {activeTab === 'Calendar' && (
            <motion.div
              key="calendar"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm p-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-lg font-serif text-[#eab308]">May 2026</h2>
                  <div className="flex gap-3 text-[8px] uppercase tracking-widest text-white/40">
                    <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-sm bg-[#eab308]"></div> High</span>
                    <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-sm bg-[#1e1b4b]"></div> Mid</span>
                    <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-sm bg-[#dc2626]/40"></div> Clash</span>
                  </div>
                </div>

                <div className="grid grid-cols-7 gap-2 sm:gap-3">
                  {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map(d => (
                    <div key={d} className="text-center text-[10px] font-bold text-white/20 pb-2">{d}</div>
                  ))}
                  {/* May 1 2026 is Friday -> 5 empty cells */}
                  {[...Array(5)].map((_, i) => <div key={`empty-${i}`} />)}
                  
                  {HEATMAP_SCORES.map((d) => (
                    <motion.button
                      key={d.day}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setSelectedDay(d.day)}
                      className={`aspect-square rounded-lg flex flex-col items-center justify-center relative transition-all border ${
                        selectedDay === d.day ? 'ring-2 ring-[#eab308] ring-offset-2 ring-offset-[#0c0a14]' : 'border-transparent'
                      } ${getHeatmapColor(d.score, d.isClash)}`}
                    >
                      <span className="text-xs font-bold">{d.day}</span>
                      {MOCK_TOP_PICKS.some(p => p.day === d.day) && (
                        <div className="absolute top-1 right-1 w-1 h-1 bg-[#0c0a14] rounded-full" />
                      )}
                    </motion.button>
                  ))}
                </div>
              </div>

              {selectedDayData && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm p-5"
                >
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-lg font-serif text-[#eab308]">May {selectedDay}</h3>
                      <p className="text-[10px] uppercase tracking-widest text-white/40">{selectedDayData.pillar} Day Window</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-[#eab308] leading-none">{selectedDayData.score}</div>
                      <p className="text-[8px] uppercase tracking-widest text-white/30">Auspiciousness</p>
                    </div>
                  </div>
                  
                  <div className="space-y-3">
                    <div className="flex gap-3 items-start">
                      <div className="mt-1 w-1.5 h-1.5 rounded-full bg-[#eab308]" />
                      <p className="text-xs text-white/70 leading-relaxed">
                        {selectedDayData.isClash 
                          ? "Heavy clash with your birth branch. Avoid signing contracts or high-value commitments today."
                          : "Neutral to positive alignment. Captured Qi is stable enough for routine negotiations."}
                      </p>
                    </div>
                    <div className="p-3 bg-white/5 border border-white/10 rounded-lg">
                      <p className="text-[9px] uppercase tracking-widest text-white/40 mb-1">Classical Indicator</p>
                      <p className="text-xs font-serif italic text-white/60 leading-relaxed">
                        {selectedDayData.score >= 80 ? "◈ Di Tian Sui: 'Success' Officer presiding. Wealth flows toward the steady." : "◈ General Calendar: Observe silence and internal planning today."}
                      </p>
                    </div>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* WHY TAB (REDESIGNED) */}
          {activeTab === 'Why' && (
            <motion.div
              key="why"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              {/* Accordion Context Switcher */}
              <div className="flex gap-2 overflow-x-auto no-scrollbar pb-2">
                {MOCK_TOP_PICKS.map(p => (
                  <button
                    key={p.id}
                    onClick={() => setActiveWhyDate(p.day)}
                    className={`px-4 py-2 rounded-full border text-[10px] font-bold uppercase tracking-widest whitespace-nowrap transition-all ${
                      activeWhyDate === p.day 
                        ? 'bg-[#eab308] border-[#eab308] text-[#0c0a14]' 
                        : 'bg-[#1e1b4b]/40 border-[#eab308]/20 text-white/40'
                    }`}
                  >
                    May {p.day} · {p.pillar}
                  </button>
                ))}
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-3 py-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#eab308]" />
                  <h2 className="text-lg font-serif text-[#eab308]">Mechanism Analysis: May {activeWhyDate}</h2>
                </div>

                {whyDateData.mechanisms.map((mech, i) => (
                  <motion.div
                    key={mech.name}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm p-5"
                  >
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 rounded-lg bg-[#eab308]/10 border border-[#eab308]/20">
                        {mech.icon}
                      </div>
                      <h3 className="font-serif font-bold text-white/90">{mech.name}</h3>
                    </div>
                    
                    <ul className="space-y-3 mb-5">
                      {mech.bullets.map((bullet, bi) => (
                        <li key={bi} className="flex gap-3 text-xs text-white/70 leading-relaxed">
                          <span className="text-[#eab308] mt-0.5">◈</span>
                          {bullet}
                        </li>
                      ))}
                    </ul>

                    <div className="relative pt-4 border-t border-white/5">
                      <div className="absolute -top-2 left-4 px-2 bg-[#0c0a14] text-[8px] uppercase tracking-[0.2em] text-[#eab308]/60">
                        {mech.citation.source}
                      </div>
                      <p className="text-xs font-serif italic text-white/50 leading-loose">
                        {mech.citation.content}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {/* ASK TAB — shared Sacred Scroll component */}
          {activeTab === 'Ask' && (
            <motion.div
              key="ask"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
            >
              <FortuneAgentAskTab
                purpose="lucky-day"
                history={askHistory}
                suggestedChips={SUGGESTED_CHIPS}
                input={askInput}
                onInputChange={setAskInput}
                onSend={handleSend}
                heading="Ask the almanac"
                placeholder="Inquire about the date or the hour…"
              />
            </motion.div>
          )}

        </AnimatePresence>
    </FortuneAgentResultShell>
  );
};

export default FortuneAgentOccasionResult;
