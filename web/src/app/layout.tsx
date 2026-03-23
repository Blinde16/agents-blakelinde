import "./globals.css";
import React from "react";

import { ClerkProvider } from "@clerk/nextjs";

import { HeaderAuth } from "@/components/HeaderAuth";

export const metadata = {
  title: "Blake Linde - System Command",
  description: "Internal operations and command layer.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <body className="bg-black text-zinc-100 font-sans antialiased min-h-screen flex flex-col selection:bg-emerald-900 selection:text-white relative">
          <div className="absolute inset-0 z-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-zinc-900/30 via-black to-black pointer-events-none" />

          <header className="w-full glass-panel px-6 py-4 flex items-center justify-between sticky top-0 z-50">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse-glow" />
              <h1 className="font-mono text-sm tracking-widest font-semibold uppercase text-zinc-200">Command Center</h1>
            </div>
            <div className="flex items-center gap-3 text-xs font-mono">
              <HeaderAuth />
            </div>
          </header>

          <main className="flex-1 flex w-full max-w-6xl mx-auto flex-col h-[calc(100vh-65px)] overflow-hidden relative z-10">
            {children}
          </main>
        </body>
      </html>
    </ClerkProvider>
  );
}
