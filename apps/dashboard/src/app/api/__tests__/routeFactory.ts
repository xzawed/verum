/**
 * createRouteTests — generates the standard auth / bad-request / not-found / success
 * test cases that every Next.js API route in this project shares.
 *
 * Usage:
 *
 *   jest.mock("@/auth", () => ({ auth: jest.fn() }));
 *   import { GET } from "../route";
 *   import { auth } from "@/auth";
 *
 *   const mockAuth = auth as jest.MockedFunction<typeof auth>;
 *
 *   createRouteTests(GET, {
 *     description: "GET /api/v1/experiments",
 *     auth: {
 *       setupMocks: () => mockAuth.mockResolvedValueOnce(null),
 *       request: new Request("http://localhost/api/v1/experiments?deployment_id=dep-1"),
 *     },
 *     badRequest: {
 *       setupMocks: () => mockAuth.mockResolvedValueOnce({ user: { id: "u-1" } } as never),
 *       request: new Request("http://localhost/api/v1/experiments"),
 *     },
 *     notFound: {
 *       setupMocks: () => {
 *         mockAuth.mockResolvedValueOnce({ user: { id: "u-1" } } as never);
 *         mockGetDeployment.mockResolvedValueOnce(null);
 *       },
 *       request: new Request("http://localhost/api/v1/experiments?deployment_id=dep-x"),
 *     },
 *     success: {
 *       setupMocks: () => {
 *         mockAuth.mockResolvedValueOnce({ user: { id: "u-1" } } as never);
 *         mockGetDeployment.mockResolvedValueOnce({ id: "dep-1" } as never);
 *         mockGetExperiments.mockResolvedValueOnce([]);
 *       },
 *       request: new Request("http://localhost/api/v1/experiments?deployment_id=dep-1"),
 *       assertBody: (body) => expect((body as { experiments: unknown[] }).experiments).toHaveLength(0),
 *     },
 *   });
 */

/** Context shape used by dynamic-segment Next.js route handlers. */
export type RouteContext = { params: Promise<Record<string, string>> };

/**
 * A Next.js route handler — may or may not accept a Request and/or context.
 * Using `unknown` here lets TypeScript accept both `GET(req)` and `GET()` shapes.
 */
export type RouteHandler = (req?: unknown, ctx?: unknown) => Promise<Response>;

interface CaseConfig {
  /** Called immediately before invoking the handler. Set up mock return values here. */
  setupMocks?: () => void;
  /** The Request to pass to the handler. Omit for handlers that take no request (e.g. quota GET). */
  request?: Request;
  /** Route segment context, e.g. `{ params: Promise.resolve({ id: "dep-1" }) }`. */
  ctx?: RouteContext;
}

interface SuccessCaseConfig extends CaseConfig {
  /** Expected HTTP status. Defaults to 200. */
  expectedStatus?: number;
  /** Optional assertion on the parsed response body. */
  assertBody?: (body: unknown) => void;
}

export interface RouteTestConfig {
  /** Jest `describe` label, e.g. `"GET /api/v1/experiments"`. */
  description: string;
  /** Standard 401 case — must result in `401 Unauthorized`. */
  auth: CaseConfig;
  /** Optional 400 case — must result in `400 Bad Request`. */
  badRequest?: CaseConfig;
  /** Optional 404 case — must result in `404 Not Found`. */
  notFound?: CaseConfig;
  /** Happy-path case. */
  success: SuccessCaseConfig;
  /** Any route-specific extra cases not covered by the standards above. */
  extra?: Array<CaseConfig & { description: string; expectedStatus: number }>;
}

async function invoke(
  handler: RouteHandler,
  cfg: CaseConfig,
): Promise<Response> {
  return handler(cfg.request, cfg.ctx);
}

/**
 * Registers a standard Jest `describe` block for a route handler.
 *
 * @param handler - The exported handler function (`GET`, `POST`, `PATCH`, …).
 * @param config  - Per-case configuration (setup + request + optional assertions).
 */
export function createRouteTests(
  handler: RouteHandler,
  config: RouteTestConfig,
): void {
  describe(config.description, () => {
    beforeEach(() => {
      jest.clearAllMocks();
    });

    it("returns 401 when not authenticated", async () => {
      config.auth.setupMocks?.();
      const res = await invoke(handler, config.auth);
      expect(res.status).toBe(401);
    });

    if (config.badRequest) {
      it("returns 400 when request is invalid", async () => {
        config.badRequest!.setupMocks?.();
        const res = await invoke(handler, config.badRequest!);
        expect(res.status).toBe(400);
      });
    }

    if (config.notFound) {
      it("returns 404 when resource is not found", async () => {
        config.notFound!.setupMocks?.();
        const res = await invoke(handler, config.notFound!);
        expect(res.status).toBe(404);
      });
    }

    const successStatus = config.success.expectedStatus ?? 200;
    it(`returns ${successStatus} on success`, async () => {
      config.success.setupMocks?.();
      const res = await invoke(handler, config.success);
      expect(res.status).toBe(successStatus);
      if (config.success.assertBody) {
        const body: unknown = await res.json();
        config.success.assertBody(body);
      }
    });

    config.extra?.forEach((extraCase) => {
      it(extraCase.description, async () => {
        extraCase.setupMocks?.();
        const res = await invoke(handler, extraCase);
        expect(res.status).toBe(extraCase.expectedStatus);
      });
    });
  });
}
