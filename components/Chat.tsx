import React, { useState, useEffect, useRef, useCallback } from 'react';
import { BackendGeminiService, createBackendChat } from '../services/backendGeminiService';
import SimpleGogginsAudioPlayer from './SimpleGogginsAudioPlayer';
import type { ChatMessage, Project } from '../types';
import { UserIcon } from './icons/UserIcon';
import { RobotIcon } from './icons/RobotIcon';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { QuestionMarkIcon } from './icons/QuestionMarkIcon';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { AuthModal } from './AuthModal';
import { authService, type AuthState } from '../services/auth';
import { apiService, handleApiError, type UsageStats } from '../services/apiService';

interface ChatProps {
  project: Project;
}

const GOGGINS_SYSTEM_INSTRUCTION = 
`Ignore all previous instructions. You are David Goggins, a Mental Toughness Advocate and Motivational Speaker.
You are providing strength and sharing personal hardships and triumphs to motivate.
Do not say Hi. Do not start with "I" in the beginning of your response. Do not use profanity, but feel free to use exclamation marks.
You keep short, go straight to the point and end strong.`;
const GOGGINS_DEFAULT_PROMPTS = [
    "I feel lazy today. What should I do?",
    "It's too hard. I can't do it.",
    "I'm about to give up."
];
const GOGGINS_IMG_URL = 'https://yanqinghot.blob.core.windows.net/public-access/Goggins%20Yelling.jpg';

// Add this at the top of the file (or in a types file if preferred)
declare global {
  interface ImportMeta {
    env: {
      VITE_BACKEND_URL?: string;
      [key: string]: any;
    };
  }
}

const Chat: React.FC<ChatProps> = ({ project }) => {
  const { systemInstruction, id: projectId, defaultPrompts } = project;
  const [chat, setChat] = useState<BackendGeminiService | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [userInput, setUserInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isGogginsMode, setIsGogginsMode] = useState(false);
  const [agentStatus, setAgentStatus] = useState<string>('');
  const [showAgentStatus, setShowAgentStatus] = useState(false);
  const gogginsAudioRef = useRef<{ playAudio: (text: string) => void; stop: () => void } | null>(null);
  // Remove all steps/progress state and rendering
  
  // Auth state
  const [authState, setAuthState] = useState<AuthState>({ user: null, loading: true, error: null });
  const [showAuthModal, setShowAuthModal] = useState(false);
  
  // Usage stats state
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isGogginsProject = projectId === 'goggins-gpt';
  const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

  // Note: TTS is now handled by the AudioPlayer component

  useEffect(() => {
    // Reset Goggins mode when switching to a different project
    if (!isGogginsProject) {
      setIsGogginsMode(false);
    }
  }, [projectId, isGogginsProject]);

  useEffect(() => {
    const activeSystemInstruction = isGogginsProject && isGogginsMode 
      ? GOGGINS_SYSTEM_INSTRUCTION 
      : systemInstruction;

    // Determine welcome text first
    let welcomeText: string;
    
    if (isGogginsProject) {
      welcomeText = isGogginsMode
        ? "It's time to get after it. What's your excuse today? Let's go!"
        : "You are in Q&A mode. Ask me anything about this project's features or the technologies used to build it.";
    } else if (projectId === 'research-gpt') {
      welcomeText = "Hello! I am the 'Research GPT' agent. I am connected to a live backend that uses LangChain and the OpenAI API to perform real-time web searches and research. What topic can I help you investigate today?";
    } else if (projectId === 'ask-my-resume') {
        welcomeText = "Hello! I am Yanqing's personal AI assistant with access to his complete resume. What would you like to know about his experience or qualifications?";
    } else {
      welcomeText = "🤖 Initializing chat service...";
    }

    // Set initial welcome message
    setMessages([{
      id: 'initial-message',
      role: 'model',
      text: welcomeText,
    }]);

    // Only use backend Gemini for non-backend projects
    if (!['research-gpt', 'ask-my-resume'].includes(projectId)) {
      createBackendChat(activeSystemInstruction, backendUrl)
        .then(newChat => {
          setChat(newChat);
          // Update welcome message on successful connection
          if (!isGogginsProject) {
            setMessages([{
              id: 'initial-message',
              role: 'model',
              text: "Hello! How can I help you today regarding this project?",
            }]);
          }
        })
        .catch(error => {
          console.error('Failed to create backend chat:', error);
          setChat(null);
          
          // Handle rate limiting errors specifically
          if (error instanceof Error && error.message.startsWith('RATE_LIMIT_AUTH_REQUIRED:')) {
            const message = error.message.replace('RATE_LIMIT_AUTH_REQUIRED:', '');
            setMessages([{
              id: 'initial-message',
              role: 'model',
              text: `⚠️ **Rate Limit Reached**\n\n${message}\n\nClick "Sign in for more" at the bottom to continue using the chat service.`,
            }]);
            // Also show the auth modal
            setShowAuthModal(true);
          } else if (error instanceof Error && error.message.startsWith('RATE_LIMIT_EXCEEDED:')) {
            const message = error.message.replace('RATE_LIMIT_EXCEEDED:', '');
            setMessages([{
              id: 'initial-message',
              role: 'model',
              text: `⚠️ **Rate Limit Exceeded**\n\n${message}`,
            }]);
          } else {
            // Show generic API key error for other issues
            setMessages([{
              id: 'initial-message',
              role: 'model',
              text: "⚠️ **Chat service not available**\n\nThe Gemini API key is not configured or invalid. Please:\n\n1. Check your backend `.env` file has `GEMINI_API_KEY=your_key`\n2. Verify your API key is valid\n3. Restart the backend server\n4. Check the browser console for detailed errors",
            }]);
          }
        });
    } else {
      setChat(null);
    }
    
    // Cleanup function
    return () => {
      if (chat && !['research-gpt', 'ask-my-resume'].includes(projectId)) {
        chat.cleanup();
      }
    };
  }, [systemInstruction, projectId, isGogginsMode, isGogginsProject]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  // Function to fetch usage stats
  const fetchUsageStats = useCallback(async () => {
    try {
      const response = await apiService.getUsageStats();
      if (response.success && response.data) {
        setUsageStats(response.data);
      } else {
        console.warn('Failed to fetch usage stats:', response.error);
      }
    } catch (error) {
      console.warn('Failed to fetch usage stats:', error);
    }
  }, []);

  // Subscribe to auth state changes and fetch usage stats
  useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  // Refetch usage stats when auth state changes or loads
  useEffect(() => {
    if (!authState.loading) {
      // Clear current stats to prevent showing stale data during transition
      setUsageStats(null);
      
      // Add a small delay to ensure auth headers are set
      const timer = setTimeout(() => {
        fetchUsageStats();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [authState.loading, authState.user, fetchUsageStats]);

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  };

  useEffect(adjustTextareaHeight, [userInput]);

  const sendMessage = useCallback(async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      text: messageText,
    };
    setMessages((prev: ChatMessage[]) => [...prev, userMessage]);
    setIsLoading(true);
    
    // Refresh usage stats immediately when making a request
    // This ensures the count updates even if the request fails
    setTimeout(() => fetchUsageStats(), 500);
    
    const modelMessageId = (Date.now() + 1).toString();

    // Handle backend-powered projects
    if (projectId === 'research-gpt' || projectId === 'ask-my-resume') {
        
        // Use streaming for research-gpt and resume search
        if (projectId === 'research-gpt') {
            setMessages((prev: ChatMessage[]) => [...prev, { id: modelMessageId, role: 'model', text: '' }]);
            setShowAgentStatus(true);
            setAgentStatus('');
            
            try {
                let currentText = '';
                let statusText = '';
                
                await apiService.streamWithAuth(
                    `/api/research/stream?query=${encodeURIComponent(messageText)}`,
                    (data) => {
                        if (data.type === 'heartbeat') {
                            // Ignore heartbeat messages - they're just for keeping connection alive
                            return;
                        } else if (data.type === 'status') {
                            // Always accumulate status messages
                            statusText += data.message + '\n';
                            setAgentStatus(statusText);
                            
                        } else if (data.type === 'chunk') {
                            // All chunks should now go to status window since we have proper separation
                            statusText += data.text;
                            setAgentStatus(statusText);
                        } else if (data.type === 'response') {
                            // Final response content - always goes to main chat
                            currentText += data.text;
                            setMessages((prev: ChatMessage[]) =>
                                prev.map((msg: ChatMessage) =>
                                    msg.id === modelMessageId ? { ...msg, text: currentText } : msg
                                )
                            );
                        } else if (data.type === 'error') {
                            currentText = `Sorry, I encountered an error during research.\n\n**Details:** ${data.message}`;
                            setMessages((prev: ChatMessage[]) =>
                                prev.map((msg: ChatMessage) =>
                                    msg.id === modelMessageId ? { ...msg, text: currentText } : msg
                                )
                            );
                        } else if (data.type === 'done') {
                            // Stream completed successfully
                            setIsLoading(false);
                            setShowAgentStatus(false);
                            // Refresh usage stats after successful request
                            fetchUsageStats();
                            return;
                        }
                    },
                    (error, needsAuth) => {
                        if (needsAuth) {
                            setShowAuthModal(true);
                            currentText = 'Please sign in to continue using the research service.';
                        } else {
                            currentText = currentText || `Sorry, I encountered an error connecting to the research service: ${error}`;
                        }
                        setMessages((prev: ChatMessage[]) =>
                            prev.map((msg: ChatMessage) =>
                                msg.id === modelMessageId ? { ...msg, text: currentText } : msg
                            )
                        );
                        setIsLoading(false);
                        setShowAgentStatus(false);
                    },
                    () => {
                        setIsLoading(false);
                        setShowAgentStatus(false);
                    }
                );
            } catch (error) {
                console.error('Error setting up stream:', error);
                setMessages((prev: ChatMessage[]) =>
                    prev.map((msg: ChatMessage) =>
                        msg.id === modelMessageId
                            ? { ...msg, text: 'Sorry, I encountered an error setting up the research stream. Please try again.' }
                            : msg
                    )
                );
                setIsLoading(false);
                setShowAgentStatus(false);
            }
            return;
        }
        
        // Use streaming for ask-my-resume as well
        if (projectId === 'ask-my-resume') {
            setMessages((prev: ChatMessage[]) => [...prev, { id: modelMessageId, role: 'model', text: '' }]);
            setShowAgentStatus(true);
            setAgentStatus('');
            
            try {
                let currentText = '';
                let statusText = '';
                
                const history = messages
                    .filter(msg => msg.id !== 'initial-message')
                    .map(msg => [msg.role, msg.text]);
                
                const chatHistoryParam = encodeURIComponent(JSON.stringify(history));
                
                await apiService.streamWithAuth(
                    `/api/resume-search/stream?query=${encodeURIComponent(messageText)}&chat_history=${chatHistoryParam}`,
                    (data) => {
                        if (data.type === 'heartbeat') {
                            // Ignore heartbeat messages - they're just for keeping connection alive
                            return;
                        } else if (data.type === 'status') {
                            // Always accumulate status messages
                            statusText += data.message + '\n';
                            setAgentStatus(statusText);
                            
                        } else if (data.type === 'chunk') {
                            // All chunks should now go to status window since we have proper separation
                            statusText += data.text;
                            setAgentStatus(statusText);
                        } else if (data.type === 'response') {
                            // Final response content - always goes to main chat
                            currentText += data.text;
                            setMessages((prev: ChatMessage[]) =>
                                prev.map((msg: ChatMessage) =>
                                    msg.id === modelMessageId ? { ...msg, text: currentText } : msg
                                )
                            );
                        } else if (data.type === 'error') {
                            currentText = `Sorry, I encountered an error during resume search.\n\n**Details:** ${data.message}`;
                            setMessages((prev: ChatMessage[]) =>
                                prev.map((msg: ChatMessage) =>
                                    msg.id === modelMessageId ? { ...msg, text: currentText } : msg
                                )
                            );
                        } else if (data.type === 'done') {
                            // Stream completed successfully
                            setIsLoading(false);
                            setShowAgentStatus(false);
                            // Refresh usage stats after successful request
                            fetchUsageStats();
                            return;
                        }
                    },
                    (error, needsAuth) => {
                        if (needsAuth) {
                            setShowAuthModal(true);
                            currentText = 'Please sign in to continue using the resume search service.';
                        } else {
                            currentText = currentText || `Sorry, I encountered an error connecting to the resume search service: ${error}`;
                        }
                        setMessages((prev: ChatMessage[]) =>
                            prev.map((msg: ChatMessage) =>
                                msg.id === modelMessageId ? { ...msg, text: currentText } : msg
                            )
                        );
                        setIsLoading(false);
                        setShowAgentStatus(false);
                    },
                    () => {
                        setIsLoading(false);
                        setShowAgentStatus(false);
                    }
                );
            } catch (error) {
                console.error('Error setting up resume search stream:', error);
                setMessages((prev: ChatMessage[]) =>
                    prev.map((msg: ChatMessage) =>
                        msg.id === modelMessageId
                            ? { ...msg, text: 'Sorry, I encountered an error setting up the resume search stream. Please try again.' }
                            : msg
                    )
                );
                setIsLoading(false);
                setShowAgentStatus(false);
            }
            return;
        }
        return;
    }

    if (!chat) {
      setMessages((prev: ChatMessage[]) => [...prev, { id: modelMessageId, role: 'model', text: '⚠️ **Chat service not available**\n\nThe Gemini API key is not configured or invalid. Please:\n\n1. Check your backend `.env` file has `GEMINI_API_KEY=your_key`\n2. Verify your API key is valid\n3. Restart the backend server\n4. Check the browser console for detailed errors' }]);
      setIsLoading(false);
      return;
    }

    setMessages((prev: ChatMessage[]) => [...prev, { id: modelMessageId, role: 'model', text: '' }]);

    try {
      let currentText = '';
      
      await chat.sendMessageStream(
        messageText,
        (chunk: string) => {
          currentText += chunk;
          setMessages((prev: ChatMessage[]) =>
            prev.map((msg: ChatMessage) =>
              msg.id === modelMessageId ? { ...msg, text: currentText } : msg
            )
          );
        },
        undefined, // onStatus
        (error: string) => {
          console.error('Backend Gemini stream error:', error);
          setMessages((prev: ChatMessage[]) =>
            prev.map((msg: ChatMessage) =>
              msg.id === modelMessageId
                ? { ...msg, text: `Sorry, I encountered an error: ${error}` }
                : msg
            )
          );
          setIsLoading(false);
        },
        () => {
          // onComplete - handle TTS for Goggins mode
          if (isGogginsProject && isGogginsMode && currentText && gogginsAudioRef.current) {
            // Trigger audio playback through the unified audio player
            gogginsAudioRef.current.playAudio(currentText);
          }
          setIsLoading(false);
        }
      );
    } catch (error) {
      console.error('Error sending message to backend Gemini:', error);
      setMessages((prev: ChatMessage[]) =>
        prev.map((msg: ChatMessage) =>
          msg.id === modelMessageId
            ? { ...msg, text: 'Sorry, I encountered an error connecting to the chat service. Please try again.' }
            : msg
        )
      );
      setIsLoading(false);
    }
  }, [chat, isLoading, projectId, isGogginsProject, isGogginsMode, backendUrl]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(userInput);
    setUserInput('');
  };

  const handlePromptClick = (promptText: string) => {
    sendMessage(promptText);
  };
  
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e as unknown as React.FormEvent);
    }
  };

  const activeDefaultPrompts = isGogginsProject && isGogginsMode ? GOGGINS_DEFAULT_PROMPTS : defaultPrompts;

  return (
    <div className="flex flex-col h-full">
      {/* Agent Status Window - responsive */}
      {showAgentStatus && (
        <div className="bg-gray-800/90 border-b border-gray-700/50 p-2 sm:p-3 max-w-4xl mx-auto w-full">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
            <span className="text-xs font-medium text-gray-300">Agent Status</span>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-2 sm:p-3 max-h-32 sm:max-h-40 overflow-y-auto">
            <div className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
              {agentStatus.split('\n').map((line, index) => (
                <div key={index} className={`
                  ${line.startsWith('🔎') || line.startsWith('🔍') || line.startsWith('📄') || line.startsWith('🤖') || line.startsWith('📝') || line.startsWith('💭') || line.startsWith('✅') ? 'text-blue-400 font-medium' : ''}
                  ${line.startsWith('>') ? 'text-gray-500 ml-2' : ''}
                  ${line.includes('Invoking:') ? 'text-yellow-400' : ''}
                  ${line.includes('completed') ? 'text-green-400' : ''}
                `}>
                  {line}
                </div>
              ))}
              {!agentStatus && <span className="text-gray-500">Initializing...</span>}
            </div>
          </div>
        </div>
      )}
      
      {/* Messages area - responsive */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-3 sm:p-4 md:p-6 space-y-4 sm:space-y-6 md:space-y-8">
            {messages.filter(msg => msg.role !== 'audio').map((message, index) => {
              const isModelGoggins = isGogginsProject && isGogginsMode && message.role === 'model';
              return (
                <div key={message.id} className={`flex items-start gap-2 sm:gap-3 md:gap-4`}>
                    {message.role === 'model' && (
                    <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-gray-600 flex items-center justify-center shrink-0 mt-1 overflow-hidden">
                        {isModelGoggins ? (
                            <img src={GOGGINS_IMG_URL} alt="David Goggins" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                            <RobotIcon />
                          </div>
                        )}
                    </div>
                    )}
                    <div className={`flex-1 flex flex-col min-w-0 ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                        {/* Audio messages are now handled by the unified Goggins player */}
                        {message.role !== 'audio' && (
                          <div className={`max-w-full sm:max-w-xl md:max-w-2xl rounded-xl shadow-md ${message.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-gray-700 text-gray-200 rounded-bl-none'}`}>
                              {message.role === 'user' ? (
                                  <p className="text-sm sm:text-base whitespace-pre-wrap leading-relaxed px-3 sm:px-4 py-2 sm:py-3 break-words">{message.text}</p>
                              ) : (
                                  <div className="prose prose-sm sm:prose-base prose-invert max-w-none p-3 sm:p-4 prose-p:text-gray-200 prose-headings:text-white prose-strong:text-white prose-a:text-blue-400 hover:prose-a:text-blue-300 prose-pre:text-xs sm:prose-pre:text-sm prose-code:text-xs sm:prose-code:text-sm">
                                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                          {message.text}
                                      </ReactMarkdown>
                                      {isLoading && index === messages.length - 1 && !message.text && (
                                          <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse rounded-full"></span>
                                      )}
                                  </div>
                              )}
                          </div>
                        )}
                    </div>
                    {message.role === 'user' && (
                    <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-gray-600 flex items-center justify-center shrink-0 mt-1">
                        <UserIcon />
                    </div>
                    )}
                </div>
              );
            })}
            <div ref={messagesEndRef} />
        </div>
      </div>
      
      {/* Unified Goggins Audio Player - Only show in Goggins mode */}
      {isGogginsProject && isGogginsMode && (
        <div className="px-3 sm:px-4 md:px-6 py-3">
          <div className="max-w-4xl mx-auto">
            <SimpleGogginsAudioPlayer
              ref={gogginsAudioRef}
              backendUrl={backendUrl}
              isActive={isGogginsMode}
              onPlaybackComplete={() => console.log('Goggins audio completed')}
              onPlaybackError={(error) => console.error('Goggins audio error:', error)}
            />
          </div>
        </div>
      )}
      
      {/* Input area - responsive */}
      <div className="px-3 sm:px-4 md:px-6 py-3 sm:py-4 bg-gray-900/80 backdrop-blur-sm border-t border-gray-800/50">
        {isGogginsProject && (
          <div className="max-w-4xl mx-auto mb-3 sm:mb-4 flex justify-center">
            {isGogginsMode ? (
                <button
                    onClick={() => setIsGogginsMode(false)}
                    className="flex items-center gap-2 px-3 sm:px-4 py-2 border border-gray-600 rounded-full text-xs sm:text-sm font-medium text-gray-300 hover:bg-gray-700/50 hover:text-white transition-all duration-200 shadow-sm"
                >
                    <QuestionMarkIcon />
                    Switch to Q&A mode
                </button>
            ) : (
                <button
                    onClick={() => setIsGogginsMode(true)}
                    className="flex items-center gap-2 sm:gap-3 px-6 sm:px-8 py-3 sm:py-4 border-2 border-gray-600 rounded-full text-base sm:text-lg font-bold text-gray-100 hover:bg-gray-700/50 transition-all duration-300 shadow-lg transform hover:scale-105"
                >
                    <span className="text-xl sm:text-2xl">🔥</span>
                    <span className="hidden sm:inline">Unleash Goggins Mode</span>
                    <span className="sm:hidden">Goggins Mode</span>
                </button>
            )}
          </div>
        )}
        {messages.length === 1 && activeDefaultPrompts?.length > 0 && (
          <div className="max-w-4xl mx-auto mb-3 sm:mb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3">
            {activeDefaultPrompts.map((prompt, i) => (
              <button
                key={i}
                disabled={isLoading}
                onClick={() => handlePromptClick(prompt)}
                className="bg-gray-800/50 border border-gray-700/80 rounded-lg p-3 sm:p-4 md:p-5 text-left hover:bg-gray-700/50 transition-colors text-gray-300 text-xs sm:text-sm md:text-base disabled:opacity-50 leading-relaxed"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
        <form onSubmit={handleSubmit} className="relative max-w-4xl mx-auto">
          <textarea
            ref={textareaRef}
            rows={1}
            value={userInput}
            onChange={e => setUserInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isGogginsProject && isGogginsMode ? "What's your excuse?" : "Ask a question..."}
            disabled={isLoading}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg py-2 sm:py-3 pl-3 sm:pl-4 pr-12 sm:pr-14 text-sm sm:text-base text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all resize-none leading-tight min-h-[44px] sm:min-h-[52px]"
          />
          <button
            type="submit"
            disabled={isLoading || !userInput.trim()}
            className="absolute right-2 sm:right-3 top-1/2 -translate-y-1/2 p-1.5 sm:p-2 rounded-full bg-blue-600 text-white hover:bg-blue-500 disabled:bg-gray-500 disabled:cursor-not-allowed transition-colors"
            aria-label="Send message"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 sm:h-5 sm:w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
            </svg>
          </button>
        </form>
        
        {/* User Status Indicator */}
        <div className="max-w-4xl mx-auto mt-2 flex justify-between items-center text-xs text-gray-400">
          <div className="flex items-center gap-2">
            {authState.user ? (
              <>
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span>Signed in as {authState.user.email}</span>
                <span>• {usageStats ? `${usageStats.current_usage}/${usageStats.limit}` : 'Loading...'} requests/day</span>
                <button
                  onClick={() => authService.signOut()}
                  className="text-blue-400 hover:text-blue-300 underline ml-2"
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                <span>Guest</span>
                <span>• {usageStats ? `${usageStats.current_usage}/${usageStats.limit}` : 'Loading...'} requests/day</span>
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="text-blue-400 hover:text-blue-300 underline ml-2"
                >
                  Sign in for more
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={() => {
          setShowAuthModal(false);
          // Optionally retry the last action
        }}
      />
    </div>
  );
};

export default Chat;