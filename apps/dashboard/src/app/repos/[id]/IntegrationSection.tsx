"use client";

import { useState, useEffect } from "react";

interface Integration {
  id: string;
  platform_service_name: string | null;
  platform_project_id: string | null;
  status: string;
  injected_vars: Record<string, string>;
  created_at: string;
}

interface RailwayService {
  id: string;
  name: string;
  projectId: string;
  projectName: string;
  environmentId: string | null;
}

interface Props {
  repoId: string;
  deploymentId: string | null;
}

export default function IntegrationSection({ repoId, deploymentId }: Props) {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    fetch("/api/integrations")
      .then((r) => r.json())
      .then((d: { integrations: Integration[] }) =>
        setIntegrations(
          d.integrations.filter((i) => i.status === "connected"),
        ),
      )
      .catch(() => {});
  }, []);

  const handleDisconnect = async (integrationId: string) => {
    if (!confirm("Remove Verum env vars from this Railway service and redeploy?")) return;
    const res = await fetch(`/api/integrations/${integrationId}/disconnect`, {
      method: "POST",
    });
    if (res.ok) {
      setIntegrations((prev) => prev.filter((i) => i.id !== integrationId));
    } else {
      alert("Disconnect failed — check console");
    }
  };

  if (!deploymentId) {
    return (
      <div className="rounded-xl border-l-4 border-l-slate-300 border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">
          [5] DEPLOY — Service Integration
        </h2>
        <p className="text-xs text-slate-400">
          Complete GENERATE and activate a deployment first.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border-l-4 border-l-blue-400 border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">
          [5] DEPLOY — Service Integration
        </h2>
        <button
          onClick={() => setShowModal(true)}
          className="rounded-md bg-blue-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-600 transition-colors"
        >
          Connect Railway Service
        </button>
      </div>

      {integrations.length === 0 && (
        <p className="text-xs text-slate-400">
          No integrations yet. Connect a Railway service to inject OTLP telemetry
          — zero code changes.
        </p>
      )}

      {integrations.map((integration) => (
        <div
          key={integration.id}
          className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-emerald-800">
                {integration.platform_service_name ?? integration.platform_project_id}
              </p>
              <p className="text-xs text-emerald-600">
                Connected · {Object.keys(integration.injected_vars).join(", ")}
              </p>
            </div>
            <button
              onClick={() => void handleDisconnect(integration.id)}
              className="rounded-md border border-red-300 px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 transition-colors"
            >
              Disconnect
            </button>
          </div>
        </div>
      ))}

      {showModal && (
        <ConnectRailwayModal
          repoId={repoId}
          onClose={() => setShowModal(false)}
          onConnected={(integration) => {
            setIntegrations((prev) => [...prev, integration]);
            setShowModal(false);
          }}
        />
      )}
    </div>
  );
}

function ConnectRailwayModal({
  repoId,
  onClose,
  onConnected,
}: {
  repoId: string;
  onClose: () => void;
  onConnected: (integration: Integration) => void;
}) {
  const [step, setStep] = useState<"token" | "service" | "confirm">("token");
  const [token, setToken] = useState("");
  const [services, setServices] = useState<RailwayService[]>([]);
  const [selectedService, setSelectedService] = useState<RailwayService | null>(null);
  const [injectNodeOptions, setInjectNodeOptions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchServices = async () => {
    if (!token.trim()) {
      setError("Railway API token is required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `/api/integrations/railway/services?token=${encodeURIComponent(token)}`,
      );
      if (!res.ok) {
        const body = (await res.json()) as { error?: string };
        throw new Error(body.error ?? "Failed to fetch services");
      }
      const data = (await res.json()) as { services: RailwayService[] };
      setServices(data.services);
      setStep("service");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const connect = async () => {
    if (!selectedService?.environmentId) {
      setError("Selected service has no environment");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/integrations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          railway_token: token,
          project_id: selectedService.projectId,
          service_id: selectedService.id,
          environment_id: selectedService.environmentId,
          service_name: `${selectedService.projectName} / ${selectedService.name}`,
          repo_id: repoId,
          inject_node_options: injectNodeOptions,
        }),
      });
      if (!res.ok) {
        const body = (await res.json()) as { error?: string };
        throw new Error(body.error ?? "Failed to connect");
      }
      const data = (await res.json()) as { integration_id: string };
      onConnected({
        id: data.integration_id,
        platform_service_name: `${selectedService.projectName} / ${selectedService.name}`,
        platform_project_id: selectedService.projectId,
        status: "connected",
        injected_vars: {
          OTEL_EXPORTER_OTLP_ENDPOINT: "...",
          ...(injectNodeOptions ? { NODE_OPTIONS: "..." } : {}),
        },
        created_at: new Date().toISOString(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">
            Connect Railway Service
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            ✕
          </button>
        </div>

        {error && (
          <div className="mb-3 rounded-md bg-red-50 p-2 text-xs text-red-700">
            {error}
          </div>
        )}

        {step === "token" && (
          <div className="space-y-3">
            <p className="text-xs text-slate-600">
              Paste your Railway API token. Verum will inject{" "}
              <code className="font-mono text-blue-600">
                OTEL_EXPORTER_OTLP_ENDPOINT
              </code>{" "}
              into your service — zero code changes.
            </p>
            <a
              href="https://railway.app/account/tokens"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-500 hover:underline"
            >
              Get a Railway API token →
            </a>
            <input
              type="password"
              placeholder="railway_..."
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <button
              onClick={() => void fetchServices()}
              disabled={loading}
              className="w-full rounded-md bg-blue-500 py-2 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              {loading ? "Loading services…" : "Next →"}
            </button>
          </div>
        )}

        {step === "service" && (
          <div className="space-y-3">
            <p className="text-xs text-slate-600">Select the Railway service to connect:</p>
            <div className="max-h-48 overflow-y-auto space-y-1">
              {services.map((svc) => (
                <button
                  key={svc.id}
                  onClick={() => {
                    setSelectedService(svc);
                    setStep("confirm");
                  }}
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50 transition-colors"
                >
                  <span className="font-medium">{svc.name}</span>
                  <span className="text-xs text-slate-400 ml-2">{svc.projectName}</span>
                </button>
              ))}
              {services.length === 0 && (
                <p className="text-xs text-slate-400">No services found.</p>
              )}
            </div>
          </div>
        )}

        {step === "confirm" && selectedService && (
          <div className="space-y-3">
            <p className="text-xs text-slate-600">
              Verum will inject these env vars into{" "}
              <strong>{selectedService.name}</strong>:
            </p>
            <div className="rounded-md bg-slate-50 p-3 font-mono text-xs text-slate-700 space-y-1">
              <div>OTEL_EXPORTER_OTLP_ENDPOINT=https://…/api/v1/otlp/v1/traces</div>
              {injectNodeOptions && (
                <div>NODE_OPTIONS=--require @opentelemetry/auto-instrumentations-node/register</div>
              )}
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={injectNodeOptions}
                onChange={(e) => setInjectNodeOptions(e.target.checked)}
                className="rounded"
              />
              Also inject NODE_OPTIONS for auto-instrumentation (Node.js services)
            </label>
            <p className="text-xs text-amber-600">
              Your service will redeploy after connection.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setStep("service")}
                className="flex-1 rounded-md border border-slate-300 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
              >
                ← Back
              </button>
              <button
                onClick={() => void connect()}
                disabled={loading}
                className="flex-1 rounded-md bg-blue-500 py-2 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50 transition-colors"
              >
                {loading ? "Connecting…" : "Connect & Deploy"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
