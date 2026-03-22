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
                if (!res.ok) throw new Error("Thread creation failed");
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
            const res = await fetch(`/api/threads/${activeThreadId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: payload })
            });
            if (!res.ok) throw new Error("Message submission failed");
        } catch (err) {
            console.error(err);
            setIsProcessing(false);
        }
    };

    return (
        <div className="w-full bg-transparent p-4 sticky bottom-0 z-20 pb-8">
            <form onSubmit={handleSubmit} className="flex gap-2 max-w-3xl mx-auto relative relative group animate-fade-in-up">
                <div className="relative flex-1 flex items-center glass-pill rounded-full transition-all focus-within:ring-1 focus-within:ring-emerald-500/50 focus-within:bg-zinc-900/80 shadow-lg shadow-black/40">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Enter operation..."
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
        </div>
    );
};
