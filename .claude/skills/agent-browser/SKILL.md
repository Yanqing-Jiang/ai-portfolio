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

### Test 1: Basic Dashboard Load
```bash
agent-browser open http://localhost:5173/project/agent-to-ui --headed && agent-browser wait 1000 && agent-browser snapshot -i && agent-browser screenshot docs/testing/screenshots/a2ui-load.png
```

### Test 2: Query Flow (Revenue Trend)
```bash
agent-browser open http://localhost:5173/project/agent-to-ui --headed && agent-browser wait 1000 && agent-browser snapshot -i
# Then:
agent-browser fill @e13 "NVDA revenue trend" && agent-browser click @e14 && agent-browser wait 4000 && agent-browser screenshot docs/testing/screenshots/a2ui-revenue.png
```

### Test 3: Query Flow (Peer Compare)
```bash
agent-browser fill @e13 "Compare AMD vs NVDA" && agent-browser click @e14 && agent-browser wait 4000 && agent-browser screenshot docs/testing/screenshots/a2ui-compare.png
```

### Test 4: Query Flow (Margin Analysis)
```bash
agent-browser fill @e13 "AMD margin analysis" && agent-browser click @e14 && agent-browser wait 4000 && agent-browser screenshot docs/testing/screenshots/a2ui-margin.png
```

### Test 5: Query Flow (Explain Move)
```bash
agent-browser fill @e13 "Why did NVDA drop?" && agent-browser click @e14 && agent-browser wait 4000 && agent-browser screenshot docs/testing/screenshots/a2ui-explain.png
```

### Test 6: Full A2UI Flow (Complete)
```bash
agent-browser open http://localhost:5173/project/agent-to-ui --headed && agent-browser wait 1000 && agent-browser snapshot -i && \
agent-browser fill @e13 "Compare AMD vs NVDA revenue" && agent-browser click @e14 && agent-browser wait 4000 && \
agent-browser screenshot docs/testing/screenshots/a2ui-full-test.png && agent-browser close
```

### A2UI Sample Queries
- `"NVDA revenue trend"` - Revenue Trend skill
- `"Compare AMD vs NVDA"` - Peer Compare skill
- `"AMD margin analysis"` - Margin Analysis skill
- `"Why did NVDA drop?"` - Explain Move skill
- `"Show me what you can do"` - Feature Showcase skill

---

## Speed Tips (IMPORTANT)

1. **Chain with `&&`** - Multiple commands in one bash call = faster
2. **ONE snapshot per page** - Don't re-snapshot unless page reloads/navigates
3. **Direct URL** - Use URLs above, faster than clicking SPA links
4. **Batch interactions** - `fill @e1 "a" && fill @e2 "b" && click @e3`
5. **Skip verbose waits** - `wait 2000-4000` is usually enough

## First-time setup

```bash
agent-browser install           # Install Chromium binaries (required once)
```

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
