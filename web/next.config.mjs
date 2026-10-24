// Security headers for `next start` / dev. In production the site is a static export
// (STATIC_EXPORT=1) and the same headers are set by the host (render.yaml / nginx.conf).
export const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const staticExport = process.env.STATIC_EXPORT === "1";

// The API address is baked into the static build. Fail loudly instead of shipping a site that calls localhost.
if (staticExport && !/^https?:\/\//.test(process.env.NEXT_PUBLIC_API_URL ?? "")) {
  throw new Error("NEXT_PUBLIC_API_URL must be set (e.g. https://genscr-api.onrender.com) for a static export build.");
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  ...(staticExport
    ? { output: "export", trailingSlash: true, images: { unoptimized: true } }
    : {
        output: "standalone",
        async headers() {
          return [{ source: "/:path*", headers: securityHeaders }];
        },
      }),
};

export default nextConfig;
