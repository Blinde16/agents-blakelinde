import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export async function POST() {
    const { backendUrl } = getBackendConfig();

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeaders();
    } catch {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        const response = await fetch(`${backendUrl}/api/threads`, {
            method: "POST",
            headers,
        });

        if (!response.ok) throw new Error("Backend creation failed");

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
