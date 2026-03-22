"use client";

import { SignInButton, UserButton, useUser } from "@clerk/nextjs";

export function HeaderAuth() {
  const { isSignedIn, isLoaded } = useUser();

  if (!isLoaded) {
    return <div className="h-8 w-20 rounded bg-zinc-900/50 animate-pulse" aria-hidden />;
  }

  if (!isSignedIn) {
    return (
      <SignInButton mode="modal">
        <button
          type="button"
          className="px-2.5 py-1 bg-zinc-900/80 rounded border border-zinc-800/80 text-zinc-300 hover:text-white"
        >
          Sign in
        </button>
      </SignInButton>
    );
  }

  return <UserButton appearance={{ elements: { userButtonAvatarBox: "w-8 h-8" } }} />;
}
