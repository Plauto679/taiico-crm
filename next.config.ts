import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // MetLife workbooks can be up to 100 MB. Leave room for multipart framing
    // before the same-origin rewrite streams the request to FastAPI.
    proxyClientMaxBodySize: "110mb",
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
