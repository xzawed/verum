import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import rehypeStringify from "rehype-stringify";

const DOCS_DIR =
  process.env.DOCS_PATH || path.join(process.cwd(), "..", "..", "docs");

export interface DocMeta {
  slug: string;
  title: string;
  description: string;
}

export function getAllDocs(): DocMeta[] {
  try {
    const files = fs.readdirSync(DOCS_DIR).filter((f) => f.endsWith(".md"));
    return files
      .map((filename) => {
        const slug = filename.replace(/\.md$/, "").toLowerCase();
        const filePath = path.join(DOCS_DIR, filename);
        const raw = fs.readFileSync(filePath, "utf-8");
        const { data } = matter(raw);
        return {
          slug,
          title:
            (data.title as string) ||
            filename.replace(/\.md$/, "").replace(/[-_]/g, " "),
          description: (data.description as string) || "",
        };
      })
      .sort((a, b) => a.title.localeCompare(b.title));
  } catch {
    return [];
  }
}

export async function getDoc(
  slug: string,
): Promise<{ title: string; contentHtml: string } | null> {
  try {
    const files = fs.readdirSync(DOCS_DIR).filter((f) => f.endsWith(".md"));
    const match = files.find(
      (f) => f.replace(/\.md$/, "").toLowerCase() === slug.toLowerCase(),
    );
    if (!match) return null;

    const filePath = path.join(DOCS_DIR, match);
    const raw = fs.readFileSync(filePath, "utf-8");
    const { data, content } = matter(raw);

    const result = await unified()
      .use(remarkParse)
      .use(remarkGfm)
      .use(remarkRehype)
      .use(rehypeSanitize, {
        ...defaultSchema,
        attributes: {
          ...defaultSchema.attributes,
          code: [...(defaultSchema.attributes?.code ?? []), "className"],
          span: [...(defaultSchema.attributes?.span ?? []), "className"],
        },
      })
      .use(rehypeStringify)
      .process(content);
    const contentHtml = result.toString();

    return {
      title:
        (data.title as string) ||
        match.replace(/\.md$/, "").replace(/[-_]/g, " "),
      contentHtml,
    };
  } catch {
    return null;
  }
}
