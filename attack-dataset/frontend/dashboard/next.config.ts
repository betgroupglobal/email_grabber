import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Pin project root so Turbopack does not pick a parent lockfile (e.g. ~/package-lock.json).
const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: dashboardRoot,
  },
  async redirects() {
    return [
      {
        source: "/dashboard",
        destination: "/operations",
        permanent: false,
      },
      {
        source: "/guided-assessment",
        destination: "/operations",
        permanent: false,
      },
      {
        source: "/attack-dashboard",
        destination: "/operations",
        permanent: false,
      },
      {
        source: "/opsec-tools",
        destination: "/operations",
        permanent: false,
      },
      {
        source: "/search",
        destination: "/operations",
        permanent: false,
      },
      {
        source: "/mitre",
        destination: "/operations",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
