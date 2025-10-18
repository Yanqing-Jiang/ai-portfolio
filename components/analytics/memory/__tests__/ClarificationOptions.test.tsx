import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { ClarificationOptions } from '../ClarificationOptions';
import type { ClarifyRequest } from '../../types';

const baseRequest: ClarifyRequest = {
  session_id: 'sess-1',
  request_id: 'req-1',
  slot: 'timeframe',
  question: 'How many years of data should we analyze?',
  type: 'single',
  options: ['last_5_years', 'last_8_quarters'],
  default: null,
  reason: 'Timeframe is required',
  required: true,
  allow_custom: true,
};

describe('ClarificationOptions', () => {
  it('allows custom input when allow_custom is true', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ClarificationOptions clarification={baseRequest} onSubmit={onSubmit} />);

    const customInput = screen.getByPlaceholderText('Enter a custom value');
    fireEvent.change(customInput, { target: { value: 'custom timeframe' } });

    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('custom timeframe');
    });
  });

  it('hides custom input when allow_custom is false', () => {
    const onSubmit = vi.fn();
    const request = { ...baseRequest, allow_custom: false };
    render(<ClarificationOptions clarification={request} onSubmit={onSubmit} />);

    expect(screen.queryByPlaceholderText('Enter a custom value')).toBeNull();
  });
});

