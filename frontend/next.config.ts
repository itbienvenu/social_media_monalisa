import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "ec2-100-55-92-146.compute-1.amazonaws.com",
    "itims.online",
    "www.itims.online",
    "localhost:3000"
  ]
};

export default nextConfig;
