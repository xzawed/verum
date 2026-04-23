import { notFound } from "next/navigation";
import Link from "next/link";
import { getDoc, getAllDocs } from "@/lib/docs";

export async function generateStaticParams() {
  try {
    const docs = getAllDocs();
    return docs.map((doc) => ({ slug: doc.slug }));
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = await getDoc(slug);
  return { title: doc ? `${doc.title} — Verum Docs` : "Not Found" };
}

export default async function DocPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = await getDoc(slug);
  if (!doc) notFound();

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <Link
        href="/docs"
        className="text-sm text-gray-500 hover:text-gray-700 mb-6 inline-block"
      >
        ← Back to docs
      </Link>
      <article
        className="prose prose-gray max-w-none"
        dangerouslySetInnerHTML={{ __html: doc.contentHtml }}
      />
    </main>
  );
}
