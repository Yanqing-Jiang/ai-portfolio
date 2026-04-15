import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Flame,
  Zap,
  ChevronDown,
  Send,
  Sparkles,
  Layers,
  Heart
} from 'lucide-react';

/**
 * Function: FortuneAgentCompatibilityResult
 * Called from: FortuneAgent main dashboard
 * Invokes: Framer Motion for sophisticated transitions
 * Why: Provides an elegant, scholarly Bazi compatibility reading between two people.
 */

interface FortuneAgentCompatibilityResultProps {
  onBack?: () => void;
}

// --- Mock Data ---
const PARTNER_A = {
  name: 'You',
  birth: '1991-09-05 07:20',
  dayMaster: '丙 Bing Fire',
  dominant: 'Fire',
  weakest: 'Water',
  elements: { Wood: 15, Fire: 45, Earth: 20, Metal: 10, Water: 10 },
  pillars: [
    { label: 'Year', stem: 'Xin 辛', branch: 'Wei 未', note: 'Metal-Earth' },
    { label: 'Month', stem: 'Bing 丙', branch: 'Shen 申', note: 'Fire-Metal' },
    { label: 'Day', stem: '丙 Bing', branch: 'Wu 午', note: 'Fire-Fire' },
    { label: 'Hour', stem: 'Ren 壬', branch: 'Chen 辰', note: 'Water-Earth' },
  ]
};

const PARTNER_B = {
  name: 'Her',
  birth: '1993-06-12 14:30',
  dayMaster: '己 Ji Earth',
  dominant: 'Earth',
  weakest: 'Wood',
  elements: { Wood: 10, Fire: 20, Earth: 50, Metal: 15, Water: 5 },
  pillars: [
    { label: 'Year', stem: 'Gui 癸', branch: 'You 酉', note: 'Water-Metal' },
    { label: 'Month', stem: 'Wu 戊', branch: 'Wu 午', note: 'Earth-Fire' },
    { label: 'Day', stem: '己 Ji', branch: 'Mao 卯', note: 'Earth-Wood' },
    { label: 'Hour', stem: 'Xin 辛', branch: 'Wei 未', note: 'Metal-Earth' },
  ]
};

const DYNAMICS = [
  { label: 'Supportive', text: 'Earth tames your Fire', type: 'positive', chinese: '支持' },
  { label: 'Warming', text: 'Your Fire warms her Earth', type: 'positive', chinese: '温暖' },
  { label: 'Friction', text: 'Hour Pillar friction', type: 'negative', chinese: '摩擦' },
];

const MECHANISMS = [
  {
    icon: <Flame className="w-4 h-4 text-[#eab308]" />,
    title: "Bing 丙 Fire warmed by Ji 己 Earth",
    points: [
      "Your intense Fire is safely absorbed by her soft Earth.",
      "Creates a cycle of production rather than exhaustion.",
      "Ensures mutual emotional stability during high stress."
    ],
    citation: {
      source: "滴天髓 · 丙火",
      text: "丙火猛烈, 欺霜侮雪. 能煅庚金, 逢辛反怯. 土众成慈, 水猖显节.",
      translation: "Bing fire is fierce... with abundant Earth it becomes compassionate; with rampant Water it shows integrity."
    }
  },
  {
    icon: <Sparkles className="w-4 h-4 text-[#eab308]" />,
    title: "Year Pillar Harmonize (Wood-Earth)",
    points: [
      "Foundational values align through elemental balance.",
      "Family backgrounds provide a stable root for growth.",
      "Shared long-term vision for security and heritage."
    ],
    citation: {
      source: "渊海子平 · 月令",
      text: "木能生火, 火多木焚; 強金得水, 方挫其鋒.",
      translation: "Wood can produce Fire, but too much Fire burns the Wood. Strong Metal needs Water to blunt its edge."
    }
  },
  {
    icon: <Heart className="w-4 h-4 text-[#eab308]" />,
    title: "Day Master Support",
    points: [
      "Natural affinity between your Day Stems.",
      "Intrinsic understanding of each other's core needs.",
      "Supportive dynamic in daily decision-making."
    ],
    citation: {
      source: "滴天髓 · 天干论",
      text: "五陽皆陽丙為最, 五陰皆陰癸為至.",
      translation: "Of the five Yang, Bing Fire is the most Yang; of the five Yin, Gui Water is the most Yin."
    }
  },
  {
    icon: <Zap className="w-4 h-4 text-[#dc2626]" />,
    title: "Hour Pillar Clash (Hai 亥 vs Si 巳)",
    points: [
      "Minor friction regarding late-night habits or future goals.",
      "Tension arises when discussing 10-year retirement plans.",
      "Requires conscious compromise on non-urgent matters."
    ],
    citation: {
      source: "子平真诠 · 冲合",
      text: "刑冲會合, 為命理之關鍵.",
      translation: "Punishment, Clash, Union, and Combination are the keys to destiny."
    }
  },
  {
    icon: <Layers className="w-4 h-4 text-[#eab308]" />,
    title: "10-god dynamic: Wealth meets Resource",
    points: [
      "Your drive for results (Wealth) is guided by her wisdom (Resource).",
      "She provides the strategy, you provide the execution.",
      "A powerful partnership for wealth accumulation."
    ],
    citation: {
      source: "命理约言",
      text: "財官印綬, 各有所宜.",
      translation: "Wealth, Officer, and Resource: each has its proper place."
    }
  }
];

const SUGGESTED_CHIPS = [
  "What about moving in together?",
  "How to handle his Fire temper?",
  "Best month to propose?",
  "Does 2027 help or hurt us?"
];

// --- Sub-components ---

const ScoreRing = ({ score }: { score: number }) => (
  <div className="relative w-20 h-20 flex items-center justify-center mx-auto mb-2">
    <svg className="w-full h-full transform -rotate-90">
      <circle cx="40" cy="40" r="36" stroke="rgba(234, 179, 8, 0.1)" strokeWidth="4" fill="transparent" />
      <motion.circle
        cx="40" cy="40" r="36" stroke="#eab308" strokeWidth="4" fill="transparent"
        strokeDasharray="226.2"
        initial={{ strokeDashoffset: 226.2 }}
        animate={{ strokeDashoffset: 226.2 - (score / 100) * 226.2 }}
        transition={{ duration: 1.5, ease: "easeOut" }}
      />
    </svg>
    <div className="absolute inset-0 flex flex-col items-center justify-center">
      <span className="text-xl font-bold text-[#f8fafc]">{score}</span>
    </div>
  </div>
);

const TabButton = ({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) => (
  <button
    onClick={onClick}
    className={`flex-1 py-4 text-[10px] font-bold uppercase tracking-[0.2em] transition-all relative ${
      active ? 'text-[#eab308]' : 'text-white/40'
    }`}
  >
    {label}
    {active && <motion.div layoutId="tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#eab308]" />}
  </button>
);

const MechanismCard = ({ item, isOpen, onToggle }: { item: typeof MECHANISMS[0]; isOpen: boolean; onToggle: () => void }) => (
  <div className="rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm overflow-hidden mb-3">
    <button onClick={onToggle} className="w-full p-4 flex items-center justify-between text-left">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-[#eab308]/10 flex items-center justify-center border border-[#eab308]/20">
          {item.icon}
        </div>
        <span className="text-sm font-serif font-bold text-[#f8fafc]">{item.title}</span>
      </div>
      <ChevronDown className={`w-4 h-4 text-[#eab308]/50 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
    </button>
    <AnimatePresence>
      {isOpen && (
        <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
          <div className="px-4 pb-4 space-y-3">
            <ul className="space-y-2">
              {item.points.map((p, i) => (
                <li key={i} className="flex gap-2 text-xs text-[#f8fafc]/70 leading-relaxed">
                  <span className="text-[#eab308]">·</span> {p}
                </li>
              ))}
            </ul>
            <div className="pt-3 mt-3 border-t border-[#eab308]/10">
              <div className="p-3 rounded-lg border border-[#eab308]/20 bg-[#eab308]/5">
                <p className="text-[10px] text-[#eab308] font-bold uppercase tracking-widest mb-1">{item.citation.source}</p>
                <p className="text-sm font-serif text-[#f8fafc] leading-relaxed mb-1">{item.citation.text}</p>
                <p className="text-[10px] text-[#f8fafc]/40 italic">{item.citation.translation}</p>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  </div>
);

export const FortuneAgentCompatibilityResult: React.FC<FortuneAgentCompatibilityResultProps> = ({ onBack }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'pillars' | 'why' | 'ask'>('overview');
  const [openMechanism, setOpenMechanism] = useState<number | null>(0);
  const [expandedPillar, setExpandedPillar] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const [history, setHistory] = useState([
    { role: 'assistant', content: "How do you work together?" },
    { role: 'user', content: "Will our elements cause conflict in 2027?" },
    { role: 'assistant', content: "In 2027 (Ding Wei year), your Bing Fire receives a subtle boost, while her Earth core provides a grounding field. The interaction is harmonious, though mindful communication in the summer months is advised." }
  ]);

  const handleSend = () => {
    if (!message.trim()) return;
    const newHistory = [...history, { role: 'user', content: message }];
    setHistory(newHistory);
    setMessage('');
    console.log('User query:', message);
    // Mock reply
    setTimeout(() => {
      setHistory(prev => [...prev, { role: 'assistant', content: "That is a fascinating question. Based on your Day Masters, I see a clear path for growth in that area..." }]);
    }, 1000);
  };

  return (
    <div
      className="min-h-screen text-[#f8fafc] font-sans selection:bg-[#eab308]/30"
      style={{
        background:
          'linear-gradient(180deg, #1a0a10 0%, #3a0f14 55%, #0c0a14 100%)',
      }}
    >
      {/* Universal Fixed Top Bar */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#0c0a14]/90 backdrop-blur-xl border-b border-[#eab308]/10">
        <div className="max-w-2xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full border border-[#eab308] flex items-center justify-center text-[#eab308] font-serif text-lg">
              ☯
            </div>
            <div>
              <h1 className="text-xs font-bold tracking-[0.2em] uppercase text-[#eab308]">Fortune Agent</h1>
              <p className="text-[10px] text-[#f8fafc]/50">Compatibility Reading</p>
            </div>
          </div>
          {onBack && (
            <button 
              onClick={onBack}
              className="px-4 py-1.5 rounded-full border border-[#eab308]/30 text-[10px] font-bold uppercase tracking-widest text-[#eab308] hover:bg-[#eab308]/10 transition-colors"
            >
              Back
            </button>
          )}
        </div>
        <nav className="max-w-2xl mx-auto flex px-2">
          {['overview', 'pillars', 'why', 'ask'].map((tab) => (
            <TabButton 
              key={tab} 
              label={tab} 
              active={activeTab === tab} 
              onClick={() => setActiveTab(tab as any)} 
            />
          ))}
        </nav>
      </header>

      <main className="max-w-2xl mx-auto px-4 pt-32 pb-24">
        <AnimatePresence mode="wait">
          {activeTab === 'overview' && (
            <motion.div
              key="overview"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-8"
            >
              {/* Hero Score */}
              <section className="text-center">
                <ScoreRing score={78} />
                <h2 className="text-xl font-serif text-[#f8fafc] italic px-8 leading-relaxed">
                  "Her Earth tames your Fire, providing a soft harbor for your intensity."
                </h2>
              </section>

              {/* Dynamics */}
              <section className="flex flex-wrap justify-center gap-3">
                {DYNAMICS.map((d, i) => (
                  <div key={i} className={`px-3 py-2 rounded-full border text-[10px] font-bold uppercase tracking-widest flex items-center gap-2 ${
                    d.type === 'positive' ? 'bg-[#eab308]/5 border-[#eab308]/30 text-[#eab308]' : 'bg-[#dc2626]/5 border-[#dc2626]/30 text-[#dc2626]'
                  }`}>
                    <span className="opacity-50">{d.chinese}</span>
                    <span>{d.text}</span>
                  </div>
                ))}
              </section>

              {/* Elemental Balance */}
              <section className="space-y-4">
                <div className="flex justify-between items-end">
                  <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#eab308]">Elemental Dualism</h3>
                  <span className="text-[10px] text-white/30 uppercase">Fire vs Earth Dominance</span>
                </div>
                <div className="space-y-3">
                  {(['Wood', 'Fire', 'Earth', 'Metal', 'Water'] as const).map(el => (
                    <div key={el} className="relative h-4 w-full bg-[#1c192a] rounded-full overflow-hidden flex">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${PARTNER_A.elements[el]}%` }}
                        className="h-full bg-[#eab308]/40 border-r border-[#0c0a14]"
                      />
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${PARTNER_B.elements[el]}%` }}
                        className="h-full bg-[#f8fafc]/10"
                      />
                      <div className="absolute inset-0 flex items-center justify-between px-3">
                        <span className="text-[9px] font-bold uppercase text-white/50">{el}</span>
                        <div className="flex gap-2 text-[9px] font-mono">
                          <span className="text-[#eab308]">{PARTNER_A.elements[el]}%</span>
                          <span className="text-white/20">/</span>
                          <span className="text-white/40">{PARTNER_B.elements[el]}%</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </motion.div>
          )}

          {activeTab === 'pillars' && (
            <motion.div
              key="pillars"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="text-center text-[10px] uppercase tracking-widest text-[#eab308]/50">Partner A (You)</div>
                <div className="text-center text-[10px] uppercase tracking-widest text-[#eab308]/50">Partner B (Her)</div>
              </div>

              {PARTNER_A.pillars.map((p, i) => (
                <div key={i} className="space-y-2">
                  <div 
                    onClick={() => setExpandedPillar(expandedPillar === i ? null : i)}
                    className="flex items-center gap-4 cursor-pointer group"
                  >
                    {/* Person A Pillar */}
                    <div className="flex-1 rounded-xl border border-[#eab308]/20 bg-[#1e1b4b]/20 p-3 flex flex-col items-center group-hover:border-[#eab308]/40 transition-colors">
                      <span className="text-[9px] uppercase tracking-tighter text-white/30 mb-1">{p.label}</span>
                      <span className="text-lg font-serif text-[#f8fafc]">{p.stem}</span>
                      <span className="text-lg font-serif text-[#f8fafc]">{p.branch}</span>
                    </div>

                    {/* Interaction Dot */}
                    <div className="flex flex-col items-center">
                      <div className={`w-2 h-2 rounded-full ${i === 3 ? 'bg-[#dc2626]' : 'bg-[#eab308]'} shadow-[0_0_8px_rgba(234,179,8,0.5)]`} />
                      <div className="w-px h-full bg-[#eab308]/10 min-h-[10px]" />
                    </div>

                    {/* Person B Pillar */}
                    <div className="flex-1 rounded-xl border border-[#eab308]/20 bg-[#1e1b4b]/20 p-3 flex flex-col items-center group-hover:border-[#eab308]/40 transition-colors">
                      <span className="text-[9px] uppercase tracking-tighter text-white/30 mb-1">{PARTNER_B.pillars[i].label}</span>
                      <span className="text-lg font-serif text-[#f8fafc]">{PARTNER_B.pillars[i].stem}</span>
                      <span className="text-lg font-serif text-[#f8fafc]">{PARTNER_B.pillars[i].branch}</span>
                    </div>
                  </div>
                  
                  <AnimatePresence>
                    {expandedPillar === i && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                        <div className="p-3 rounded-lg border border-[#eab308]/10 bg-[#eab308]/5 text-[11px] text-[#f8fafc]/70 leading-relaxed italic text-center">
                          "{p.label} Interaction: {i === 3 ? 'The Branch clash creates a dynamic of constant movement and late-stage refinement.' : 'The Stems harmonize, creating a baseline of natural agreement and shared aesthetic values.'}"
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ))}
            </motion.div>
          )}

          {activeTab === 'why' && (
            <motion.div
              key="why"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-2"
            >
              {MECHANISMS.map((item, i) => (
                <MechanismCard 
                  key={i} 
                  item={item} 
                  isOpen={openMechanism === i} 
                  onToggle={() => setOpenMechanism(openMechanism === i ? null : i)} 
                />
              ))}
            </motion.div>
          )}

          {activeTab === 'ask' && (
            <motion.div
              key="ask"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col h-full min-h-[50vh]"
            >
              <div className="flex-1 space-y-6">
                {history.map((chat, i) => (
                  <div key={i} className={`flex ${chat.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                      chat.role === 'user' 
                        ? 'bg-[#eab308] text-[#0c0a14] font-bold rounded-tr-none' 
                        : 'border border-[#eab308]/20 bg-[#1e1b4b]/30 text-[#f8fafc]/90 rounded-tl-none italic'
                    }`}>
                      {chat.role === 'assistant' && <div className="text-[10px] uppercase font-bold text-[#eab308]/50 mb-1">Fortune Sage</div>}
                      {chat.content}
                    </div>
                  </div>
                ))}
              </div>

              {/* Chat Input Inside Ask Tab Only */}
              <div className="mt-8 space-y-4">
                <div className="flex gap-2 overflow-x-auto no-scrollbar py-1">
                  {SUGGESTED_CHIPS.map(chip => (
                    <button
                      key={chip}
                      onClick={() => { setMessage(chip); handleSend(); }}
                      className="whitespace-nowrap px-4 py-2 rounded-full border border-[#eab308]/20 bg-[#1e1b4b]/40 text-[10px] text-[#f8fafc]/70 hover:border-[#eab308]/60 transition-colors"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
                <div className="relative">
                  <input
                    type="text"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Ask a follow-up..."
                    className="w-full bg-[#1e1b4b]/60 border border-[#eab308]/30 rounded-full py-4 pl-6 pr-12 text-sm focus:outline-none focus:border-[#eab308] transition-all placeholder:text-[#f8fafc]/30"
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
                  />
                  <button onClick={handleSend} className="absolute right-4 top-1/2 -translate-y-1/2 text-[#eab308]">
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Persistent Decorative Bottom Glyph */}
      <footer className="fixed bottom-6 left-0 right-0 pointer-events-none flex justify-center opacity-10">
        <div className="text-[60px] font-serif text-[#eab308]">合</div>
      </footer>
    </div>
  );
};

export default FortuneAgentCompatibilityResult;
