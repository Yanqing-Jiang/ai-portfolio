// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WebSearchCard } from '../WebSearchCard';

describe('WebSearchCard provider/model chips', () => {
  it('renders provider and model badges when present', () => {
    render(
      <WebSearchCard
        result={{
          query: 'NVDA earnings',
          summary: 'Latest highlights',
          snippets: [],
          fromCache: false,
          ready: true,
          provider: 'Gemini',
          model: 'gemini-2.5-flash',
          latencyMs: 1234,
        }}
      />
    );
    expect(screen.getByText('Gemini')).toBeInTheDocument();
    expect(screen.getByText('gemini-2.5-flash')).toBeInTheDocument();
  });
});

