import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { OracleChat } from '../../components/generativeUiDashboard/fortune/shared/OracleChat';
import { GlassBoxPanel } from '../../components/generativeUiDashboard/fortune/shared/GlassBoxPanel';
import {
  getFortuneAskErrorMessage,
  isFortuneAskErrorRetryable,
  useConversationHydration,
  useFortuneAsk,
} from '../../components/generativeUiDashboard/hooks/useFortuneAsk';
import { useFortuneSession } from '../../components/generativeUiDashboard/hooks/useFortuneSession';
import { useFortuneStream } from '../../components/generativeUiDashboard/hooks/useFortuneStream';
import { useA2UIStream } from '../../components/generativeUiDashboard/a2ui/useA2UIStream';
import { authService } from '../../services/auth';
import { fortuneClient, FortuneApiError } from '../../components/generativeUiDashboard/lib/fortuneClient';
import { useFortuneStore } from '../../components/generativeUiDashboard/stores/fortuneStore';

describe('fortune Ask state', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    useFortuneStore.getState().reset();
  });

  it('reports a failed Pause request instead of silently accepting it', async () => {
    vi.spyOn(authService, 'getAuthHeaders').mockResolvedValue({});
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ detail: 'Fortune session not found' }, { status: 404 })));
    await expect(fortuneClient.cancelFortune('missing')).rejects.toMatchObject({ status: 404 });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('hydrates remote conversation without discarding optimistic local turns', () => {
    const store = useFortuneStore.getState();
    store.beginAsk({
      id: 'local',
      role: 'user',
      content: 'A new local question',
      timestampISO: '2026-07-13T12:01:00Z',
    });
    store.hydrateAskHistory([{
      id: 'remote',
      role: 'agent',
      content: 'A restored answer',
      timestampISO: '2026-07-13T12:00:00Z',
    }]);

    expect(useFortuneStore.getState().askHistory.map((turn) => turn.id)).toEqual([
      'remote',
      'local',
    ]);
  });

  it('preserves a retryable failed exchange when conversation hydration remounts Ask', () => {
    const store = useFortuneStore.getState();
    store.beginAsk({
      id: 'failed-question', role: 'user', content: 'Please explain this.',
      timestampISO: '2026-07-13T12:01:00Z', clientRequestId: 'request-1',
    });
    store.failAsk(
      'The service is temporarily unavailable.',
      'Please explain this.',
      undefined,
      'request-1',
      true,
    );
    store.hydrateAskHistory([{
      id: 'remote', role: 'agent', content: 'Earlier answer', timestampISO: '2026-07-13T12:00:00Z',
    }]);

    expect(useFortuneStore.getState().askHistory.map((turn) => turn.id)).toEqual([
      'remote', 'failed-question', expect.stringMatching(/^err-/),
    ]);
  });

  it('preserves the retrying question when delayed hydration lands mid-retry', () => {
    const store = useFortuneStore.getState();
    store.beginAsk({
      id: 'retry-question', role: 'user', content: 'Please retry this.',
      timestampISO: '2026-07-13T12:01:00Z', clientRequestId: 'request-retry',
    });
    store.failAsk(
      'Temporary failure.',
      'Please retry this.',
      undefined,
      'request-retry',
      true,
    );
    store.retryAsk('request-retry');
    store.hydrateAskHistory([{
      id: 'remote', role: 'agent', content: 'Earlier answer', timestampISO: '2026-07-13T12:00:00Z',
    }]);

    expect(useFortuneStore.getState().askHistory.map((turn) => turn.id)).toEqual([
      'remote', 'retry-question',
    ]);
    expect(useFortuneStore.getState().askHistory.at(-1)?.pending).toBe(true);
  });

  it('does not duplicate locally rendered turns when server timestamps differ', () => {
    const store = useFortuneStore.getState();
    store.beginAsk({
      id: 'local-user', role: 'user', content: 'Same question', timestampISO: 'local-1',
    });
    store.finishAsk({
      id: 'local-agent', role: 'agent', content: 'Same answer', timestampISO: 'local-2',
    });
    store.hydrateAskHistory([
      { id: 'remote-user', role: 'user', content: 'Same question', timestampISO: 'server-1' },
      { id: 'remote-agent', role: 'agent', content: 'Same answer', timestampISO: 'server-2' },
    ]);

    expect(useFortuneStore.getState().askHistory).toHaveLength(2);
  });

  it('preserves Ask history when a same-fortune snapshot resync has no conversation payload', () => {
    const store = useFortuneStore.getState();
    store.setFortune('fortune-a', 'run-a');
    store.hydrateAskHistory([
      { id: 'q', role: 'user', content: 'Why?', timestampISO: '1' },
      { id: 'a', role: 'agent', content: 'Because.', timestampISO: '2' },
    ]);
    store.hydrateFromReplay({
      fortune_id: 'fortune-a', run_id: 'run-a2', function_id: 'wish',
      status: 'complete', last_seq: 0, metadata: { created_at: '3' },
      data_model: {}, ask_history: [],
    });
    expect(useFortuneStore.getState().askHistory.map((turn) => turn.id)).toEqual(['q', 'a']);
  });

  it('uses durable ordering for intentionally repeated questions', () => {
    const store = useFortuneStore.getState();
    store.setFortune('fortune-a', 'run-a');
    store.hydrateAskHistory([
      { id: 'q1', role: 'user', content: 'Why?', timestampISO: '1' },
      { id: 'a1', role: 'agent', content: 'First.', timestampISO: '2' },
      { id: 'q2', role: 'user', content: 'Why?', timestampISO: '3' },
      { id: 'a2', role: 'agent', content: 'Second.', timestampISO: '4' },
    ]);
    expect(useFortuneStore.getState().askHistory.map((turn) => turn.id)).toEqual([
      'q1', 'a1', 'q2', 'a2',
    ]);
  });

  it('drops a delayed conversation response after switching fortunes', async () => {
    let resolveConversation!: (value: { fortune_id: string; turns: Array<{ role: 'user' | 'assistant'; text: string; at: string }> }) => void;
    const pending = new Promise<{ fortune_id: string; turns: Array<{ role: 'user' | 'assistant'; text: string; at: string }> }>((resolve) => {
      resolveConversation = resolve;
    });
    vi.spyOn(fortuneClient, 'getConversation').mockImplementation((fortuneId) => (
      fortuneId === 'fortune-a'
        ? pending
        : Promise.resolve({ fortune_id: fortuneId, turns: [] })
    ));

    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    const { unmount } = renderHook(() => {
      const fortuneId = useFortuneStore((state) => state.fortuneId);
      useConversationHydration(fortuneId);
    });
    await waitFor(() => expect(fortuneClient.getConversation).toHaveBeenCalledWith('fortune-a'));
    act(() => useFortuneStore.getState().setFortune('fortune-b', 'run-b'));
    await act(async () => {
      resolveConversation({
        fortune_id: 'fortune-a',
        turns: [{ role: 'assistant', text: 'Answer from A', at: '2026-07-13T12:00:00Z' }],
      });
      await pending;
    });

    expect(useFortuneStore.getState().askHistory).toEqual([]);
    unmount();
  });

  it('does not let delayed snapshot A overwrite fortune B', async () => {
    let resolveA!: (value: Awaited<ReturnType<typeof fortuneClient.getFortune>>) => void;
    const pendingA = new Promise<Awaited<ReturnType<typeof fortuneClient.getFortune>>>((resolve) => {
      resolveA = resolve;
    });
    const snapshot = (id: string, marker: string) => ({
      fortune_id: id,
      status: 'done',
      metadata: { created_at: '2026-07-13T12:00:00Z', function_id: 'wish' },
      data: {},
      data_model: { marker },
    });
    vi.spyOn(fortuneClient, 'getFortune').mockImplementation((id) => (
      id === 'fortune-a' ? pendingA : Promise.resolve(snapshot(id, 'B'))
    ));

    function Harness() {
      useFortuneSession({ functionId: 'wish', baseRoute: '/fortune' });
      return null;
    }
    const route = (id: string) => (
      <MemoryRouter key={id} initialEntries={[`/fortune/${id}`]}>
        <Routes><Route path="/fortune/:fortuneId" element={<Harness />} /></Routes>
      </MemoryRouter>
    );
    const view = render(route('fortune-a'));
    await waitFor(() => expect(fortuneClient.getFortune).toHaveBeenCalledWith('fortune-a'));

    view.rerender(route('fortune-b'));
    await waitFor(() => expect(useFortuneStore.getState().fortuneId).toBe('fortune-b'));
    await act(async () => {
      resolveA(snapshot('fortune-a', 'A'));
      await pendingA;
    });

    expect(useFortuneStore.getState().fortuneId).toBe('fortune-b');
    expect(useFortuneStore.getState().dataModel).toMatchObject({ marker: 'B' });
  });

  it('starts an Ask without waiting for a stalled conversation hydration', async () => {
    vi.spyOn(fortuneClient, 'getConversation').mockImplementation(() => new Promise(() => {}));
    const ask = vi.spyOn(fortuneClient, 'askFollowUp').mockResolvedValue({
      fortune_id: 'fortune-a',
      run_id: 'run-answer',
      narrative: { tldr: 'Immediate answer', insights: [] },
      degraded_memory: false,
    });
    act(() => {
      useFortuneStore.getState().setFortune('fortune-a', 'run-a');
      useFortuneStore.getState().setAskInput('Can I ask now?');
    });
    const { result } = renderHook(() => {
      const fortuneId = useFortuneStore((state) => state.fortuneId);
      useConversationHydration(fortuneId);
      return useFortuneAsk();
    });

    act(() => result.current.send());

    await waitFor(() => expect(ask).toHaveBeenCalledOnce());
    await waitFor(() => expect(useFortuneStore.getState().askLoading).toBe(false));
    expect(useFortuneStore.getState().askHistory.at(-1)?.content).toBe('Immediate answer');
  });

  it('submits a predefined question without waiting for composer state to update', async () => {
    vi.spyOn(fortuneClient, 'getConversation').mockResolvedValue({ fortune_id: 'fortune-a', turns: [] });
    const ask = vi.spyOn(fortuneClient, 'askFollowUp').mockResolvedValue({
      fortune_id: 'fortune-a',
      run_id: 'run-suggestion',
      narrative: { tldr: 'Suggested answer', insights: [] },
      degraded_memory: false,
    });
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    const { result } = renderHook(() => useFortuneAsk());

    act(() => result.current.send('What defines a Lucky Day?'));

    await waitFor(() => expect(ask).toHaveBeenCalledWith(
      'fortune-a',
      'What defines a Lucky Day?',
      expect.any(String),
      undefined,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));
    expect(useFortuneStore.getState().askHistory[0]).toMatchObject({
      role: 'user',
      content: 'What defines a Lucky Day?',
    });
  });

  it('drops an in-flight answer after an A to B to A navigation', async () => {
    let resolveAsk!: (value: Awaited<ReturnType<typeof fortuneClient.askFollowUp>>) => void;
    const pendingAsk = new Promise<Awaited<ReturnType<typeof fortuneClient.askFollowUp>>>((resolve) => {
      resolveAsk = resolve;
    });
    vi.spyOn(fortuneClient, 'getConversation').mockResolvedValue({ fortune_id: 'fortune-a', turns: [] });
    vi.spyOn(fortuneClient, 'askFollowUp').mockReturnValue(pendingAsk);
    act(() => {
      useFortuneStore.getState().setFortune('fortune-a', 'run-a');
      useFortuneStore.getState().setAskInput('Question from the first A visit');
    });
    const { result } = renderHook(() => useFortuneAsk());

    act(() => result.current.send());
    await waitFor(() => expect(useFortuneStore.getState().askLoading).toBe(true));
    act(() => {
      useFortuneStore.getState().setFortune('fortune-b', 'run-b');
      useFortuneStore.getState().setFortune('fortune-a', 'run-a-return');
    });
    await act(async () => {
      resolveAsk({
        fortune_id: 'fortune-a',
        run_id: 'orphan-run',
        narrative: { tldr: 'Orphan answer', insights: [] },
        degraded_memory: false,
      });
      await pendingAsk;
    });

    expect(useFortuneStore.getState().fortuneId).toBe('fortune-a');
    expect(useFortuneStore.getState().askHistory).toEqual([]);
    expect(useFortuneStore.getState().runId).toBe('run-a-return');
  });

  it('advances the Ask generation across replay A to B to A navigation', () => {
    const replay = (id: string) => ({
      fortune_id: id,
      run_id: `run-${id}`,
      function_id: 'wish' as const,
      status: 'complete' as const,
      last_seq: 0,
      metadata: { created_at: '2026-07-13T12:00:00Z' },
      data_model: {},
      ask_history: [],
    });
    const store = useFortuneStore.getState();
    store.hydrateFromReplay(replay('fortune-a'));
    const firstA = useFortuneStore.getState().fortuneGeneration;
    store.hydrateFromReplay(replay('fortune-b'));
    store.hydrateFromReplay(replay('fortune-a'));

    expect(useFortuneStore.getState().fortuneGeneration).toBe(firstA + 2);
  });

  it('ignores a stale EventSource callback after switching fortunes', () => {
    class MockEventSource {
      static instances: MockEventSource[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();

      constructor(public url: string) {
        MockEventSource.instances.push(this);
      }

      addEventListener = vi.fn();
    }
    vi.stubGlobal('EventSource', MockEventSource);
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    const { rerender } = renderHook(
      ({ fortuneId, streamUrl }) => useFortuneStream({ fortuneId, streamUrl }),
      { initialProps: { fortuneId: 'fortune-a', streamUrl: 'https://example.test/a' } },
    );
    const oldConnection = MockEventSource.instances[0];

    act(() => useFortuneStore.getState().setFortune('fortune-b', 'run-b'));
    rerender({ fortuneId: 'fortune-b', streamUrl: 'https://example.test/b' });
    act(() => {
      oldConnection.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({
          fortune_id: 'fortune-a',
          run_id: 'stale-run-a',
          seq: 1,
          payload: {
            dataModelUpdate: {
              path: '/data/stale',
              contents: [{ key: 'marker', valueString: 'from-a' }],
            },
          },
        }),
      }));
    });

    const state = useFortuneStore.getState();
    expect(state.fortuneId).toBe('fortune-b');
    expect(state.runId).toBe('run-b');
    expect((state.dataModel as Record<string, unknown> | null)?.stale).toBeUndefined();
  });

  it('resets the sequence cursor when switching fortunes', () => {
    class MockEventSource {
      static instances: MockEventSource[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      constructor(public url: string) { MockEventSource.instances.push(this); }
      addEventListener = vi.fn();
    }
    vi.stubGlobal('EventSource', MockEventSource);
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    const { rerender } = renderHook(
      ({ fortuneId, streamUrl }) => useFortuneStream({ fortuneId, streamUrl }),
      { initialProps: { fortuneId: 'fortune-a', streamUrl: 'https://example.test/a' } },
    );
    act(() => MockEventSource.instances[0].onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ fortune_id: 'fortune-a', run_id: 'run-a', seq: 10, payload: {} }),
    })));
    act(() => useFortuneStore.getState().setFortune('fortune-b', 'run-b'));
    rerender({ fortuneId: 'fortune-b', streamUrl: 'https://example.test/b' });
    const current = MockEventSource.instances.at(-1)!;
    act(() => current.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({
        fortune_id: 'fortune-b', run_id: 'run-b', seq: 1,
        payload: { dataModelUpdate: { path: '/data/fresh', contents: [{ key: 'ok', valueBoolean: true }] } },
      }),
    })));
    expect((useFortuneStore.getState().dataModel as Record<string, unknown>).fresh).toEqual({ ok: true });
  });

  it('resets completion and sequence for a new run on the same fortune', () => {
    class MockEventSource {
      static instances: MockEventSource[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      constructor(public url: string) { MockEventSource.instances.push(this); }
      addEventListener = vi.fn();
    }
    vi.stubGlobal('EventSource', MockEventSource);
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    const { rerender } = renderHook(
      ({ streamUrl }) => useFortuneStream({ fortuneId: 'fortune-a', streamUrl }),
      { initialProps: { streamUrl: 'https://example.test/run-a' } },
    );
    act(() => MockEventSource.instances[0].onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ fortune_id: 'fortune-a', run_id: 'run-a', seq: 10, payload: {} }),
    })));

    rerender({ streamUrl: 'https://example.test/run-b' });
    const current = MockEventSource.instances.at(-1)!;
    act(() => current.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({
        fortune_id: 'fortune-a', run_id: 'run-b', seq: 1,
        payload: { dataModelUpdate: { path: '/data/action', contents: [{ key: 'accepted', valueBoolean: true }] } },
      }),
    })));

    expect(MockEventSource.instances).toHaveLength(2);
    expect((useFortuneStore.getState().dataModel as Record<string, unknown>).action).toEqual({ accepted: true });
  });

  it('manual reconnect clears a completed latch even when the stream URL is unchanged', () => {
    class MockEventSource {
      static instances: MockEventSource[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      constructor(public url: string) { MockEventSource.instances.push(this); }
      addEventListener = vi.fn();
    }
    vi.stubGlobal('EventSource', MockEventSource);
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    const { result } = renderHook(() => useFortuneStream({
      fortuneId: 'fortune-a', streamUrl: 'https://example.test/same-url',
    }));
    act(() => MockEventSource.instances[0].onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ fortune_id: 'fortune-a', run_id: 'run-a', done: true }),
    })));
    act(() => result.current.reconnect());

    expect(MockEventSource.instances).toHaveLength(2);
    expect(MockEventSource.instances[1].url).toBe('https://example.test/same-url');
  });

  it('keeps a terminal stream error from being overwritten by the done sentinel', () => {
    class MockEventSource {
      static instances: MockEventSource[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      constructor(public url: string) { MockEventSource.instances.push(this); }
      addEventListener = vi.fn();
    }
    vi.stubGlobal('EventSource', MockEventSource);
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    const { result } = renderHook(() => useFortuneStream({
      fortuneId: 'fortune-a', streamUrl: 'https://example.test/error-run',
    }));
    const connection = MockEventSource.instances[0];
    act(() => connection.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({
        fortune_id: 'fortune-a', run_id: 'run-a', seq: 1,
        payload: {
          dataModelUpdate: {
            path: '/data/meta',
            contents: [
              { key: 'status', valueString: 'error' },
              { key: 'error_message', valueString: 'withheld' },
            ],
          },
        },
      }),
    })));
    act(() => connection.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ fortune_id: 'fortune-a', run_id: 'run-a', seq: 2, payload: { done: true } }),
    })));

    expect(result.current.phase).toBe('error');
    expect(useFortuneStore.getState().status).toBe('error');
  });

  it('unwraps fortune envelopes and keeps A2UI terminal errors after done', async () => {
    class MockEventSource {
      static instances: MockEventSource[] = [];
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      constructor(public url: string) { MockEventSource.instances.push(this); }
      addEventListener = vi.fn();
    }
    vi.stubGlobal('EventSource', MockEventSource);
    const { result } = renderHook(() => useA2UIStream('https://example.test/a2ui-error'));
    const connection = MockEventSource.instances[0];

    act(() => connection.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({
        fortune_id: 'fortune-a', run_id: 'run-a', seq: 1,
        payload: {
          dataModelUpdate: {
            surfaceId: 'fortune_main', path: '/data/meta',
            contents: [
              { key: 'status', valueString: 'error' },
              { key: 'error_message', valueString: 'Guardrail withheld this response.' },
            ],
          },
        },
      }),
    })));
    act(() => connection.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({
        fortune_id: 'fortune-a', run_id: 'run-a', seq: 2,
        payload: { done: true },
      }),
    })));

    await waitFor(() => expect(result.current[0].isDone).toBe(true));
    expect(result.current[0].connectionStatus).toBe('error');
    expect(result.current[0].error?.message).toBe('Guardrail withheld this response.');
  });

  it('distinguishes a busy Ask lock from an unfinished reading', () => {
    expect(getFortuneAskErrorMessage(
      new FortuneApiError('This fortune is busy', 409),
    )).toContain('Another answer');
    expect(getFortuneAskErrorMessage(
      new FortuneApiError('Initial reading not yet complete', 409),
    )).toContain('still being prepared');
  });

  it('only offers retry for transient Ask failures', () => {
    expect(isFortuneAskErrorRetryable(new FortuneApiError('invalid', 422))).toBe(false);
    expect(isFortuneAskErrorRetryable(new FortuneApiError('down', 503))).toBe(true);
  });

  it('clears Ask state when navigating to another fortune', () => {
    const store = useFortuneStore.getState();
    store.setFortune('fortune-a', 'run-a');
    store.setAskInput('stale draft');
    store.beginAsk({
      id: 'local', role: 'user', content: 'old question', timestampISO: '2026-07-13T12:00:00Z',
    });
    store.setFortune('fortune-b', 'run-b');

    const next = useFortuneStore.getState();
    expect(next.askInput).toBe('');
    expect(next.askHistory).toEqual([]);
    expect(next.askLoading).toBe(false);
  });

  it('stops trace refreshes for a fortune after a terminal quota error', async () => {
    const getTrace = vi.spyOn(fortuneClient, 'getTrace').mockRejectedValue(
      new FortuneApiError('Unauthorized', 401),
    );
    act(() => useFortuneStore.getState().setFortune('fortune-a', 'run-a'));
    render(<GlassBoxPanel />);
    // The trace only loads once the drawer is opened.
    fireEvent.click(screen.getByRole('button', { expanded: false }));

    await waitFor(() => expect(getTrace).toHaveBeenCalledOnce());
    act(() => useFortuneStore.getState().beginAsk({
      id: 'question', role: 'user', content: 'Why?', timestampISO: '1',
    }));
    act(() => useFortuneStore.getState().finishAsk({
      id: 'answer', role: 'agent', content: 'Because.', timestampISO: '2',
    }));
    await act(async () => { await Promise.resolve(); });

    expect(getTrace).toHaveBeenCalledOnce();
  });
});

describe('OracleChat accessibility and recovery', () => {
  it('turns cold-start and follow-up suggestions into immediate chat submissions', () => {
    const onSend = vi.fn();
    const { rerender } = render(
      <OracleChat
        messages={[]}
        input=""
        onInputChange={vi.fn()}
        onSend={onSend}
        suggestions={['What defines a Lucky Day?']}
      />,
    );

    const chat = screen.getByRole('log', { name: 'Ask conversation' });
    const coldStartQuestion = screen.getByRole('button', { name: 'What defines a Lucky Day?' });
    expect(chat).toContainElement(coldStartQuestion);
    fireEvent.click(coldStartQuestion);
    expect(onSend).toHaveBeenCalledWith('What defines a Lucky Day?');

    rerender(
      <OracleChat
        messages={[{ id: 'answer', role: 'agent', content: 'A complete answer.' }]}
        input=""
        onInputChange={vi.fn()}
        onSend={onSend}
        suggestions={['Compare the top picks']}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Compare the top picks/ }));
    expect(onSend).toHaveBeenCalledWith('Compare the top picks');
  });

  it('shows selected context, exposes a bounded composer, and retries an error', () => {
    const onRetry = vi.fn();
    render(
      <OracleChat
        messages={[{
          id: 'error',
          role: 'agent',
          content: 'The service is temporarily unavailable.',
          error: true,
          retryable: true,
          retryQuestion: 'What does this anchor mean?',
        }]}
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        onRetry={onRetry}
        contextLabel="Anchor"
      />,
    );

    expect(screen.getByRole('log', { name: 'Ask conversation' })).toBeInTheDocument();
    expect(screen.getByText('Anchor')).toBeInTheDocument();
    expect(screen.getByLabelText('Ask a question about this reading')).toHaveAttribute('maxlength', '500');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledWith(expect.objectContaining({ id: 'error' }));
  });
});
