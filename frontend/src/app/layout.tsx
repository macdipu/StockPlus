import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, Schibsted_Grotesk } from "next/font/google";
import type { ReactNode } from "react";
import { AppShell } from "./_components/AppShell";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "DSE Live Analyzer", template: "%s · DSE Live" },
  description: "Live quotes, technical and fundamental analysis and scanners for the Dhaka Stock Exchange. For research only.",
};

// Self-hosted at build time by next/font (no runtime request to Google, so the CSP stays 'self').
const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex", display: "swap" });
const schibsted = Schibsted_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-schibsted", display: "swap" });

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${plex.variable} ${schibsted.variable}`}>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
