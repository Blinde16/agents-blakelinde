import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeadersFormData } from "@/lib/backendAuth";

export async function POST(request: Request) {
    const formData = await request.formData();
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
        return NextResponse.json({ error: "file is required" }, { status: 400 });
    }

    const { backendUrl } = getBackendConfig();

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeadersFormData();
    } catch {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const upstream = new FormData();
    upstream.append("file", file);

    try {
        const response = await fetch(`${backendUrl}/api/finance/sheets/upload`, {
            method: "POST",
            headers,
            body: upstream,
        });

        const text = await response.text();
        if (!response.ok) {
            let detail = text;
            try {
                const j = JSON.parse(text) as { detail?: unknown };
                if (typeof j.detail === "string") detail = j.detail;
            } catch {
                /* use raw */
            }
            return NextResponse.json({ error: detail || "Upload failed" }, { status: response.status });
        }

        try {
            const data = JSON.parse(text) as Record<string, unknown>;
            return NextResponse.json(data);
        } catch {
            return NextResponse.json({ error: "Invalid upstream response" }, { status: 502 });
        }
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
