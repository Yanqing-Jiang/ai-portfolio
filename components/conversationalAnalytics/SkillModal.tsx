/**
 * Function: SkillModal — Displays skill.md information in an elegant popup
 * Called from: ThinkingProcessBar when "View details" is clicked
 * Invokes: API to fetch skill content
 * Purpose: Educates users about what SKILL.md files are and shows the active skill details
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { SkillInfo } from './hooks/useSSEStream';
import { theme, motionVariants } from './styles';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { configService } from '../../services/config';

interface SkillModalProps {
  skill: SkillInfo;
  isOpen: boolean;
  onClose: () => void;
  initialTab?: 'current' | 'what';
}

const SkillModal: React.FC<SkillModalProps> = ({ skill, isOpen, onClose, initialTab = 'current' }) => {
  const [skillContent, setSkillContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'what' | 'current'>(initialTab);

  // Function: parseSkillContent — parses YAML frontmatter and reformats to "Skill: [Name]" format
  const parseSkillContent = (rawContent: string, skillName: string): string => {
    // Remove YAML frontmatter if present (between --- markers)
    let content = rawContent;
    const yamlFrontmatterRegex = /^---[\s\S]*?---\s*/;
    content = content.replace(yamlFrontmatterRegex, '');

    // Trim any leading/trailing whitespace
    content = content.trim();

    // Format with Skill header
    return `## Skill: ${skillName}\n\n${content}`;
  };

  // Fetch skill content when modal opens
  useEffect(() => {
    if (isOpen && skill && !skillContent) {
      setIsLoading(true);
      const backendUrl = configService.getBackendUrl();
      fetch(`${backendUrl}/api/conv-analytics/skills/${skill.id}`)
        .then(res => res.text())
        .then(content => {
          setSkillContent(parseSkillContent(content, skill.name));
          setIsLoading(false);
        })
        .catch(() => {
          setSkillContent('Failed to load skill content.');
          setIsLoading(false);
        });
    }
  }, [isOpen, skill, skillContent]);

  // Reset content when skill changes
  useEffect(() => {
    setSkillContent(null);
    setActiveTab(initialTab);
  }, [skill?.id, initialTab]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-8"
          {...motionVariants.backdrop}
          onClick={onClose}
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(4px)' }}
          />

          {/* Modal - Smaller, centered, responsive */}
          <motion.div
            className="relative w-full max-w-md sm:max-w-lg max-h-[85vh] overflow-hidden rounded-xl flex flex-col"
            style={{
              backgroundColor: theme.colors.bg.tertiary,
              border: `1px solid ${theme.colors.border.medium}`,
              boxShadow: theme.shadows.lg,
            }}
            {...motionVariants.modal}
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 sm:px-5 py-3"
              style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}
            >
              <div className="flex items-center gap-2">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-base"
                  style={{
                    background: theme.colors.accent.muted,
                    color: theme.colors.accent.primary
                  }}
                >
                  ⚡
                </div>
                <div>
                  <h2
                    className="text-sm font-semibold"
                    style={{ color: theme.colors.text.primary }}
                  >
                    {skill.name}
                  </h2>
                </div>
              </div>
              <button
                onClick={onClose}
                className="w-7 h-7 rounded-md flex items-center justify-center transition-colors text-sm"
                style={{
                  color: theme.colors.text.muted,
                  backgroundColor: 'transparent',
                }}
                onMouseEnter={e => e.currentTarget.style.backgroundColor = theme.colors.bg.elevated}
                onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                ✕
              </button>
            </div>

            {/* Tabs - Current Skill Details on LEFT, What is a Skill? on RIGHT */}
            <div
              className="flex gap-1 px-4 sm:px-5 py-2"
              style={{ borderBottom: `1px solid ${theme.colors.border.subtle}` }}
            >
              <button
                onClick={() => setActiveTab('current')}
                className="px-3 py-1.5 rounded-md text-xs font-medium transition-all"
                style={{
                  backgroundColor: activeTab === 'current' ? theme.colors.accent.muted : 'transparent',
                  color: activeTab === 'current' ? theme.colors.accent.primary : theme.colors.text.secondary,
                }}
              >
                Current Skill Details
              </button>
              <button
                onClick={() => setActiveTab('what')}
                className="px-3 py-1.5 rounded-md text-xs font-medium transition-all"
                style={{
                  backgroundColor: activeTab === 'what' ? theme.colors.accent.muted : 'transparent',
                  color: activeTab === 'what' ? theme.colors.accent.primary : theme.colors.text.secondary,
                }}
              >
                What is a Skill?
              </button>
            </div>

            {/* Content */}
            <div className="p-4 sm:p-5 overflow-y-auto flex-1" style={{ minHeight: 0 }}>
              <AnimatePresence mode="wait">
                {activeTab === 'current' ? (
                  <motion.div
                    key="current"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 10 }}
                    transition={{ duration: 0.15 }}
                  >
                    {isLoading ? (
                      <div className="flex items-center justify-center py-8">
                        <div className="flex items-center gap-2">
                          <motion.div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: theme.colors.accent.primary }}
                            animate={{ scale: [1, 1.2, 1] }}
                            transition={{ duration: 0.6, repeat: Infinity }}
                          />
                          <span className="text-xs" style={{ color: theme.colors.text.secondary }}>Loading...</span>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="prose prose-sm max-w-none prose-invert
                          prose-headings:text-slate-100 prose-headings:font-semibold
                          prose-h1:text-base prose-h2:text-sm prose-h3:text-sm
                          prose-p:text-slate-300 prose-p:leading-relaxed prose-p:text-xs
                          prose-strong:text-amber-400 prose-strong:font-semibold
                          prose-ul:text-slate-300 prose-li:text-slate-300 prose-li:text-xs
                          prose-code:text-amber-400 prose-code:bg-slate-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                          prose-hr:border-slate-700
                        "
                      >
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {skillContent || ''}
                        </ReactMarkdown>
                      </div>
                    )}
                  </motion.div>
                ) : (
                  <motion.div
                    key="what"
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.15 }}
                  >
                    <div className="space-y-3">
                      <div
                        className="p-3 rounded-lg"
                        style={{ backgroundColor: theme.colors.bg.elevated }}
                      >
                        <h3
                          className="text-sm font-semibold mb-1.5 flex items-center gap-2"
                          style={{ color: theme.colors.text.primary }}
                        >
                          <span style={{ color: theme.colors.accent.primary }}>📄</span>
                          What is a SKILL.md file?
                        </h3>
                        <p
                          className="text-xs leading-relaxed mb-2"
                          style={{ color: theme.colors.text.secondary }}
                        >
                          A <strong style={{ color: theme.colors.text.primary }}>SKILL.md</strong> file is a
                          structured markdown document that defines how the AI agent should handle specific
                          types of requests. It acts as a "playbook" that guides the agent's behavior.
                        </p>
                        <a
                          href="https://code.claude.com/docs/en/skills"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs font-medium transition-colors"
                          style={{ color: theme.colors.status.info }}
                        >
                          <span>📚</span>
                          <span className="hover:underline">Learn more about Skills.md use →</span>
                        </a>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div
                          className="p-3 rounded-lg"
                          style={{ backgroundColor: theme.colors.bg.elevated }}
                        >
                          <div className="text-xl mb-1">🎯</div>
                          <h4
                            className="text-xs font-medium mb-0.5"
                            style={{ color: theme.colors.text.primary }}
                          >
                            Intent & Triggers
                          </h4>
                          <p
                            className="text-[10px]"
                            style={{ color: theme.colors.text.muted }}
                          >
                            Keywords that activate this skill
                          </p>
                        </div>
                        <div
                          className="p-3 rounded-lg"
                          style={{ backgroundColor: theme.colors.bg.elevated }}
                        >
                          <div className="text-xl mb-1">🛡️</div>
                          <h4
                            className="text-xs font-medium mb-0.5"
                            style={{ color: theme.colors.text.primary }}
                          >
                            Guardrails
                          </h4>
                          <p
                            className="text-[10px]"
                            style={{ color: theme.colors.text.muted }}
                          >
                            Safety rules and constraints
                          </p>
                        </div>
                        <div
                          className="p-3 rounded-lg"
                          style={{ backgroundColor: theme.colors.bg.elevated }}
                        >
                          <div className="text-xl mb-1">📊</div>
                          <h4
                            className="text-xs font-medium mb-0.5"
                            style={{ color: theme.colors.text.primary }}
                          >
                            Chart Guidance
                          </h4>
                          <p
                            className="text-[10px]"
                            style={{ color: theme.colors.text.muted }}
                          >
                            Visualization rules
                          </p>
                        </div>
                        <div
                          className="p-3 rounded-lg"
                          style={{ backgroundColor: theme.colors.bg.elevated }}
                        >
                          <div className="text-xl mb-1">📰</div>
                          <h4
                            className="text-xs font-medium mb-0.5"
                            style={{ color: theme.colors.text.primary }}
                          >
                            News Hooks
                          </h4>
                          <p
                            className="text-[10px]"
                            style={{ color: theme.colors.text.muted }}
                          >
                            When to fetch context
                          </p>
                        </div>
                      </div>

                      <div
                        className="p-3 rounded-lg border"
                        style={{
                          backgroundColor: theme.colors.thinking.bg,
                          borderColor: theme.colors.thinking.border,
                        }}
                      >
                        <p
                          className="text-xs"
                          style={{ color: theme.colors.text.secondary }}
                        >
                          <strong style={{ color: theme.colors.accent.primary }}>💡</strong>{' '}
                          Skills ensure accurate, well-formatted responses using the right SQL, chart types, and data formats.
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Footer - Only Got it button, no download */}
            <div
              className="px-4 sm:px-5 py-3 flex justify-end"
              style={{ borderTop: `1px solid ${theme.colors.border.subtle}` }}
            >
              <button
                onClick={onClose}
                className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: theme.colors.user.bg,
                  color: theme.colors.user.text,
                }}
              >
                Got it
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default SkillModal;
