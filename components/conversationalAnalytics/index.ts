/**
 * Function: index — Export barrel for conversational analytics components
 * Purpose: Provides clean imports for the conversational analytics feature
 */

export { default as ConversationalAnalyticsPage } from './ConversationalAnalyticsPage';
export { default as MessageBubble } from './MessageBubble';
export { default as ThinkingProcessBar } from './ThinkingProcessBar';
export { default as SkillModal } from './SkillModal';
export { default as ChatInput } from './ChatInput';
export { useSSEStream } from './hooks/useSSEStream';
export { theme, motionVariants } from './styles';
export type {
  SSEEvent,
  ThinkingStep,
  PlanStep,
  DebugLog,
  NewsResult,
  NewsArticle,
  SkillInfo,
  UseSSEStreamResult,
} from './hooks/useSSEStream';
