import type { NextConfig } from "next";

import { apiBase } from "./src/lib/api-base";

// The browser calls /api/v1/* on this origin and Next.js forwards it to the FastAPI backend
// (S4-R10), so the same URLs work locally and when deployed.
const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiBase()}/api/v1/:path*` }];
  },
};

export default nextConfig;
