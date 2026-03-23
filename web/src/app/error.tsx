"use client";

import { useEffect } from "react";

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error(error);
    }, [error]);

    return (
        <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 px-4">
            <h2 className="font-mono text-sm tracking-wider text-zinc-400">RUNTIME_ERROR</h2>
            <p className="max-w-md text-center text-sm text-zinc-300">{error.message || "Something failed."}</p>
            <button
                type="button"
                onClick={() => reset()}
                className="rounded-xl border border-zinc-600 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
            >
                Retry
            </button>
        </div>
    );
}
