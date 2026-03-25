import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export async function GET() {
    const { backendUrl } = getBackendConfig();

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeaders();
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unauthorized";
        return NextResponse.json(
            {
                connectors: [],
                auth_ready: false,
                error: message,
            },
            { status: 200 }
        );
    }

    try {
        const response = await fetch(`${backendUrl}/api/integrations/status`, {
            method: "GET",
            headers,
        });
        const text = await response.text();
        if (!response.ok) {
            return NextResponse.json(
                {
                    connectors: [],
                    auth_ready: true,
                    error: text || "Failed to load connectors",
                },
                { status: 200 }
            );
        }
        const payload = JSON.parse(text) as Record<string, unknown>;
        return NextResponse.json({ auth_ready: true, ...payload });
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json(
            {
                connectors: [],
                auth_ready: true,
                error: message,
            },
            { status: 200 }
        );
    }
}
