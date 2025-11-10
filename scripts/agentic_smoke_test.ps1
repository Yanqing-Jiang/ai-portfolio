[CmdletBinding()]
param(
  [string]$BackendUrl = $(if ($env:BACKEND_URL) { $env:BACKEND_URL } else { 'http://localhost:8000' }),
  [string]$Flow = 'single-agent',
  [string]$ViteLogPath = 'vite.log',
  [int]$TimeoutSeconds = 90,
  [string]$BaselineQuery = 'Summarize NVDA''s latest earnings using SQL, chart, and web context.',
  [string]$StockOnlyQuery = 'Only refresh the market snapshot for NVDA — keep SQL and analysis reused.',
  [string]$ReuseSqlQuery = 'Reuse the SQL dataset but redraw the revenue chart grouped by quarter.',
  [string]$RedirectQuery = 'This feels stale - restart with a fresh FULL_PIPELINE run.',
  [string]$FixtureDirectory = $null,
  [string]$FreshReasoningEffort = 'minimal',
  [string]$RevisionReasoningEffort = 'medium',
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$UsingFixtures = -not [string]::IsNullOrWhiteSpace($FixtureDirectory)
if ($UsingFixtures) {
  $FixtureDirectory = (Resolve-Path $FixtureDirectory).Path
}

if ($DryRun) {
  Write-Host '[agentic-smoke] Dry run only. No network calls executed.'
  return
}

Add-Type -AssemblyName System.Web
$httpClient = $null
if (-not $UsingFixtures) {
  $httpClient = [System.Net.Http.HttpClient]::new()
  $httpClient.Timeout = [TimeSpan]::FromMilliseconds(-1)
}

function New-StreamUri {
  param(
    [string]$Query,
    [string]$SessionId
  )
  $builder = [System.UriBuilder]::new($BackendUrl)
  $builder.Path = ($builder.Path.TrimEnd('/') + '/api/analytics/memory/stream')
  $queryParams = [System.Web.HttpUtility]::ParseQueryString('')
  $queryParams['query'] = $Query
  $queryParams['flow'] = $Flow
  if ($SessionId) {
    $queryParams['session_id'] = $SessionId
  }
  $builder.Query = $queryParams.ToString()
  return $builder.Uri
}

function Get-FixtureEvents {
  param([string]$Label)
  if (-not $UsingFixtures) { return $null }
  $fileName = "$Label.json"
  $path = Join-Path $FixtureDirectory $fileName
  if (-not (Test-Path $path)) {
    throw "Fixture file $fileName not found in $FixtureDirectory"
  }
  (Get-Content $path -Raw | ConvertFrom-Json)
}

function Invoke-AgenticStream {
  param(
    [string]$Label,
    [string]$Query,
    [string]$SessionId
  )
  if ($UsingFixtures) {
    $events = Get-FixtureEvents -Label $Label
    $sessionValue = if ($SessionId) { $SessionId } else {
      ($events | Where-Object { $_.event -eq 'session_started' } | Select-Object -First 1).data.session_id
    }
    if (-not $sessionValue) { $sessionValue = 'fixture-session' }
    $hasRedirect = ($events | Where-Object { $_.event -eq 'workflow_redirect' } | Select-Object -First 1) -ne $null
    return [pscustomobject]@{
      Label = $Label
      Query = $Query
      Events = $events
      SessionId = $sessionValue
      HasRedirect = $hasRedirect
    }
  }


  $uri = New-StreamUri -Query $Query -SessionId $SessionId
  $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $uri)
  $request.Headers.Accept.ParseAdd('text/event-stream')
  $cts = [System.Threading.CancellationTokenSource]::new()
  $cts.CancelAfter([TimeSpan]::FromSeconds($TimeoutSeconds))
  $response = $httpClient.SendAsync($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead, $cts.Token).Result
  $response.EnsureSuccessStatusCode()
  $stream = $response.Content.ReadAsStreamAsync().Result
  $reader = New-Object System.IO.StreamReader($stream)
  $events = @()
  $sessionValue = $SessionId
  $hasRedirect = $false
  try {
    while (-not $reader.EndOfStream) {
      $line = $reader.ReadLine()
      if ([string]::IsNullOrWhiteSpace($line)) {
        continue
      }
      if (-not $line.StartsWith('data:')) {
        continue
      }
      $payload = $line.Substring(5).Trim()
      if (-not $payload) {
        continue
      }
      try {
        $evt = $payload | ConvertFrom-Json -Depth 16
      } catch {
        continue
      }
      $events += $evt
      if (-not $sessionValue -and $evt.event -eq 'session_started') {
        $sessionValue = $evt.data.session_id
      }
      if ($evt.event -eq 'workflow_redirect') {
        $hasRedirect = $true
        break
      }
      if ($evt.event -eq 'workflow_complete' -or $evt.event -eq 'error') {
        break
      }
    }
  } finally {
    $reader.Dispose()
    $response.Dispose()
  }

  [pscustomobject]@{
    Label = $Label
    Query = $Query
    Events = $events
    SessionId = $sessionValue
    HasRedirect = $hasRedirect
  }
}

function Get-GuardrailEvents {
  param(
    [object[]]$Events
  )
  if (-not $Events) { return @() }
  $keywords = @('guardrail', 'guardrail_id', 'guardrail_name', 'guardrail_result', 'guardrail_trip', 'tripwire', 'tripwires', 'guardrails', 'safety_checks', 'policy')
  $matched = @()
  foreach ($evt in $Events) {
    $eventName = $evt.event
    $data = $evt.data
    $found = $false
    if ($eventName -and $eventName -like 'guardrail*') {
      $found = $true
    }
    if (-not $found -and $data) {
      $propertyNames = @()
      if ($data -is [System.Collections.IDictionary]) {
        $propertyNames = @($data.Keys)
      } else {
        $propertyNames = @($data.PSObject.Properties.Name)
      }
      foreach ($key in $keywords) {
        if ($propertyNames -contains $key -and $data.$key) {
          $found = $true
          break
        }
      }
      if (-not $found -and $data.reason -and $data.reason -like '*guardrail*') {
        $found = $true
      }
    }
    if ($found) {
      $matched += $evt
    }
  }
  return $matched
}

function Save-SmokeEvents {
  param(
    [pscustomobject]$Result,
    [string]$Suffix
  )
  $targetDir = Join-Path -Path 'reports' -ChildPath 'agentic_smoke'
  if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
  }
  $stamp = (Get-Date).ToString('yyyyMMdd-HHmmss')
  $filePath = Join-Path $targetDir "$stamp-$Suffix.json"
  $Result.Events | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $filePath
  $guardrailEvents = Get-GuardrailEvents -Events $Result.Events
  if ($guardrailEvents.Count -gt 0) {
    $guardrailPath = Join-Path $targetDir "$stamp-$Suffix-guardrails.json"
    $guardrailEvents | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $guardrailPath
    Write-Host "[agentic-smoke] Saved guardrail events to $guardrailPath"
  }
  return $filePath
}

function Test-ToolEvents {
  param(
    [pscustomobject]$Result,
    [string]$Scenario
  )
  $toolEvents = $Result.Events | Where-Object { $_.event -in @('agent_tool_call', 'agent_tool_complete') }
  if (-not $toolEvents) {
    Write-Warning "[$Scenario] No agent_tool_call telemetry detected."
    return $false
  }
  return $true
}

function Test-SessionTelemetry {
  param(
    [pscustomobject]$Result,
    [string]$Scenario
  )
  $sessionEvent = $Result.Events | Where-Object { $_.event -eq 'session_started' } | Select-Object -First 1
  if ($sessionEvent) { return $true }
  $fallback = $Result.Events | Where-Object { $_.data -and $_.data.session_id } | Select-Object -First 1
  if ($fallback) { return $true }
  Write-Warning "[$Scenario] session telemetry missing."
  return $false
}

function Test-FreshFullPipeline {
  param(
    [pscustomobject]$Result,
    [string]$Scenario
  )
  $requiredEvents = @('sql_ready', 'chart_ready', 'market_ready', 'web_ready', 'analysis_ready')
  $missing = @()
  foreach ($name in $requiredEvents) {
    if (-not ($Result.Events | Where-Object { $_.event -eq $name })) {
      $missing += $name
    }
  }
  $reuseEvent = $Result.Events | Where-Object { $_.event -eq 'lane_reused' } | Select-Object -First 1
  if ($missing.Count -gt 0) {
    Write-Warning "[$Scenario] Missing fresh-lane completions: $($missing -join ', ')"
  }
  if ($reuseEvent) {
    Write-Warning "[$Scenario] Unexpected lane_reused telemetry during fresh run."
  }
  return ($missing.Count -eq 0 -and -not $reuseEvent)
}

function Test-GuardrailTelemetry {
  param(
    [pscustomobject]$Result,
    [string]$Scenario
  )
  $guardrailEvents = Get-GuardrailEvents -Events $Result.Events
  if ($guardrailEvents.Count -gt 0) { return $true }
  Write-Warning "[$Scenario] Guardrail telemetry missing."
  return $false
}

function Test-ReasoningSettings {
  param(
    [pscustomobject]$Result,
    [string]$Scenario,
    [string]$ExpectedEffort
  )
  if (-not $ExpectedEffort) { return $true }
  $settingEvents = $Result.Events | Where-Object {
    $_.event -eq 'model_settings' -or
    ($_.data -and $_.data.model_settings)
  }
  if (-not $settingEvents) {
    Write-Warning "[$Scenario] Missing model_settings telemetry."
    return $false
  }
  $withSettings = $settingEvents | Where-Object {
    $_.data -and $_.data.model_settings -and $_.data.model_settings.reasoning_effort
  }
  if (-not $withSettings) {
    Write-Warning "[$Scenario] Missing model_settings telemetry."
    return $false
  }
  $mismatch = $withSettings | Where-Object {
    $_.data.model_settings.reasoning_effort -ne $ExpectedEffort
  }
  if ($mismatch) {
    Write-Warning "[$Scenario] reasoning_effort mismatch (expected $ExpectedEffort)."
    return $false
  }
  return $true
}

function Test-LaneReuse {
  param(
    [pscustomobject]$Result,
    [string]$Lane
  )
  $laneEvent = $Result.Events | Where-Object { $_.event -eq 'lane_reused' -and $_.data.lane -eq $Lane } | Select-Object -First 1
  if (-not $laneEvent) {
    Write-Warning "[$Lane] lane reuse marker missing."
    return $false
  }
  return $true
}

function Test-AgentToolParity {
  param(
    [pscustomobject]$Result,
    [string]$Scenario
  )
  $callCounts = @{}
  $completeCounts = @{}
  foreach ($evt in $Result.Events) {
    if ($evt.event -eq 'agent_tool_call' -and $evt.data.tool_call) {
      $toolCall = $evt.data.tool_call
      $key = $toolCall.id
      if (-not $key) {
        $key = "{0}:{1}" -f ($toolCall.name ?? 'unknown'), ($toolCall.sequence_number ?? $toolCall.sequence ?? $evt.seq ?? 0)
      }
      if (-not $key) { continue }
      $callCounts[$key] = ($callCounts[$key] + 1)
    } elseif ($evt.event -eq 'agent_tool_complete' -and $evt.data.tool_call) {
      $toolCall = $evt.data.tool_call
      $key = $toolCall.id
      if (-not $key) {
        $key = "{0}:{1}" -f ($toolCall.name ?? 'unknown'), ($toolCall.sequence_number ?? $toolCall.sequence ?? $evt.seq ?? 0)
      }
      if (-not $key) { continue }
      $completeCounts[$key] = ($completeCounts[$key] + 1)
    }
  }
  if ($callCounts.Count -eq 0) {
    Write-Warning "[$Scenario] No agent_tool_call identifiers detected for parity check."
    return $false
  }
  $missing = @()
  foreach ($key in $callCounts.Keys) {
    if (-not $completeCounts.ContainsKey($key)) {
      $missing += $key
    }
  }
  if ($missing.Count -gt 0) {
    Write-Warning "[$Scenario] agent_tool_call without completion: $($missing -join ', ')"
    return $false
  }
  return $true
}

function Tail-ViteLog {
  param(
    [string]$Scenario
  )
  if (-not (Test-Path $ViteLogPath)) {
    return $null
  }
  $tail = Get-Content $ViteLogPath -Tail 400 -ErrorAction SilentlyContinue
  if (-not $tail) { return $null }
  $hasTool = $tail -match 'agent_tool_call'
  [pscustomobject]@{
    Scenario = $Scenario
    AgentToolCallMentioned = $hasTool
  }
}

$results = @()
$summary = @()

$baseline = Invoke-AgenticStream -Label 'baseline' -Query $BaselineQuery -SessionId $null
$results += $baseline
if (-not $baseline.SessionId) {
  throw 'Baseline run did not emit session_id; cannot run revisions.'
}
$summary += [pscustomobject]@{
  Scenario = 'Baseline'
  SessionId = $baseline.SessionId
  ToolsOk = (Test-ToolEvents -Result $baseline -Scenario 'Baseline')
  SessionOk = (Test-SessionTelemetry -Result $baseline -Scenario 'Baseline')
  FreshPipelineOk = (Test-FreshFullPipeline -Result $baseline -Scenario 'Baseline')
  LaneReuseOk = $false
  RedirectSeen = $false
  ParityOk = (Test-AgentToolParity -Result $baseline -Scenario 'Baseline')
  GuardrailOk = (Test-GuardrailTelemetry -Result $baseline -Scenario 'Baseline')
  ReasoningOk = (Test-ReasoningSettings -Result $baseline -Scenario 'Baseline' -ExpectedEffort $FreshReasoningEffort)
  Artifact = Save-SmokeEvents -Result $baseline -Suffix 'baseline'
}

$sessionId = $baseline.SessionId

$stock = Invoke-AgenticStream -Label 'stock' -Query $StockOnlyQuery -SessionId $sessionId
$results += $stock
$summary += [pscustomobject]@{
  Scenario = 'stock'
  SessionId = $sessionId
  ToolsOk = (Test-ToolEvents -Result $stock -Scenario 'stock')
  SessionOk = (Test-SessionTelemetry -Result $stock -Scenario 'stock')
  FreshPipelineOk = $null
  LaneReuseOk = (Test-LaneReuse -Result $stock -Lane 'market')
  RedirectSeen = $stock.HasRedirect
  ParityOk = (Test-AgentToolParity -Result $stock -Scenario 'stock')
  GuardrailOk = (Test-GuardrailTelemetry -Result $stock -Scenario 'stock')
  ReasoningOk = (Test-ReasoningSettings -Result $stock -Scenario 'stock' -ExpectedEffort $RevisionReasoningEffort)
  Artifact = Save-SmokeEvents -Result $stock -Suffix 'stock'
}

$reuseSql = Invoke-AgenticStream -Label 'reuse-sql' -Query $ReuseSqlQuery -SessionId $sessionId
$results += $reuseSql
$summary += [pscustomobject]@{
  Scenario = 'reuse-sql'
  SessionId = $sessionId
  ToolsOk = (Test-ToolEvents -Result $reuseSql -Scenario 'reuse-sql')
  SessionOk = (Test-SessionTelemetry -Result $reuseSql -Scenario 'reuse-sql')
  FreshPipelineOk = $null
  LaneReuseOk = (Test-LaneReuse -Result $reuseSql -Lane 'web')
  RedirectSeen = $reuseSql.HasRedirect
  ParityOk = (Test-AgentToolParity -Result $reuseSql -Scenario 'reuse-sql')
  GuardrailOk = (Test-GuardrailTelemetry -Result $reuseSql -Scenario 'reuse-sql')
  ReasoningOk = (Test-ReasoningSettings -Result $reuseSql -Scenario 'reuse-sql' -ExpectedEffort $RevisionReasoningEffort)
  Artifact = Save-SmokeEvents -Result $reuseSql -Suffix 'reuse-sql'
}

$redirectRun = Invoke-AgenticStream -Label 'redirect' -Query $RedirectQuery -SessionId $sessionId
$results += $redirectRun
$summary += [pscustomobject]@{
  Scenario = 'REDIRECT'
  SessionId = $sessionId
  ToolsOk = (Test-ToolEvents -Result $redirectRun -Scenario 'REDIRECT')
  SessionOk = (Test-SessionTelemetry -Result $redirectRun -Scenario 'REDIRECT')
  FreshPipelineOk = $null
  LaneReuseOk = $false
  RedirectSeen = $redirectRun.HasRedirect
  ParityOk = (Test-AgentToolParity -Result $redirectRun -Scenario 'REDIRECT')
  GuardrailOk = (Test-GuardrailTelemetry -Result $redirectRun -Scenario 'REDIRECT')
  ReasoningOk = (Test-ReasoningSettings -Result $redirectRun -Scenario 'REDIRECT' -ExpectedEffort $RevisionReasoningEffort)
  Artifact = Save-SmokeEvents -Result $redirectRun -Suffix 'redirect'
}

if (-not $UsingFixtures) {
  $viteSummary = Tail-ViteLog -Scenario 'Final'
} else {
  $viteSummary = $null
  Write-Host '[agentic-smoke] Fixture mode - skipping Vite log tail.'
}
if ($viteSummary) {
  Write-Host "[agentic-smoke] Vite log mentions agent_tool_call: $($viteSummary.AgentToolCallMentioned)"
}

Write-Host "[agentic-smoke] Completed runs against $BackendUrl ($Flow)"
$summary | Format-Table -AutoSize

$failureNotes = @()
foreach ($row in $summary) {
  $scenarioKey = ($row.Scenario ?? '').ToLowerInvariant()
  if (-not $row.ToolsOk) {
    $failureNotes += "[$($row.Scenario)] missing agent_tool telemetry"
  }
  if (-not $row.SessionOk) {
    $failureNotes += "[$($row.Scenario)] missing session telemetry"
  }
  if ($row.Scenario -eq 'Baseline' -and -not $row.FreshPipelineOk) {
    $failureNotes += '[Baseline] missing full fresh-pipeline coverage'
  }
  if ($scenarioKey -eq 'stock' -and -not $row.LaneReuseOk) {
    $failureNotes += '[STOCK_ONLY] missing market lane_reused marker'
  }
  if ($scenarioKey -eq 'reuse-sql' -and -not $row.LaneReuseOk) {
    $failureNotes += '[REUSE_SQL] missing web lane_reused marker'
  }
  if ($row.Scenario -eq 'REDIRECT' -and -not $row.RedirectSeen) {
    $failureNotes += '[REDIRECT] workflow_redirect not observed'
  }
  if (-not $row.ParityOk) {
    $failureNotes += "[$($row.Scenario)] agent_tool_call events missing matching completions"
  }
  if (-not $row.GuardrailOk) {
    $failureNotes += "[$($row.Scenario)] guardrail telemetry missing"
  }
  if (-not $row.ReasoningOk) {
    $failureNotes += "[$($row.Scenario)] reasoning_effort telemetry mismatch"
  }
}
if ($failureNotes.Count -gt 0) {
  $failureNotes | ForEach-Object { Write-Error $_ }
  throw 'agentic smoke validations failed'
}

