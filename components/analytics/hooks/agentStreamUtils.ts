import { ToolFanoutResult } from '../types';

export interface ToolCallUpdateResult {
  results: ToolFanoutResult[];
  laneStatus: 'in_progress' | 'completed' | 'error';
  thinking: string[];
}

type ToolCallEventName = 'tool_call_delta' | 'tool_call_arguments';

interface ToolCallPayload {
  id?: string | null;
  name?: string | null;
  arguments_delta?: Record<string, any> | null;
  arguments?: Record<string, any> | null;
  sequence_number?: number | null;
  output_index?: number | null;
}

type ToolLifecycleEventName = 'tool_attempt' | 'tool_result';

interface ToolLifecyclePayload {
  tool?: string | null;
  lane?: string | null;
  status?: string | null;
  attempt?: number | null;
  retry_count?: number | null;
  summary?: string | null;
  error_code?: string | null;
  ts?: string | null;
  receipt?: Record<string, any> | null;
  elapsed_ms?: number | null;
  artifacts?: Record<string, any> | null;
}

export const upsertToolCallResult = (
  existingResults: ToolFanoutResult[],
  eventName: ToolCallEventName,
  toolCall: ToolCallPayload,
  timestamp?: string | null
): ToolCallUpdateResult => {
  const toolName = String(toolCall.name || toolCall.id || 'agent_tool');
  const toolKey = toolName.toLowerCase();

  const metadata = toolCall.sequence_number !== undefined || toolCall.output_index !== undefined
    ? {
        ...(toolCall.sequence_number !== undefined ? { sequence_number: toolCall.sequence_number } : {}),
        ...(toolCall.output_index !== undefined ? { output_index: toolCall.output_index } : {}),
      }
    : {};

  const results = existingResults.map((entry) => ({ ...entry }));
  const existingIndex = results.findIndex((entry) => entry.tool.toLowerCase() === toolKey);
  const existing = existingIndex >= 0 ? results[existingIndex] : undefined;

  const mergedMetadata: Record<string, any> = {
    ...(existing?.metadata ?? {}),
    ...metadata,
  };

  if (eventName === 'tool_call_delta' && toolCall.arguments_delta) {
    mergedMetadata.arguments_delta = {
      ...(mergedMetadata.arguments_delta ?? {}),
      ...toolCall.arguments_delta,
    };
  }

  const payload: Record<string, any> = {
    ...(existing?.payload ?? {}),
  };
  if (eventName === 'tool_call_arguments' && toolCall.arguments) {
    payload.arguments = toolCall.arguments;
  }

  const nextResult: ToolFanoutResult = {
    ...(existing ?? { tool: toolName, status: 'queued' }),
    tool: toolName,
    status: eventName === 'tool_call_arguments' ? 'completed' : 'running',
    started_at: existing?.started_at ?? timestamp ?? null,
    completed_at:
      eventName === 'tool_call_arguments' ? timestamp ?? existing?.completed_at ?? null : existing?.completed_at ?? null,
    metadata: mergedMetadata,
    payload: Object.keys(payload).length ? payload : existing?.payload,
  };

  if (existingIndex >= 0) {
    results[existingIndex] = nextResult;
  } else {
    results.push(nextResult);
  }

  const deltaKeys =
    (mergedMetadata.arguments_delta && Object.keys(mergedMetadata.arguments_delta as Record<string, any>)) ?? [];
  const thinking =
    eventName === 'tool_call_delta'
      ? [
          deltaKeys.length
            ? `SQL draft updated (${deltaKeys.join(', ')})`
            : 'SQL draft updated',
        ]
      : [`${toolName} completed with arguments.`];

  return {
    results: results.slice(-10),
    laneStatus: eventName === 'tool_call_arguments' ? 'completed' : 'in_progress',
    thinking,
  };
};

export const mergeToolLifecycleEvent = (
  existingResults: ToolFanoutResult[],
  eventName: ToolLifecycleEventName,
  payload: ToolLifecyclePayload
): ToolCallUpdateResult => {
  const toolName = String(payload.tool || 'agent_tool');
  const toolKey = toolName.toLowerCase();
  const results = existingResults.map((entry) => ({ ...entry }));
  const existingIndex = results.findIndex((entry) => entry.tool.toLowerCase() === toolKey);
  const existing = existingIndex >= 0 ? results[existingIndex] : undefined;

  const nextResult: ToolFanoutResult = {
    ...(existing ?? { tool: toolName, status: 'queued' }),
    tool: toolName,
    metadata: {
      ...(existing?.metadata ?? {}),
      lane: payload.lane ?? existing?.metadata?.lane,
      attempt: payload.attempt ?? existing?.metadata?.attempt,
      retry_count: payload.retry_count ?? existing?.metadata?.retry_count,
      elapsed_ms: payload.elapsed_ms ?? existing?.metadata?.elapsed_ms,
    },
    payload: {
      ...(existing?.payload ?? {}),
      summary: payload.summary ?? existing?.payload?.summary,
      receipt: payload.receipt ?? existing?.payload?.receipt,
      artifacts: payload.artifacts ?? existing?.payload?.artifacts,
      error_code: payload.error_code ?? existing?.payload?.error_code,
    },
  };

  let laneStatus: ToolCallUpdateResult['laneStatus'] = 'in_progress';
  let thinking: string[] = [];

  if (eventName === 'tool_attempt') {
    nextResult.status = 'running';
    nextResult.started_at = payload.ts ?? existing?.started_at ?? null;
    nextResult.completed_at = existing?.completed_at ?? null;
    laneStatus = 'in_progress';
    thinking = [
      `Starting ${toolName} (attempt ${payload.attempt ?? 1}${payload.retry_count ? `, retry ${payload.retry_count}` : ''})`,
    ];
  } else {
    const status = (payload.status || '').toLowerCase();
    nextResult.completed_at = payload.ts ?? new Date().toISOString();
    nextResult.status = status === 'error' ? 'failed' : 'completed';
    if (status === 'error') {
      nextResult.error = payload.summary || payload.error_code || 'Tool failed';
      laneStatus = 'error';
      thinking = [
        `${toolName} failed${payload.error_code ? ` (${payload.error_code})` : ''}${payload.summary ? `: ${payload.summary}` : ''}`,
      ];
    } else {
      nextResult.error = null;
      laneStatus = 'completed';
      thinking = [
        payload.summary ? `${toolName} completed: ${payload.summary}` : `${toolName} completed successfully.`,
      ];
    }
  }

  if (existingIndex >= 0) {
    results[existingIndex] = nextResult;
  } else {
    results.push(nextResult);
  }

  return {
    results: results.slice(-10),
    laneStatus,
    thinking,
  };
};
