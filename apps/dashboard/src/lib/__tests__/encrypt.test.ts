import { encrypt, decrypt } from "../encrypt";

const KEY = "a".repeat(64); // 64-char hex = 32 bytes, valid for tests

beforeEach(() => {
  process.env.ENCRYPTION_KEY = KEY;
});

afterEach(() => {
  delete process.env.ENCRYPTION_KEY;
});

describe("encrypt / decrypt", () => {
  it("round-trips plaintext", () => {
    const plaintext = "railway_abc123";
    const ciphertext = encrypt(plaintext);
    expect(decrypt(ciphertext)).toBe(plaintext);
  });

  it("produces different ciphertext each time (random IV)", () => {
    const plaintext = "same-input";
    expect(encrypt(plaintext)).not.toBe(encrypt(plaintext));
  });

  it("throws when ENCRYPTION_KEY is missing", () => {
    delete process.env.ENCRYPTION_KEY;
    expect(() => encrypt("x")).toThrow("ENCRYPTION_KEY");
  });

  it("throws when ENCRYPTION_KEY is wrong length", () => {
    process.env.ENCRYPTION_KEY = "short";
    expect(() => encrypt("x")).toThrow("ENCRYPTION_KEY");
  });
});
