import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
    const { id: threadId } = await params;
    const { backendUrl } = getBackendConfig();

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeaders();
    } catch {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        const response = await fetch(`${backendUrl}/api/threads/${threadId}/state`, {
            method: "GET",
            headers,
        });

        if (!response.ok) {
            let error = "Failed to fetch state";
            try {
                const ct = response.headers.get("content-type") ?? "";
                if (ct.includes("application/json")) {
                    const j = (await response.json()) as {
                        detail?: unknown;
                        message?: unknown;
                    };
                    if (typeof j.detail === "string") error = j.detail;
                    else if (typeof j.message === "string") error = j.message;
                } else {
                    const t = await response.text();
                    if (t) error = t.slice(0, 2000);
                }
            } catch {
                /* keep default */
            }
            return NextResponse.json({ error }, { status: response.status });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
