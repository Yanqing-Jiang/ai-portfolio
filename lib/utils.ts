import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Function: isFullPageLink - true for a project `link` that must leave the SPA:
// an external site, or a page served as static files on this same origin
// (e.g. /supreme-metric). react-router treats a same-origin absolute URL as an
// in-app path, so these need a full document navigation instead of <Link>.
export const isFullPageLink = (link?: string): boolean => !!link && /^https?:\/\//i.test(link);
