import '@testing-library/jest-dom/vitest';

// JSDOM doesn't ship matchMedia; GSAP/ScrollTrigger registers a plugin at
// module-init that calls window.matchMedia(...). Tests that import any
// component pulling GSAP transitively crash without this stub. Returning
// `matches: false` keeps the static (non-interactive) branch of any
// matchMedia consumers.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
