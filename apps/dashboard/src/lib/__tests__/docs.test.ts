// Mock ESM-only unified pipeline packages before any import.
// Jest's module factory approach prevents Node from loading these ESM modules,
// which would fail in a CJS test environment.
jest.mock("unified", () => ({
  unified: jest.fn(() => ({
    use: jest.fn().mockReturnThis(),
    process: jest.fn().mockResolvedValue({ toString: () => "<p>rendered content</p>" }),
  })),
}));
jest.mock("remark-parse", () => ({ default: jest.fn() }));
jest.mock("remark-gfm", () => ({ default: jest.fn() }));
jest.mock("remark-rehype", () => ({ default: jest.fn() }));
jest.mock("rehype-sanitize", () => ({
  default: jest.fn(),
  defaultSchema: { attributes: {} },
}));
jest.mock("rehype-stringify", () => ({ default: jest.fn() }));
jest.mock("gray-matter", () => jest.fn(() => ({ data: {}, content: "" })));
jest.mock("fs", () => ({
  readdirSync: jest.fn(),
  readFileSync: jest.fn(),
}));

import fs from "fs";
import matter from "gray-matter";
import { getAllDocs, getDoc } from "../docs";

const mockReaddirSync = fs.readdirSync as jest.Mock;
const mockReadFileSync = fs.readFileSync as jest.Mock;
const mockMatter = matter as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("getAllDocs()", () => {
  it("returns [] when directory is empty", () => {
    mockReaddirSync.mockReturnValueOnce([]);
    expect(getAllDocs()).toEqual([]);
  });

  it("returns [] on filesystem error", () => {
    mockReaddirSync.mockImplementationOnce(() => {
      throw new Error("ENOENT: no such file or directory");
    });
    expect(getAllDocs()).toEqual([]);
  });

  it("returns docs sorted alphabetically by title", () => {
    mockReaddirSync.mockReturnValueOnce(["z-guide.md", "a-guide.md"]);
    mockReadFileSync.mockReturnValue("# content");
    mockMatter
      .mockReturnValueOnce({ data: { title: "Z Guide" }, content: "" })
      .mockReturnValueOnce({ data: { title: "A Guide" }, content: "" });
    const docs = getAllDocs();
    expect(docs).toHaveLength(2);
    expect(docs[0].title).toBe("A Guide");
    expect(docs[1].title).toBe("Z Guide");
  });

  it("derives title and slug from filename when frontmatter has none", () => {
    mockReaddirSync.mockReturnValueOnce(["my-api-guide.md"]);
    mockReadFileSync.mockReturnValue("# content");
    mockMatter.mockReturnValueOnce({ data: {}, content: "" });
    const docs = getAllDocs();
    expect(docs[0].title).toBe("my api guide");
    expect(docs[0].slug).toBe("my-api-guide");
  });

  it("ignores non-.md files", () => {
    mockReaddirSync.mockReturnValueOnce(["README.txt", "guide.md", "image.png"]);
    mockReadFileSync.mockReturnValue("# content");
    mockMatter.mockReturnValueOnce({ data: { title: "Guide" }, content: "" });
    expect(getAllDocs()).toHaveLength(1);
  });
});

describe("getDoc()", () => {
  it("returns null when slug is not found", async () => {
    mockReaddirSync.mockReturnValueOnce(["other.md"]);
    expect(await getDoc("nonexistent-slug")).toBeNull();
  });

  it("returns null on filesystem error", async () => {
    mockReaddirSync.mockImplementationOnce(() => {
      throw new Error("ENOENT");
    });
    expect(await getDoc("any-slug")).toBeNull();
  });

  it("returns title and rendered HTML when found", async () => {
    mockReaddirSync.mockReturnValueOnce(["api.md"]);
    mockReadFileSync.mockReturnValueOnce("---\ntitle: API Guide\n---\n# API");
    mockMatter.mockReturnValueOnce({ data: { title: "API Guide" }, content: "# API" });
    const result = await getDoc("api");
    expect(result).not.toBeNull();
    expect(result?.title).toBe("API Guide");
    expect(result?.contentHtml).toBe("<p>rendered content</p>");
  });

  it("derives title from filename when frontmatter has none", async () => {
    mockReaddirSync.mockReturnValueOnce(["loop-overview.md"]);
    mockReadFileSync.mockReturnValueOnce("# Loop");
    mockMatter.mockReturnValueOnce({ data: {}, content: "# Loop" });
    const result = await getDoc("loop-overview");
    expect(result?.title).toBe("loop overview");
  });

  it("is case-insensitive when matching slug", async () => {
    mockReaddirSync.mockReturnValueOnce(["API.md"]);
    mockReadFileSync.mockReturnValueOnce("# API");
    mockMatter.mockReturnValueOnce({ data: { title: "API" }, content: "" });
    const result = await getDoc("api");
    expect(result).not.toBeNull();
  });
});
