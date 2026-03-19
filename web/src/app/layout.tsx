import "./globals.css";
import React from "react";

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
    <html lang="en" className="dark">
      <body className="bg-black text-zinc-100 font-sans antialiased min-h-screen flex flex-col selection:bg-emerald-900 selection:text-white">
        {/* Placeholder header. Real implementation wraps <ClerkProvider> here. */}
        <header className="w-full border-b border-zinc-800 bg-zinc-950 px-6 py-4 flex items-center justify-between sticky top-0 z-50">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
            <h1 className="font-mono text-sm tracking-widest font-semibold uppercase text-zinc-300">Command Center</h1>
          </div>
          <div className="text-xs font-mono px-2 py-1 bg-zinc-900 rounded border border-zinc-800 text-zinc-500">
            SYSTEM.AUTHORIZED
          </div>
        </header>

        <main className="flex-1 flex w-full max-w-3xl mx-auto flex-col h-[calc(100vh-65px)] overflow-hidden relative">
          {children}
        </main>
      </body>
    </html>
  );
}
