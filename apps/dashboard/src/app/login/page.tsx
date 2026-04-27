import { signIn } from "@/auth";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-[0_4px_24px_rgba(99,102,241,0.08)]">
        {/* Logo */}
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500">
            <span className="text-sm font-black text-white">V</span>
          </div>
          <span className="text-lg font-bold text-slate-900">Verum</span>
        </div>

        {/* Headline */}
        <h1 className="mb-1 text-base font-semibold text-slate-900">Welcome back</h1>
        <p className="mb-6 text-sm text-slate-500">
          Connect your repo. Auto-evolve your AI.
        </p>

        {/* GitHub sign-in */}
        <form
          action={async () => {
            "use server";
            await signIn("github", { redirectTo: "/repos" });
          }}
        >
          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#24292f] px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
            Continue with GitHub
          </button>
        </form>

        {/* Disclaimer */}
        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="text-center text-xs text-slate-300">
            Not affiliated with Verum AI Platform (verumai.com).
          </p>
        </div>
      </div>
    </main>
  );
}
