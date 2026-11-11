import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "./_components/AppShell";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "DSE Live Analyzer", template: "%s · DSE Live" },
  description: "Live quotes, technical and fundamental analysis and scanners for the Dhaka Stock Exchange. For research only.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
