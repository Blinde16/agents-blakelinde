import crypto from "crypto";
import { NextResponse } from "next/server";

const GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
];

export async function GET(request: Request) {
    const clientId = process.env.GOOGLE_OAUTH_CLIENT_ID;
    if (!clientId) {
        return NextResponse.redirect(new URL("/?connector_error=google_client_missing", request.url));
    }

    const url = new URL(request.url);
    const origin = url.origin;
    const redirectUri = `${origin}/api/integrations/google/oauth/callback`;
    const state = crypto.randomBytes(24).toString("hex");

    const googleUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth");
    googleUrl.searchParams.set("client_id", clientId);
    googleUrl.searchParams.set("redirect_uri", redirectUri);
    googleUrl.searchParams.set("response_type", "code");
    googleUrl.searchParams.set("access_type", "offline");
    googleUrl.searchParams.set("prompt", "consent");
    googleUrl.searchParams.set("include_granted_scopes", "true");
    googleUrl.searchParams.set("scope", GOOGLE_SCOPES.join(" "));
    googleUrl.searchParams.set("state", state);

    const response = NextResponse.redirect(googleUrl);
    response.cookies.set("google_oauth_state", state, {
        httpOnly: true,
        sameSite: "lax",
        secure: true,
        path: "/",
        maxAge: 60 * 10,
    });
    return response;
}
