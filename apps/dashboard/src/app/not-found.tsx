import Link from "next/link";

export default function NotFound() {
  return (
    <main className="max-w-[480px] mx-auto mt-20 font-mono px-4 text-center">
      <h1 style={{ fontSize: 48, margin: "0 0 8px" }}>404</h1>
      <p style={{ color: "#888" }}>Page not found</p>
      <Link href="/" style={{ fontSize: 13, color: "#666" }}>← Home</Link>
    </main>
  );
}
