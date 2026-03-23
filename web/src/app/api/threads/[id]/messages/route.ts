import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const { id: threadId } = await params;
    let body: Record<string, unknown>;
    try {
        body = (await request.json()) as Record<string, unknown>;
    } catch {
        return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }
    const stream = body.stream === true;
    const { backendUrl } = getBackendConfig();

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeaders();
    } catch {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        const response = await fetch(`${backendUrl}/api/threads/${threadId}/messages`, {
            method: "POST",
            headers,
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const errText = await response.text();
            return NextResponse.json(
                { error: errText || "Failed to push message" },
                { status: response.status }
            );
        }

        if (stream && response.body) {
            return new Response(response.body, {
                status: response.status,
                headers: {
                    "Content-Type": response.headers.get("Content-Type") || "text/event-stream",
                    "Cache-Control": "no-store",
                },
            });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
