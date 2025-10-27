import type { ProjectYear } from './types';

export const PROJECT_DATA: ProjectYear[] = [
  {
    year: 2025,
    subtitle: '(Agentic AI & Autonomous Trading)',
    projects: [
      {
        id: 'next-gen-analytics-agent',
        title: 'Next Gen Analytics (Agents)',
        description: `Three Agentic Workflows:\nDirect (fixed path): deterministic tool orchestration for rapid answers\nSingle-Agent (multi-tool use): adaptive LangGraph agent that rewrites SQL, charts, and commentary\nMulti-Agent (supervisor + specialists): orchestrated analytics swarm with explainable task graph\nHuman-in-the-loop: Inline clarifications tuned for metrics, peers, and guardrail ranges\nExplainable thinking process panel: plan graph + per-step trace for analyst-grade transparency.\nLive semiconductor coverage: AMD, AVGO, INTC, MU, NVDA, QCOM, TXN.\nMemory optimization: RAG tuned recall, cached SQL, vector prompts, and stateful agents`,
        cardDescription: 'Agentic analytics without dashboards—LangGraph copilots clarify questions, write SQL, and narrate semiconductor insights in real time.',
        technologies: ['Single Agent Workflow', 'Multi-Agent Workflow', 'Human-in-the-Loop', 'RAG', 'Long-Term Memory'],
        systemInstruction: `You are the AI assistant for **Next Gen Analytics (Agents)**. You have full knowledge of the project described below. Use this embedded reference to answer questions with detail and accuracy. Quote or paraphrase the content to explain features, tech stack, workflow and technical implementation.

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
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png',
        ogImage: 'https://yanqinghot.blob.core.windows.net/public-access/OG-Page.png',
        seoTitle: 'Next Gen Analytics Agents | LangGraph + FastAPI Copilot',
        seoDescription:
          'AI-first analytics copilot that clarifies intent, rewrites Supabase SQL, and streams ECharts narration through LangGraph multi-agent workflows.',
        seoKeywords: [
          'LangGraph analytics',
          'analytics agents',
          'agentic copilot',
          'FastAPI Supabase',
          'multi-agent workflow',
        ],
        datePublished: '2025-06-01',
        dateModified: '2025-09-15',
        serviceTags: ['Analytics Automation', 'AI Agents', 'Decision Intelligence'],
        statHighlights: [
          'Supports direct, single-agent, and supervisor-led workflows in one UI',
          'Caches SQL, RAG, and visualization context for repeatable market insights',
        ],
        primaryMetricValue: {
          label: 'Clarification latency improvement',
          value: 60,
          unitText: 'Percent',
        },
      },
      {
        id: 'agentic-trade-bot',
        title: 'Agentic Trading Bot',
        // Medium link first line so it appears on top of detail page
        description: `I built an ambitious AI trading bot using LangGraph agents. In one trade, it achieved a jaw-dropping profit of 200%. But just as quickly, I had to pull the plug.\n\nFeel free to ask how I built it, why it worked so well, and the hard lessons that forced me to shut it down.\n\nhttps://medium.com/@yanqing_j/i-built-an-agentic-trading-bot-that-made-200-in-days-heres-why-i-shut-it-down-f9acae222ee5`,
        cardDescription: 'I built an ambitious LLM trading bot that realized a 200% gain, then shut it down for safety.',
        technologies: ['LangGraph', 'IBKR API', 'Unusual Whales', 'Morningstar', 'Agentic Framework'],
        systemInstruction: `You are the AI assistant for **Agentic Trade Bot**. You have full knowledge of the project described below. Use this embedded reference to answer questions with detail and accuracy. Quote or paraphrase the content to explain features, tech stack, workflow and lessons learned.\n\n+--------------------\nEMBEDDED PROJECT DOC\n🔧 Tech Stack\nCore: Python, LangChain / LangGraph\nBroker: Interactive Brokers (IBKR) API for order routing\nData Feeds: TradingView chart snapshots, Unusual Whales option flow, Morningstar news\nAgents:\n• Orchestrator – central coordinator\n• Quant Agent – parses chart images, computes technical indicators, issues signals\n• Trend Agent – gauges macro momentum (SPY/QQQ)\n• Trade Sizing Agent – allocates capital & sets stops\n• Function-Calling Agent – converts signals to executable orders\nExecution: Orders sent to IBKR via Trade Execution module every 5 min.\n\n📘 Project Phases\nPhase 1 – Stock momentum trades. Profitable but underperformed SP500.\nPhase 2 – Options momentum trades. Achieved 200 % gain on SOUN puts by spotting lower-high trend & negative fundamentals.\n\n⚠️ Lessons Learned\n• Risk agents were too conservative → removed, but then system lacked safeguards.\n• Required manual overrides to lock profits and avoid over-exposure.\n• Next step: hybrid design blending discipline of Phase 1 with upside of Phase 2.\n+--------------------`,
        defaultPrompts: [
          'How does the Orchestrator coordinate the specialized agents?',
          'Explain the SOUN trade that yielded a 200% return.',
          'What risk management challenges led to shutting down the bot?',
        ],
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Agentic%20Trading%20Pic.png',
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Agentic%20Trading%20Pic.png',
        ogImage: 'https://yanqinghot.blob.core.windows.net/public-access/Agentic%20Trading%20Pic.png',
        seoTitle: 'Agentic Trading Bot | LangGraph + IBKR Automation',
        seoDescription:
          'LangGraph multi-agent trading bot connecting IBKR execution, Unusual Whales flow, and Morningstar insights to size trades and achieve a 200% supervised gain.',
        seoKeywords: [
          'agentic trading bot',
          'LangGraph automation',
          'IBKR API',
          'options flow intelligence',
          'AI trading copilot',
        ],
        datePublished: '2025-05-10',
        dateModified: '2025-09-12',
        serviceTags: ['Agentic Trading', 'Automation', 'Risk Management'],
        statHighlights: [
          'Delivered a 200% realized gain on SOUN puts before shutdown safeguards triggered',
          'Combines quant, trend, sizing, and execution agents orchestrated through LangGraph',
        ],
        primaryMetricValue: {
          label: 'Pilot gain',
          value: 200,
          unitText: 'Percent',
        },
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
        description: `Real-time financial data analysis with direct SQL generation and execution.
Streamlined workflow covering query analysis, SQL generation, chart creation, and insight delivery.
High-performance data processing with immediate insights and responsive visualizations.

Result:

Interactive financial analysis for AMD, AVGO, INTC, MU, NVDA, QCOM, TXN with optimized performance.
Real-time streaming analytics with comprehensive charting and data export.
Direct database queries enable intelligent chart generation and detailed financial commentary.`,
        cardDescription: '5-second query-to-insight streaming SQL copilot for semiconductor coverage.',
        technologies: ['Agentic Workflow', 'LangGraph', 'State Management', 'RAG', 'Smart SQL'],
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
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png',
        ogImage: 'https://yanqinghot.blob.core.windows.net/public-access/next-gen-sql.png',
        seoTitle: 'Next Gen Analytics SQL Copilot | LangGraph Streaming Insights',
        seoDescription:
          'Streaming SQL copilot that pairs LangGraph orchestration with Supabase analytics to generate charts, commentary, and comparisons for semiconductor tickers in real time.',
        seoKeywords: [
          'analytics sql copilot',
          'LangGraph workflow',
          'Supabase financial data',
          'RAG SQL agent',
          'streaming analytics app',
        ],
        datePublished: '2024-11-15',
        dateModified: '2025-08-20',
        serviceTags: ['Analytics Automation', 'SQL Generation', 'Visualization'],
        statHighlights: [
          'Auto-compares semiconductor tickers with streaming commentary and ECharts visualizations',
          'LangGraph state machine coordinates schema, SQL, visualization, and narrative agents',
        ],
        primaryMetricValue: {
          label: 'Query-to-insight latency',
          value: 5,
          unitText: 'Seconds',
        },
      },
      {
        id: 'llm-invoice-processor',
        title: 'LLM Invoice Processor',
        description: `• Accounting team struggled to validate invoices with complex parent-child item numbers.\n• Millions of dollars in invoices were delayed or unpaid due to mismatches.\n\nResult:\n\n• Automates 1,000+ hours of manual work every year.\n• Dramatically reduces late payment rate by 90%.`,
        cardDescription: 'Automates 1,000 analyst hours and slashes late payments 90% with PDF-to-ledger reconciliation.',
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
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Deal%20Matching%20GIF',
        seoTitle: 'LLM Invoice Processor | Multi-Format Automation Copilot',
        seoDescription:
          'Production LLM invoice processor that parses PDFs/XLSB files, reconciles parent-child items, and auto-generates discrepancy reports saving 1,000+ hours every year.',
        seoKeywords: [
          'invoice automation',
          'LLM function calling',
          'Azure blob storage',
          'LangChain matching',
          'finance workflow automation',
        ],
        datePublished: '2024-08-12',
        dateModified: '2025-07-20',
        serviceTags: ['Data Automation', 'Document AI', 'Finance Operations'],
        statHighlights: [
          'Automates 1,000+ analyst hours annually across P&G Walgreens teams',
          'Reduces late payment rate by roughly 90% through automated discrepancy reports',
        ],
        primaryMetricValue: {
          label: 'Manual hours removed',
          value: 1000,
          unitText: 'Hours per year',
        },
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
        cardDescription: '95% resume coverage answers recruiter questions with citations in seconds.',
        technologies: ['RAG', 'Vector Search', 'FAISS', 'Agent'],
        systemInstruction: "Hello, I am Yanqing's AI assistant. I have access to his resume data. Please ask me any questions you would have as a hiring manager.",
        defaultPrompts: [
            "How have you used advanced analytics to drive measurable business outcomes in your recent roles?",
            "Can you share an example where you led a cross-functional team to solve a complex business problem using data",
          "What's your approach to developing scalable data or AI solutions that align with business goals?",
        ],
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Yanqing%20Exp%20Retrival.png',
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Yanqing%20Exp%20Retrival.png',
        seoTitle: 'Ask My Resume | RAG Career Copilot',
        seoDescription:
          'Retrieval-augmented resume agent that embeds roles and projects, answers hiring questions, and advocates with evidence-backed responses.',
        seoKeywords: [
          'career rag agent',
          'resume chatbot',
          'LangChain vector search',
          'FAISS retrieval',
          'AI interview copilot',
        ],
        datePublished: '2023-09-01',
        dateModified: '2025-07-15',
        serviceTags: ['RAG', 'Talent AI', 'Personal Branding'],
        statHighlights: [
          'Vector store ingestion of resume sections and case studies via LangChain',
          'Delivers recruiter-ready answers with embedded citations and follow-ups',
        ],
        primaryMetricValue: {
          label: 'Resume response coverage',
          value: 95,
          unitText: 'Percent',
        },
      },
      {
        id: 'goggins-gpt',
        title: 'Goggins GPT',
        description: `Inspired by David Goggins and the surge of “AI companion” apps (Character AI).\n• Purpose: create a personal drill-sergeant that shouts no-excuse motivation on demand.\n• Voice: ElevenLabs multilingual-v2 model streams real-time TTS.\n• Click "Unleash Goggins Mode" to try it out!`,
        cardDescription: 'Hear Goggins motivate you in real time! Activate Goggins Mode to try!',
        technologies: ['Gemini API', 'Prompt Engineering', 'ElevenLabs', 'State Management'],
        systemInstruction: `You created “Goggins GPT”. You'll answer as "I".  Provide clear, concise answers about: \n• Architecture & tech stack – React&nbsp;+ Tailwind&nbsp;+ Framer-Motion on the client, FastAPI backend, Gemini Flash LLM via Google GenAI SDK, and ElevenLabs multilingual-v2 TTS for the voice. \n• Data flow – chat → Gemini → FastAPI /api/tts → audio stream to browser. \n• Motivation – born from the trend of "AI girlfriends"/Character AI, but pivoted to embody David Goggins’ mindset so users get hardcore motivation instead of coddling. \n• Features – toggleable Goggins Mode (system prompt swap), real-time speech, animated UI, message history. \nWhen asked, emphasise how Goggins Mode loads a different system instruction and triggers TTS playback.`,
        defaultPrompts: [
            "Tell me about what inspired you to create this project.",
            "What is 'Goggins Mode' and how is it implemented?",
            "Who is David Goggins?",
        ],
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/David%20Goggins.png',
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Goggins%20GPT%20Diagram',
        seoTitle: 'Goggins GPT | Motivational Companion with Gemini + ElevenLabs',
        seoDescription:
          'Voice-enabled motivational companion that streams Gemini responses through ElevenLabs while toggling “Goggins Mode” prompts for no-excuse coaching.',
        seoKeywords: [
          'motivational ai companion',
          'Gemini flash chatbot',
          'ElevenLabs streaming',
          'Goggins mode prompt',
          'react fastapi voice agent',
        ],
        datePublished: '2023-06-20',
        dateModified: '2025-07-05',
        serviceTags: ['Conversational AI', 'Voice Agent', 'Motivation'],
        statHighlights: [
          'Realtime Gemini-to-ElevenLabs speech with animated UI and message history',
          'Toggleable Goggins Mode swaps prompts to yield drill-sergeant coaching',
        ],
        primaryMetricValue: {
          label: 'Concurrent listeners supported',
          value: 200,
          unitText: 'Sessions',
        },
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
            cardDescription: 'Pre-Perplexity (2022) web research agent pairing Serper search with Browserless scraping for live briefs.',
            technologies: ['Serper API', 'Browserless Scraping', 'Lang Chain Agent', 'Memory Chain', 'OpenAI API'],
            systemInstruction: 'You are the "Research GPT" AI. You are a powerful research agent connected to a live backend. When a user gives you a research topic, you will use your tools to browse the internet, gather information, and provide a comprehensive, fact-based answer. Your capabilities are powered by LangChain and the OpenAI API, running on a custom FastAPI server. Start by asking the user what they would like to research.',
            defaultPrompts: [
                "What is the best reasoning large language model right now?",
                "Make some suggestions for vibe coding.",
                "What are some of the latest trends in LLMs?"
            ],
            coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/research%20GPT%20Diagram.png',
            imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/research%20GPT%20Diagram.png',
            seoTitle: 'Research GPT | Early LangChain Web Research Agent',
            seoDescription:
              'LangChain research agent (pre-Perplexity) combining Serper search, Browserless scraping, and summarization loops for timely briefs.',
            seoKeywords: [
              'LangChain research agent',
              'Serper API search',
              'Browserless scraping',
              'LLM memoization',
              'research copilot',
            ],
            datePublished: '2022-10-05',
            dateModified: '2025-07-10',
            serviceTags: ['Research Automation', 'Web Browsing', 'LangChain'],
            statHighlights: [
              'Automates Serper search + Browserless scraping with summarization loops',
              'Captures memoized context for iterative research conversations',
            ],
            primaryMetricValue: {
              label: 'Sources summarized per query',
              value: 8,
              unitText: 'Articles',
            },
        }
    ]
  },
  {
    year: 2021,
    label: 'Pre-AI Projects',
    hiddenOnLanding: true,
    projects: [
      {
        id: 'global-inventory-dashboard',
        title: 'Global Inventory Dashboard',
        description: 'Power BI control tower that consolidates 20+ regional inventory reports with action cards and a Dataflow pipeline so leaders resolve stock risks in minutes.',
        technologies: ['Power BI', 'Supply Chain Analytics', 'Data Automation'],
        systemInstruction: 'You are the assistant for the Global Inventory Dashboard project. Explain how the control tower unifies worldwide inventory data, which KPIs matter, and how action cards accelerate mitigation.',
        defaultPrompts: [
          'How does the dashboard keep global inventory teams aligned?',
          'What reports sit behind the action cards?',
          'Describe the business impact of consolidating 20+ sub-reports.'
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Inventory%20Dashboard/Global-Inventory-Dashboard.png',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Inventory%20Dashboard/Global-Inventory-Dashboard.png',
        link: 'https://www.jiangyanqing.com/portfolio/global-inventory-dashboard/',
        contentHtml: `<div class="inventory-content">
          <p><em>*Real project, hence sensitive data is blurred.</em></p>
          <img class="inventory-main" src="https://yanqinghot.blob.core.windows.net/public-access/Inventory%20Dashboard/Global-Inventory-Dashboard.png" alt="Global Inventory Dashboard overview" loading="lazy" />
          <div class="inventory-row">
            <img class="inventory-sidebar" src="https://yanqinghot.blob.core.windows.net/public-access/Inventory%20Dashboard/side%20bar.gif" alt="Inventory navigation sidebar animation" loading="lazy" />
            <div class="inventory-text">
              <h3>Global Inventory Dashboard Power BI report</h3>
              <h4>Features</h4>
              <ul>
                <li>One main dashboard with 20+ sub reports that users can navigate inline.</li>
                <li>"Actions Comment" block highlights mitigation steps whenever a KPI turns red.</li>
                <li>Built-in definitions keep KPIs transparent for every stakeholder.</li>
              </ul>
              <h3>Back-end Data Processing</h3>
              <p>PBIX dataset -> Power BI Dataflow (Cloud) -> unified SQL queries across multiple databases. The Dataflow approach bypasses the 2 GB PBIX limit and lets other teams reuse the curated schema.</p>
            </div>
          </div>
        </div>`,
        seoTitle: 'Global Inventory Control Tower | Power BI & Dataflow Automation',
        seoDescription:
          'Power BI control tower consolidating 20+ regional inventory feeds, action cards, and Dataflow automation so leaders mitigate stock risks within minutes.',
        seoKeywords: [
          'inventory dashboard',
          'power bi control tower',
          'supply chain analytics',
          'dataflow automation',
          'action card workflow',
        ],
        datePublished: '2021-10-01',
        dateModified: '2025-07-01',
        serviceTags: ['Supply Chain Analytics', 'BI Automation', 'Data Governance'],
        statHighlights: [
          'Consolidates 20+ regional reports into a single Power BI control tower',
          'Action cards capture risk mitigations and reduce executive response time to minutes',
        ],
        primaryMetricValue: {
          label: 'Regional reports unified',
          value: 20,
          unitText: 'Reports',
        },
      },
      {
        id: 'time-series-forecasting-pre',
        title: 'R Time Series Forecasting',
        description: 'Automated R scripts embedded in Power BI compare seven forecasting models, benchmark accuracy, and publish demand outlooks straight to stakeholders.',
        technologies: ['Power BI', 'R', 'Forecasting'],
        systemInstruction: 'You speak for the R Time Series Forecasting project. Focus on the modeling pipeline, accuracy benchmarking, and how results surface inside Power BI for merchandisers.',
        defaultPrompts: [
          'Which forecasting models are compared in this solution?',
          'How are the R scripts operationalized inside Power BI?',
          'What decisions do merchandisers make with the forecasts?'
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/R-Time-Series/R-Script-1.gif',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/R-Time-Series/R-Script-1.gif',
        link: 'https://www.jiangyanqing.com/portfolio/machine-learning-forecasting-visual/',
        contentHtml: `<div class='legacy-content'>
          <img class='legacy-hero' src='https://yanqinghot.blob.core.windows.net/public-access/R-Time-Series/R-dashboard.png' alt='R Time Series dashboard overview' loading='lazy' />
          <p><em>*Real project, hence sensitive data is removed.</em></p>
          <h3>Power BI Report: Advanced R Visualization</h3>
          <ul>
            <li>Custom R visuals embedded in Power BI Service with fully automated refresh.</li>
            <li>No manual steps-forecasts and visuals ship straight to decision makers.</li>
          </ul>
          <h3>Time Series Forecasting</h3>
          <p>The solution benchmarks seven models (Naive, SES, Holt&apos;s, Auto ARIMA, TBATS, Prophet, Neural Network) on 90-day holdout data and promotes the best performer before forecasting the next 90 days.</p>
          <img class='legacy-hero' src='https://yanqinghot.blob.core.windows.net/public-access/R-Time-Series/R-Script-1.gif' alt='R Time Series Forecasting' loading='lazy' />
          <p>Additional Power BI reports reuse the same R pipeline for broader analytics.</p>
          <div class='legacy-gallery'>
            <img src='https://yanqinghot.blob.core.windows.net/public-access/R-Time-Series/PBI%20advance%20forecasting.png' alt='Power BI advanced forecasting report' loading='lazy' />
          </div>
        </div>`,
        seoTitle: 'R Time Series Forecasting | Power BI + Embedded R Models',
        seoDescription:
          'Automated R forecasting pipeline embedded in Power BI to benchmark seven models, refresh results, and publish demand outlooks directly to merchandisers.',
        seoKeywords: [
          'time series forecasting',
          'Power BI R scripts',
          'Auto ARIMA',
          'Prophet forecasting',
          'demand planning automation',
        ],
        datePublished: '2021-05-01',
        dateModified: '2025-06-20',
        serviceTags: ['Forecasting', 'Analytics Automation', 'Power BI'],
        statHighlights: [
          'Benchmarks seven time-series models and deploys best performer per SKU',
          'Automated Power BI refresh pushes forecasts directly into decision workflows',
        ],
        primaryMetricValue: {
          label: 'Models benchmarked',
          value: 7,
          unitText: 'Models',
        },
      },
      {
        id: 'supplier-review-system',
        title: 'All-in-One Supplier Review System',
        description: 'Interactive Power BI workspace for conducting supplier scorecards, capturing review notes, and sharing results with stakeholders in real time.',
        technologies: ['Power BI', 'Supplier Management', 'Automation'],
        systemInstruction: 'You summarize the All-in-One Supplier Review System. Highlight the review workflow, collaboration features, and how data refresh keeps stakeholders aligned.',
        defaultPrompts: [
          'Walk me through a supplier review inside the tool.',
          'How does the system collect qualitative feedback?',
          'What automation keeps data current for stakeholders?'
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/supplier-review-system/Email-PDF-Blurred-pbi.gif',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/supplier-review-system/Email-PDF-Blurred-pbi.gif',
        link: 'https://www.jiangyanqing.com/portfolio/all-in-one-supplier-review-system/',
        contentHtml: `<div class="legacy-content">
          <p><em>*Real project, hence sensitive data is blurred.</em></p>
          <h3>Technology Stack</h3>
          <p>Power BI + Power Automate + Power Apps + SharePoint power an interactive supplier assessment workspace.</p>
          <h3>What's Included</h3>
          <ul>
            <li>Excel-like input experience with live data updates.</li>
            <li>Supplier reviews, notes, and PDF scorecards generated from one screen.</li>
            <li>Periodic business review and email automation functions built in.</li>
          </ul>
          <img class="legacy-hero" src="https://yanqinghot.blob.core.windows.net/public-access/supplier-review-system/Email-PDF-Blurred-pbi.gif" alt="Supplier review automation workflow" loading="lazy" />        </div>`,
        seoTitle: 'Supplier Review System | Power BI + Power Platform Workflow',
        seoDescription:
          'Supplier review cockpit combining Power BI, Automate, and Apps for live scorecards, qualitative notes, and automated PDF/email distribution.',
        seoKeywords: [
          'supplier review automation',
          'power platform workflow',
          'Power BI scorecards',
          'Power Automate email',
          'procurement analytics',
        ],
        datePublished: '2021-04-10',
        dateModified: '2025-06-20',
        serviceTags: ['Procurement Automation', 'Power Platform', 'Collaboration'],
        statHighlights: [
          'Generates PDF scorecards and automated emails directly from Power BI workspace',
          'Converges qualitative notes, KPIs, and supplier actions in one dashboard',
        ],
        primaryMetricValue: {
          label: 'Scorecards automated',
          value: 150,
          unitText: 'Per quarter',
        },
      },
      {
        id: 'capex-project-tracker',
        title: 'Capex Project Application',
        description: 'One-stop Power Apps style tracker that manages project headers and line items with a shopping-cart approval flow for capital investments.',
        technologies: ['Power Apps', 'Project Management', 'Process Automation'],
        systemInstruction: 'You represent the Capex Project Application. Explain the shopping-cart intake pattern, approval automation, and how finance and procurement use the data.',
        defaultPrompts: [
          'How does the shopping-cart workflow improve Capex approvals?',
          'Which teams rely on the tracker day to day?',
          'Describe the data captured for each Capex line item.'
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/capex-tracker/Capex-Project.gif',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/capex-tracker/Capex-Project.gif',
        link: 'https://www.jiangyanqing.com/portfolio/capex-project-tracker/',
        contentHtml: `<div class="legacy-content">
          <p><em>*Real project, hence sensitive data is blurred.</em></p>
          <h3>Capex Project Application Highlights</h3>
          <ul>
            <li>One-stop Power Apps experience that blends project headers and line items.</li>
            <li>Shopping-cart intake pattern streamlines approvals for capital requests.</li>
            <li>Full data pipeline ends in Power BI reporting for finance and procurement.</li>
          </ul>
          <img class="legacy-hero" src="https://yanqinghot.blob.core.windows.net/public-access/capex-tracker/Capex-Project.gif" alt="Capex request intake workflow" loading="lazy" />
          <img class="legacy-hero" src="https://yanqinghot.blob.core.windows.net/public-access/capex-tracker/BC-Approval-Flow2.png" alt="Business case approval flow" loading="lazy" />
          <img class="legacy-hero" src="https://yanqinghot.blob.core.windows.net/public-access/capex-tracker/Power%20Automate.png" alt="Power Automate automation overview" loading="lazy" />
        </div>`,
        seoTitle: 'Capex Project Tracker | Power Apps Intake & Approval Automation',
        seoDescription:
          'Power Apps tracker that merges headers and line items, introduces shopping-cart style approvals, and feeds Power BI for capital planning alignment.',
        seoKeywords: [
          'capex intake automation',
          'Power Apps workflow',
          'Power Automate approvals',
          'capital project tracker',
          'finance process automation',
        ],
        datePublished: '2021-02-15',
        dateModified: '2025-06-20',
        serviceTags: ['Power Platform', 'Capital Planning', 'Workflow Automation'],
        statHighlights: [
          'Shopping-cart approvals reduce finance turnaround time for capital requests',
          'Power BI pipeline shares intake, approvals, and spend with finance/procurement',
        ],
        primaryMetricValue: {
          label: 'Approval workflow steps automated',
          value: 12,
          unitText: 'Steps',
        },
      },
      {
        id: 'engagement-intake-pre',
        title: 'All-in-One Engagement Intake',
        description: 'Complex Power Platform intake portal with thousands of business rules that orchestrates procurement engagement requests end to end.',
        technologies: ['Power Platform', 'Workflow Automation', 'Procurement'],
        systemInstruction: 'You speak for the All-in-One Engagement Intake project. Cover the scale of business rules, user adoption metrics, and how approvals are automated.',
        defaultPrompts: [
          'How many teams input work through Engagement Intake?',
          'What kinds of rules govern an intake submission?',
          'Explain how approvals and downstream reporting are automated.'
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/engagement-tracker/Engagement-Intake.gif',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/engagement-tracker/Engagement-Intake.gif',
        link: 'https://www.jiangyanqing.com/portfolio/all-in-one-engagement-intake/',
        contentHtml: `<div class="legacy-content">
          <p>All-in-one Engagement Intake orchestrates procurement submissions with thousands of embedded business rules.</p>
          <ul>
            <li>Serves two procurement departments with 100-200 daily users.</li>
            <li>Automates approvals and notifications-no more hand-typed emails.</li>
            <li>Feeds Power BI Dataflows so downstream stakeholders can monitor progress.</li>
          </ul>
          <img class="legacy-hero" src="https://yanqinghot.blob.core.windows.net/public-access/engagement-tracker/Engagement-Intake.gif" alt="Engagement intake workflow overview" loading="lazy" />
          <p>The original portfolio showcases process screenshots covering intake states, approvals, and reporting.</p>
          <img class="legacy-hero" src="https://yanqinghot.blob.core.windows.net/public-access/engagement-tracker/Business%20Case%20Approval%20Flow%20Chart.png" alt="Business case approval flow" loading="lazy" />
          <img class="legacy-hero" src="https://yanqinghot.blob.core.windows.net/public-access/engagement-tracker/after-reject.png" alt="Post-rejection automation workflow" loading="lazy" />
        </div>`,
        seoTitle: 'Engagement Intake Portal | Power Platform Business Rules Automation',
        seoDescription:
          'Power Platform portal enforcing thousands of procurement business rules, orchestrating approvals, and syncing status to Power BI dataflows for 100–200 daily users.',
        seoKeywords: [
          'procurement intake automation',
          'Power Platform portal',
          'business rule engine',
          'Power Automate approvals',
          'Power BI dataflows',
        ],
        datePublished: '2021-03-10',
        dateModified: '2025-06-20',
        serviceTags: ['Procurement Automation', 'Workflow Platform', 'Business Rules'],
        statHighlights: [
          'Serves two procurement departments with 100-200 daily active submitters',
          'Thousands of business rules drive automatic approvals and downstream notifications',
        ],
        primaryMetricValue: {
          label: 'Daily procurement users',
          value: 200,
          unitText: 'Users',
        },
      },
    ],
  },
];













