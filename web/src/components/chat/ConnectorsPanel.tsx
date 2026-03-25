"use client";

import React from "react";
import { useUser } from "@clerk/nextjs";
import useSWR from "swr";
import { CheckCircle2, ExternalLink, Link2, PlugZap, ShieldAlert } from "lucide-react";

type Connector = {
    id: string;
    label: string;
    available: boolean;
    connected: boolean;
    account_label?: string | null;
    configured_via_env?: boolean;
    updated_at?: string | null;
    capabilities?: string[];
};

type ConnectorStatusResponse = {
    connectors?: Connector[];
    auth_ready?: boolean;
    error?: string;
};

const fetcher = (url: string) =>
    fetch(url).then((r) => {
        if (!r.ok) throw new Error(`Failed to load connectors: ${r.status}`);
        return r.json();
    });

export function ConnectorsPanel() {
    const { isLoaded, isSignedIn } = useUser();
    const shouldFetch = isLoaded && isSignedIn;
    const { data, error, mutate, isLoading } = useSWR<ConnectorStatusResponse>(
        shouldFetch ? "/api/integrations/status" : null,
        fetcher,
        {
            refreshInterval: 30000,
            revalidateOnFocus: true,
        }
    );

    const connectors = data?.connectors ?? [];
    const authPending = !isLoaded || (shouldFetch && data?.auth_ready === false);
    const signedOut = isLoaded && !isSignedIn;
    const hasStatusError = Boolean(data?.error) || Boolean(error);

    return (
        <section className="border-b border-zinc-900/80 bg-black/30 px-4 py-3 backdrop-blur">
            <div className="mx-auto flex max-w-5xl flex-col gap-3">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <p className="text-[11px] font-mono uppercase tracking-[0.24em] text-zinc-500">Connectors</p>
                        <p className="text-sm text-zinc-300">
                            Connect each client workspace to external systems before asking agents to use them.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => void mutate()}
                        disabled={!shouldFetch}
                        className="rounded-full border border-zinc-800 px-3 py-1 text-[11px] font-mono text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-200"
                    >
                        Refresh
                    </button>
                </div>

                {authPending && (
                    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/50 px-4 py-3 text-sm text-zinc-500">
                        Loading your session before checking connectors...
                    </div>
                )}

                {signedOut && (
                    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/50 px-4 py-3 text-sm text-zinc-500">
                        Sign in to load available connectors for this workspace.
                    </div>
                )}

                {data?.auth_ready === false && (
                    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                        Your session is still syncing. Refresh once if connectors do not appear in a moment.
                    </div>
                )}

                {hasStatusError && data?.auth_ready !== false && (
                    <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                        {data?.error || "Failed to load connector status."}
                    </div>
                )}

                <div className="grid gap-3 md:grid-cols-2">
                    {shouldFetch && isLoading && connectors.length === 0 && (
                        <div className="rounded-2xl border border-zinc-800 bg-zinc-950/50 px-4 py-4 text-sm text-zinc-500">
                            Loading connectors...
                        </div>
                    )}

                    {connectors.map((connector) => {
                        const connectHref =
                            connector.id === "google" ? "/api/integrations/google/oauth/start" : undefined;
                        return (
                            <div
                                key={connector.id}
                                className="rounded-2xl border border-zinc-800 bg-zinc-950/60 px-4 py-4 text-zinc-200"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div className="space-y-2">
                                        <div className="flex items-center gap-2">
                                            <PlugZap size={16} className="text-emerald-400" />
                                            <p className="text-base font-semibold">{connector.label}</p>
                                        </div>
                                        <div className="flex flex-wrap gap-2 text-[11px] font-mono">
                                            <span className="rounded-full border border-zinc-800 px-2.5 py-1 text-zinc-400">
                                                {connector.available ? "available" : "not configured on server"}
                                            </span>
                                            <span
                                                className={`rounded-full border px-2.5 py-1 ${
                                                    connector.connected
                                                        ? "border-emerald-500/30 text-emerald-300"
                                                        : "border-amber-500/30 text-amber-200"
                                                }`}
                                            >
                                                {connector.connected ? "connected" : "not connected"}
                                            </span>
                                        </div>
                                        {connector.account_label && (
                                            <p className="text-sm text-zinc-400">{connector.account_label}</p>
                                        )}
                                        {connector.capabilities && connector.capabilities.length > 0 && (
                                            <p className="text-xs text-zinc-500">
                                                {connector.capabilities.join(" • ")}
                                            </p>
                                        )}
                                        {connector.updated_at && (
                                            <p className="text-[11px] font-mono text-zinc-600">
                                                Updated {new Date(connector.updated_at).toLocaleString()}
                                            </p>
                                        )}
                                    </div>

                                    <div className="flex flex-col items-end gap-2">
                                        {connector.connected ? (
                                            <span className="inline-flex items-center gap-1 text-sm text-emerald-300">
                                                <CheckCircle2 size={16} />
                                                Ready
                                            </span>
                                        ) : connector.available ? (
                                            connectHref ? (
                                                <a
                                                    href={connectHref}
                                                    className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500"
                                                >
                                                    <Link2 size={15} />
                                                    Connect
                                                </a>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 rounded-full border border-zinc-800 px-3 py-2 text-sm text-zinc-400">
                                                    <ExternalLink size={15} />
                                                    Coming soon
                                                </span>
                                            )
                                        ) : (
                                            <span className="inline-flex items-center gap-1 rounded-full border border-red-500/20 px-3 py-2 text-sm text-red-300">
                                                <ShieldAlert size={15} />
                                                Missing server config
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
