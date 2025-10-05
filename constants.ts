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
        coverUrl: 'http://jiangyanqing.com/wp-content/uploads/2021/10/15FA1F15-25C5-4AE6-A84A-EB5972FB0996.gif',
        imageUrl: 'http://jiangyanqing.com/wp-content/uploads/2021/10/15FA1F15-25C5-4AE6-A84A-EB5972FB0996.gif',
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
        </div>`
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
        </div>`
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
        coverUrl: 'https://www.jiangyanqing.com/wp-content/uploads/2021/10/02Q2JyM7Iq3t8rFTddlZMxa-7.1569482292.fit_scale.size_760x427-300x169.jpg',
        imageUrl: 'https://www.jiangyanqing.com/wp-content/uploads/2021/10/02Q2JyM7Iq3t8rFTddlZMxa-7.1569482292.fit_scale.size_760x427-300x169.jpg',
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
          <div class="legacy-gallery">
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Add-Comment-Blurred.gif" alt="Supplier review comment workflow" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Periodic-Business-Review-Blurred.gif" alt="Periodic business review automation" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Email-PDF-Blurred.gif" alt="Automated PDF email delivery" loading="lazy" />
          </div>
        </div>`
      },
      {
        id: 'capex-project-tracker',
        title: 'Capex Project Tracker',
        description: 'One-stop Power Apps style tracker that manages project headers and line items with a shopping-cart approval flow for capital investments.',
        technologies: ['Power Apps', 'Project Management', 'Process Automation'],
        systemInstruction: 'You represent the Capex Project Tracker. Explain the shopping-cart intake pattern, approval automation, and how finance and procurement use the data.',
        defaultPrompts: [
          'How does the shopping-cart workflow improve Capex approvals?',
          'Which teams rely on the tracker day to day?',
          'Describe the data captured for each Capex line item.'
        ],
        coverUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Capex-Project-Tracker-Showcase-1.gif',
        imageUrl: 'https://yanqinghot.blob.core.windows.net/public-access/Capex-Project-Tracker-Showcase-1.gif',
        link: 'https://www.jiangyanqing.com/portfolio/capex-project-tracker/',
        contentHtml: `<div class="legacy-content">
          <p><em>*Real project, hence sensitive data is blurred.</em></p>
          <h3>Capex Project Tracker Highlights</h3>
          <ul>
            <li>One-stop Power Apps experience that blends project headers and line items.</li>
            <li>Shopping-cart intake pattern streamlines approvals for capital requests.</li>
            <li>Full data pipeline ends in Power BI reporting for finance and procurement.</li>
          </ul>
          <div class="legacy-gallery">
            <img src="https://yanqinghot.blob.core.windows.net/public-access/Capex-Project-Tracker-Showcase-1.gif" alt="Capex request intake workflow" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/2021-10-09_18-35-28-1024x578.png" alt="Capital approval summary dashboard" loading="lazy" />
          </div>
        </div>`
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
        coverUrl: 'https://www.jiangyanqing.com/wp-content/uploads/2021/10/Untitled1-300x177.png',
        imageUrl: 'https://www.jiangyanqing.com/wp-content/uploads/2021/10/Untitled1-300x177.png',
        link: 'https://www.jiangyanqing.com/portfolio/all-in-one-engagement-intake/',
        contentHtml: `<div class="legacy-content">
          <p>All-in-one Engagement Intake orchestrates procurement submissions with thousands of embedded business rules.</p>
          <ul>
            <li>Serves two procurement departments with 100-200 daily users.</li>
            <li>Automates approvals and notifications-no more hand-typed emails.</li>
            <li>Feeds Power BI Dataflows so downstream stakeholders can monitor progress.</li>
          </ul>
          <p>The original portfolio showcases process screenshots covering intake states, approvals, and reporting.</p>
          <div class="legacy-gallery">
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Engagement-Intake.gif" alt="Engagement intake workflow overview" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Untitled1-300x177.png" alt="Intake landing experience" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Untitled2-300x177.png" alt="Submission routing rules" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Untitled3-300x177.png" alt="Work queue monitoring" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Untitled4-300x182.png" alt="Approval escalations" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/Untitled5-300x179.png" alt="Status dashboards" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/10/2021-10-09_18-45-10-300x166.png" alt="Request detail view" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/12/BC-Approval-Flow-300x167.png" alt="Business case approval flow" loading="lazy" />
            <img src="https://www.jiangyanqing.com/wp-content/uploads/2021/12/Process-Overview-300x170.png" alt="Process overview diagram" loading="lazy" />
          </div>
        </div>`
      },
    ],
  },
];

