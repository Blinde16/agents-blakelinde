import { NextResponse } from "next/server";

import { getBackendConfig } from "@/lib/backend";
import { buildAuthHeaders } from "@/lib/backendAuth";

export async function GET(request: Request) {
    const url = new URL(request.url);
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state");
    const storedState = request.headers.get("cookie")
        ?.split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith("google_oauth_state="))
        ?.split("=")[1];

    if (!code || !state || !storedState || state !== storedState) {
        return NextResponse.redirect(new URL("/?connector_error=google_oauth_state", request.url));
    }

    let headers: HeadersInit;
    try {
        headers = await buildAuthHeaders();
    } catch {
        return NextResponse.redirect(new URL("/?connector_error=unauthorized", request.url));
    }

    const { backendUrl } = getBackendConfig();
    const redirectUri = `${url.origin}/api/integrations/google/oauth/callback`;

    try {
        const response = await fetch(`${backendUrl}/api/integrations/google/oauth/exchange`, {
            method: "POST",
            headers,
            body: JSON.stringify({ code, redirect_uri: redirectUri }),
        });

        const nextUrl = new URL("/", request.url);
        if (!response.ok) {
            const raw = await response.text();
            nextUrl.searchParams.set("connector_error", raw.slice(0, 120));
        } else {
            nextUrl.searchParams.set("connector_success", "google");
        }
        const redirect = NextResponse.redirect(nextUrl);
        redirect.cookies.set("google_oauth_state", "", { path: "/", maxAge: 0 });
        return redirect;
    } catch {
        return NextResponse.redirect(new URL("/?connector_error=google_exchange_failed", request.url));
    }
}
