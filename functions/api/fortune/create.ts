// POST /api/fortune/create — BFF forward to the Python backend.
import { forwardPost, type BffEnv, type PagesHandler } from "../../_shared/bff";

export const onRequestPost: PagesHandler<BffEnv> = async ({ request, env }) =>
  forwardPost(request, env, {
    bucket: "fortune_create",
    upstreamPath: "/api/fortune/create",
  });

// Block other methods at the edge so the backend doesn't see them at all.
export const onRequest: PagesHandler<BffEnv> = async () =>
  new Response(null, { status: 405, headers: { allow: "POST" } });
