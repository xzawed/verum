import Link from "next/link";
import { getAllDocs } from "@/lib/docs";

export const metadata = {
  title: "Verum Docs",
  description: "Documentation for the Verum AI optimization platform",
};

export default function DocsPage() {
  const docs = getAllDocs();
  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-2">Verum Documentation</h1>
      <p className="text-gray-500 mb-8">
        Reference docs for the Verum Loop — self-hosted AI optimization platform.
      </p>
      <ul className="divide-y divide-gray-200">
        {docs.map((doc) => (
          <li key={doc.slug} className="py-4">
            <Link
              href={`/docs/${doc.slug}`}
              className="text-blue-600 hover:underline font-medium"
            >
              {doc.title}
            </Link>
            {doc.description && (
              <p className="text-sm text-gray-500 mt-1">{doc.description}</p>
            )}
          </li>
        ))}
        {docs.length === 0 && (
          <li className="py-4 text-gray-400 text-sm">No documentation files found.</li>
        )}
      </ul>
    </main>
  );
}
