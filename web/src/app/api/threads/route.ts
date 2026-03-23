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

        const text = await response.text();
        if (!response.ok) {
            let detail: unknown = text;
            try {
                detail = JSON.parse(text);
            } catch {
                /* keep raw text */
            }
            return NextResponse.json(
                { error: "Backend thread creation failed", status: response.status, detail },
                { status: response.status >= 500 ? 502 : response.status },
            );
        }

        const data = JSON.parse(text);
        return NextResponse.json(data);
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
