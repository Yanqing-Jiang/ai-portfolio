// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { onRequestGet as snapshot } from '../../functions/api/fortune/[fortune_id]/index';
import { onRequestGet as trace } from '../../functions/api/fortune/[fortune_id]/trace';
import { onRequestGet as conversation } from '../../functions/api/fortune/[fortune_id]/conversation';

const fortuneId = 'fe70f979-fd7a-4034-abf9-ff06b761eb55';
afterEach(() => vi.unstubAllGlobals());

describe.each([['snapshot', snapshot], ['trace', trace], ['conversation', conversation]] as const)('%s replay forwarding', (_, handler) => {
  it('preserves the edge client identity and auth without trusting caller-supplied XFF', async () => {
    const upstream = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', upstream);
    const response = await handler({
      request: new Request(`https://yanqing.app/api/fortune/${fortuneId}`, { headers: {
        'cf-connecting-ip': '203.0.113.12',
        'x-forwarded-for': '198.51.100.99',
        authorization: 'Bearer test-token',
      } }),
      env: {}, params: { fortune_id: fortuneId },
    });
    const headers = new Headers(upstream.mock.calls[0][1].headers);
    expect(headers.get('cf-connecting-ip')).toBe('203.0.113.12');
    expect(headers.get('x-forwarded-for')).toBe('203.0.113.12');
    expect(headers.get('authorization')).toBe('Bearer test-token');
    expect(response.headers.get('cache-control')).toBe('no-store');
    expect(response.headers.get('x-request-id')).toBe(headers.get('x-request-id'));
  });
});
