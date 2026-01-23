/**
 * Implementation Verification Hook
 *
 * Triggers codex-agent CLI (verify mode) when code implementation is claimed complete.
 * Detects completion via: explicit claims, summary patterns, or multiple code edits.
 *
 * Called by: Claude Code hooks system (after:assistant-message event)
 * Invokes: codex-agent sub-agent with verify mode
 * Purpose: Automated quality gate for code implementations
 */

// Minimum code files changed to auto-trigger verification (without explicit completion claim)
const MIN_CODE_FILES_FOR_AUTO_VERIFY = 2

module.exports = {
  name: 'verify-implementation',
  description: 'Triggers codex-agent CLI to verify code quality after implementation completion',
  events: ['after:assistant-message'],

  async run({ message, tools, context }) {
    // === PATTERN 1: Explicit completion claims ===
    const explicitCompletionPatterns = [
      /✅.*(?:done|complete|finished|implemented)/i,
      /(?:implementation|code|feature).*(?:complete|done|finished)/i,
      /successfully.*(?:implemented|added|created|fixed)/i,
      /all.*changes.*(?:made|done|complete)/i,
      /fix.*(?:applied|implemented|complete)/i,
      /(?:fix|bug|issue).*(?:is\s+)?(?:now\s+)?(?:fixed|resolved|working)/i,
      /I've\s+(?:completed|finished|fixed|updated|removed)/i,
      /the\s+fix\s+is\s+(?:applied|confirmed|verified|working)/i
    ]

    // === PATTERN 2: Summary section indicators (common after implementations) ===
    const summaryPatterns = [
      /^##\s*summary/im,  // More flexible: just "## Summary" or "## Summary of changes"
      /^##\s*changes/im,  // "## Changes" or "## Changes made"
      /^###\s*(?:debug|logging|bug|backend|frontend)/im,  // Section headers about fixes
      /the\s+(?:fix|implementation|changes?)\s+eliminates?/i,
      /all\s+(?:the\s+)?(?:main\s+)?(?:code\s+)?changes\s+are\s+done/i,
      /let\s+me\s+provide\s+a\s+summary/i,
      /here(?:'s|\s+is)\s+(?:a\s+)?summary/i,
      /I've\s+completed\s+the\s+following/i,
      /all\s+fixes\s+are\s+verified/i
    ]

    // === PATTERN 3: File listing patterns (indicates multi-file implementation) ===
    const fileListingPatterns = [
      /files?\s+(?:to\s+)?modif(?:y|ied)/i,
      /\*\*\d+\.\s+`[^`]+`\*\*/,  // **1. `filename`**
      /###\s+\d+\.\s+\*\*`[^`]+`\*\*/,  // ### 1. **`filename`**
      /\d+\.\s+\*\*[^*]+\.(?:tsx?|jsx?|py|vue)\*\*/i,  // 1. **KpiCard.tsx** format
      /\*\*[^*]+\.(?:tsx?|jsx?|py|vue)\*\*\s*[-–—]/i  // **filename.tsx** - description
    ]

    const hasExplicitCompletion = explicitCompletionPatterns.some(r => r.test(message))
    const hasSummarySection = summaryPatterns.some(r => r.test(message))
    const hasFileListing = fileListingPatterns.some(r => r.test(message))

    // Filter out non-implementation completions
    const excludePatterns = [
      /plan(?:ning)?\s+complete/i,
      /research.*complete/i,
      /analysis.*complete/i,
      /design.*complete/i,
      /found.*files?/i,
      /search.*complete/i,
      /explored.*codebase/i,
      /saved to.*docs\/(?:planning|research|designs)/i,
      /verification\s+(?:complete|passed|done)/i  // Don't re-verify after verification
    ]

    const isNonImplementation = excludePatterns.some(regex => regex.test(message))

    if (isNonImplementation) {
      return // Skip planning/research/search/verification completions
    }

    // Check if any code files were modified
    const gitStatus = await tools.bash('git diff --name-only HEAD')

    if (gitStatus.exitCode !== 0 || !gitStatus.stdout.trim()) {
      return // No files modified, skip verification
    }

    const modifiedFiles = gitStatus.stdout.trim().split('\n')

    // Filter for code files (exclude docs, config, etc.)
    const codeExtensions = ['.ts', '.tsx', '.js', '.jsx', '.py', '.vue', '.svelte']
    const codeFiles = modifiedFiles.filter(file =>
      codeExtensions.some(ext => file.endsWith(ext)) &&
      !file.includes('docs/') &&
      !file.includes('.test.') &&
      !file.includes('.spec.')
    )

    if (codeFiles.length === 0) {
      return // No code files modified, skip verification
    }

    // === DECISION LOGIC ===
    // Trigger if:
    // 1. Explicit completion claim detected, OR
    // 2. Summary section + file listing detected (strong signal), OR
    // 3. Multiple code files changed + any summary pattern (auto-detect)
    const shouldTrigger =
      hasExplicitCompletion ||
      (hasSummarySection && hasFileListing) ||
      (codeFiles.length >= MIN_CODE_FILES_FOR_AUTO_VERIFY && hasSummarySection)

    if (!shouldTrigger) {
      return // Not enough signals to trigger verification
    }

    console.log(`\n🔍 Code implementation detected. Triggering verification for ${codeFiles.length} file(s)...\n`)

    // Extract task description from message (improved heuristics)
    let taskDescription = 'Code implementation'
    const taskPatterns = [
      /(?:implemented|added|created|fixed|updated)\s+(.+?)(?:\.|$)/i,
      /(?:fix|implementation|changes?)\s+(?:for\s+)?(.+?)(?:\.|$)/i,
      /##\s*(?:summary[:\s]+)?(.+)/i
    ]
    for (const pattern of taskPatterns) {
      const match = message.match(pattern)
      if (match && match[1] && match[1].length < 100) {
        taskDescription = match[1].trim().replace(/^the\s+/i, '')
        break
      }
    }

    // Trigger codex-agent CLI in verify mode
    try {
      await tools.task({
        subagent_type: 'codex-agent',
        description: `Verify: ${taskDescription}`,
        prompt: `VERIFY the code implementation that was just completed.

Task: ${taskDescription}

Files Modified (${codeFiles.length}):
${codeFiles.join('\n')}

Run Codex CLI verification:
1. Read all modified files listed above
2. Execute comprehensive verification using Codex CLI (gpt-5.2-codex xhigh)
3. Check for: completeness, code quality, security vulnerabilities, edge cases, performance issues, best practices
4. Save verification report to docs/verification/
5. Return concise summary with quality score (1-10) and key findings

IMPORTANT: Analyze and report ONLY - do NOT make any code changes or corrections.`
      })

      console.log('✅ codex-agent verification triggered\n')
    } catch (error) {
      console.error(`⚠️ Failed to trigger codex-agent verification: ${error.message}`)
    }
  }
}
