import { render, screen, fireEvent } from '@testing-library/react';
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

    expect(screen.getByText('Market Research')).toBeInTheDocument();
    expect(screen.getByText('Research topic')).toBeInTheDocument();
    expect(screen.getByText('Nvidia Q2 2025 results')).toBeInTheDocument();
    expect(screen.getByText('Nvidia posted $24B in revenue, up 89% year over year.')).toBeInTheDocument();
    expect(screen.getByText('1 result')).toBeInTheDocument();
    expect(screen.getByText('Topic 1 of 1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous topic' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next topic' })).toBeDisabled();
    expect(screen.getByRole('link', { name: 'Open source 1' })).toHaveAttribute('href', 'https://example.com/nvidia-q2');
    expect(screen.queryByText('Nvidia beat expectations with record data center revenue.')).toBeNull();
  });

  it('handles multiple topics and enables navigation', () => {
    const result: WebSearchResult = {
      query: 'AMD vs NVIDIA revenue comparison 2021-2024',
      searchTopics: ['AMD vs NVIDIA revenue comparison 2021-2024', 'AMD semiconductor industry outlook 2025'],
      snippets: [],
      topics: [
        {
          label: 'Primary question',
          topic_label: 'Primary question',
          query: 'AMD vs NVIDIA revenue comparison 2021-2024',
          topic_index: 0,
          snippets: [
            {
              title: 'alphastreet.com',
              url: 'https://vertex.example/amd-q4',
              snippet: 'AMD reported revenue of $7.66 billion.',
              display_url: 'vertex.example',
              published_at: '2025-01-28',
            },
          ],
        },
        {
          label: 'Secondary question',
          topic_label: 'Secondary question',
          query: 'AMD semiconductor industry outlook 2025',
          topic_index: 1,
          snippets: [
            {
              title: 'ainvest.com',
              url: 'https://vertex.example/industry',
              snippet: 'Semiconductor industry projected to reach $700B in 2025.',
              display_url: 'vertex.example',
              published_at: '2025-07-12',
            },
          ],
        },
      ],
      annotations: [],
      searchId: 'search_multi',
      fromCache: false,
      fetchedAt: '2025-10-23T20:14:10.605709Z',
      latencyMs: 2103,
      ready: true,
    };

    render(<WebSearchCard result={result} />);

    expect(screen.getByText('Topics: AMD vs NVIDIA revenue comparison 2021-2024; AMD semiconductor industry outlook 2025')).toBeInTheDocument();
    expect(screen.getByText('Topic 1 of 2')).toBeInTheDocument();
    expect(screen.getByText('Primary question')).toBeInTheDocument();
    expect(screen.getByText('AMD vs NVIDIA revenue comparison 2021-2024')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open source 1' })).toHaveAttribute('href', 'https://vertex.example/amd-q4');

    fireEvent.click(screen.getByRole('button', { name: 'Next topic' }));

    expect(screen.getByText('Topic 2 of 2')).toBeInTheDocument();
    expect(screen.getByText('Secondary question')).toBeInTheDocument();
    expect(screen.getByText('AMD semiconductor industry outlook 2025')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open source 1' })).toHaveAttribute('href', 'https://vertex.example/industry');
  });

  it('chunks fallback snippets into paginated topics of two results', () => {
    const result: WebSearchResult = {
      query: 'Semiconductor industry outlook',
      summary: 'Context on the semiconductor market.',
      snippets: [
        { title: 'infosys.com', url: 'https://example.com/1', snippet: 'Growth projected to 11%', display_url: 'example.com', published_at: '2025-08-01' },
        { title: 'deloitte.com', url: 'https://example.com/2', snippet: 'AI demand remains high', display_url: 'example.com', published_at: '2025-08-02' },
        { title: 'ing.com', url: 'https://example.com/3', snippet: 'Capex accelerating into 2026', display_url: 'example.com', published_at: '2025-08-03' },
      ],
      annotations: [],
      searchId: 'chunked',
      fromCache: false,
      fetchedAt: '2025-10-24T15:00:00Z',
      latencyMs: 420,
      ready: true,
    };

    render(<WebSearchCard result={result} />);

    expect(screen.getByText('Topic 1 of 2')).toBeInTheDocument();
    expect(screen.getByText('Research topic')).toBeInTheDocument();
    expect(screen.getByText('[1]')).toBeInTheDocument();
    expect(screen.getByText('[2]')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Next topic' }));

    expect(screen.getByText('Topic 2 of 2')).toBeInTheDocument();
    expect(screen.getByText('Research topic (2)')).toBeInTheDocument();
    expect(screen.getByText('[1]')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open source 1' })).toHaveAttribute('href', 'https://example.com/3');
  });
});
