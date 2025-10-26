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

    expect(screen.getByText('Topics: showing 1 of 2')).toBeInTheDocument();
    expect(screen.getByText('Waiting on 1 more topic from merge pipeline')).toBeInTheDocument();
    expect(screen.getByText('Topic 1 of 2')).toBeInTheDocument();
    expect(screen.getByText('Company focus')).toBeInTheDocument();
    expect(screen.getByText(/Snippet body/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Next topic' })).not.toBeInTheDocument();
  });

  it('indicates when additional topics are still pending from the provider', () => {
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

    expect(screen.getByText('Topics: showing 1 of 2')).toBeInTheDocument();
    expect(screen.getByText('Waiting on 1 more topic from merge pipeline')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Previous topic' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Next topic' })).not.toBeInTheDocument();
    expect(screen.getByText('AMD vs NVIDIA revenue comparison')).toBeInTheDocument();
  });

  it('renders primary and secondary market research questions together', () => {
    render(
      <WebSearchCard
        result={{
          query: 'Qualcomm market perception',
          topics: [
            {
              label: 'Primary question',
              display_name: 'Market Research Question A',
              snippets: [
                {
                  title: 'Primary coverage',
                  url: 'https://example.com/a',
                  snippet: 'Primary insight body.',
                  display_url: 'example.com',
                },
              ],
            },
            {
              label: 'Secondary question',
              display_name: 'Market Research Question B',
              snippets: [
                {
                  title: 'Secondary coverage',
                  url: 'https://example.com/b',
                  snippet: 'Secondary insight body.',
                  display_url: 'example.com',
                },
              ],
            },
          ],
        }}
      />
    );

    expect(screen.getByText('Topics: 2')).toBeInTheDocument();
    expect(screen.getByText('Market Research Question A')).toBeInTheDocument();
    expect(screen.getByText('Primary insight body.')).toBeInTheDocument();
    expect(screen.getByText('Market Research Question B')).toBeInTheDocument();
    expect(screen.getByText('Secondary insight body.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Next topic' })).not.toBeInTheDocument();
  });
});
