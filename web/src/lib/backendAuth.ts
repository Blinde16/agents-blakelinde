import { auth } from "@clerk/nextjs/server";

import { getBackendConfig } from "@/lib/backend";

function getDevBypassAuthorization(): string | null {
  if (process.env.ALLOW_INSECURE_DEV_AUTH !== "1") {
    return null;
  }
  if (!process.env.DEV_CLERK_USER_ID) {
    return null;
  }
  return "Bearer dev-bypass-token";
}

/**
 * Headers for proxying to FastAPI with internal service token + Clerk JWT.
 * Use only from Next.js route handlers or server components.
 */
export async function buildAuthHeaders(): Promise<HeadersInit> {
  const { serviceToken } = getBackendConfig();
  const { userId, getToken } = await auth();
  const devBypass = getDevBypassAuthorization();
  if (!userId && devBypass) {
    return {
      "Content-Type": "application/json",
      "x-service-token": serviceToken,
      Authorization: devBypass,
    };
  }
  if (!userId) {
    throw new Error("Unauthorized: no Clerk user in request");
  }
  const token = await getToken();
  if (!token) {
    if (devBypass) {
      return {
        "Content-Type": "application/json",
        "x-service-token": serviceToken,
        Authorization: devBypass,
      };
    }
    throw new Error("Unauthorized: no Clerk session token");
  }
  return {
    "Content-Type": "application/json",
    "x-service-token": serviceToken,
    Authorization: `Bearer ${token}`,
  };
}

/** Same as buildAuthHeaders but omits Content-Type so multipart FormData sets the boundary. */
export async function buildAuthHeadersFormData(): Promise<HeadersInit> {
  const { serviceToken } = getBackendConfig();
  const { userId, getToken } = await auth();
  const devBypass = getDevBypassAuthorization();
  if (!userId && devBypass) {
    return {
      "x-service-token": serviceToken,
      Authorization: devBypass,
    };
  }
  if (!userId) {
    throw new Error("Unauthorized: no Clerk user in request");
  }
  const token = await getToken();
  if (!token) {
    if (devBypass) {
      return {
        "x-service-token": serviceToken,
        Authorization: devBypass,
      };
    }
    throw new Error("Unauthorized: no Clerk session token");
  }
  return {
    "x-service-token": serviceToken,
    Authorization: `Bearer ${token}`,
  };
}
