// Shared helpers for the Cloudflare Pages Function BFF layer.
//
// The BFF sits in front of the Mac Mini Docker backend and does three things:
//   1. Attach an `x-request-id` to every forwarded request so traces can
//      be correlated across CF edge and the Python backend logs.
//   2. Propagate the caller's IP (via `cf-connecting-ip` + `x-forwarded-for`)
//      so the backend's Redis rate limiter can key off the real client rather
//      than the CF Tunnel egress IP.
//   3. Optionally apply a coarse IP token bucket using the CF Workers Rate
//      Limiting binding, when present. The binding is feature-flagged via
//      `env.FORTUNE_RATE_LIMIT` — absence is a no-op, so we ship the Function
//      before the binding is provisioned in the Pages dashboard.
//
// Intentionally NOT in scope for the BFF: auth, Turnstile, body shape
// validation, or caching. The portfolio narrative is "agent harness build",
// not "edge security build".

export interface BffEnv {
  BACKEND_ORIGIN?: string;
  FORTUNE_RATE_LIMIT?: {
    limit: (opts: { key: string }) => Promise<{ success: boolean }>;
  };
  HOMER_PLAY_RATE_LIMIT?: {
    limit: (opts: { key: string }) => Promise<{ success: boolean }>;
  };
}

// Minimal shape of the Pages Function context. Kept inline so this file
// compiles in the frontend's tsconfig without adding @cloudflare/workers-types.
export interface PagesFunctionContext<E = BffEnv> {
  request: Request;
  env: E;
  params: Record<string, string | string[] | undefined>;
}
export type PagesHandler<E = BffEnv> = (ctx: PagesFunctionContext<E>) => Promise<Response> | Response;

export const DEFAULT_BACKEND_ORIGIN = "https://portfolio-api.yanqing.app";

export interface ForwardOptions {
  /** Logical bucket name for the rate-limit key (e.g. "create", "ask"). */
  bucket: string;
  /** Upstream path to call on the backend, starting with `/api/...`. */
  upstreamPath: string;
  /** Purpose-named Workers Rate Limiting binding. Defaults to Fortune. */
  rateLimitBinding?: "FORTUNE_RATE_LIMIT" | "HOMER_PLAY_RATE_LIMIT";
  /** Optional edge body cap; the actual bytes are checked even without Content-Length. */
  maxBodyBytes?: number;
  /** Preserve legacy errors unless a route opts into the Homer play envelope. */
  errorProfile?: "default" | "homer_play";
}

export async function forwardPost(
  request: Request,
  env: BffEnv,
  opts: ForwardOptions,
): Promise<Response> {
  const ip = request.headers.get("cf-connecting-ip") || "0.0.0.0";
  const requestId = crypto.randomUUID();

  const declaredLength = Number(request.headers.get("content-length"));
  if (
    opts.maxBodyBytes !== undefined &&
    Number.isFinite(declaredLength) &&
    declaredLength > opts.maxBodyBytes
  ) {
    return payloadTooLarge(requestId, opts.maxBodyBytes);
  }

  // Read the body as bytes so the edge can enforce the real size and forward
  // exactly those bytes without logging or JSON-parsing visitor content.
  const body = request.method === "GET" || request.method === "HEAD"
    ? undefined
    : await request.arrayBuffer();
  if (opts.maxBodyBytes !== undefined && body && body.byteLength > opts.maxBodyBytes) {
    return payloadTooLarge(requestId, opts.maxBodyBytes);
  }

  // Coarse IP rate limit — no-op when the binding isn't configured yet.
  const rateLimitBinding = opts.rateLimitBinding || "FORTUNE_RATE_LIMIT";
  const rateLimiter = env[rateLimitBinding];
  if (rateLimiter) {
    try {
      const { success } = await rateLimiter.limit({
        key: `${opts.bucket}:${ip}`,
      });
      if (!success) {
        if (opts.errorProfile === "homer_play") {
          return homerPlayRateLimited(requestId);
        }
        return Response.json(
          {
            error: "rate_limited",
            message: "Too many requests from this IP. Try again shortly.",
            request_id: requestId,
          },
          {
            status: 429,
            headers: {
              "retry-after": "10",
              "x-request-id": requestId,
              "cache-control": "no-store",
            },
          },
        );
      }
    } catch (err) {
      // Never fail-closed: the BFF is a thin guard, the backend rate limiter
      // is the real enforcement layer.
      console.warn("[BFF] rate limit check failed", err);
    }
  }

  const backend = (env.BACKEND_ORIGIN || DEFAULT_BACKEND_ORIGIN).replace(/\/$/, "");
  const upstreamUrl = backend + opts.upstreamPath;

  const upstreamHeaders: Record<string, string> = {
    "content-type": request.headers.get("content-type") || "application/json",
    "x-request-id": requestId,
    "cf-connecting-ip": ip,
    // Do NOT trust inbound x-forwarded-for — clients can spoof it to attack
    // the backend's IP-keyed rate limiter. The trust anchor is the CF edge:
    // overwrite with the CF-connecting-ip so the upstream only sees what we
    // believe about the client.
    "x-forwarded-for": ip,
  };
  const ua = request.headers.get("user-agent");
  if (ua) upstreamHeaders["user-agent"] = ua;
  const accept = request.headers.get("accept");
  if (accept) upstreamHeaders["accept"] = accept;
  // Forward the Supabase JWT so the backend's rate limiter can resolve the
  // signed-in user (and superuser bypass). Without this the backend keys
  // every POST by Cloudflare egress IP and denies with 401 "Sign-in required
  // after free quota" after 3 guest requests.
  const auth = request.headers.get("authorization");
  if (auth) upstreamHeaders["authorization"] = auth;

  let upstreamResp: Response;
  try {
    upstreamResp = await fetch(upstreamUrl, {
      method: request.method,
      headers: upstreamHeaders,
      body,
    });
  } catch (err) {
    console.error("[BFF] upstream fetch failed", err);
    if (opts.errorProfile === "homer_play") {
      return homerPlayServiceUnavailable(requestId);
    }
    return Response.json(
      {
        error: "bad_gateway",
        message: "Backend unreachable from edge.",
        request_id: requestId,
      },
      {
        status: 502,
        headers: { "x-request-id": requestId, "cache-control": "no-store" },
      },
    );
  }

  // Pass the upstream response straight through, but overlay our request id
  // so clients see the same one we sent to the backend. We preserve the
  // backend's own headers (including `X-Fortune-Persistence: degraded`).
  const outHeaders = new Headers(upstreamResp.headers);
  outHeaders.set("x-request-id", requestId);
  return new Response(upstreamResp.body, {
    status: upstreamResp.status,
    statusText: upstreamResp.statusText,
    headers: outHeaders,
  });
}

function payloadTooLarge(requestId: string, maxBodyBytes: number): Response {
  return Response.json(
    {
      ok: false,
      request_id: requestId,
      error: {
        code: "payload_too_large",
        message: "Request body exceeds the 8 KiB public limit.",
        retryable: false,
        fields: { body: `maximum ${maxBodyBytes} bytes` },
      },
    },
    {
      status: 413,
      headers: {
        "x-request-id": requestId,
        "cache-control": "no-store, private",
        "x-content-type-options": "nosniff",
      },
    },
  );
}

function homerPlayRateLimited(requestId: string): Response {
  const now = Date.now();
  const resetMs = (Math.floor(now / 3_600_000) + 1) * 3_600_000;
  const retryAfter = Math.max(1, Math.ceil((resetMs - now) / 1000));
  return Response.json(
    {
      ok: false,
      request_id: requestId,
      error: {
        code: "rate_limited",
        message: "Too many Homer play requests from this IP. Try again after the hourly window resets.",
        retryable: true,
      },
      limits: { remaining_this_hour: 0, reset_at: new Date(resetMs).toISOString() },
    },
    {
      status: 429,
      headers: {
        "retry-after": String(retryAfter),
        "x-request-id": requestId,
        "cache-control": "no-store, private",
        "x-content-type-options": "nosniff",
      },
    },
  );
}

function homerPlayServiceUnavailable(requestId: string): Response {
  return Response.json(
    {
      ok: false,
      request_id: requestId,
      error: {
        code: "service_unavailable",
        message: "Homer play and its recorded fallback are temporarily unavailable.",
        retryable: true,
      },
    },
    {
      status: 503,
      headers: {
        "x-request-id": requestId,
        "cache-control": "no-store, private",
        "x-content-type-options": "nosniff",
      },
    },
  );
}
