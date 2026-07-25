/**
 * The in-chat picker must not leave the parent holding a slot the visitor moved
 * away from. The contact step that follows a pick is the button that BOOKS, so a
 * stale pick meant: no time looks selected, yet clicking through books the
 * abandoned one.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { InChatCalendar } from '@/components/consulting/IntakeChat';

vi.mock('@/services/config', () => ({
    configService: { getBackendUrl: () => 'http://backend.test' },
}));

/** Slots keyed by date, so switching days returns a genuinely different set. */
const slotsFor = (date: string) => [
    { start: `${date}T13:00:00-08:00`, end: `${date}T13:30:00-08:00` },
    { start: `${date}T13:30:00-08:00`, end: `${date}T14:00:00-08:00` },
];

const dayCells = () =>
    screen.getAllByRole('button').filter((b) => /^\d{1,2}$/.test(b.textContent ?? '') && !(b as HTMLButtonElement).disabled);

beforeEach(() => {
    vi.restoreAllMocks();
});

const mockSlots = (bookable = true) =>
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
        const date = new URL(url).searchParams.get('date')!;
        return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ slots: slotsFor(date), timezone: 'America/Los_Angeles', bookable }),
        });
    }));

describe('InChatCalendar', () => {
    it('retracts the pick when the visitor changes date', async () => {
        mockSlots();
        const onPick = vi.fn();
        const onClearPick = vi.fn();
        const user = userEvent.setup();

        render(<InChatCalendar sessionType="fit" onPick={onPick} onClearPick={onClearPick} />);

        const days = dayCells();
        await user.click(days[0]);
        await waitFor(() => expect(screen.getByText(/Available times/i)).toBeTruthy());

        const times = await screen.findAllByText(/\d{1,2}:\d{2}\s?(AM|PM)/i);
        await user.click(times[0]);
        expect(onPick).toHaveBeenCalledTimes(1);
        expect(screen.getByText(/Time saved/i)).toBeTruthy();

        onClearPick.mockClear();
        await user.click(dayCells()[1]);

        // The parent is told to drop it, and the confirmation line goes away.
        await waitFor(() => expect(onClearPick).toHaveBeenCalled());
        await waitFor(() => expect(screen.queryByText(/Time saved/i)).toBeNull());
    });

    it('retracts the pick if the backend stops being bookable', async () => {
        // First response bookable, the next not — e.g. credentials expired, or a
        // worker with a different verdict answered.
        let bookable = true;
        vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
            const date = new URL(url).searchParams.get('date')!;
            return Promise.resolve({
                ok: true, status: 200,
                json: async () => ({ slots: slotsFor(date), bookable }),
            });
        }));

        const onClearPick = vi.fn();
        const user = userEvent.setup();
        render(<InChatCalendar sessionType="fit" onPick={vi.fn()} onClearPick={onClearPick} />);

        await user.click(dayCells()[0]);
        const times = await screen.findAllByText(/\d{1,2}:\d{2}\s?(AM|PM)/i);
        await user.click(times[0]);
        expect(screen.getByText(/Time saved/i)).toBeTruthy();

        bookable = false;
        onClearPick.mockClear();
        await user.click(dayCells()[1]);

        await waitFor(() => expect(onClearPick).toHaveBeenCalled());
        expect(await screen.findByText(/temporarily unavailable/i)).toBeTruthy();
    });

    it('offers the email fallback instead of unbookable times', async () => {
        mockSlots(false);
        const onPick = vi.fn();
        const user = userEvent.setup();

        render(<InChatCalendar sessionType="fit" onPick={onPick} onClearPick={vi.fn()} />);
        await user.click(dayCells()[0]);

        expect(await screen.findByText(/temporarily unavailable/i)).toBeTruthy();
        expect(screen.queryByText(/\d{1,2}:\d{2}\s?(AM|PM)/i)).toBeNull();
        expect(onPick).not.toHaveBeenCalled();
    });
});
