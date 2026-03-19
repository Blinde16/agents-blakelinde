import { NextResponse } from "next/server";
import { getBackendConfig } from "@/lib/backend";

export async function POST() {
    const { backendUrl, headers } = getBackendConfig();
    
    try {
        const response = await fetch(`${backendUrl}/api/threads`, {
            method: "POST",
            headers,
        });

        if (!response.ok) throw new Error("Backend creation failed");
        
        const data = await response.json();
        return NextResponse.json(data);
    } catch (error: any) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
