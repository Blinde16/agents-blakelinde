import { NextRequest, NextResponse } from "next/server";
import { createHmac } from "crypto";

const PUBLIC_PATHS = ["/login", "/api/auth/login", "/api/auth/logout", "/_next", "/favicon.ico"];
const COOKIE_NAME = "bl_session";

function signValue(value: string, secret: string): string {
    return createHmac("sha256", secret).update(value).digest("hex");
}

function isValidSession(token: string | undefined, secret: string): boolean {
    if (!token) return false;
    // Token format: "authenticated.<hmac>"
    const [payload, sig] = token.split(".");
    if (payload !== "authenticated" || !sig) return false;
    const expected = signValue(payload, secret);
    return sig === expected;
}

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Always allow public paths
    if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
        return NextResponse.next();
    }

    const secret = process.env.INTERNAL_SERVICE_KEY_SIGNER || "dev_service_token_123";
    const sessionToken = request.cookies.get(COOKIE_NAME)?.value;

    if (!isValidSession(sessionToken, secret)) {
        const loginUrl = new URL("/login", request.url);
        loginUrl.searchParams.set("next", pathname);
        return NextResponse.redirect(loginUrl);
    }

    return NextResponse.next();
}

export const config = {
    matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
