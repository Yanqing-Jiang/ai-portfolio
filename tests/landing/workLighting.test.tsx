/**
 * The work section has to light up without a cursor.
 *
 * Every reveal in that section was driven by `group-hover:` — so on a phone the
 * covers stayed permanently greyscale and no card ever gained its accent border.
 * Scroll-into-view now stands in for the pointer below `lg`.
 *
 * Two things are asserted, because either alone passes while the feature is
 * broken: the lit utilities are applied, AND they are `max-lg:`-scoped so the
 * desktop hover design is untouched. (That those utilities compile to a real
 * media query is a Tailwind-level concern verified against the built CSS —
 * stacking `max-lg:` with `group-data-[…]` silently drops the @media.)
 */
import { render, screen } from '@testing-library/react';
import { HelmetProvider } from 'react-helmet-async';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import LandingPageFlow from '@/components/LandingPageFlow';
import type { ProjectYear } from '@/types';

// jsdom ships no IntersectionObserver. Stubbing one that reports "intersecting"
// exercises the real observer path in `useInViewOnce` rather than its
// reduced-motion shortcut, and framer-motion's whileInView needs it to exist at
// all (it throws otherwise, which is what surfaced this).
beforeAll(() => {
    class StubObserver {
        constructor(private cb: IntersectionObserverCallback) {}
        observe(target: Element) {
            this.cb(
                [{ isIntersecting: true, target } as IntersectionObserverEntry],
                this as unknown as IntersectionObserver,
            );
        }
        unobserve() {}
        disconnect() {}
        takeRecords(): IntersectionObserverEntry[] {
            return [];
        }
        root = null;
        rootMargin = '';
        thresholds = [];
    }
    vi.stubGlobal('IntersectionObserver', StubObserver);
});
const PROJECT_DATA = [
    {
        year: 2026,
        subtitle: 'Agent era',
        projects: [
            {
                id: 'lit-probe',
                title: 'Lit Probe',
                description: 'A project used to assert the lighting behaviour.',
                cardDescription: 'A project used to assert the lighting behaviour.',
                technologies: ['TypeScript'],
                imageUrl: 'https://example.test/cover.png',
            },
        ],
    },
] as unknown as ProjectYear[];

const renderLanding = () =>
    render(
        <HelmetProvider>
            <MemoryRouter>
                <LandingPageFlow projectData={PROJECT_DATA} onSelectProject={() => {}} />
            </MemoryRouter>
        </HelmetProvider>,
    );

describe('the work section lights up without a cursor', () => {
    it('marks the row lit once it is in view', () => {
        renderLanding();
        const row = document.querySelector('[data-lit]');
        expect(row).not.toBeNull();
        expect(row?.getAttribute('data-lit')).toBe('true');
    });

    it('brings the cover out of greyscale on mobile only', () => {
        renderLanding();
        const cover = screen.getByAltText('Lit Probe');
        const cls = cover.getAttribute('class') ?? '';

        // The base state is grey; hover is the desktop trigger and must survive.
        expect(cls).toContain('grayscale');
        expect(cls).toContain('group-hover:grayscale-0');
        // The cursorless trigger, scoped below lg so desktop is unchanged.
        expect(cls).toContain('max-lg:grayscale-0');
        expect(cls).not.toContain('lg:grayscale-0 ');
    });

    it('accents the border and lifts the card on mobile only', () => {
        renderLanding();
        const cover = screen.getByAltText('Lit Probe');
        const mediaLink = cover.closest('a');
        const cls = mediaLink?.getAttribute('class') ?? '';

        for (const util of [
            'max-lg:-translate-y-1',
            'max-lg:border-[#F04A32]/60',
            'max-lg:shadow-[0_16px_40px_rgba(0,0,0,0.35)]',
        ]) {
            expect(cls).toContain(util);
        }
        // Every lit utility must carry the max-lg: guard — an unguarded one would
        // permanently apply a hover affordance on desktop too.
        const unguarded = cls
            .split(/\s+/)
            .filter((c) => c.startsWith('-translate-y-1') || c === 'border-[#F04A32]/60');
        expect(unguarded).toEqual([]);
    });
});
