import { NextResponse } from "next/server";
import { getBackendConfig } from "@/lib/backend";

// Forces Next.js not to cache the polling route. Highly critical for real-time DB states.
export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const { id: threadId } = await params;
    const { backendUrl, headers } = getBackendConfig();

    try {
        const response = await fetch(`${backendUrl}/api/threads/${threadId}/state`, {
            method: "GET",
            headers,
        });

        if (!response.ok) throw new Error("Failed to fetch state");
        
        const data = await response.json();
        return NextResponse.json(data);
    } catch (error: any) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
