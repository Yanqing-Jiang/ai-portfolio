import { describe, expect, it } from 'vitest';

import { mergeToolLifecycleEvent, upsertToolCallResult } from '../agentStreamUtils';
import { ToolFanoutResult } from '../../types';

describe('agent stream tool call updates', () => {
  it('records arguments delta and marks branch running', () => {
    const initialResults: ToolFanoutResult[] = [];
    const update = upsertToolCallResult(
      initialResults,
      'tool_call_delta',
      {
        id: 'call_1',
        name: 'generate_sql',
        arguments_delta: { sql: 'SELECT 1' },
        sequence_number: 0,
        output_index: 0,
      },
      '2025-11-05T08:00:00Z'
    );

    expect(update.results).toHaveLength(1);
    const [result] = update.results;
    expect(result.tool).toBe('generate_sql');
    expect(result.status).toBe('running');
    expect(result.metadata?.arguments_delta).toEqual({ sql: 'SELECT 1' });
    expect(result.metadata?.sequence_number).toBe(0);
    expect(update.laneStatus).toBe('in_progress');
    expect(update.thinking[0]).toContain('SQL draft updated');
  });

  it('merges final arguments and marks branch completed', () => {
    const seedResults: ToolFanoutResult[] = [
      {
        tool: 'generate_sql',
        status: 'running',
        metadata: { arguments_delta: { sql: 'SELECT 1' } },
        payload: {},
      },
    ];

    const update = upsertToolCallResult(
      seedResults,
      'tool_call_arguments',
      {
        id: 'call_1',
        name: 'generate_sql',
        arguments: { sql: 'SELECT 1' },
        sequence_number: 1,
        output_index: 0,
      },
      '2025-11-05T08:00:01Z'
    );

    expect(update.results).toHaveLength(1);
    const [result] = update.results;
    expect(result.status).toBe('completed');
    expect(result.payload?.arguments).toEqual({ sql: 'SELECT 1' });
    expect(result.metadata?.arguments_delta).toEqual({ sql: 'SELECT 1' });
    expect(update.laneStatus).toBe('completed');
    expect(update.thinking[0]).toContain('completed with arguments');
  });
});

describe('agent tool lifecycle events', () => {
  it('records tool attempt as running', () => {
    const initial: ToolFanoutResult[] = [];
    const update = mergeToolLifecycleEvent(initial, 'tool_attempt', {
      tool: 'sql_generator',
      lane: 'sql',
      attempt: 1,
      retry_count: 0,
      ts: '2025-11-06T02:00:00Z',
    });

    expect(update.results).toHaveLength(1);
    const [result] = update.results;
    expect(result.tool).toBe('sql_generator');
    expect(result.status).toBe('running');
    expect(result.started_at).toBe('2025-11-06T02:00:00Z');
    expect(result.metadata?.lane).toBe('sql');
    expect(update.laneStatus).toBe('in_progress');
    expect(update.thinking[0]).toContain('Starting sql_generator');
  });

  it('marks tool result as completed with summary', () => {
    const seed: ToolFanoutResult[] = [
      { tool: 'sql_generator', status: 'running', metadata: { lane: 'sql', attempt: 1 }, payload: {} },
    ];
    const update = mergeToolLifecycleEvent(seed, 'tool_result', {
      tool: 'sql_generator',
      status: 'completed',
      summary: 'Generated SQL successfully',
      ts: '2025-11-06T02:00:02Z',
      elapsed_ms: 1200,
    });

    expect(update.results).toHaveLength(1);
    const [result] = update.results;
    expect(result.status).toBe('completed');
    expect(result.completed_at).toBe('2025-11-06T02:00:02Z');
    expect(result.metadata?.elapsed_ms).toBe(1200);
    expect(result.payload?.summary).toBe('Generated SQL successfully');
    expect(update.laneStatus).toBe('completed');
  });

  it('marks tool result as error when status fails', () => {
    const seed: ToolFanoutResult[] = [
      { tool: 'web_retriever', status: 'running', metadata: { lane: 'web', attempt: 2 }, payload: {} },
    ];
    const update = mergeToolLifecycleEvent(seed, 'tool_result', {
      tool: 'web_retriever',
      status: 'error',
      error_code: 'NETWORK',
      summary: 'Timeout contacting search API',
      ts: '2025-11-06T02:01:00Z',
    });

    expect(update.results).toHaveLength(1);
    const [result] = update.results;
    expect(result.status).toBe('failed');
    expect(result.error).toContain('Timeout contacting search API');
    expect(update.laneStatus).toBe('error');
    expect(update.thinking[0]).toContain('failed');
  });
});
