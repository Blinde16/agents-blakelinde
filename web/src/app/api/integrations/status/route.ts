import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export async function GET() {
    const { backendUrl } = getBackendConfig();

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeaders();
    } catch {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        const response = await fetch(`${backendUrl}/api/integrations/status`, {
            method: "GET",
            headers,
        });
        const text = await response.text();
        if (!response.ok) {
            return NextResponse.json({ error: text || "Failed to load connectors" }, { status: response.status });
        }
        return NextResponse.json(JSON.parse(text) as Record<string, unknown>);
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
