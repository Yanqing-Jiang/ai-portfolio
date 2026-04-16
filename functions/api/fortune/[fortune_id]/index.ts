// GET /api/fortune/:fortune_id — BFF proxy for replay snapshot.
//
// Forwards to the Python backend's GET /api/fortune/{id} endpoint.
// Passes through auth headers and the If-None-Match header for ETag support.
import { DEFAULT_BACKEND_ORIGIN, type BffEnv, type PagesHandler } from "../../../_shared/bff";

export const onRequestGet: PagesHandler<BffEnv> = async ({ request, env, params }) => {
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

  const requestId = crypto.randomUUID();
  const backendUrl = env.BACKEND_ORIGIN || DEFAULT_BACKEND_ORIGIN;

  // Forward auth + conditional headers
  const fwdHeaders: Record<string, string> = {
    "x-request-id": requestId,
    "x-forwarded-for": request.headers.get("cf-connecting-ip") || "",
  };
  const auth = request.headers.get("authorization");
  if (auth) fwdHeaders["authorization"] = auth;
  const etag = request.headers.get("if-none-match");
  if (etag) fwdHeaders["if-none-match"] = etag;

  const upstreamResp = await fetch(`${backendUrl}/api/fortune/${fortuneId}`, {
    headers: fwdHeaders,
  });

  const outHeaders = new Headers(upstreamResp.headers);
  outHeaders.set("x-request-id", requestId);

  return new Response(upstreamResp.body, {
    status: upstreamResp.status,
    statusText: upstreamResp.statusText,
    headers: outHeaders,
  });
};

// Block non-GET methods
export const onRequest: PagesHandler<BffEnv> = async () =>
  new Response(null, { status: 405, headers: { allow: "GET" } });
