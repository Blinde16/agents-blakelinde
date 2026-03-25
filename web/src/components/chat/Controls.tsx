"use client";

import React, { useRef, useState } from "react";
import { Mic, Paperclip, SendHorizontal } from "lucide-react";
import { mutate } from "swr";
import { useChatStore } from "@/lib/store";
import { consumeChatSse } from "@/lib/sseChat";

export const Controls = () => {
    const [input, setInput] = useState("");
    const [bootstrapError, setBootstrapError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const {
        threadId,
        setThreadId,
        setIsProcessing,
        isProcessing,
        appendStreamingDelta,
        resetStreamingBuffer,
        setStreamingPhase,
        setActiveAgent,
        lastSheetUploadId,
        setLastSheetUploadId,
        resetSession,
    } = useChatStore();

    const handleSheetUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const f = e.target.files?.[0];
        e.target.value = "";
        if (!f) return;
        const fd = new FormData();
        fd.append("file", f);
        try {
            const res = await fetch("/api/finance/sheets/upload", { method: "POST", body: fd });
            const data = (await res.json().catch(() => ({}))) as {
                upload_id?: string;
                error?: string;
            };
            if (!res.ok) {
                console.error("Sheet upload failed", data.error ?? res.status);
                return;
            }
            if (data.upload_id) setLastSheetUploadId(data.upload_id);
        } catch (err) {
            console.error(err);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isProcessing) return;

        let activeThreadId = threadId;

        // Cold start - bootstrap the backend thread first
        if (!activeThreadId) {
            setIsProcessing(true);
            setBootstrapError(null);
            try {
                const res = await fetch("/api/threads", {
                    method: "POST",
                    credentials: "include",
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const detail =
                        typeof (data as { detail?: unknown }).detail === "string"
                            ? (data as { detail: string }).detail
                            : JSON.stringify(data);
                    console.error("Thread create failed", res.status, data);
                    setBootstrapError(
                        res.status === 401
                            ? "Sign in required (session missing or expired)."
                            : res.status === 502
                              ? "Python backend unreachable from Next.js (check BACKEND_API_URL and that the agent is running)."
                              : `Thread create failed (${res.status}): ${detail}`,
                    );
                    setIsProcessing(false);
                    return;
                }
                const newId = (data as { thread_id?: string }).thread_id;
                if (!newId) {
                    console.error("Thread create: missing thread_id", data);
                    setBootstrapError("Thread create returned no thread_id.");
                    setIsProcessing(false);
                    return;
                }
                activeThreadId = newId;
                setThreadId(newId);
            } catch (err) {
                console.error("Failed to boot thread context.", err);
                const isNetwork =
                    err instanceof TypeError && String(err.message).includes("fetch");
                setBootstrapError(
                    isNetwork
                        ? "Network error talking to Next.js or the request was blocked. If you use Clerk middleware, ensure /api routes are public in middleware (see web/src/middleware.ts)."
                        : String(err),
                );
                setIsProcessing(false);
                return;
            }
        }

        // Fire text payload to the thread boundary (Async task starts in python)
        const payload = input;
        setInput("");
        setIsProcessing(true); // Engages the UI frontend loader + SWR interval
        resetStreamingBuffer();
        setStreamingPhase(null);

        try {
            const res = await fetch(`/api/threads/${activeThreadId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ message: payload, stream: true }),
            });
            if (!res.ok) {
                const errBody = await res.json().catch(() => ({}));
                const msg =
                    typeof (errBody as { error?: string }).error === "string"
                        ? (errBody as { error: string }).error
                        : "Message submission failed";
                throw new Error(msg);
            }

            await consumeChatSse(res.body, {
                onDelta: (text) => appendStreamingDelta(text),
                onStatus: (text) => setStreamingPhase(text),
                onDone: (evt) => {
                    if (evt.active_agent) setActiveAgent(evt.active_agent);
                },
                onError: (message) => {
                    console.error("Stream error:", message);
                    appendStreamingDelta(`\n\n[stream error] ${message}`);
                },
            });
        } catch (err) {
            console.error(err);
            const msg = err instanceof Error ? err.message : String(err);
            appendStreamingDelta(`\n\n[request error] ${msg}`);
        } finally {
            await mutate(`/api/threads/${activeThreadId}/state`);
            resetStreamingBuffer();
            setStreamingPhase(null);
            setIsProcessing(false);
        }
    };

    return (
        <div className="w-full bg-transparent p-4 sticky bottom-0 z-20 pb-8">
            <div className="max-w-3xl mx-auto mb-2 flex flex-wrap items-center gap-2 px-1">
                {threadId && (
                    <span className="rounded-full border border-zinc-800 bg-zinc-950/70 px-3 py-1 text-[11px] font-mono text-zinc-400">
                        Active thread: {threadId.slice(0, 8)}…
                    </span>
                )}
                {lastSheetUploadId && (
                    <span className="rounded-full border border-emerald-900/60 bg-emerald-950/30 px-3 py-1 text-[11px] font-mono text-emerald-300">
                        Sheet staged: {lastSheetUploadId.slice(0, 8)}…
                    </span>
                )}
                {(threadId || lastSheetUploadId) && (
                    <button
                        type="button"
                        onClick={() => {
                            resetSession();
                            setBootstrapError(null);
                        }}
                        className="rounded-full border border-zinc-800 px-3 py-1 text-[11px] font-mono text-zinc-500 transition hover:border-zinc-700 hover:text-zinc-300"
                    >
                        Reset Session
                    </button>
                )}
            </div>
            <form onSubmit={handleSubmit} className="flex gap-2 max-w-3xl mx-auto relative group animate-fade-in-up items-center">
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                    className="hidden"
                    onChange={handleSheetUpload}
                />
                <button
                    type="button"
                    title="Upload CSV or XLSX (CFO staging)"
                    disabled={isProcessing}
                    onClick={() => fileInputRef.current?.click()}
                    className="shrink-0 p-3 rounded-full border border-zinc-700/60 text-zinc-400 hover:text-emerald-400 hover:border-emerald-600/50 transition-colors disabled:opacity-40"
                >
                    <Paperclip size={20} />
                </button>
                <div className="relative flex-1 flex items-center glass-pill rounded-full transition-all focus-within:ring-1 focus-within:ring-emerald-500/50 focus-within:bg-zinc-900/80 shadow-lg shadow-black/40">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask for work, approvals, finance checks, inbox triage..."
                        className="flex-1 bg-transparent px-6 py-4 text-[15px] focus:outline-none text-zinc-100 placeholder:text-zinc-500 transition-all font-sans"
                        autoComplete="off"
                    />
                    
                    {/* Text submission */}
                    {input.trim().length > 0 ? (
                        <button 
                            type="submit" 
                            disabled={isProcessing}
                            className="absolute right-2 p-2.5 bg-emerald-600 text-white rounded-full flex items-center justify-center hover:bg-emerald-500 transition-all disabled:opacity-50 shadow-md transform hover:scale-105"
                        >
                            <SendHorizontal size={18} className="ml-0.5" />
                        </button>
                    ) : (
                        /* The designated Vapi "Push to Talk" hook placeholder matching MOBILE_UX specs */
                        <button 
                            type="button" 
                            className="absolute right-2 p-2.5 bg-transparent text-zinc-400 rounded-full hover:text-emerald-400 hover:bg-zinc-800/80 transition-all flex items-center justify-center"
                            onClick={() => alert("Vapi Web SDK Hook Placeholder - Opens Mic Stream")}
                        >
                            <Mic size={18} />
                        </button>
                    )}
                </div>
            </form>
            {bootstrapError && (
                <p className="max-w-3xl mx-auto mt-2 px-1 text-xs text-red-400" role="alert">
                    {bootstrapError}
                </p>
            )}
            {lastSheetUploadId && (
                <p className="max-w-3xl mx-auto mt-2 px-1 text-[11px] font-mono text-zinc-500 truncate">
                    Staging upload_id: {lastSheetUploadId}
                </p>
            )}
        </div>
    );
};
