import { NextRequest, NextResponse } from "next/server";
import { createHmac } from "crypto";

const COOKIE_NAME = "bl_session";
// 30-day session
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30;

function signValue(value: string, secret: string): string {
    return createHmac("sha256", secret).update(value).digest("hex");
}

export async function POST(request: NextRequest) {
    const body = await request.json().catch(() => ({}));
    const { password, next = "/" } = body as { password?: string; next?: string };

    const sitePassword = process.env.SITE_PASSWORD;
    if (!sitePassword) {
        return NextResponse.json(
            { error: "SITE_PASSWORD not configured on server." },
            { status: 500 }
        );
    }

    if (!password || password !== sitePassword) {
        return NextResponse.json({ error: "Invalid password." }, { status: 401 });
    }

    const secret = process.env.INTERNAL_SERVICE_KEY_SIGNER || "dev_service_token_123";
    const payload = "authenticated";
    const sig = signValue(payload, secret);
    const token = `${payload}.${sig}`;

    const response = NextResponse.json({ ok: true, redirect: next });
    response.cookies.set(COOKIE_NAME, token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: COOKIE_MAX_AGE,
        path: "/",
    });

    return response;
}
