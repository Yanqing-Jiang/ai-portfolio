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

describe('WebSearchCard topics', () => {
  it('renders topic sections with snippets', () => {
    render(
      <WebSearchCard
        result={{
          query: 'AMD market share',
          searchTopics: ['AMD market share', 'Semiconductor industry outlook'],
          snippets: [],
          topics: [
            {
              label: 'Company focus',
              query: 'AMD market share',
              snippets: [
                { title: 'Example', url: 'https://example.com', snippet: 'Snippet body', display_url: 'example.com', published_at: '2025-10-01' },
              ],
            },
          ],
        }}
      />
    );
    expect(screen.getByText('Company focus')).toBeInTheDocument();
    expect(screen.getByText(/Snippet body/)).toBeInTheDocument();
  });

  it('keeps navigation disabled until additional topics arrive even if topicTotal advertises more', () => {
    render(
      <WebSearchCard
        result={{
          query: 'AMD vs NVIDIA revenue comparison',
          topicTotal: 2,
          topics: [
            {
              label: 'Primary question',
              query: 'AMD vs NVIDIA revenue comparison',
              snippets: [
                {
                  title: 'Example',
                  url: 'https://example.com',
                  snippet: 'Snippet body',
                  display_url: 'example.com',
                  published_at: '2025-10-01',
                },
              ],
            },
          ],
        }}
      />
    );

    expect(screen.getByText('Topic 1 of 2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous topic' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next topic' })).toBeDisabled();
    expect(screen.getByText('Primary question')).toBeInTheDocument();
  });
});
