---
description: Clean up test/log files, auto-generate commit message from changes, and push to GitHub
allowed-tools: Bash, Read, Grep
---

# Push Changes to GitHub

Automatically analyzes changes, generates a commit message, cleans up test/log files, commits, and pushes to GitHub.

## Usage

```
/push
```

No arguments needed - commit message is auto-generated from your changes.

## Workflow

### Step 1: Cleanup Phase

Remove test files, log files, and temporary files:

```bash
rm -rf tmpclaude-*
find . -type f -name "*.png" ! -path "*/node_modules/*" ! -path "*/.venv/*" ! -path "*/public/*" ! -path "*/assets/*" -delete
find . -type f \( -name "*.test.ts" -o -name "*.test.tsx" -o -name "*.test.js" -o -name "*.test.jsx" -o -name "*.spec.ts" -o -name "*.spec.tsx" -o -name "*.spec.js" -o -name "*.spec.jsx" -o -name "test_*.py" -o -name "test*.js" -o -name "test*.mjs" -o -name "test*.cjs" -o -name "test*.ts" -o -name "test*.tsx" \) ! -path "*/node_modules/*" ! -path "*/.venv/*" ! -path "*/tests/*" -delete
find . -type f \( -name "*.log" -o -name "*-debug.log" -o -name "*-error.log" \) ! -path "*/node_modules/*" ! -path "*/.venv/*" -delete
find . -type f \( -name "*_pid.txt" -o -name "temp_view.txt" \) ! -path "*/node_modules/*" ! -path "*/.venv/*" -delete
```

Report cleanup:
```
🧹 Cleanup complete
```

### Step 2: Verify Changes Exist

```bash
git status
```

If no changes:
```
⚠️ No changes to commit. Aborting.
```

### Step 3: Stage Changes

```bash
git add .
```

### Step 4: Analyze Changes and Generate Commit Message

Run git diff to analyze what changed:

```bash
# Get list of modified files
git diff --cached --name-only

# Get summary of changes
git diff --cached --stat

# Get actual changes (limit to first 100 lines for analysis)
git diff --cached | head -100
```

**Analyze the changes** to generate a concise commit message:

**Rules for commit message**:
1. Start with type prefix: `feat:`, `fix:`, `refactor:`, `docs:`, `style:`, `test:`, `chore:`
2. Keep first line under 72 characters
3. Be specific about what changed
4. Focus on the "what" and "why", not the "how"

**Examples**:
- Multiple new files in `src/components/` → `feat: add user profile components`
- Fixed bug in `auth.ts` → `fix: resolve JWT token expiration issue`
- Updated documentation → `docs: update API documentation`
- Refactored code → `refactor: simplify authentication logic`
- Multiple changes → `feat: implement dark mode with theme persistence`

**Message format**:
```
{type}: {concise description}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Step 5: Create Commit

```bash
git commit -m "$(cat <<'EOF'
{GENERATED_COMMIT_MESSAGE}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

Show the generated commit message to user:
```
📝 Commit message: "{GENERATED_COMMIT_MESSAGE}"
```

### Step 6: Push to GitHub

```bash
git push
```

### Step 7: Report Success

```
✅ Pushed to GitHub

Commit: {hash}
Message: "{message}"
Files changed: {X}

Branch: {current_branch}
Remote: {remote_name}
```

## Examples

### Example 1: Added New Feature

**Changes detected**:
- New files: `src/components/LoginForm.tsx`, `src/hooks/useAuth.ts`
- Modified: `src/App.tsx`

**Generated message**: `feat: add login form with authentication hook`

**Result**:
```
📝 Commit message: "feat: add login form with authentication hook"
✅ Pushed to GitHub
```

### Example 2: Bug Fix

**Changes detected**:
- Modified: `src/api/fetchData.ts` (fixed race condition)

**Generated message**: `fix: resolve race condition in data fetching`

**Result**:
```
📝 Commit message: "fix: resolve race condition in data fetching"
✅ Pushed to GitHub
```

### Example 3: Documentation Update

**Changes detected**:
- Modified: `README.md`, `docs/api.md`

**Generated message**: `docs: update README and API documentation`

**Result**:
```
📝 Commit message: "docs: update README and API documentation"
✅ Pushed to GitHub
```

### Example 4: Multiple Components

**Changes detected**:
- New: `src/components/Modal.tsx`, `src/components/Button.tsx`, `src/components/Input.tsx`
- Modified: `src/styles/globals.css`

**Generated message**: `feat: add reusable UI components with styling`

**Result**:
```
📝 Commit message: "feat: add reusable UI components with styling"
✅ Pushed to GitHub
```

## Commit Type Prefixes

Use these prefixes based on change type:

- **feat**: New feature or functionality
- **fix**: Bug fix
- **refactor**: Code restructuring without functionality change
- **docs**: Documentation only changes
- **style**: Formatting, missing semicolons, etc.
- **test**: Adding or updating tests
- **chore**: Build process, dependencies, tooling

## Analysis Strategy

### Step-by-step analysis:

1. **Get file list**: `git diff --cached --name-only`
2. **Categorize changes**:
   - New files (`A` status)
   - Modified files (`M` status)
   - Deleted files (`D` status)
3. **Identify patterns**:
   - All in same directory? → Focused feature
   - Multiple directories? → Broader change
   - Only docs? → Documentation update
   - Only tests? → Test update
4. **Determine type**:
   - New feature files → `feat:`
   - Bug fix in existing → `fix:`
   - Restructuring → `refactor:`
   - Docs only → `docs:`
5. **Write concise description**:
   - Focus on business value
   - Mention key component/feature
   - Keep under 72 chars

### Example analysis:

**Scenario**: Added 3 files in `src/components/auth/`, modified `src/App.tsx`

**Analysis**:
- Pattern: New auth components + app integration
- Type: New feature → `feat:`
- Description: "add authentication components"
- Final: `feat: add authentication components`

## Safety Features

- ✅ Auto-cleans test/log files (never committed)
- ✅ Verifies changes exist before commit
- ✅ Shows generated message for transparency
- ✅ Adds co-authorship attribution
- ✅ Reports errors if push fails

## Files Removed Before Commit

**PNG Files**:
- `*.png` (screenshots, test images, etc.)

**Test Files**:
- `*.test.ts`, `*.test.tsx`, `*.test.js`, `*.test.jsx`
- `*.spec.ts`, `*.spec.tsx`, `*.spec.js`, `*.spec.jsx`
- `test_*.py`
- `test*.js`, `test*.mjs`, `test*.cjs`, `test*.ts`, `test*.tsx` (files starting with "test")

**Log Files**:
- `*.log`, `*-debug.log`, `*-error.log`

**Temp Files**:
- `tmpclaude-*`, `*_pid.txt`, `temp_view.txt`

**Exclusions**: `node_modules/`, `.venv/`, `tests/`, `public/`, `assets/` directories never touched

## Error Handling

### No Changes
```
⚠️ No changes to commit. Aborting.
```

### No Remote
```
❌ Push failed: No remote repository configured
Suggestion: Run `git remote add origin <repo-url>`
```

### Branch Not Tracking
```
❌ Push failed: Branch not tracking remote
Suggestion: Run `git push -u origin main`
```

### Merge Conflicts
```
❌ Push failed: Remote has changes
Suggestion: Run `git pull --rebase` first
```

## Integration with Workflow

**Typical Flow**:
1. Implement feature with Claude
2. Claude: "✅ Implementation complete"
3. codex-verifier hook runs (auto verification)
4. Review verification report (optional)
5. Run `/push`
6. Auto-generated commit message + push to GitHub

**Result**: Clean, well-described commits with quality verification.

## Advanced: Custom Message Override

If auto-generation isn't suitable, use git directly:

```bash
# Manual commit with custom message
git add .
git commit -m "Your custom message

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
git push
```

## Tips for Good Auto-Generated Messages

The quality of auto-generated messages depends on:

1. **Focused commits**: One feature/fix per commit
2. **Clear file naming**: `LoginForm.tsx` is better than `component1.tsx`
3. **Logical grouping**: Related files changed together
4. **Clean diffs**: Remove debug code before committing

**Good example** (easy to auto-generate):
- Files: `src/components/auth/LoginForm.tsx`, `src/components/auth/SignupForm.tsx`
- Message: `feat: add authentication forms`

**Bad example** (harder to auto-generate):
- Files: `file1.ts`, `test.tsx`, `utils.js`, `README.md`, `styles.css`
- Message: `chore: misc updates` (too vague)

For best results, commit focused changes that are easy to summarize.
