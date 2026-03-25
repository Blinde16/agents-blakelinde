import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * API routes authenticate in Route Handlers (Clerk JWT + service token).
 * Do not run auth.protect() on /api/* — redirects break client-side fetch() (TypeError: Failed to fetch).
 */
const isPublicRoute = createRouteMatcher([
    "/sign-in(.*)",
    "/sign-up(.*)",
    "/api(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
    if (!isPublicRoute(req)) {
        await auth.protect();
    }
});

export const config = {
    matcher: [
        "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpg|jpeg|png|gif|svg|ico|ttf|woff2?|csv|docx?|xlsx?|zip|webmanifest)).*)",
        "/(api|trpc)(.*)",
    ],
};
