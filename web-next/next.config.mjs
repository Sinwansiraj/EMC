import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin the file-tracing root to this app (a stray parent lockfile otherwise
  // makes Next infer the wrong workspace root).
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
