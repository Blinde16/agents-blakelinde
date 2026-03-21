"use client";

import { useRouter } from "next/navigation";

export function LogoutButton() {
    const router = useRouter();

    async function handleLogout() {
        await fetch("/api/auth/logout", { method: "POST" });
        router.replace("/login");
    }

    return (
        <button
            onClick={handleLogout}
            className="text-xs font-mono px-2 py-1 bg-zinc-900 rounded border border-zinc-800 text-zinc-500 hover:border-zinc-600 hover:text-zinc-400 transition"
        >
            SYSTEM.AUTHORIZED
        </button>
    );
}
