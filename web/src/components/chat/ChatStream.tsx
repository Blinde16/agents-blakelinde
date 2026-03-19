"use client";

import React, { useRef, useEffect, useState } from "react";
import useSWR from "swr";
import { useChatStore } from "@/lib/store";
import { ActionCard } from "./ActionCard";
import { cn } from "@/lib/utils";
import { Bot } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

export const ChatStream = () => {
    const threadId = useChatStore((state) => state.threadId);
    const { isProcessing, setIsProcessing, activeAgent, setActiveAgent } = useChatStore();
    const bottomRef = useRef<HTMLDivElement>(null);
    const [messages, setMessages] = useState<any[]>([]);
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

            if (data.status === "completed" && !data.pending_approval) {
                setIsProcessing(false);
            }
            if (data.active_agent && data.active_agent !== activeAgent) {
                setActiveAgent(data.active_agent);
            }

            // Auto scroll down gracefully
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [data, setIsProcessing, activeAgent, setActiveAgent]);

    // Loading / Transition label abstraction
    const getLoadingLabel = () => {
        if (needsApproval) return "Awaiting human approval...";
        if (!activeAgent || activeAgent === "OPS") return "Routing request...";
        return `Querying ${activeAgent} Layer databases...`;
    };

    return (
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto px-4 py-6 scroll-smooth pb-24">
            {messages.length === 0 && !isProcessing && (
                <div className="m-auto text-center opacity-50 flex flex-col items-center gap-4">
                    <Bot size={48} className="text-zinc-500" />
                    <p className="font-mono text-xs tracking-widest text-zinc-400">OPERATION LAYER IDLE</p>
                </div>
            )}
            
            {messages.map((msg: any, i: number) => {
                const isHuman = msg.role === "user";
                return (
                    <div 
                        key={i} 
                        className={cn(
                            "max-w-[85%] rounded-lg p-3 text-[15px] leading-relaxed",
                            isHuman ? "ml-auto bg-zinc-800 text-zinc-100" : "mr-auto bg-transparent border border-zinc-800/80 text-zinc-300 font-mono text-sm"
                        )}
                    >
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                );
            })}

            {/* The structural pause injected into the stream visually */}
            {needsApproval && threadId && (
                <ActionCard 
                    threadId={threadId} 
                    onDecisionResolved={() => mutate()} 
                />
            )}

            {/* System Status Indicator directly conforming to UX_COPY_GUIDELINES.md */}
            {isProcessing && !needsApproval && (
                <div className="mr-auto inline-flex items-center gap-3 px-4 py-2 bg-zinc-900/50 rounded-full border border-zinc-800">
                    <span className="flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    <span className="text-xs font-mono text-zinc-400 tracking-wide">
                        {getLoadingLabel()}
                    </span>
                </div>
            )}
            
            <div ref={bottomRef} className="h-4" />
        </div>
    );
};
