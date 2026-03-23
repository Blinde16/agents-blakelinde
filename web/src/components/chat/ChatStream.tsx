"use client";

import React, { useRef, useEffect, useState } from "react";
import useSWR from "swr";
import { useChatStore } from "@/lib/store";
import { ActionCard } from "./ActionCard";
import { cn } from "@/lib/utils";
import { Bot } from "lucide-react";

type ThreadMessage = { role: string; content: string };

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
    const { isProcessing, setIsProcessing, activeAgent, setActiveAgent } = useChatStore();
    const bottomRef = useRef<HTMLDivElement>(null);
    const [messages, setMessages] = useState<ThreadMessage[]>([]);
    const [needsApproval, setNeedsApproval] = useState(false);

    // Core logic: If we have a thread and it's processing, ping every 1.5s as mandated.
    const { data, mutate } = useSWR(
        threadId && isProcessing ? `/api/threads/${threadId}/state` : null,
        fetcher,
        { refreshInterval: 1500 }
    );

    // Side effect to sync the SWR DB pull with the global Zustand HUD state
    useEffect(() => {
        if (data) {
            if (data.messages?.length > 0) {
                setMessages(data.messages);
            }
            setNeedsApproval(data.pending_approval || false);

            // Do not clear isProcessing here when status is "completed". A poll can return the
            // *previous* run's completed row before push_message flips the row to "processing",
            // which would kill the spinner mid-SSE (~1–3s). Processing ends in Controls when the
            // stream finishes (or on error there).
            if (data.active_agent && data.active_agent !== activeAgent) {
                setActiveAgent(data.active_agent);
            }

            // Auto scroll down gracefully
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [data, setIsProcessing, activeAgent, setActiveAgent]);

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
            {messages.length === 0 && !isProcessing && (
                <div className="m-auto text-center opacity-50 flex flex-col items-center gap-4">
                    <Bot size={48} className="text-zinc-500" />
                    <p className="font-mono text-xs tracking-widest text-zinc-400">OPERATION LAYER IDLE</p>
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
                    onDecisionResolved={() => mutate()} 
                />
            )}

            {/* System Status Indicator directly conforming to UX_COPY_GUIDELINES.md */}
            {isProcessing && !needsApproval && streamingBuffer.length === 0 && (
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
