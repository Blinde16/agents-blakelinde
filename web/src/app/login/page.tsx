"use client";

import { useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function LoginPage() {
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const router = useRouter();
    const searchParams = useSearchParams();
    const next = searchParams.get("next") || "/";

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setLoading(true);
        setError("");

        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ password, next }),
            });

            if (res.ok) {
                router.replace(next);
            } else {
                const data = await res.json();
                setError(data.error || "Invalid password.");
            }
        } catch {
            setError("Connection error. Try again.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-black px-4">
            <div className="w-full max-w-sm">
                {/* Header */}
                <div className="flex items-center gap-3 mb-10">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                    <span className="font-mono text-sm tracking-widest font-semibold uppercase text-zinc-300">
                        Command Center
                    </span>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                    <div>
                        <label
                            htmlFor="password"
                            className="block font-mono text-xs text-zinc-500 uppercase tracking-widest mb-2"
                        >
                            Access Key
                        </label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            autoFocus
                            autoComplete="current-password"
                            className="w-full bg-zinc-900 border border-zinc-800 rounded px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:border-emerald-700 focus:ring-1 focus:ring-emerald-700 transition"
                        />
                    </div>

                    {error && (
                        <p className="font-mono text-xs text-red-500 tracking-wide">{error}</p>
                    )}

                    <button
                        type="submit"
                        disabled={loading || !password}
                        className="w-full bg-emerald-700 hover:bg-emerald-600 disabled:bg-zinc-800 disabled:text-zinc-600 text-white font-mono text-sm font-semibold py-3 rounded transition tracking-widest uppercase"
                    >
                        {loading ? "Authorizing..." : "Authorize"}
                    </button>
                </form>
            </div>
        </div>
    );
}
