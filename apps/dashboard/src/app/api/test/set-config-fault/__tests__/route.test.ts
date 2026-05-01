jest.mock("@/lib/test/configFault", () => ({
  setConfigFault: jest.fn(),
  resetConfigFault: jest.fn(),
}));

import { POST, DELETE } from "../route";
import { setConfigFault, resetConfigFault } from "@/lib/test/configFault";

const mockSet = setConfigFault as jest.MockedFunction<typeof setConfigFault>;
const mockReset = resetConfigFault as jest.MockedFunction<typeof resetConfigFault>;

const _origEnv = process.env.VERUM_TEST_MODE;
afterAll(() => {
  process.env.VERUM_TEST_MODE = _origEnv;
});

describe("POST /api/test/set-config-fault", () => {
  it("returns 404 when VERUM_TEST_MODE is not set", async () => {
    delete process.env.VERUM_TEST_MODE;
    const req = new Request("http://localhost/api/test/set-config-fault", {
      method: "POST",
      body: JSON.stringify({ count: 5 }),
    });
    const res = await POST(req);
    expect(res.status).toBe(404);
    expect(mockSet).not.toHaveBeenCalled();
  });

  it("sets fault count and returns ok when VERUM_TEST_MODE=1", async () => {
    process.env.VERUM_TEST_MODE = "1";
    const req = new Request("http://localhost/api/test/set-config-fault", {
      method: "POST",
      body: JSON.stringify({ count: 3 }),
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ ok: true, count: 3 });
    expect(mockSet).toHaveBeenCalledWith(3);
  });

  it("defaults count to 1 when count is omitted", async () => {
    process.env.VERUM_TEST_MODE = "1";
    const req = new Request("http://localhost/api/test/set-config-fault", {
      method: "POST",
      body: JSON.stringify({}),
    });
    await POST(req);
    expect(mockSet).toHaveBeenCalledWith(1);
  });
});

describe("DELETE /api/test/set-config-fault", () => {
  it("returns 404 when VERUM_TEST_MODE is not set", async () => {
    delete process.env.VERUM_TEST_MODE;
    const res = await DELETE();
    expect(res.status).toBe(404);
    expect(mockReset).not.toHaveBeenCalled();
  });

  it("resets fault and returns ok when VERUM_TEST_MODE=1", async () => {
    process.env.VERUM_TEST_MODE = "1";
    const res = await DELETE();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ ok: true });
    expect(mockReset).toHaveBeenCalled();
  });
});
