// POST /api/fortune/:fortune_id/correction — BFF forward to the Python backend.
import { forwardPost, type BffEnv, type PagesHandler } from "../../../_shared/bff";

export const onRequestPost: PagesHandler<BffEnv> = async ({ request, env, params }) => {
  const raw = params.fortune_id;
  const fortuneId = Array.isArray(raw) ? raw[0] : raw;
  if (!fortuneId || typeof fortuneId !== "string") {
    return new Response(
      JSON.stringify({ error: "bad_request", message: "fortune_id missing" }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }
  if (!/^[0-9a-f-]{32,36}$/i.test(fortuneId)) {
    return new Response(
      JSON.stringify({ error: "bad_request", message: "fortune_id malformed" }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }

  return forwardPost(request, env, {
    bucket: "fortune_correction",
    upstreamPath: `/api/fortune/${fortuneId}/correction`,
  });
};

export const onRequest: PagesHandler<BffEnv> = async () =>
  new Response(null, { status: 405, headers: { allow: "POST" } });
