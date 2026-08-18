import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { CalendarPicker } from '@/components/consulting/CalendarPicker';

describe('CalendarPicker', () => {
    it('shows the calendar but prevents date selection when disabled', () => {
        const onSelectDate = vi.fn();
        render(
            <CalendarPicker
                selectedDate={null}
                onSelectDate={onSelectDate}
                disabled
            />
        );

        const dateButtons = screen.getAllByRole('button').slice(2);
        expect(dateButtons.length).toBeGreaterThan(0);
        expect(dateButtons.every((button) => button.hasAttribute('disabled'))).toBe(true);

        fireEvent.click(dateButtons.at(-1)!);
        expect(onSelectDate).not.toHaveBeenCalled();
    });
});
