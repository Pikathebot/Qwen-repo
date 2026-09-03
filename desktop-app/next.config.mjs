/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  distDir: "out",
  images: {
    unoptimized: true,
  },
  // Folder + index.html output (out/hud/index.html) rather than a flat
  // out/hud.html file, so Tauri's secondary windows resolve the same
  // extensionless path ("hud") in both `next dev` (served by route) and the
  // static export (served by directory-index fallback).
  trailingSlash: true,
};

export default nextConfig;
