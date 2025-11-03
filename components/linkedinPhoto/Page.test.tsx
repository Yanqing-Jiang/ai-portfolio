import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Page } from './Page';

const createHeadshotResponse = () => ({
  expanded_prompt:
    'Corporate studio portrait with flattering clamshell lighting, confident expression, and soft blue gradient backdrop.',
  variations: [
    {
      id: 'var-1-test',
      image_base64: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII=',
      image_mime_type: 'image/png',
      width: 1024,
      height: 1024,
    },
    {
      id: 'var-2-test',
      image_base64: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII=',
      image_mime_type: 'image/png',
      width: 1024,
      height: 1024,
    },
    {
      id: 'var-3-test',
      image_base64: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII=',
      image_mime_type: 'image/png',
      width: 1024,
      height: 1024,
    },
  ],
  processing_ms: 2500,
});

describe('LinkedInPhotoPage', () => {
  const originalFetch = global.fetch;
  const originalCreateObjectUrl = global.URL.createObjectURL;
  const originalRevokeObjectUrl = global.URL.revokeObjectURL;

  beforeAll(() => {
    Object.defineProperty(global.URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(() => 'blob:preview-url'),
    });
    Object.defineProperty(global.URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
  });

  afterAll(() => {
    if (originalCreateObjectUrl) {
      Object.defineProperty(global.URL, 'createObjectURL', {
        configurable: true,
        writable: true,
        value: originalCreateObjectUrl,
      });
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (global.URL as any).createObjectURL;
    }
    if (originalRevokeObjectUrl) {
      Object.defineProperty(global.URL, 'revokeObjectURL', {
        configurable: true,
        writable: true,
        value: originalRevokeObjectUrl,
      });
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (global.URL as any).revokeObjectURL;
    }
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
    global.fetch = originalFetch;
  });

  it('keeps Generate button disabled until photo is uploaded and style is selected', async () => {
    render(<Page apiPath="/api/mock" />);

    const generateButton = screen.getByRole('button', { name: /generate professional headshots/i });
    expect(generateButton).toBeDisabled();

    // Upload a photo
    const fileInput = screen.getByRole('textbox', { hidden: true }) as HTMLInputElement;
    const file = new File(['portrait-bytes'], 'portrait.jpg', { type: 'image/jpeg' });
    await userEvent.upload(fileInput, file);

    // Button still disabled until style selected
    expect(generateButton).toBeDisabled();

    // Select a style preset
    const professionalCard = screen.getByText('Professional Corporate');
    await userEvent.click(professionalCard);

    await waitFor(() => expect(generateButton).toBeEnabled());
  });

  it('submits form data and renders multiple variations with expanded prompt', async () => {
    const mockResponse = createHeadshotResponse();
    const fetchMock = vi.fn(async (_input: RequestInfo, init?: RequestInit) => {
      expect(init?.method).toBe('POST');
      expect(init?.body).toBeInstanceOf(FormData);
      const formData = init?.body as FormData;
      expect(formData.get('prompt')).toBeTruthy();
      const uploaded = formData.get('photo');
      expect(uploaded).toBeInstanceOf(File);
      return {
        ok: true,
        json: async () => mockResponse,
      } as Response;
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    render(<Page apiPath="/api/mock" />);

    // Upload photo
    const fileInput = screen.getByRole('textbox', { hidden: true }) as HTMLInputElement;
    const file = new File(['portrait-bytes'], 'portrait.jpg', { type: 'image/jpeg' });
    await userEvent.upload(fileInput, file);

    // Select Professional Corporate style
    const professionalCard = screen.getByText('Professional Corporate');
    await userEvent.click(professionalCard);

    // Click generate button
    const generateButton = screen.getByRole('button', { name: /generate professional headshots/i });
    await userEvent.click(generateButton);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    // Check that variations are rendered
    await waitFor(() => {
      expect(screen.getByText(/3 variations generated/i)).toBeInTheDocument();
    });

    // Check expanded prompt is displayed
    expect(screen.getByText(mockResponse.expanded_prompt)).toBeInTheDocument();
  });

  it('displays error message when generation fails', async () => {
    const fetchMock = vi.fn(async () => {
      return {
        ok: false,
        json: async () => ({ detail: 'Generation failed due to server error' }),
      } as Response;
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    render(<Page apiPath="/api/mock" />);

    // Upload photo
    const fileInput = screen.getByRole('textbox', { hidden: true }) as HTMLInputElement;
    const file = new File(['portrait-bytes'], 'portrait.jpg', { type: 'image/jpeg' });
    await userEvent.upload(fileInput, file);

    // Select style
    const professionalCard = screen.getByText('Professional Corporate');
    await userEvent.click(professionalCard);

    // Generate
    const generateButton = screen.getByRole('button', { name: /generate professional headshots/i });
    await userEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByText(/generation failed due to server error/i)).toBeInTheDocument();
    });
  });
});
