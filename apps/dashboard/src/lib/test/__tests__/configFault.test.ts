import { setConfigFault, resetConfigFault, consumeConfigFault } from "../configFault";

const _origEnv = process.env.VERUM_TEST_MODE;
afterEach(() => {
  resetConfigFault();
  process.env.VERUM_TEST_MODE = _origEnv;
});

describe("consumeConfigFault", () => {
  it("returns false when VERUM_TEST_MODE is not set", () => {
    delete process.env.VERUM_TEST_MODE;
    setConfigFault(5);
    expect(consumeConfigFault()).toBe(false);
  });

  it("returns false when VERUM_TEST_MODE=1 but count is 0", () => {
    process.env.VERUM_TEST_MODE = "1";
    expect(consumeConfigFault()).toBe(false);
  });

  it("returns true and decrements when VERUM_TEST_MODE=1 and count > 0", () => {
    process.env.VERUM_TEST_MODE = "1";
    setConfigFault(2);
    expect(consumeConfigFault()).toBe(true);
    expect(consumeConfigFault()).toBe(true);
    expect(consumeConfigFault()).toBe(false);
  });

  it("returns false after resetConfigFault clears the count", () => {
    process.env.VERUM_TEST_MODE = "1";
    setConfigFault(10);
    resetConfigFault();
    expect(consumeConfigFault()).toBe(false);
  });
});
