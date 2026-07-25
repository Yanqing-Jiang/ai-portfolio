/**
 * Booking readiness rules.
 *
 * `bookable` decides whether the consult page offers times at all. Getting it
 * wrong in the permissive direction means a visitor picks a slot, clicks book,
 * and hits an error — so every uncertain state has to read as NOT bookable.
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAvailableSlots } from '@/components/consulting/useAvailableSlots';

vi.mock('@/services/config', () => ({
    configService: { getBackendUrl: () => 'http://backend.test' },
}));

const SLOTS = [
    { start: '2099-03-01T13:00:00-08:00', end: '2099-03-01T13:30:00-08:00' },
    { start: '2099-03-01T13:30:00-08:00', end: '2099-03-01T14:00:00-08:00' },
];

const respond = (body: unknown, ok = true) => ({
    ok,
    status: ok ? 200 : 500,
    json: async () => body,
});

beforeEach(() => {
    vi.restoreAllMocks();
});

describe('useAvailableSlots', () => {
    it('is bookable when the backend says so', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
            respond({ slots: SLOTS, timezone: 'America/Los_Angeles', bookable: true })
        ));

        const { result } = renderHook(() => useAvailableSlots('2099-03-01', '30'));
        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.bookable).toBe(true);
        expect(result.current.slots).toHaveLength(2);
    });

    it('is not bookable when the backend says the calendar is unavailable', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
            respond({ slots: SLOTS, timezone: 'America/Los_Angeles', bookable: false })
        ));

        const { result } = renderHook(() => useAvailableSlots('2099-03-01', '30'));
        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.bookable).toBe(false);
    });

    it('is not bookable when the field is missing', async () => {
        // A backend older than the flag served MOCK slots when its calendar was
        // unconfigured. Treating absent as bookable would offer those during a
        // frontend-first rollout or a rollback.
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
            respond({ slots: SLOTS, timezone: 'America/Los_Angeles' })
        ));

        const { result } = renderHook(() => useAvailableSlots('2099-03-01', '30'));
        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.slots).toHaveLength(2);
        expect(result.current.bookable).toBe(false);
    });

    it('is not bookable while the request is in flight', async () => {
        let release: (v: unknown) => void = () => {};
        vi.stubGlobal('fetch', vi.fn().mockImplementation(
            () => new Promise((res) => { release = res; })
        ));

        const { result } = renderHook(() => useAvailableSlots('2099-03-01', '30'));
        await waitFor(() => expect(result.current.loading).toBe(true));
        expect(result.current.bookable).toBe(false);

        await act(async () => {
            release(respond({ slots: SLOTS, bookable: true }));
        });
        await waitFor(() => expect(result.current.bookable).toBe(true));
    });

    it('is not bookable after a failed request', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

        const { result } = renderHook(() => useAvailableSlots('2099-03-01', '30'));
        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.bookable).toBe(false);
        expect(result.current.slots).toEqual([]);
        expect(result.current.error).toBeTruthy();
    });

    it('is not bookable with no date selected', async () => {
        const fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);

        const { result } = renderHook(() => useAvailableSlots(null, '30'));
        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.bookable).toBe(false);
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it('ignores a superseded response that resolves late', async () => {
        // Pick date A, then date B. If A lands second it must not repaint A's
        // times under B's heading — the visitor would book a slot they never saw.
        const dayA = [{ start: '2099-03-01T13:00:00-08:00', end: '2099-03-01T13:30:00-08:00' }];
        const dayB = [{ start: '2099-03-02T15:00:00-08:00', end: '2099-03-02T15:30:00-08:00' }];

        const pending: Array<(v: unknown) => void> = [];
        vi.stubGlobal('fetch', vi.fn().mockImplementation(
            () => new Promise((res) => { pending.push(res); })
        ));

        const { result, rerender } = renderHook(
            ({ date }: { date: string }) => useAvailableSlots(date, '30'),
            { initialProps: { date: '2099-03-01' } },
        );
        await waitFor(() => expect(pending).toHaveLength(1));

        rerender({ date: '2099-03-02' });
        await waitFor(() => expect(pending).toHaveLength(2));

        // B resolves first, then the stale A.
        await act(async () => { pending[1](respond({ slots: dayB, bookable: true })); });
        await waitFor(() => expect(result.current.slots).toEqual(dayB));

        await act(async () => { pending[0](respond({ slots: dayA, bookable: true })); });

        expect(result.current.slots).toEqual(dayB);
    });
});
