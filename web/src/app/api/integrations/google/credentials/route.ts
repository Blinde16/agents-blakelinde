import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export async function POST(request: Request) {
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
        const response = await fetch(`${backendUrl}/api/integrations/google/credentials`, {
            method: "POST",
            headers,
            body: JSON.stringify(body),
        });

        const text = await response.text();
        if (!response.ok) {
            let detail = text;
            try {
                const j = JSON.parse(text) as { detail?: unknown };
                if (typeof j.detail === "string") detail = j.detail;
            } catch {
                /* raw */
            }
            return NextResponse.json({ error: detail || "Save failed" }, { status: response.status });
        }

        try {
            return NextResponse.json(JSON.parse(text) as Record<string, unknown>);
        } catch {
            return NextResponse.json({ status: "saved" });
        }
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
