import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WebSearchCard } from '../common/WebSearchCard';
import { WebSearchResult } from '../types';

describe('WebSearchCard', () => {
  it('renders summary and snippets', () => {
    const result: WebSearchResult = {
      query: 'latest Nvidia earnings',
      summary: 'Nvidia beat expectations with record data center revenue.',
      snippets: [
        {
          title: 'Nvidia Q2 2025 results',
          url: 'https://example.com/nvidia-q2',
          snippet: 'Nvidia posted $24B in revenue, up 89% year over year.',
          display_url: 'example.com/nvidia-q2',
          published_at: '2025-08-24',
        },
      ],
      annotations: [],
      searchId: 'search_xyz',
      fromCache: false,
      fetchedAt: '2025-10-02T14:00:00Z',
      latencyMs: 152,
      ready: true,
    };

    render(<WebSearchCard result={result} />);

    expect(screen.getByText('Search Highlights')).toBeInTheDocument();
    expect(screen.getByText('latest Nvidia earnings', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('Nvidia Q2 2025 results')).toBeInTheDocument();
    expect(screen.getByText('Nvidia posted $24B in revenue, up 89% year over year.')).toBeInTheDocument();
    expect(screen.getByText('Fresh')).toBeInTheDocument();
  });
});
