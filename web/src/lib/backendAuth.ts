import { auth } from "@clerk/nextjs/server";

import { getBackendConfig } from "@/lib/backend";

/**
 * Headers for proxying to FastAPI with internal service token + Clerk JWT.
 * Use only from Next.js route handlers or server components.
 */
export async function buildAuthHeaders(): Promise<HeadersInit> {
  const { userId, getToken } = await auth();
  if (!userId) {
    throw new Error("Unauthorized");
  }
  const token = await getToken();
  if (!token) {
    throw new Error("No Clerk session token");
  }
  const { serviceToken } = getBackendConfig();
  return {
    "Content-Type": "application/json",
    "x-service-token": serviceToken,
    Authorization: `Bearer ${token}`,
  };
}

/** Same as buildAuthHeaders but omits Content-Type so multipart FormData sets the boundary. */
export async function buildAuthHeadersFormData(): Promise<HeadersInit> {
  const { userId, getToken } = await auth();
  if (!userId) {
    throw new Error("Unauthorized");
  }
  const token = await getToken();
  if (!token) {
    throw new Error("No Clerk session token");
  }
  const { serviceToken } = getBackendConfig();
  return {
    "x-service-token": serviceToken,
    Authorization: `Bearer ${token}`,
  };
}
