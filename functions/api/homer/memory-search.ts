// POST /api/homer/memory-search — BFF forward to the Python backend.
import { forwardPost, type BffEnv, type PagesHandler } from "../../_shared/bff";

export const onRequestPost: PagesHandler<BffEnv> = async ({ request, env }) =>
  forwardPost(request, env, {
    bucket: "homer_memory_search",
    upstreamPath: "/api/homer/memory-search",
  });

export const onRequest: PagesHandler<BffEnv> = async () =>
  new Response(null, { status: 405, headers: { allow: "POST" } });
