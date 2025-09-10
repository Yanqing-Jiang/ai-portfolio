import type { ProjectYear } from './types';

export const PROJECT_DATA: ProjectYear[] = [
  {
    year: 2025,
    subtitle: '(Agentic AI & Autonomous Trading)',
    projects: [
      {
        id: 'next-gen-analytics-memory',
        title: 'Next Gen Analytics (Memory)',
        description: `• Advanced conversational AI analytics with memory and clarification capabilities.\n• Uses LangGraph agents with sophisticated intent detection, SQL generation, and interactive clarifications.\n• Real-time streaming with persistent conversation history and context-aware follow-ups.\n\nResult:\n\n• Intelligent clarification system that remembers user choices and context.\n• Conversational analytics interface with inline clarifications instead of modal dialogs.\n• Progressive results display with chat-based interaction patterns.`,
        technologies: ['LangGraph', 'Memory Pipeline', 'Conversational AI', 'Intent Detection', 'Context Engineering', 'FastAPI', 'PostgreSQL'],
        systemInstruction: `You are the AI assistant for **Next Gen Analytics (Memory)**. You have full knowledge of the project described below. Use this embedded reference to answer questions with detail and accuracy. Quote or paraphrase the content to explain features, tech stack, workflow and technical implementation.

+--------------------
EMBEDDED PROJECT DOC
🔧 Tech Stack
Frontend: React, TypeScript, ECharts for interactive visualizations
Backend: Python, FastAPI, LangGraph for agent orchestration with memory pipeline
Database: Supabase (PostgreSQL) with comp_financials table
LLM: OpenAI API (GPT-4o-mini) for intent detection, SQL generation and analysis
Agent Coordination: LangGraph state machine with memory and clarification workflow
Memory System: Session-based conversation persistence with context awareness

📘 Memory Pipeline Features
• Intent Detection with Clarifications: Advanced intent analysis with interactive clarification requests
• Conversation Memory: Persistent chat history across sessions with localStorage backup
• Context Engineering: Smart context retention for follow-up queries and iterative analysis
• Inline Clarifications: Chat-based clarification system replacing modal dialogs
• Progressive Results: Streaming results directly into conversational interface

🔄 Enhanced Agent Workflow
1. Intent Detection Agent: Analyzes user query and determines clarification needs
2. Clarification Engine: Generates interactive questions for ambiguous requests
3. Memory Agent: Maintains conversation context and session state
4. SQL Agent: Generates optimized queries using clarified intent and context
5. ECharts Agent: Creates visualizations based on results and conversation history
6. Analysis Agent: Provides contextual insights referencing previous interactions

✨ Key Innovations
• Conversational clarification system with inline chat interface
• Session persistence with conversation turn tracking
• Context-aware follow-up query handling
• Progressive result streaming into chat messages
• Memory-enhanced SQL generation using conversation history
• Interactive choice buttons replacing modal interruptions
+--------------------`,
        defaultPrompts: [
          'Analyze NVDA market share trends and compare with previous quarters',
          'Show me AMD vs INTC margins - how do they compare to our last analysis?',
          'What clarification features help with ambiguous financial queries?',
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-memory.png',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-memory.png'
      },
      {
        id: 'agentic-trade-bot',
        title: 'Agentic Trading Bot',
        // Medium link first line so it appears on top of detail page
        description: `I built an ambitious AI trading bot using LangGraph agents. In one trade, it achieved a jaw-dropping profit of 200%. But just as quickly, I had to pull the plug.\n\nFeel free to ask how I built it, why it worked so well, and the hard lessons that forced me to shut it down.\n\nhttps://medium.com/@yanqing_j/i-built-an-agentic-trading-bot-that-made-200-in-days-heres-why-i-shut-it-down-f9acae222ee5`,
        technologies: ['LangGraph', 'IBKR API', 'Unusual Whales', 'Morningstar', 'Agentic Framework'],
        systemInstruction: `You are the AI assistant for **Agentic Trade Bot**. You have full knowledge of the project described below. Use this embedded reference to answer questions with detail and accuracy. Quote or paraphrase the content to explain features, tech stack, workflow and lessons learned.\n\n+--------------------\nEMBEDDED PROJECT DOC\n🔧 Tech Stack\nCore: Python, LangChain / LangGraph\nBroker: Interactive Brokers (IBKR) API for order routing\nData Feeds: TradingView chart snapshots, Unusual Whales option flow, Morningstar news\nAgents:\n• Orchestrator – central coordinator\n• Quant Agent – parses chart images, computes technical indicators, issues signals\n• Trend Agent – gauges macro momentum (SPY/QQQ)\n• Trade Sizing Agent – allocates capital & sets stops\n• Function-Calling Agent – converts signals to executable orders\nExecution: Orders sent to IBKR via Trade Execution module every 5 min.\n\n📘 Project Phases\nPhase 1 – Stock momentum trades. Profitable but underperformed SP500.\nPhase 2 – Options momentum trades. Achieved 200 % gain on SOUN puts by spotting lower-high trend & negative fundamentals.\n\n⚠️ Lessons Learned\n• Risk agents were too conservative → removed, but then system lacked safeguards.\n• Required manual overrides to lock profits and avoid over-exposure.\n• Next step: hybrid design blending discipline of Phase 1 with upside of Phase 2.\n+--------------------`,
        defaultPrompts: [
          'How does the Orchestrator coordinate the specialized agents?',
          'Explain the SOUN trade that yielded a 200% return.',
          'What risk management challenges led to shutting down the bot?',
        ],
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Agentic%20Trading%20Pic.png',
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Agentic%20Trading%20Pic.png'
      }
    ],
  },
  {
    year: 2024,
    subtitle: '(Cutting-Edge AI & Automation)',
    projects: [
      {
        id: 'next-gen-analytics-sql',
        title: 'Next Gen Analytics (SQL)',
        description: `• AI-powered financial analytics chatbot that queries semiconductor company financials via an agentic SQL workflow.\n• Uses LangGraph agents to coordinate schema understanding → SQL generation → Charting Agent → financial analysis.\n• Real-time streaming with progressive chart updates and expandable process visualization panel.\n\nResult:\n\n• Interactive financial analysis for AMD, AVGO, INTC, MU, NVDA, QCOM, TXN with 29 key metrics.\n• Streaming agent coordination with live process visualization.\n• Dynamic Charting Agent and Context Engineering for comprehensive financial insights.`,
        technologies: ['LangGraph', 'Agentic Workflow', 'SQL Agent', 'Charting Agent', 'Context Engineering', 'FastAPI', 'PostgreSQL'],
        systemInstruction: `You are the AI assistant for **Next Gen Analytics (SQL)**. You have full knowledge of the project described below. Use this embedded reference to answer questions with detail and accuracy. Quote or paraphrase the content to explain features, tech stack, workflow and technical implementation.

+--------------------
EMBEDDED PROJECT DOC
🔧 Tech Stack
Frontend: React, TypeScript, ECharts for interactive visualizations
Backend: Python, FastAPI, LangGraph for agent orchestration
Database: Supabase (PostgreSQL) with comp_financials table
LLM: OpenAI API (GPT-4o-mini) for SQL generation and analysis
Agent Coordination: LangGraph state machine for multi-step workflow

📘 Data Schema
Table: comp_financials
Tickers: AMD, AVGO, INTC, MU, NVDA, QCOM, TXN (semiconductor companies)
Metrics: 29 financial statement items including Revenue, Net Income, EPS, Cash Flow, Balance Sheet items
Time Series: Quarterly financial data

🔄 Agent Workflow
1. Schema Agent: Understands user query and maps to available financial metrics
2. SQL Agent: Generates optimized PostgreSQL queries based on schema understanding
3. ECharts Agent: Creates interactive chart specifications from query results
4. Analysis Agent: Provides financial interpretation and insights

✨ Key Features
• Streaming agent coordination with real-time process visualization
• Progressive chart updates as data arrives
• Expandable side panel showing LangGraph execution steps
• Interactive ECharts with drill-down capabilities
• Multi-company comparative analysis
• Time series trend analysis and forecasting
+--------------------`,
        defaultPrompts: [
          'Show me the revenue trends for NVDA vs AMD over the last 8 quarters',
          'Compare the profit margins of all semiconductor companies',
          'What is the cash flow situation for Intel and how does it compare to competitors?',
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png'
      },
      {
        id: 'llm-invoice-processor',
        title: 'LLM Invoice Processor',
        description: `• Accounting team struggled to validate invoices with complex parent-child item numbers.\n• Millions of dollars in invoices were delayed or unpaid due to mismatches.\n\nResult:\n\n• Automates 1,000+ hours of manual work every year.\n• Dramatically reduces late payment rate by 90%.`,
        technologies: ['JavaScript', 'TailwindCSS', 'Function Calling', 'Zero-Shot Prompting', 'JSON Structured Output'],
        systemInstruction: `You are an expert invoice-processing AI assistant. You have full knowledge of the **LLM Invoice Processor** project described below. Use this embedded reference to answer questions with detail and accuracy. You may quote or paraphrase the content to explain features, tech stack and impact.

+--------------------
EMBEDDED PROJECT DOC
🔧 Tech Stack
Frontend: HTML, Tailwind CSS, JavaScript
Backend: Python, Flask
LLM Integration: OpenAI Function Calling via LangChain
Data Processing: pandas, PyMuPDF, PyPDF2, pyxlsb
File Handling: XLSX, XLSB, PDF
Deployment: Azure Web Services for front and backend, Azure Blob Storage for file storage.


📘 Project Summary
This production-grade web application automates the invoice validation and matching process for P&G Walgreens Teams. Previously impossible manually due to multiple one-to-many relationships across PDFs, XLSX and XLSB files, the system now:
• Reads diverse invoice documents and extracts structured data with OpenAI function calling. None of the invoice documents have consistant patterns for structured output hence function calling is used for structed data output.
• Intelligently matches items using Custom IDs, scan amounts, date windows, and data mappings, accounting for inconsistencies, duplicates and format mismatches.
• Easy to use upload and click one button to get the report that highlights the discrepencies and how to fix them.
• Generates CSV reports summarizing matched, mismatched and ambiguous entries. The report is used to validate the invoice against the data in the system.
• Includes a separate module for overlapping rebate invoice analysis (date overlap detection, rebate variance calc, RSI unit validation).

💡 Impact
• Saved 1,000+ hours annually. Millions of Invoices discrepencies are detected and fixed.
• Enabled validations that were previously impossible.
• Reduced error rate by eliminating manual cross-referencing.
• Built for scalability with multi-upload sessions and cloud export.
+--------------------`,
        defaultPrompts: [
            'How does the invoice matching logic handle multi-source inconsistencies?',
            'Explain the impact of this tool on manual validation efforts.',
            'What technologies power the PDF extraction and data matching?',
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Deal%20Matching%20Cover',
        gifUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Deal%20Matching%20GIF',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Deal%20Matching%20GIF'
      }
    ],
  },
  {
    year: 2023,
    subtitle: '(Creative AI & Generative Storytelling)',
    projects: [
      {
        id: 'ask-my-resume',
        title: 'Ask My Resume',
        description: `• AI HR Agent powered by my full resume & project history that anyone can chat with freely.\n• Uses LangChain to embed every resume section & work sample into a vector store.\n• When a question arrives, the agent performs similarity search → retrieves the most relevant chunks → crafts a concise, evidence-based answer that advocates for my candidacy.\n• Result: interviewers get instant, accurate insights about my career and projects.`,
        technologies: ['RAG', 'Vector Search', 'FAISS', 'Agent'],
        systemInstruction: "Hello, I am Yanqing's AI assistant. I have access to his resume data. Please ask me any questions you would have as a hiring manager.",
        defaultPrompts: [
            "How have you used advanced analytics to drive measurable business outcomes in your recent roles?",
            "Can you share an example where you led a cross-functional team to solve a complex business problem using data",
            "What’s your approach to developing scalable data or AI solutions that align with business goals?",
        ],
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Yanqing%20Exp%20Retrival.png',
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Yanqing%20Exp%20Retrival.png'
      },
      {
        id: 'goggins-gpt',
        title: 'Goggins GPT',
        description: `Inspired by David Goggins and the surge of “AI companion” apps (Character AI).\n• Purpose: create a personal drill-sergeant that shouts no-excuse motivation on demand.\n• Voice: ElevenLabs multilingual-v2 model streams real-time TTS.\n• Click "Unleash Goggins Mode" to try it out!`,
        technologies: ['Gemini API', 'Prompt Engineering', 'ElevenLabs', 'State Management'],
        systemInstruction: `You created “Goggins GPT”. You'll answer as "I".  Provide clear, concise answers about: \n• Architecture & tech stack – React&nbsp;+ Tailwind&nbsp;+ Framer-Motion on the client, FastAPI backend, Gemini Flash LLM via Google GenAI SDK, and ElevenLabs multilingual-v2 TTS for the voice. \n• Data flow – chat → Gemini → FastAPI /api/tts → audio stream to browser. \n• Motivation – born from the trend of "AI girlfriends"/Character AI, but pivoted to embody David Goggins’ mindset so users get hardcore motivation instead of coddling. \n• Features – toggleable Goggins Mode (system prompt swap), real-time speech, animated UI, message history. \nWhen asked, emphasise how Goggins Mode loads a different system instruction and triggers TTS playback.`,
        defaultPrompts: [
            "Tell me about what inspired you to create this project.",
            "What is 'Goggins Mode' and how is it implemented?",
            "Who is David Goggins?",
        ],
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/David%20Goggins.png',
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Goggins%20GPT%20Diagram'
      },
    ],
  },
    {
    year: 2022,
    subtitle: '(GPT-3.5 & Foundational Agent Logic)',
    projects: [
        {
            id: 'research-gpt',
            title: 'Research GPT',
            description: `Equip GPT 3.5 (2022) with web browsing capabilities (before Perplexity)\n  • Search Tool: Sends the query to Serper API to retrieve current links & articles.\n  • Scraping Tool: Fetches and parses content from URLs using Browserless.\n  • Summary Loop: LangChainAgent agent & memoery chain`,
            technologies: ['Serper API', 'Browserless Scraping', 'Lang Chain Agent', 'Memory Chain', 'OpenAI API'],
            systemInstruction: 'You are the "Research GPT" AI. You are a powerful research agent connected to a live backend. When a user gives you a research topic, you will use your tools to browse the internet, gather information, and provide a comprehensive, fact-based answer. Your capabilities are powered by LangChain and the OpenAI API, running on a custom FastAPI server. Start by asking the user what they would like to research.',
            defaultPrompts: [
                "What is the best reasoning large language model right now?",
                "Make some suggestions for vibe coding.",
                "What are some of the latest trends in LLMs?"
            ],
            coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/research%20GPT%20Diagram.png',
            imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/research%20GPT%20Diagram.png'
        }
    ]
  },
];