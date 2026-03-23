"use client";

import React from "react";
import { useChatStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Layers, FileText, Activity } from "lucide-react";

const AGENT_LAYERS = [
    { id: "Lead_Router_Agent", label: "Lead Router" },
    { id: "Finance_Layer", label: "Finance (CFO)" },
    { id: "Sales_Ops_Layer", label: "Sales Ops (CRO)" },
    { id: "Brand_Layer", label: "Brand (CMO)" },
    { id: "Operations_Layer", label: "Operations (Ops)" },
];

export const Sidebar = () => {
    const { activeAgent, isProcessing } = useChatStore();

    // Default to Router if none explicitly active
    const currentActive = activeAgent || "Lead_Router_Agent";

    return (
        <aside className="w-64 hidden md:flex flex-col border-r border-zinc-800/60 glass-panel h-full z-10 p-4">
            <div className="mb-8">
                <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase flex items-center gap-2 mb-4">
                    <Layers size={14} /> Agent Framework
                </h2>
                <div className="flex flex-col gap-2">
                    {AGENT_LAYERS.map((agent) => {
                        const isActive = currentActive === agent.id;
                        return (
                            <div 
                                key={agent.id}
                                className={cn(
                                    "flex items-center justify-between px-3 py-2 rounded-lg text-[13px] font-sans transition-all border",
                                    isActive 
                                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.1)]" 
                                    : "bg-zinc-900/30 border-transparent text-zinc-400 opacity-60"
                                )}
                            >
                                <span className={cn(isActive && "font-medium")}>{agent.label}</span>
                                {isActive && isProcessing && (
                                    <Activity size={12} className="animate-pulse text-emerald-400" />
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="mb-8">
                <h2 className="text-xs font-mono tracking-widest text-zinc-500 uppercase flex items-center gap-2 mb-4">
                    <FileText size={14} /> Loaded Context
                </h2>
                <div className="flex flex-col gap-2">
                    {/* Mock Context Files as requested in Plan */}
                    <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-zinc-900/40 border border-zinc-800/40 text-[13px] text-zinc-300">
                        <FileText size={14} className="text-zinc-500" />
                        <span className="truncate">Brand_Guidelines.pdf</span>
                    </div>
                    <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-zinc-900/40 border border-zinc-800/40 text-[13px] text-zinc-300">
                        <FileText size={14} className="text-zinc-500" />
                        <span className="truncate">Q1_Financials.csv</span>
                    </div>
                </div>
            </div>

            <div className="mt-auto px-3 py-3 rounded-lg bg-zinc-900/40 border border-zinc-800/40 flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-glow" />
                <span className="text-xs font-mono text-zinc-400">Memory Sync: Active</span>
            </div>
        </aside>
    );
};
