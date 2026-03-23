import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const { id: threadId } = await params;
    let body: unknown;
    try {
        body = await request.json();
    } catch {
        return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }
    const { backendUrl } = getBackendConfig();

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeaders();
    } catch {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        const response = await fetch(`${backendUrl}/api/threads/${threadId}/approve`, {
            method: "POST",
            headers,
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            let error = "Failed to approve tool trigger";
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
