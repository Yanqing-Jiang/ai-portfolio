export const FORTUNE_ROUTE_SLUGS = {
  wish: 'custom-wish',
  cycle: 'luck-draw',
  compatibility: 'compatibility',
  occasion: 'lucky-day',
} as const;

export type CanonicalFortuneFunction = keyof typeof FORTUNE_ROUTE_SLUGS;
export type FortuneRouteSlug = (typeof FORTUNE_ROUTE_SLUGS)[CanonicalFortuneFunction];

const FORTUNE_BASE_ROUTE = '/project/fortune-agent';

export const fortuneIntakeRoute = (functionId: CanonicalFortuneFunction): string =>
  `${FORTUNE_BASE_ROUTE}/${FORTUNE_ROUTE_SLUGS[functionId]}`;

export const fortuneResultRoute = (
  functionId: CanonicalFortuneFunction,
  fortuneId = 'result',
): string => `${fortuneIntakeRoute(functionId)}/${fortuneId}`;
