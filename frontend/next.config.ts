import type { NextConfig } from "next";

// Where the FastAPI replicas live. Browsers only ever talk to this Next server: `/api/*` is proxied, so the
// app is same-origin (no CORS, and the refresh cookie scoped to /api/v1/auth just works).
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8001";
const isDev = process.env.NODE_ENV !== "production";

const csp = [
  "default-src 'self'",
  // Next.js injects small inline bootstrap scripts; dev mode additionally needs eval for React refresh.
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const config: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // Compression would buffer the Server-Sent Events stream proxied below; a fronting proxy can compress.
  compress: false,
  // The old section paths moved under "Find shares"; keep every bookmark and shared link working.
  async redirects() {
    return [
      { source: "/picks", destination: "/find", permanent: true },
      { source: "/scanner", destination: "/find/rules", permanent: true },
      { source: "/scanner/:preset", destination: "/find/rules/:preset", permanent: true },
      { source: "/data", destination: "/find/table", permanent: true },
    ];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
