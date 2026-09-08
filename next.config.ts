import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // MetLife workbooks can be up to 100 MB. Leave room for multipart framing
    // before the same-origin route streams the request to FastAPI.
    proxyClientMaxBodySize: "110mb",
    // Canonical workbook loads include a Drive backup, in-place replacement,
    // and SQL re-indexing before success can be confirmed. Vida loads can take
    // more than 90 seconds, so keep the proxy aligned with the 10-minute limit
    // used by the dedicated apply endpoints.
    proxyTimeout: 600_000,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Strict-Transport-Security", value: "max-age=31536000" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:7777/:path*",
      },
    ];
  },
};

export default nextConfig;
