import { signIn } from "@/auth";

export default function LoginPage() {
  return (
    <main
      style={{
        maxWidth: 480,
        margin: "120px auto",
        fontFamily: "monospace",
        padding: "0 16px",
        textAlign: "center",
      }}
    >
      <h1 style={{ fontSize: 32, marginBottom: 8, letterSpacing: "-1px" }}>Verum</h1>
      <p style={{ color: "#666", marginBottom: 40, lineHeight: 1.6 }}>
        Connect your repo. Verum learns how your AI actually behaves, then
        auto-builds and auto-evolves everything around it.
      </p>

      <form
        action={async () => {
          "use server";
          await signIn("github", { redirectTo: "/repos" });
        }}
      >
        <button
          type="submit"
          style={{
            padding: "12px 32px",
            fontSize: 15,
            fontWeight: "bold",
            background: "#24292e",
            color: "white",
            border: "none",
            cursor: "pointer",
            letterSpacing: "0.3px",
          }}
        >
          Sign in with GitHub
        </button>
      </form>

      <p style={{ marginTop: 40, fontSize: 11, color: "#999" }}>
        Not affiliated with Verum AI Platform (verumai.com).
      </p>
    </main>
  );
}
