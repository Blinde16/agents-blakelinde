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
        <div className="my-4 border rounded-lg overflow-hidden border-zinc-800 bg-zinc-950/50 max-w-[85%] mr-auto">
            <div className="bg-zinc-800/60 px-4 py-2 text-xs text-zinc-300 font-mono tracking-wider border-b border-zinc-800 flex justify-between">
                <span>SYSTEM &gt; REQUIRED_APPROVAL</span>
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
                            "flex-1 rounded py-2 px-3 text-sm font-semibold transition-all text-black",
                            submitting ? "bg-emerald-600/50" : "bg-emerald-500 hover:bg-emerald-400"
                        )}
                    >
                        {submitting ? "Sending..." : "Approve & Execute"}
                    </button>
                    <button 
                        disabled={submitting}
                        onClick={() => handleAction("REJECTED")}
                        className={cn(
                            "rounded py-2 px-4 text-sm font-semibold transition-all",
                            submitting ? "text-zinc-600 bg-zinc-900" : "text-zinc-300 bg-zinc-800 hover:bg-red-500/20 hover:text-red-400"
                        )}
                    >
                        Reject
                    </button>
                </div>
            </div>
        </div>
    );
};
