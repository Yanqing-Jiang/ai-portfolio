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
      tool: 'Web Retriever',
      laneLabel: 'Web Research',
      statusLabel: 'Complete',
      elapsedLabel: '640ms',
      reused: true,
    });
    expect(badges[1]).toMatchObject({
      tool: 'Sql Generator',
      laneLabel: 'sql_generator',
      statusLabel: 'Running',
      elapsedLabel: '120ms',
      reused: undefined,
    });
  });

  it('respects the limit parameter and falls back gracefully', () => {
    const singleBadge = buildToolBadgeModels(baseStep, 1);
    expect(singleBadge).toHaveLength(1);
    expect(singleBadge[0].tool).toBe('Web Retriever');

    const empty = buildToolBadgeModels({ ...baseStep, details: {} }, 2);
    expect(empty).toEqual([]);
  });
});
