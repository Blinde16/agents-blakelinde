"use client";

import React, { useState } from "react";
import { Mic, SendHorizontal } from "lucide-react";
import { useChatStore } from "@/lib/store";

export const Controls = () => {
    const [input, setInput] = useState("");
    const { threadId, setThreadId, setIsProcessing, isProcessing } = useChatStore();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isProcessing) return;

        let activeThreadId = threadId;

        // Cold start - bootstrap the backend thread first
        if (!activeThreadId) {
            setIsProcessing(true);
            try {
                const res = await fetch("/api/threads", { method: "POST" });
                const data = await res.json();
                activeThreadId = data.thread_id;
                setThreadId(activeThreadId as string);
            } catch (err) {
                console.error("Failed to boot thread context.");
                setIsProcessing(false);
                return;
            }
        }

        // Fire text payload to the thread boundary (Async task starts in python)
        const payload = input;
        setInput("");
        setIsProcessing(true); // Engages the UI frontend loader + SWR interval
        
        try {
            await fetch(`/api/threads/${activeThreadId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: payload })
            });
        } catch (err) {
            console.error(err);
            setIsProcessing(false);
        }
    };

    return (
        <div className="w-full bg-black/80 backdrop-blur-md p-4 sticky bottom-0 border-t border-zinc-800">
            <form onSubmit={handleSubmit} className="flex gap-2 max-w-3xl mx-auto relative">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Enter operation..."
                    className="flex-1 rounded-full bg-zinc-900 border border-zinc-800 px-6 py-3 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-600 text-zinc-100 placeholder:text-zinc-600 transition-all"
                    autoComplete="off"
                />
                
                {/* Text submission */}
                {input.trim().length > 0 ? (
                    <button 
                        type="submit" 
                        disabled={isProcessing}
                        className="absolute right-2 top-1.5 p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-500 transition-colors disabled:opacity-50"
                    >
                        <SendHorizontal size={18} />
                    </button>
                ) : (
                    /* The designated Vapi "Push to Talk" hook placeholder matching MOBILE_UX specs */
                    <button 
                        type="button" 
                        className="absolute right-2 top-1.5 p-2 bg-zinc-800 text-zinc-400 rounded-full hover:text-white hover:bg-zinc-700 transition-colors"
                        onClick={() => alert("Vapi Web SDK Hook Placeholder - Opens Mic Stream")}
                    >
                        <Mic size={18} />
                    </button>
                )}
            </form>
        </div>
    );
};
