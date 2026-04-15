import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Sparkles,
  Zap,
  Star,
  ShieldCheck,
  ArrowUpRight,
  Info
} from 'lucide-react';

/**
 * FortuneAgentCustomWishResult
 * 
 * Redesigned result page for custom "wish" inquiries.
 * Universal shell: max-w-2xl, gold/indigo theme, "Noto Serif SC".
 * Tabs: Verdict, Anchor, Why, Ask.
 */

interface Condition {
  id: string;
  type: 'check' | 'warn' | 'cross';
  text: string;
}

interface AnchorPillar {
  id: string;
  label: string;
  symbol: string;
  relevance: number;
  bullets: string[];
}

interface Mechanism {
  id: string;
  name: string;
  bullets: string[];
  citation: {
    source: string;
    content: string;
  };
  icon: React.ReactNode;
}

interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
}

interface FortuneAgentCustomWishResultProps {
  onBack?: () => void;
  initialQuestion?: string;
}

// Mock Data
const MOCK_CONDITIONS: Condition[] = [
  { id: 'c1', type: 'check', text: 'Earth-Metal flow supports career pivot' },
  { id: 'c2', type: 'warn', text: 'First 90 days friction with Hour Pillar' },
  { id: 'c3', type: 'cross', text: "Don't sign if start date is in July (Fire-Fire clash)" }
];

const MOCK_ANCHORS: AnchorPillar[] = [
  {
    id: 'p1',
    label: 'Day Master',
    symbol: '丙 Fire',
    relevance: 95,
    bullets: [
      "Your fire nature seeks challenge",
      "Shanghai's pace matches your rhythm",
      "Dynamic environment feeds your Qi"
    ]
  },
  {
    id: 'p2',
    label: 'Wealth Star',
    symbol: 'Earth',
    relevance: 72,
    bullets: [
      "Stable financial growth expected",
      "Requires consistent daily output",
      "Secondary gains from Q4 onwards"
    ]
  },
  {
    id: 'p3',
    label: 'Fame Star',
    symbol: 'Wood',
    relevance: 68,
    bullets: [
      "Industry reputation will expand",
      "Mentors appear in early 2027",
      "Visibility increases significantly"
    ]
  },
  {
    id: 'p4',
    label: 'Hour Pillar',
    symbol: '癸巳',
    relevance: 45,
    bullets: [
      "Water-Fire friction at daily cycles",
      "Late-night decision fatigue likely",
      "Physical stress needs management"
    ]
  }
];

const MOCK_MECHANISMS: Mechanism[] = [
  {
    id: 'm1',
    name: "Fire nature matches city of ambition",
    icon: <Zap className="w-4 h-4 text-[#eab308]" />,
    bullets: [
      "Bing Fire thrives in active hubs",
      "The Wood-Fire axis is dominant",
      "Success through visible action"
    ],
    citation: {
      source: "滴天髓 · 丙火",
      content: "丙火猛烈，欺霜侮雪。能煅庚金，逢辛反怯。| Bing fire is fierce; it defies frost and insults snow. It can forge Geng metal, but fears Xin metal."
    }
  },
  {
    id: 'm2',
    name: "Earth-Metal flow supports pivot",
    icon: <ShieldCheck className="w-4 h-4 text-[#eab308]" />,
    bullets: [
      "Smooth transition between roles",
      "Wealth creation through logic",
      "Structural stability in contracts"
    ],
    citation: {
      source: "渊海子平 · 财星",
      content: "何知其人富，财气通门户。| How do we know a person is wealthy? When the wealth energy flows through the gates."
    }
  },
  {
    id: 'm3',
    name: "Fame Star active in 2026",
    icon: <Star className="w-4 h-4 text-[#eab308]" />,
    bullets: [
      "2026 Fire Horse fuels recognition",
      "Year Pillar resonance is high",
      "Social capital yields dividends"
    ],
    citation: {
      source: "子平真诠 · 名利",
      content: "官以印为资，官星有气。| Authority relies on the Seal for support; when the Authority star has Qi, reputation flourishes."
    }
  },
  {
    id: 'm4',
    name: "Hour Pillar friction: late-night stress",
    icon: <AlertTriangle className="w-4 h-4 text-[#eab308]" />,
    bullets: [
      "Daily grind may tax the spirit",
      "Incompatibility with nocturnal work",
      "Need for grounding rituals"
    ],
    citation: {
      source: "命理约言 · 时柱",
      content: "凡时柱受冲，主晚景及日用。| When the Hour Pillar is clashed, it affects the later years and daily routines."
    }
  }
];

const MOCK_MESSAGES: Message[] = [
  { id: '1', role: 'user', content: "I feel stuck in my current role. Is a big move coming?", timestamp: "10:00 AM" },
  { id: '2', role: 'agent', content: "The heavens indicate a shifting of the wind. Your Year Pillar is vibrating with travel energy. Where are you looking?", timestamp: "10:01 AM" },
  { id: '3', role: 'user', content: "I have an offer from a startup in Shanghai.", timestamp: "10:02 AM" },
];

const SUGGESTED_CHIPS = [
  "What if I take the other offer?",
  "How about next quarter?",
  "Is my partner supportive?",
  "Any red flags I'm missing?"
];

export const FortuneAgentCustomWishResult: React.FC<FortuneAgentCustomWishResultProps> = ({ 
  onBack, 
  initialQuestion = "Should I take the new job in Shanghai?" 
}) => {
  const [activeTab, setActiveTab] = useState<'Verdict' | 'Anchor' | 'Why' | 'Ask'>('Verdict');
  const [expandedAnchor, setExpandedAnchor] = useState<string | null>(null);
  const [isReasoningOpen, setIsReasoningOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<Message[]>(MOCK_MESSAGES);

  const handleSend = () => {
    if (!chatInput.trim()) return;
    const newMsg: Message = { 
      id: Date.now().toString(), 
      role: 'user', 
      content: chatInput, 
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) 
    };
    setChatHistory([...chatHistory, newMsg]);
    setChatInput('');
    console.log('Console log - User asked:', chatInput);
    
    // Mock response
    setTimeout(() => {
      setChatHistory(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: "Analyzing the elemental flow... Shanghai matches your Bing Fire nature, but ensure your contract includes clear boundaries for late-night work to avoid the Hour Pillar friction.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    }, 1000);
  };

  return (
    <div
      className="min-h-screen text-[#f8fafc] font-sans selection:bg-[#eab308]/30 relative"
      style={{
        background:
          'linear-gradient(180deg, #0a0c14 0%, #161a2a 55%, #0c0a14 100%)',
      }}
    >
      
      {/* Fixed Top Shell */}
      <div className="fixed top-0 left-0 right-0 z-50 bg-[#0c0a14]/80 backdrop-blur-md border-b border-[#eab308]/10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#eab308]/10 border border-[#eab308]/30 flex items-center justify-center">
              <span className="text-[#eab308] text-lg font-serif">◈</span>
            </div>
            <div>
              <h1 className="text-sm font-serif font-bold tracking-wide text-[#eab308]">CUSTOM WISH</h1>
              <p className="text-[10px] uppercase tracking-[0.2em] text-white/50 truncate max-w-[150px]">{initialQuestion}</p>
            </div>
          </div>
          
          {onBack && (
            <button 
              onClick={onBack}
              className="px-3 py-1.5 rounded-full bg-[#1e1b4b]/60 border border-[#eab308]/20 flex items-center gap-2 hover:border-[#eab308]/50 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5 text-[#eab308]" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-[#eab308]">Back</span>
            </button>
          )}
        </div>

        {/* Universal Tab Bar */}
        <div className="max-w-2xl mx-auto px-4 flex">
          {['Verdict', 'Anchor', 'Why', 'Ask'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`flex-1 py-3 text-[10px] font-bold uppercase tracking-widest transition-all relative ${
                activeTab === tab ? 'text-[#eab308]' : 'text-white/40 hover:text-white/60'
              }`}
            >
              {tab}
              {activeTab === tab && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#eab308]"
                />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <main className="max-w-2xl mx-auto px-4 pt-24 pb-32 min-h-screen">
        <AnimatePresence mode="wait">
          
          {/* VERDICT TAB */}
          {activeTab === 'Verdict' && (
            <motion.div
              key="verdict"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              {/* Question Quote */}
              <div className="relative py-4 px-6 border-l-2 border-[#eab308]/20 bg-[#eab308]/5 rounded-r-2xl">
                <span className="absolute -left-1 -top-2 text-4xl text-[#eab308]/20 font-serif italic">“</span>
                <p className="text-lg font-serif italic text-white/90 leading-relaxed">
                  {initialQuestion}
                </p>
                <span className="absolute right-4 bottom-0 text-4xl text-[#eab308]/20 font-serif italic">”</span>
              </div>

              {/* Hero Verdict Card */}
              <div className="rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm p-6 relative overflow-hidden">
                <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/2 w-48 h-48 rounded-full border-[16px] border-[#eab308]/5 pointer-events-none" />
                
                <div className="relative z-10 space-y-6">
                  <div>
                    <h2 className="text-[10px] uppercase tracking-[0.2em] text-[#eab308] font-bold mb-2">Final Verdict</h2>
                    <p className="text-2xl font-serif text-white font-bold leading-tight">
                      Yes, but wait until <span className="text-[#eab308]">Q3 2026</span> for the most harmonious transition.
                    </p>
                  </div>

                  <div className="space-y-3">
                    {MOCK_CONDITIONS.map(cond => (
                      <div key={cond.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10 group hover:bg-white/10 transition-colors">
                        {cond.type === 'check' && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                        {cond.type === 'warn' && <AlertTriangle className="w-5 h-5 text-amber-500" />}
                        {cond.type === 'cross' && <XCircle className="w-5 h-5 text-red-500" />}
                        <span className="text-sm text-white/80 leading-snug">{cond.text}</span>
                      </div>
                    ))}
                  </div>

                  <div className="pt-4 border-t border-white/10">
                    <p className="text-sm text-white/60 leading-relaxed italic">
                      The Metal-Water axis of Shanghai provides stable ground for your Bing Fire nature, provided you don't ignite too early in the summer heat.
                    </p>
                  </div>
                </div>
              </div>

              {/* Reasoning Trace */}
              <div className="rounded-2xl border border-[#eab308]/10 bg-white/5 overflow-hidden">
                <button 
                  onClick={() => setIsReasoningOpen(!isReasoningOpen)}
                  className="w-full p-4 flex justify-between items-center group"
                >
                  <div className="flex items-center gap-2">
                    <Info className="w-4 h-4 text-[#eab308]/60" />
                    <span className="text-[10px] uppercase tracking-widest text-white/40 group-hover:text-white/60 transition-colors">View Reasoning Trace</span>
                  </div>
                  <ChevronDown className={`w-4 h-4 text-[#eab308]/40 transition-transform ${isReasoningOpen ? 'rotate-180' : ''}`} />
                </button>
                <AnimatePresence>
                  {isReasoningOpen && (
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: 'auto' }}
                      exit={{ height: 0 }}
                      className="overflow-hidden border-t border-white/5 bg-[#0c0a14]/40"
                    >
                      <div className="p-6 space-y-4">
                        {[
                          { step: 1, label: 'Chart Extraction', desc: 'Syncing with user birth pillars...' },
                          { step: 2, label: 'Elemental Balance', desc: 'Detecting dominance of Wood/Fire axis.' },
                          { step: 3, label: 'Temporal Mapping', desc: 'Correlating with 2026 Fire Horse energy.' }
                        ].map(step => (
                          <div key={step.step} className="flex gap-4 items-start">
                            <div className="w-6 h-6 rounded-full bg-[#eab308]/10 border border-[#eab308]/20 flex items-center justify-center text-[10px] font-mono text-[#eab308]">
                              {step.step}
                            </div>
                            <div>
                              <h4 className="text-xs font-bold uppercase text-white/80 tracking-wide">{step.label}</h4>
                              <p className="text-xs text-white/40 mt-1">{step.desc}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          )}

          {/* ANCHOR TAB */}
          {activeTab === 'Anchor' && (
            <motion.div
              key="anchor"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="w-6 h-px bg-[#eab308]/30"></span>
                <p className="text-[10px] uppercase tracking-[0.2em] text-[#eab308]">Chart Anchor Pillars</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {MOCK_ANCHORS.map(anchor => (
                  <motion.div
                    key={anchor.id}
                    layout
                    onClick={() => setExpandedAnchor(expandedAnchor === anchor.id ? null : anchor.id)}
                    className={`rounded-2xl border cursor-pointer transition-all p-4 ${
                      expandedAnchor === anchor.id 
                        ? 'bg-[#eab308]/10 border-[#eab308]/60 shadow-[0_0_20px_rgba(234,179,8,0.1)]' 
                        : 'bg-[rgba(12,10,20,0.55)] border-[#eab308]/25 hover:border-[#eab308]/50'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="text-[10px] uppercase tracking-widest text-[#eab308] font-bold">{anchor.label}</h3>
                        <p className="text-lg font-serif font-bold text-white/90">{anchor.symbol}</p>
                      </div>
                      <div className="px-2 py-0.5 rounded-full bg-[#eab308]/20 border border-[#eab308]/30 text-[9px] font-bold text-[#eab308]">
                        {anchor.relevance}%
                      </div>
                    </div>

                    <AnimatePresence>
                      {expandedAnchor === anchor.id && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="pt-4 border-t border-[#eab308]/20 space-y-2"
                        >
                          {anchor.bullets.map((b, i) => (
                            <div key={i} className="flex gap-2 text-xs text-white/70 leading-relaxed">
                              <span className="text-[#eab308] mt-1">◈</span>
                              {b}
                            </div>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </div>
              <p className="text-[10px] text-center text-white/30 italic px-8">
                Tap each pillar to reveal how it anchors your specific destiny flow.
              </p>
            </motion.div>
          )}

          {/* WHY TAB */}
          {activeTab === 'Why' && (
            <motion.div
              key="why"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="w-6 h-px bg-[#eab308]/30"></span>
                <p className="text-[10px] uppercase tracking-[0.2em] text-[#eab308]">Classical Mechanisms</p>
              </div>

              {MOCK_MECHANISMS.map((mech) => (
                <div key={mech.id} className="rounded-2xl border border-[#eab308]/25 bg-[rgba(12,10,20,0.55)] backdrop-blur-sm overflow-hidden">
                  <div className="p-5 space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-[#eab308]/10 border border-[#eab308]/20">
                        {mech.icon}
                      </div>
                      <h3 className="font-serif font-bold text-white/90">{mech.name}</h3>
                    </div>
                    
                    <ul className="space-y-3">
                      {mech.bullets.map((bullet, bi) => (
                        <li key={bi} className="flex gap-3 text-xs text-white/70 leading-relaxed">
                          <span className="text-[#eab308] mt-0.5">◈</span>
                          {bullet}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Vertical-RL Citation Footer */}
                  <div className="bg-[#eab308]/5 border-t border-[#eab308]/20 p-5 flex gap-6">
                    <div className="writing-vertical-rl text-xl font-serif text-[#eab308]/80 leading-none whitespace-pre-line border-r border-[#eab308]/10 pr-4 h-32">
                      {mech.citation.content.split('|')[0]}
                    </div>
                    <div className="flex-1 space-y-2 self-center">
                      <p className="text-[9px] uppercase tracking-widest text-[#eab308] font-bold">Source: {mech.citation.source}</p>
                      <p className="text-xs font-serif italic text-white/40 leading-relaxed">
                        {mech.citation.content.split('|')[1] || ""}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </motion.div>
          )}

          {/* ASK TAB */}
          {activeTab === 'Ask' && (
            <motion.div
              key="ask"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-6 flex flex-col min-h-[65vh]"
            >
              <div className="flex-1 space-y-6 overflow-y-auto no-scrollbar pb-4">
                {chatHistory.map((msg) => (
                  <div 
                    key={msg.id}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <div className="text-[9px] uppercase tracking-widest text-white/30 mb-1 px-2">
                      {msg.role} • {msg.timestamp}
                    </div>
                    <div className={`max-w-[85%] p-4 rounded-2xl border ${
                      msg.role === 'user' 
                        ? 'bg-[#eab308]/10 border-[#eab308]/30 text-white rounded-tr-none' 
                        : 'bg-[rgba(12,10,20,0.55)] border-white/10 text-white/80 rounded-tl-none'
                    }`}>
                      <p className="text-sm leading-relaxed">{msg.content}</p>
                    </div>
                  </div>
                ))}

                {/* Current Answer Card Highlight */}
                <motion.div 
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="p-6 rounded-2xl bg-gradient-to-br from-[#eab308]/20 to-transparent border border-[#eab308] shadow-[0_0_40px_rgba(234,179,8,0.1)] relative"
                >
                  <div className="absolute top-0 right-4 px-2 py-0.5 bg-[#eab308] text-[#0c0a14] text-[9px] font-bold uppercase tracking-widest rounded-b-md">
                    Current Analysis
                  </div>
                  <h4 className="font-serif text-[#eab308] mb-3 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" /> Comprehensive Synthesis
                  </h4>
                  <p className="text-sm font-serif text-white/90 leading-relaxed">
                    Based on the resonance between your birth pillars and the 2026 Fire Horse energy, the move to Shanghai is auspicious but requires timing. Q3 offers the "Resource" star support you need for a stable pivot. Ensure you manage the "Hour Pillar" stress by setting firm daily boundaries.
                  </p>
                </motion.div>
              </div>

              {/* Chat Input ONLY in Ask Tab */}
              <div className="space-y-4 pt-4 border-t border-white/5">
                <div className="flex gap-2 overflow-x-auto no-scrollbar pb-2">
                  {SUGGESTED_CHIPS.map(chip => (
                    <button
                      key={chip}
                      onClick={() => setChatInput(chip)}
                      className="whitespace-nowrap px-4 py-2 rounded-full border border-[#eab308]/20 bg-[#1e1b4b]/40 text-[10px] text-white/70 hover:border-[#eab308]/60 hover:bg-[#1e1b4b]/60 transition-all"
                    >
                      {chip}
                    </button>
                  ))}
                </div>

                <div className="relative group">
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-[#eab308]/20 to-[#dc2626]/20 rounded-2xl blur opacity-30 group-hover:opacity-60 transition duration-1000"></div>
                  <div className="relative flex items-center bg-[#0c0a14] border border-[#eab308]/30 rounded-2xl overflow-hidden py-4 pl-6 pr-14 shadow-2xl">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                      placeholder="Seek deeper clarity..."
                      className="w-full bg-transparent border-none outline-none text-sm text-white placeholder:text-white/20"
                    />
                    <button 
                      onClick={handleSend}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-xl bg-[#eab308] text-[#0c0a14] flex items-center justify-center hover:scale-105 transition-transform"
                    >
                      <ArrowUpRight className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </main>

      {/* Global Bottom Glyph */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 pointer-events-none opacity-20 hidden md:block">
        <div className="w-12 h-12 border border-[#eab308]/40 rotate-45 flex items-center justify-center">
          <div className="w-6 h-6 border border-[#eab308]/20" />
        </div>
      </div>

      <style>{`
        .writing-vertical-rl {
          writing-mode: vertical-rl;
          text-orientation: mixed;
        }
        .no-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .no-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </div>
  );
};

export default FortuneAgentCustomWishResult;
