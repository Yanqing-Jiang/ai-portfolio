---
name: agent-browser
description: Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, test web applications, or extract information from web pages.
allowed-tools: Bash(agent-browser:*)
---

# Browser Automation with agent-browser

## Project URLs (Direct Navigation)

Base: `http://localhost:5173`

### A2UI (Current Project) ⭐
| Page | URL | Notes |
|------|-----|-------|
| Dashboard | `/project/agent-to-ui` | Main A2UI demo page |
| Query input ref | `@e13` | Textbox for queries |
| Generate button ref | `@e14` | Triggers AI analysis |
| New Query button | `@e35` | Reset for new query |

### Other Projects
| Project | URL |
|---------|-----|
| Headshot Studio | `/project/linkedin-photo` |
| Next Gen Analytics (Agents) | `/project/next-gen-analytics-agent` |
| Agentic Trading Bot | `/project/agentic-trade-bot` |
| Next Gen Analytics (SQL) | `/project/next-gen-analytics-sql` |
| LLM Invoice Processor | `/project/llm-invoice-processor` |
| Ask My Resume | `/project/ask-my-resume` |
| Goggins GPT | `/project/goggins-gpt` |
| Research GPT | `/project/research-gpt` |

---

## A2UI Quick Tests ⭐

### ⚡ FASTEST: Single-Command Test (Recommended)
```bash
# Complete A2UI test in ONE command (no setup needed if chromium installed)
agent-browser --session test open http://localhost:5173/project/agent-to-ui && agent-browser --session test wait 2000 && agent-browser --session test snapshot -i -c && agent-browser --session test fill @e13 "Compare NVDA to AMD" && agent-browser --session test click @e14 && agent-browser --session test wait 8000 && agent-browser --session test snapshot -c && agent-browser --session test close
```

### Test 1: Basic Dashboard Load
```bash
agent-browser open http://localhost:5173/project/agent-to-ui --headed && agent-browser wait 2000 && agent-browser snapshot -i -c
```

### Test 2: Query + Verify Widgets (Peer Compare)
```bash
# After Test 1, refs are: @e13=textbox, @e14=Generate button
agent-browser fill @e13 "Compare AMD vs NVDA" && agent-browser click @e14 && agent-browser wait 8000 && agent-browser snapshot -c
# Look for: "Generated X valid components" in backend logs
# Look for: "Swap visualization" buttons in snapshot = widgets rendered
```

### Test 3: Query Flow (Revenue Trend)
```bash
agent-browser fill @e13 "NVDA revenue trend" && agent-browser click @e14 && agent-browser wait 8000 && agent-browser snapshot -c
```

### Test 4: Query Flow (Margin Analysis)
```bash
agent-browser fill @e13 "AMD margin analysis" && agent-browser click @e14 && agent-browser wait 8000 && agent-browser snapshot -c
```

### Test 5: Query Flow (Explain Move)
```bash
agent-browser fill @e13 "Why did NVDA drop?" && agent-browser click @e14 && agent-browser wait 8000 && agent-browser snapshot -c
```

### Test 6: Cleanup
```bash
agent-browser close
```

### A2UI Sample Queries
- `"NVDA revenue trend"` - Revenue Trend skill
- `"Compare AMD vs NVDA"` - Peer Compare skill
- `"AMD margin analysis"` - Margin Analysis skill
- `"Why did NVDA drop?"` - Explain Move skill
- `"Show me what you can do"` - Feature Showcase skill

### ✅ Verify A2UI Widget Rendering Fix
Check backend logs for success indicators:
```bash
# In backend terminal, look for:
# ✅ SUCCESS: "[LLM_GENERATOR] Generated 6 valid components"
# ❌ FAILURE: "No components found for types"

# In browser snapshot, look for:
# ✅ SUCCESS: Multiple "Swap visualization" buttons
# ❌ FAILURE: No widget buttons, only error text
```

### 🔄 Test Swap/Revert Flow (Component Swap Bug Testing)
```bash
# 1. Generate dashboard and find KPI values
agent-browser --session swap open http://localhost:5173/project/agent-to-ui
agent-browser --session swap fill 'textbox[placeholder*="Ask"]' "AMD revenue trend"
agent-browser --session swap click 'button:has-text("Generate")'
agent-browser --session swap wait 10000
agent-browser --session swap snapshot -c | head -60
# Note the KPI values (e.g., "58.458", "9,246,000,128")

# 2. Click a Swap visualization button (find ref from snapshot)
agent-browser --session swap click @e25  # Adjust ref based on snapshot
agent-browser --session swap wait 500
agent-browser --session swap snapshot -i -c  # Look for menu items

# 3. Click swap option (e.g., "Metric Chart")
agent-browser --session swap click @e18  # menuitem ref
agent-browser --session swap wait 500
agent-browser --session swap click 'button:has-text("Apply")'  # Or click Apply button
agent-browser --session swap wait 1000

# 4. Revert and verify value preserved
agent-browser --session swap click 'button:has-text("Revert")'
agent-browser --session swap wait 500
agent-browser --session swap click 'menuitem:has-text("Revert to KPI")'
agent-browser --session swap wait 1000
agent-browser --session swap snapshot -c | head -60
# ✅ SUCCESS: KPI shows original value (e.g., "58.458")
# ❌ FAILURE: KPI shows "0" after revert

# 5. Cleanup
agent-browser --session swap close
```

---

## Speed Tips (IMPORTANT)

1. **Chain with `&&`** - Multiple commands in one bash call = faster
2. **ONE snapshot per page** - Don't re-snapshot unless page reloads/navigates
3. **Direct URL** - Use URLs above, faster than clicking SPA links
4. **Batch interactions** - `fill @e1 "a" && fill @e2 "b" && click @e3`
5. **Skip verbose waits** - `wait 2000-4000` is usually enough

## ⚡ Quick Start

```bash
# Most commands just work:
agent-browser open http://localhost:5173/project/agent-to-ui && agent-browser snapshot -i -c
```

## 🔧 First-Time Setup / Version Mismatch Fix

If you see `Executable doesn't exist at chromium-XXXX`:

```bash
# Option 1: Install latest chromium (RECOMMENDED)
npx playwright@latest install chromium
# This installs the version agent-browser expects

# Option 2: Use existing chromium (macOS)
ls ~/Library/Caches/ms-playwright/ | grep chromium
# Find available version (e.g., chromium-1208), then:
agent-browser close  # Close daemon first!
agent-browser --executable-path ~/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium open <url>
```

## 🔄 Session Best Practices

```bash
# Use named sessions for isolation
agent-browser --session mytest open <url>
agent-browser --session mytest snapshot -i -c
agent-browser --session mytest close  # Always close when done!

# If connection timeout (os error 10060), just retry:
agent-browser --session mytest click @e1  # Retry same command
```

## 🔄 Daemon Management

```bash
agent-browser close              # MUST close before changing --executable-path
agent-browser session            # Show current session
agent-browser session list       # List all active sessions
```

**Important**: Daemon caches settings. If changing `--executable-path`, `--headed`, or `--profile`, close first.

## ☁️ Cloud Browser Providers

Run browsers in the cloud (no local installation needed):

```bash
# Browserbase (requires BROWSERBASE_API_KEY + BROWSERBASE_PROJECT_ID)
agent-browser -p browserbase open https://example.com

# Browser Use (requires BROWSER_USE_API_KEY)
agent-browser -p browseruse open https://example.com

# Or set env var
export AGENT_BROWSER_PROVIDER=browserbase
```

## 🔌 CDP Mode (Connect to Existing Browser)

Control existing Chrome/Electron instances via DevTools Protocol:

```bash
# Connect via port
agent-browser --cdp 9222 snapshot

# Connect via WebSocket URL
agent-browser --cdp ws://localhost:9222/devtools/browser/xxx open https://example.com

# Launch Chrome with debugging port first:
# chrome --remote-debugging-port=9222
```

## 📡 WebSocket Streaming (Live Preview)

Enable real-time browser streaming for human-AI pair browsing:

```bash
export AGENT_BROWSER_STREAM_PORT=9223
agent-browser open https://example.com --headed

# Connect viewer to ws://localhost:9223 for live JPEG frames
# Supports mouse, keyboard, touch event injection via JSON payloads
```

## 🔐 Authenticated Headers

Set origin-scoped HTTP headers (useful for API tokens, auth bypass):

```bash
# Headers apply only to matching origin
agent-browser --headers '{"Authorization": "Bearer token123"}' open https://api.example.com

# Combine with profile for persistent auth
agent-browser --profile ~/.myapp --headers '{"X-API-Key": "secret"}' open https://app.com
```

## 🌐 Proxy Configuration

```bash
# Basic proxy
agent-browser --proxy "http://127.0.0.1:8080" open https://example.com

# Authenticated proxy
agent-browser --proxy "http://user:pass@proxy.example.com:8080" open https://example.com

# Bypass proxy for specific hosts
agent-browser --proxy "http://proxy:8080" --proxy-bypass "localhost,*.internal.com" open https://example.com

# Or use env vars
export AGENT_BROWSER_PROXY="http://proxy:8080"
export AGENT_BROWSER_PROXY_BYPASS="localhost"
```

## 🔧 All Environment Variables

| Variable | Description |
|----------|-------------|
| `AGENT_BROWSER_SESSION` | Session name (default: "default") |
| `AGENT_BROWSER_PROFILE` | Persistent browser profile path |
| `AGENT_BROWSER_EXECUTABLE_PATH` | Custom browser binary path |
| `AGENT_BROWSER_ARGS` | Browser launch args (comma-separated) |
| `AGENT_BROWSER_USER_AGENT` | Custom User-Agent string |
| `AGENT_BROWSER_PROXY` | Proxy server URL |
| `AGENT_BROWSER_PROXY_BYPASS` | Hosts to bypass proxy |
| `AGENT_BROWSER_PROVIDER` | Cloud provider (browserbase/browseruse) |
| `AGENT_BROWSER_STREAM_PORT` | WebSocket streaming port |

## Core workflow

1. Navigate: `agent-browser open <url> --headed`
2. Snapshot ONCE: `agent-browser snapshot -i` (returns refs like `@e1`, `@e2`)
3. Chain all interactions: `agent-browser fill @e1 "text" && agent-browser click @e2`
4. Screenshot + close: `agent-browser screenshot path.png && agent-browser close`

## Best practices

- **Chain commands with `&&`** - ALWAYS chain to reduce round-trips
- **Direct URL navigation** - Use project URLs table above
- **Always close browser** when done: `agent-browser close`
- **Minimal snapshots** - Only re-snapshot if page structure changes

## Commands

### Navigation
```bash
agent-browser open <url>      # Navigate to URL
agent-browser back            # Go back
agent-browser forward         # Go forward
agent-browser reload          # Reload page
agent-browser close           # Close browser
```

### Snapshot (page analysis)
```bash
agent-browser snapshot            # Full accessibility tree
agent-browser snapshot -i         # Interactive elements only (recommended)
agent-browser snapshot -c         # Compact output
agent-browser snapshot -d 3       # Limit depth to 3
agent-browser snapshot -s "#main" # Scope to CSS selector
```

### Interactions (use @refs from snapshot)
```bash
agent-browser click @e1           # Click
agent-browser dblclick @e1        # Double-click
agent-browser focus @e1           # Focus element
agent-browser fill @e2 "text"     # Clear and type
agent-browser type @e2 "text"     # Type without clearing
agent-browser press Enter         # Press key
agent-browser press Control+a     # Key combination
agent-browser keydown Shift       # Hold key down
agent-browser keyup Shift         # Release key
agent-browser hover @e1           # Hover
agent-browser check @e1           # Check checkbox
agent-browser uncheck @e1         # Uncheck checkbox
agent-browser select @e1 "value"  # Select dropdown
agent-browser scroll down 500     # Scroll page
agent-browser scrollintoview @e1  # Scroll element into view
agent-browser drag @e1 @e2        # Drag and drop
agent-browser upload @e1 file.pdf # Upload files
```

### Get information
```bash
agent-browser get text @e1        # Get element text
agent-browser get html @e1        # Get innerHTML
agent-browser get value @e1       # Get input value
agent-browser get attr @e1 href   # Get attribute
agent-browser get title           # Get page title
agent-browser get url             # Get current URL
agent-browser get count ".item"   # Count matching elements
agent-browser get box @e1         # Get bounding box
```

### Check state
```bash
agent-browser is visible @e1      # Check if visible
agent-browser is enabled @e1      # Check if enabled
agent-browser is checked @e1      # Check if checked
```

### Screenshots & PDF
```bash
agent-browser screenshot          # Screenshot to stdout
agent-browser screenshot path.png # Save to file
agent-browser screenshot --full   # Full page
agent-browser pdf output.pdf      # Save as PDF
```

### Video recording
```bash
agent-browser record start ./demo.webm    # Start recording (uses current URL + state)
agent-browser click @e1                   # Perform actions
agent-browser record stop                 # Stop and save video
agent-browser record restart ./take2.webm # Stop current + start new recording
```
Recording creates a fresh context but preserves cookies/storage from your session. If no URL is provided, it automatically returns to your current page. For smooth demos, explore first, then start recording.

### Wait
```bash
agent-browser wait @e1                     # Wait for element
agent-browser wait 2000                    # Wait milliseconds
agent-browser wait --text "Success"        # Wait for text
agent-browser wait --url "**/dashboard"    # Wait for URL pattern
agent-browser wait --load networkidle      # Wait for network idle
agent-browser wait --fn "window.ready"     # Wait for JS condition
```

### Mouse control
```bash
agent-browser mouse move 100 200      # Move mouse
agent-browser mouse down left         # Press button
agent-browser mouse up left           # Release button
agent-browser mouse wheel 100         # Scroll wheel
```

### Semantic locators (alternative to refs)
```bash
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
agent-browser find first ".item" click
agent-browser find nth 2 "a" text
```

### Browser settings
```bash
agent-browser set viewport 1920 1080      # Set viewport size
agent-browser set device "iPhone 14"      # Emulate device
agent-browser set geo 37.7749 -122.4194   # Set geolocation
agent-browser set offline on              # Toggle offline mode
agent-browser set headers '{"X-Key":"v"}' # Extra HTTP headers
agent-browser set credentials user pass   # HTTP basic auth
agent-browser set media dark              # Emulate color scheme
```

### Cookies & Storage
```bash
agent-browser cookies                     # Get all cookies
agent-browser cookies set name value      # Set cookie
agent-browser cookies clear               # Clear cookies
agent-browser storage local               # Get all localStorage
agent-browser storage local key           # Get specific key
agent-browser storage local set k v       # Set value
agent-browser storage local clear         # Clear all
```

### Network
```bash
agent-browser network route <url>              # Intercept requests
agent-browser network route <url> --abort      # Block requests
agent-browser network route <url> --body '{}'  # Mock response
agent-browser network unroute [url]            # Remove routes
agent-browser network requests                 # View tracked requests
agent-browser network requests --filter api    # Filter requests
```

### Tabs & Windows
```bash
agent-browser tab                 # List tabs
agent-browser tab new [url]       # New tab
agent-browser tab 2               # Switch to tab
agent-browser tab close           # Close tab
agent-browser window new          # New window
```

### Frames
```bash
agent-browser frame "#iframe"     # Switch to iframe
agent-browser frame main          # Back to main frame
```

### Browser Extensions
```bash
# Load extension (repeatable for multiple)
agent-browser --extension /path/to/extension open https://example.com
agent-browser --extension ./ext1 --extension ./ext2 open https://example.com
```

### Browser Launch Args
```bash
# Custom Chromium flags
agent-browser --args "--no-sandbox,--disable-blink-features=AutomationControlled" open https://example.com

# Or via env var
export AGENT_BROWSER_ARGS="--no-sandbox,--disable-web-security"
```

### Custom User Agent
```bash
agent-browser --user-agent "Mozilla/5.0 Custom Agent" open https://example.com

# Or via env var
export AGENT_BROWSER_USER_AGENT="Custom Agent String"
```

### Dialogs
```bash
agent-browser dialog accept [text]  # Accept dialog
agent-browser dialog dismiss        # Dismiss dialog
```

### JavaScript
```bash
agent-browser eval "document.title"   # Run JavaScript
```

## Example: Form submission

```bash
agent-browser open https://example.com/form
agent-browser snapshot -i
# Output shows: textbox "Email" [ref=e1], textbox "Password" [ref=e2], button "Submit" [ref=e3]

agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password123"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i  # Check result
```

## Example: Authentication with saved state

```bash
# Login once
agent-browser open https://app.example.com/login
agent-browser snapshot -i
agent-browser fill @e1 "username"
agent-browser fill @e2 "password"
agent-browser click @e3
agent-browser wait --url "**/dashboard"
agent-browser state save auth.json

# Later sessions: load saved state
agent-browser state load auth.json
agent-browser open https://app.example.com/dashboard
```

## Example: Persistent Profile (Alternative to State)

```bash
# Use --profile for automatic state persistence across restarts
# Stores: cookies, localStorage, IndexedDB, login sessions

agent-browser --profile ~/.myapp open https://app.example.com/login
agent-browser snapshot -i && agent-browser fill @e1 "user" && agent-browser fill @e2 "pass" && agent-browser click @e3

# Next time - already logged in!
agent-browser --profile ~/.myapp open https://app.example.com/dashboard
```

## Sessions (parallel browsers)

```bash
agent-browser --session test1 open site-a.com
agent-browser --session test2 open site-b.com
agent-browser session list
```

## JSON output (for parsing)

Add `--json` for machine-readable output:
```bash
agent-browser snapshot -i --json
agent-browser get text @e1 --json
```

## Debugging

```bash
agent-browser open example.com --headed   # Show browser window (not headless)
agent-browser --cdp 9222 snapshot         # Connect via Chrome DevTools Protocol
agent-browser console                     # View console messages
agent-browser console --clear             # Clear console
agent-browser errors                      # View page errors
agent-browser errors --clear              # Clear errors
agent-browser highlight @e1               # Highlight element visually
agent-browser trace start                 # Start recording trace
agent-browser trace stop trace.zip        # Stop and save trace
agent-browser record start ./debug.webm   # Record video from current page
agent-browser record stop                 # Save recording
```

## Troubleshooting

### Daemon failed to start
Run `agent-browser install` to install browser binaries.

### Executable doesn't exist (version mismatch)
```bash
# 1. Close existing daemon
agent-browser close

# 2. Find available chromium (macOS)
ls ~/Library/Caches/ms-playwright/ | grep chromium

# 3. Use available version (macOS)
agent-browser --executable-path ~/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium open <url>
```

### Connection timeout / os error 10060
Daemon connection timed out. Retry the command:
```bash
# If you see "connected party did not properly respond"
# Just retry the same command - daemon may need warmup
agent-browser click @e2  # Retry
```

### Click fails on SPA links
Single-page apps (React, Vue) may not respond to ref clicks. Use direct navigation:
```bash
# Instead of: agent-browser click @e5
agent-browser open http://localhost:5173/project/my-page
```

### Context destroyed / navigation error
Page navigated during command execution. Wait for stability:
```bash
agent-browser wait --load networkidle
agent-browser snapshot -i
```

### Stale refs after DOM change
Re-snapshot to get fresh refs:
```bash
agent-browser snapshot -i   # Get new refs after any navigation/AJAX
```

### Timeout on slow pages
Use Bash timeout parameter:
```bash
# In Claude Code, set timeout: 30000 for slow operations
```

### --executable-path ignored warning
Daemon is already running with different settings:
```bash
agent-browser close  # Close first
agent-browser --executable-path "..." open <url>  # Then reopen
```

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  CLI (Rust)     │────▶│  Daemon (Node)   │────▶│  Playwright │
│  Fast parsing   │     │  Browser mgmt    │     │  Chromium   │
└─────────────────┘     └──────────────────┘     └─────────────┘
```

- **Rust CLI**: Fast command parsing, daemon communication
- **Node.js Daemon**: Persistent process managing Playwright browser instances
- **Daemon auto-starts** on first command, maintains state between calls
- **93% context savings** vs Playwright MCP (optimized for AI agents)
- **Fallback**: Uses Node.js directly if native binaries unavailable
