"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";

interface ActionCardProps {
    threadId: string;
    onDecisionResolved: () => void;
}

export const ActionCard = ({ threadId, onDecisionResolved }: ActionCardProps) => {
    const [submitting, setSubmitting] = useState(false);

    const handleAction = async (decision: "APPROVED" | "REJECTED") => {
        setSubmitting(true);
        try {
            await fetch(`/api/threads/${threadId}/approve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ decision }),
            });
            onDecisionResolved();
        } catch (e) {
            console.error(e);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="my-4 border rounded-2xl overflow-hidden glass-panel max-w-[85%] mr-auto shadow-lg shadow-black/30 animate-fade-in-up">
            <div className="bg-zinc-900/40 px-5 py-3 text-xs text-zinc-300 font-mono tracking-wider border-b border-zinc-700/50 flex justify-between items-center backdrop-blur-md">
                <span className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                    SYSTEM &gt; REQUIRED_APPROVAL
                </span>
            </div>
            <div className="p-4 flex flex-col gap-2">
                <p className="text-sm text-zinc-200">
                    The agent is attempting to execute a potentially destructive tool. Please review and authorize.
                </p>
                
                <div className="mt-4 flex gap-3">
                    <button 
                        disabled={submitting}
                        onClick={() => handleAction("APPROVED")}
                        className={cn(
                            "flex-1 rounded-xl py-2.5 px-3 text-sm font-semibold transition-all text-white shadow-md",
                            submitting ? "bg-emerald-600/50" : "bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 transform hover:scale-[1.02]"
                        )}
                    >
                        {submitting ? "Sending..." : "Approve & Execute"}
                    </button>
                    <button 
                        disabled={submitting}
                        onClick={() => handleAction("REJECTED")}
                        className={cn(
                            "rounded-xl py-2.5 px-5 text-sm font-semibold transition-all",
                            submitting ? "text-zinc-600 bg-zinc-900" : "text-zinc-300 bg-zinc-800/50 hover:bg-red-500/20 hover:text-red-400 border border-zinc-700/50 transform hover:scale-[1.02]"
                        )}
                    >
                        Reject
                    </button>
                </div>
            </div>
        </div>
    );
};
