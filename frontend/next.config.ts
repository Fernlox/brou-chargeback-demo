import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow local loopback host in development so dev assets/hydration are not blocked.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
