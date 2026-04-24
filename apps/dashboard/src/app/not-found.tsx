import Link from "next/link";

export default function NotFound() {
  return (
    <main style={{ maxWidth: 480, margin: "80px auto", fontFamily: "monospace", padding: "0 16px", textAlign: "center" }}>
      <h1 style={{ fontSize: 48, margin: "0 0 8px" }}>404</h1>
      <p style={{ color: "#888" }}>Page not found</p>
      <Link href="/" style={{ fontSize: 13, color: "#666" }}>← Home</Link>
    </main>
  );
}
