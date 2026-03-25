"use client";

import React, { useRef, useEffect } from "react";
import useSWR from "swr";
import { useChatStore } from "@/lib/store";
import { ActionCard } from "./ActionCard";
import { cn } from "@/lib/utils";
import { Activity, AlertTriangle, Bot, Clock3, RefreshCcw } from "lucide-react";

type ThreadMessage = { role: string; content: string };
type ThreadStateResponse = {
    messages?: ThreadMessage[];
    pending_approval?: boolean;
    active_agent?: string | null;
    status?: string | null;
    approval_gate_id?: string | null;
    last_error?: string | null;
    stale?: boolean;
    status_detail?: string | null;
    updated_at?: string | null;
    started_at?: string | null;
    completed_at?: string | null;
};

const fetcher = (url: string) =>
    fetch(url).then((r) => {
        if (!r.ok) {
            throw new Error(`State fetch failed: ${r.status}`);
        }
        return r.json();
    });

export const ChatStream = () => {
    const threadId = useChatStore((state) => state.threadId);
    const streamingBuffer = useChatStore((state) => state.streamingBuffer);
    const streamingPhase = useChatStore((state) => state.streamingPhase);
    const { isProcessing, setIsProcessing, activeAgent, setActiveAgent, resetSession } = useChatStore();
    const bottomRef = useRef<HTMLDivElement>(null);

    const { data, mutate } = useSWR(
        threadId ? `/api/threads/${threadId}/state` : null,
        fetcher,
        {
            refreshInterval: (state: ThreadStateResponse | undefined) => {
                const status = state?.status ?? null;
                const pendingApproval = Boolean(state?.pending_approval);
                if (isProcessing || pendingApproval) return 1500;
                if (status === "processing" || status === "awaiting_approval") return 1500;
                return 0;
            },
            revalidateOnFocus: true,
        }
    );

    const state = (data as ThreadStateResponse | undefined) ?? undefined;
    const messages = state?.messages ?? [];
    const needsApproval = Boolean(state?.pending_approval);
    const runStatus = state?.status ?? null;
    const lastError = state?.last_error ?? null;
    const isStale = Boolean(state?.stale);
    const statusDetail = state?.status_detail ?? null;
    const startedAt = state?.started_at ?? null;
    const updatedAt = state?.updated_at ?? null;
    const completedAt = state?.completed_at ?? null;

    useEffect(() => {
        if (!state) return;

        if (state.active_agent && state.active_agent !== activeAgent) {
            setActiveAgent(state.active_agent);
        }

        const shouldProcess = state.status === "processing" || state.status === "awaiting_approval";
        if (shouldProcess !== isProcessing) {
            setIsProcessing(shouldProcess);
        }

        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [state, setIsProcessing, isProcessing, activeAgent, setActiveAgent]);

    const getLoadingLabel = () => {
        if (needsApproval) return "Awaiting human approval...";
        if (!activeAgent) return "Routing request...";
        if (activeAgent.includes("Operations")) {
            return "Running operations (email, calendar, triage)...";
        }
        if (activeAgent.includes("Finance")) return "Running finance tools...";
        if (activeAgent.includes("Sales")) return "Running CRM / revenue tools...";
        if (activeAgent.includes("Brand")) return "Running brand and marketing tools...";
        return `Using ${activeAgent}...`;
    };

    return (
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto px-4 py-6 scroll-smooth pb-24">
            {threadId && (
                <div className="sticky top-0 z-10 -mt-2 mb-1 flex flex-wrap items-center gap-2 rounded-2xl border border-zinc-800/70 bg-black/60 px-3 py-2 backdrop-blur">
                    <span className="inline-flex items-center gap-2 rounded-full bg-zinc-900/80 px-2.5 py-1 text-[11px] font-mono text-zinc-400">
                        <Activity size={12} className={cn(isProcessing && !isStale && "text-emerald-400", isStale && "text-amber-300")} />
                        {runStatus ?? "idle"}
                    </span>
                    {isStale && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-mono text-amber-200">
                            <AlertTriangle size={11} />
                            stale run detected
                        </span>
                    )}
                    {activeAgent && (
                        <span className="rounded-full border border-zinc-800 px-2.5 py-1 text-[11px] font-mono text-zinc-400">
                            {activeAgent}
                        </span>
                    )}
                    <span className="truncate text-[11px] font-mono text-zinc-500">thread {threadId}</span>
                    <button
                        type="button"
                        onClick={() => void mutate()}
                        className="ml-auto inline-flex items-center gap-1 rounded-full border border-zinc-800 px-2.5 py-1 text-[11px] font-mono text-zinc-400 transition hover:border-emerald-600/60 hover:text-emerald-300"
                    >
                        <RefreshCcw size={11} />
                        Refresh
                    </button>
                    <button
                        type="button"
                        onClick={() => resetSession()}
                        className="inline-flex items-center gap-1 rounded-full border border-zinc-800 px-2.5 py-1 text-[11px] font-mono text-zinc-500 transition hover:border-zinc-700 hover:text-zinc-300"
                    >
                        New Thread
                    </button>
                </div>
            )}

            {statusDetail && (
                <div className="mr-auto max-w-[95%] rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber-200/80">Run Status</p>
                    <p className="mt-1 whitespace-pre-wrap">{statusDetail}</p>
                </div>
            )}

            {lastError && (
                <div className="mr-auto max-w-[95%] rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-red-300/80">Run Error</p>
                    <p className="mt-1 whitespace-pre-wrap">{lastError}</p>
                </div>
            )}

            {threadId && (startedAt || updatedAt || completedAt) && (
                <div className="mr-auto flex max-w-[95%] flex-wrap items-center gap-2 text-[11px] font-mono text-zinc-500">
                    <span className="inline-flex items-center gap-1 rounded-full border border-zinc-800 px-2.5 py-1">
                        <Clock3 size={11} />
                        {startedAt ? `started ${new Date(startedAt).toLocaleString()}` : "not started"}
                    </span>
                    {updatedAt && (
                        <span className="rounded-full border border-zinc-800 px-2.5 py-1">
                            updated {new Date(updatedAt).toLocaleString()}
                        </span>
                    )}
                    {completedAt && (
                        <span className="rounded-full border border-zinc-800 px-2.5 py-1">
                            completed {new Date(completedAt).toLocaleString()}
                        </span>
                    )}
                </div>
            )}

            {messages.length === 0 && !isProcessing && (
                <div className="m-auto text-center opacity-50 flex flex-col items-center gap-4">
                    <Bot size={48} className="text-zinc-500" />
                    <p className="font-mono text-xs tracking-widest text-zinc-400">OPERATION LAYER IDLE</p>
                    <p className="max-w-xs text-sm text-zinc-500">
                        Start a thread and the workspace will keep syncing run status, approvals, and message history.
                    </p>
                </div>
            )}
            
            {messages.map((msg, i: number) => {
                const isHuman = msg.role === "user";
                return (
                    <div 
                        key={i} 
                        className={cn(
                            "animate-fade-in-up max-w-[85%] rounded-2xl p-4 text-[15px] leading-relaxed shadow-sm",
                            isHuman 
                              ? "ml-auto bg-gradient-to-br from-emerald-600 to-emerald-800 text-white shadow-emerald-900/20 rounded-tr-sm" 
                              : "mr-auto glass-panel text-zinc-200 font-mono text-sm rounded-tl-sm"
                        )}
                        style={{ animationDelay: `${i * 0.05}s` }}
                    >
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                );
            })}

            {streamingBuffer.length > 0 && (
                <div className="animate-fade-in-up mr-auto max-w-[85%] rounded-2xl rounded-tl-sm p-4 glass-panel text-zinc-200 font-mono text-sm shadow-sm">
                    <p className="whitespace-pre-wrap">{streamingBuffer}</p>
                </div>
            )}

            {/* The structural pause injected into the stream visually */}
            {needsApproval && threadId && (
                <ActionCard 
                    threadId={threadId} 
                    onDecisionResolved={() => {
                        setIsProcessing(true);
                        void mutate();
                    }} 
                />
            )}

            {/* System Status Indicator directly conforming to UX_COPY_GUIDELINES.md */}
            {isProcessing && !needsApproval && streamingBuffer.length === 0 && !isStale && (
                <div className="mr-auto inline-flex items-center gap-3 px-4 py-2 bg-zinc-900/50 rounded-full border border-zinc-800">
                    <span className="flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    <span className="text-xs font-mono text-zinc-400 tracking-wide">
                        {streamingPhase || getLoadingLabel()}
                    </span>
                </div>
            )}
            
            <div ref={bottomRef} className="h-4" />
        </div>
    );
};
