import { createRouteTests } from "./routeFactory";
import type { RouteHandler } from "./routeFactory";

/**
 * Verifies that createRouteTests registers the correct it() blocks and that
 * each generated case invokes the handler with the right request / context.
 */

function makeOkHandler(status: number, body?: unknown): RouteHandler {
  return async () =>
    new Response(body !== undefined ? JSON.stringify(body) : null, {
      status,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    });
}

describe("createRouteTests factory", () => {
  describe("generates auth / badRequest / notFound / success cases", () => {
    const handler401 = jest.fn(makeOkHandler(401));
    const handler400 = jest.fn(makeOkHandler(400));
    const handler404 = jest.fn(makeOkHandler(404));
    const handler200 = jest.fn(makeOkHandler(200, { ok: true }));

    let callCount = 0;
    const sequentialHandler: RouteHandler = async (req, ctx) => {
      callCount += 1;
      if (callCount === 1) return handler401(req, ctx);
      if (callCount === 2) return handler400(req, ctx);
      if (callCount === 3) return handler404(req, ctx);
      return handler200(req, ctx);
    };

    createRouteTests(sequentialHandler, {
      description: "sequential handler tests",
      auth: {
        request: new Request("http://localhost/test"),
      },
      badRequest: {
        request: new Request("http://localhost/test"),
      },
      notFound: {
        request: new Request("http://localhost/test"),
      },
      success: {
        request: new Request("http://localhost/test"),
        assertBody: (body) =>
          expect((body as { ok: boolean }).ok).toBe(true),
      },
    });
  });

  describe("setupMocks callbacks are invoked before the handler", () => {
    const sideEffects: string[] = [];
    const captureHandler: RouteHandler = async () => {
      sideEffects.push("handler");
      return new Response(null, { status: 401 });
    };

    createRouteTests(captureHandler, {
      description: "setupMocks ordering",
      auth: {
        setupMocks: () => sideEffects.push("setup"),
        request: new Request("http://localhost/test"),
      },
      success: {
        setupMocks: () => sideEffects.push("setup"),
        request: new Request("http://localhost/test"),
        expectedStatus: 401,
      },
    });

    it("setup always precedes handler invocation", () => {
      expect(sideEffects.slice(0, 2)).toEqual(["setup", "handler"]);
    });
  });

  describe("optional badRequest and notFound are skipped when absent", () => {
    const handler: RouteHandler = async () => new Response(null, { status: 401 });

    createRouteTests(handler, {
      description: "minimal two-case route",
      auth: { request: new Request("http://localhost/test") },
      success: { request: new Request("http://localhost/test"), expectedStatus: 401 },
    });
  });

  describe("extra cases are registered", () => {
    // Handler returns 401 on first call (auth), 409 on all subsequent calls.
    let extraCallCount = 0;
    const extraHandler: RouteHandler = async () => {
      extraCallCount += 1;
      return new Response(null, { status: extraCallCount === 1 ? 401 : 409 });
    };

    createRouteTests(extraHandler, {
      description: "route with 409 extra case",
      auth: {
        request: new Request("http://localhost/test"),
      },
      success: {
        request: new Request("http://localhost/test"),
        expectedStatus: 409,
      },
      extra: [
        {
          description: "returns 409 when resource is in conflict",
          request: new Request("http://localhost/test"),
          expectedStatus: 409,
        },
      ],
    });
  });

  describe("ctx is forwarded to the handler", () => {
    let receivedCtx: unknown;
    const ctxCapture: RouteHandler = async (_req, ctx) => {
      receivedCtx = ctx;
      return new Response(null, { status: 401 });
    };

    const ctx = { params: Promise.resolve({ id: "resource-1" }) };

    createRouteTests(ctxCapture, {
      description: "ctx forwarding",
      auth: {
        request: new Request("http://localhost/api/test/resource-1"),
        ctx,
      },
      success: {
        request: new Request("http://localhost/api/test/resource-1"),
        ctx,
        expectedStatus: 401,
      },
    });

    it("ctx object is the same reference passed to the handler", () => {
      expect(receivedCtx).toBe(ctx);
    });
  });
});
