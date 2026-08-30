// POST /api/homer/play — public playable-architecture BFF route.
import { forwardPost, type BffEnv, type PagesHandler } from "../../_shared/bff";

export const onRequestPost: PagesHandler<BffEnv> = async ({ request, env }) =>
  forwardPost(request, env, {
    bucket: "homer_play",
    upstreamPath: "/api/homer/play",
    rateLimitBinding: "HOMER_PLAY_RATE_LIMIT",
    maxBodyBytes: 8 * 1024,
    errorProfile: "homer_play",
  });

export const onRequest: PagesHandler<BffEnv> = async () =>
  new Response(null, { status: 405, headers: { allow: "POST", "cache-control": "no-store" } });
