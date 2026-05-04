/// <reference types="vite/client" />

// MDX module shape — used by `import.meta.glob('/content/blog/*.mdx', { eager: true })`
declare module '*.mdx' {
  import type { ComponentType } from 'react';
  export const frontmatter: unknown;
  const Component: ComponentType<Record<string, unknown>>;
  export default Component;
}
