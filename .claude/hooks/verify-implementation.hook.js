/**
 * Implementation Verification Hook
 *
 * Triggers codex-verifier sub-agent when code implementation is claimed complete.
 * Filters out planning, research, and file search completions.
 */

module.exports = {
  name: 'verify-implementation',
  description: 'Triggers codex-verifier sub-agent to check code quality after implementation completion',
  events: ['after:assistant-message'],

  async run({ message, tools, context }) {
    // Detect completion claims
    const completionKeywords = [
      /✅.*(?:done|complete|finished|implemented)/i,
      /(?:implementation|code|feature).*(?:complete|done|finished)/i,
      /successfully.*(?:implemented|added|created|fixed)/i
    ]

    const hasCompletion = completionKeywords.some(regex => regex.test(message))

    if (!hasCompletion) {
      return // Not a completion claim
    }

    // Filter out non-implementation completions
    const excludePatterns = [
      /plan(?:ning)?\s+complete/i,
      /research.*complete/i,
      /analysis.*complete/i,
      /design.*complete/i,
      /found.*files?/i,
      /search.*complete/i,
      /explored.*codebase/i,
      /saved to.*docs\/(?:planning|research|designs)/i
    ]

    const isNonImplementation = excludePatterns.some(regex => regex.test(message))

    if (isNonImplementation) {
      return // Skip planning/research/search completions
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

    console.log(`\n🔍 Code implementation detected. Triggering verification for ${codeFiles.length} file(s)...\n`)

    // Extract task description from message (simple heuristic)
    let taskDescription = 'Code implementation'
    const taskMatch = message.match(/(?:implemented|added|created|fixed)\s+(.+?)(?:\.|$)/i)
    if (taskMatch) {
      taskDescription = taskMatch[1].trim()
    }

    // Trigger codex-verifier sub-agent
    try {
      await tools.task({
        subagent_type: 'codex-verifier',
        description: `Verify: ${taskDescription}`,
        prompt: `Verify the code implementation that was just completed.

Task: ${taskDescription}

Files Modified (${codeFiles.length}):
${codeFiles.join('\n')}

Please:
1. Read all modified files
2. Use Codex CLI (gpt-5.2-codex xhigh) to perform comprehensive verification
3. Check for: completeness, code quality, security, edge cases, performance, best practices
4. Save full verification report to docs/verification/
5. Return concise summary with quality score and key findings

Do NOT take any corrective action - only analyze and report.`
      })

      console.log('✅ Verification sub-agent triggered\n')
    } catch (error) {
      console.error(`⚠️ Failed to trigger verification: ${error.message}`)
    }
  }
}
