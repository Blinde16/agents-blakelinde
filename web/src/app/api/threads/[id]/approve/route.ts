import { NextResponse } from "next/server";
import { getBackendConfig } from "@/lib/backend";

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const { id: threadId } = await params;
    const body = await request.json();
    const { backendUrl, headers } = getBackendConfig();

    try {
        const response = await fetch(`${backendUrl}/api/threads/${threadId}/approve`, {
            method: "POST",
            headers,
            body: JSON.stringify(body),
        });

        if (!response.ok) throw new Error("Failed to approve tool trigger");
        
        const data = await response.json();
        return NextResponse.json(data);
    } catch (error: any) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
