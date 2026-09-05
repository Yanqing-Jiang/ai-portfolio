import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReadingErrorCard } from '../../components/generativeUiDashboard/fortune/shared/ReadingErrorCard';
vi.mock('../../components/AuthModal', () => ({ AuthModal: ({ isOpen }: { isOpen: boolean }) => isOpen ? <div role="dialog">Sign in</div> : null }));

describe('reading quota recovery', () => {
  it('opens sign-in without discarding the reading or restarting the quota loop', () => {
    const restart = vi.fn();
    render(<ReadingErrorCard failure={{ kind: 'failed', message: 'Sign-in required after free quota' }} onRestart={restart} />);
    fireEvent.click(screen.getByRole('button', { name: 'Sign in to continue' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(restart).not.toHaveBeenCalled();
  });
  it('retains restart recovery for a stopped generation', () => {
    const restart = vi.fn();
    render(<ReadingErrorCard failure={{ kind: 'failed', message: 'This reading stopped.' }} onRestart={restart} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start a new reading' }));
    expect(restart).toHaveBeenCalledOnce();
  });
});
