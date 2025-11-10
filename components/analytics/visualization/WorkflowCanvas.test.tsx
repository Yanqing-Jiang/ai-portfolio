import React from 'react';
import { describe, it, expect, beforeAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { WorkflowCanvas } from './WorkflowCanvas';
import type { ProcessStep } from '../types';

beforeAll(() => {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  (globalThis as any).ResizeObserver = ResizeObserverMock;
});

const buildStep = (overrides?: Partial<ProcessStep>): ProcessStep => ({
  id: 'tool_execution',
  name: 'Tool Execution',
  status: 'completed',
  thinking: ['Planning tool calls'],
  details: {
    tool_calls: [
      {
        tool: 'web_retriever',
        status: 'end',
        lane: 'web',
        elapsed_ms: 620,
        ts: new Date().toISOString(),
        sequence: 1,
      },
    ],
    agent_turns: [
      {
        role: 'web_specialist',
        status: 'complete',
        lane: 'web',
        tool: 'web_retriever',
        elapsed_ms: 450,
        ts: new Date().toISOString(),
        sequence: 2,
      },
    ],
  },
  ...overrides,
});

describe('WorkflowCanvas', () => {
  it('renders tool badges when tool telemetry is present', async () => {
    const step = buildStep();
    render(<WorkflowCanvas steps={[step]} flowMode="single-agent" isVisible />);
    await waitFor(() => expect(screen.getByTestId('process-node-tool-badges')).toBeInTheDocument());
    expect(screen.getAllByText(/Web Retriever/i).length).toBeGreaterThan(0);
  });

  it('surfaces lane reuse pills and redirect notice in the header', async () => {
    const step = buildStep();
    render(
      <WorkflowCanvas
        steps={[step]}
        flowMode="single-agent"
        laneReuseNotices={[{ lane: 'web', message: 'Web lane reused', ageSeconds: 58 }]}
        redirectNotice="Agent requested a fresh baseline"
      />,
    );
    await waitFor(() => expect(screen.getByTitle(/Web lane reused/i)).toBeInTheDocument());
    expect(screen.getByText(/fresh baseline/i)).toBeInTheDocument();
  });

  it('tags the root container with screenshot metadata', () => {
    const step = buildStep();
    render(<WorkflowCanvas steps={[step]} flowMode="single-agent" isVisible />);
    const root = screen.getByTestId('workflow-canvas-root');
    expect(root).toHaveAttribute('data-screenshot-target', 'workflow-canvas');
  });

  it('shows agentic badge and fresh lane telemetry pills', async () => {
    const step = buildStep();
    render(
      <WorkflowCanvas
        steps={[step]}
        flowMode="single-agent"
        agenticRevision
        freshLaneStates={{
          sql: {
            lane: 'sql',
            status: 'completed',
            ts: new Date().toISOString(),
            reason: 'Forced fresh run',
            reasoningEffort: 'minimal',
          },
        }}
      />,
    );
    await waitFor(() => expect(screen.getByText(/Agentic Revision/i)).toBeInTheDocument());
    expect(screen.getByText(/SQL Lane completed/i)).toBeInTheDocument();
  });
});
