import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['0.0.0.0', '192.168.29.34', 'localhost'],
  async rewrites() {
    return [
      {
        source: '/ws/:path*',
        destination: 'http://127.0.0.1:8000/ws/:path*'
      }
    ]
  }
};

export default nextConfig;
