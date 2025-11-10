// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useProcessSteps } from './useProcessSteps';

describe('useProcessSteps', () => {
  it('dedupes repeated thinking logs for the same step', () => {
    const { result } = renderHook(() => useProcessSteps());

    act(() => {
      result.current.updateStepStatus('classification', 'in_progress', ['Starting query classification...']);
    });
    act(() => {
      result.current.updateStepStatus('classification', 'in_progress', ['Starting query classification...']);
    });

    const step = result.current.processSteps.find((entry) => entry.id === 'classification');
    expect(step?.thinking).toEqual(['Starting query classification...']);
  });

  it('replaces details when replaceDetails flag is provided', () => {
    const { result } = renderHook(() => useProcessSteps());

    act(() => {
      result.current.updateStepStatus('clarification', 'in_progress', [], { request: { question: 'Need ticker' } });
    });
    act(() => {
      result.current.updateStepStatus(
        'clarification',
        'in_progress',
        [],
        { slot: 'company' },
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        { replaceDetails: true },
      );
    });

    const step = result.current.processSteps.find((entry) => entry.id === 'clarification');
    expect(step?.details).toEqual({ slot: 'company' });
  });
});
