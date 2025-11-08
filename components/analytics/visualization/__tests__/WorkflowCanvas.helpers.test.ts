import { describe, expect, it } from 'vitest';

import { buildToolBadgeModels } from '../WorkflowCanvas';
import { ProcessStep } from '../../types';

describe('buildToolBadgeModels', () => {
  const baseStep: ProcessStep = {
    id: 'tool_execution',
    name: 'Tool Execution',
    status: 'completed',
    thinking: [],
    details: {
      tool_calls: [
        { tool: 'sql_generator', status: 'start', lane: 'sql_generator', elapsed_ms: 120 },
        { tool: 'web_retriever', status: 'end', lane: 'web', reused: true, elapsed_ms: 640 },
      ],
    },
  };

  it('captures tool, lane, status, and reuse metadata', () => {
    const badges = buildToolBadgeModels(baseStep, 3);
    expect(badges).toHaveLength(2);
    expect(badges[0]).toMatchObject({
      tool: 'sql_generator',
      laneLabel: 'Sql Generator',
      statusLabel: 'running',
      elapsedLabel: '120ms',
      reused: false,
    });
    expect(badges[1]).toMatchObject({
      tool: 'web_retriever',
      laneLabel: 'Web',
      statusLabel: 'completed',
      elapsedLabel: '640ms',
      reused: true,
    });
  });

  it('respects the limit parameter and falls back gracefully', () => {
    const singleBadge = buildToolBadgeModels(baseStep, 1);
    expect(singleBadge).toHaveLength(1);
    expect(singleBadge[0].tool).toBe('web_retriever');

    const empty = buildToolBadgeModels({ ...baseStep, details: {} }, 2);
    expect(empty).toEqual([]);
  });
});
