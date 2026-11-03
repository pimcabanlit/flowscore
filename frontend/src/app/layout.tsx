import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FlowScore",
  description: "Cash-flow credit assessment demo on synthetic borrowers",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={plex.variable}>
      <body className="min-h-screen antialiased">
        <header className="bg-shell text-shell-ink">
          <div className="mx-auto flex max-w-6xl flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 py-3 sm:px-6">
            <Link href="/" className="text-lg font-semibold tracking-tight text-shell-ink no-underline hover:underline">
              FlowScore
            </Link>
            <p className="text-sm text-shell-soft">Demo with synthetic borrowers. No sign-in.</p>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 pb-16 pt-8 sm:px-6">{children}</main>
      </body>
    </html>
  );
}
