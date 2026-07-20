/** @type {import('next').NextConfig} */
const nextConfig = {
  // As telas HTML são lidas do disco em runtime pelos route handlers;
  // sem isto o build do Vercel não as inclui no bundle serverless.
  outputFileTracingIncludes: {
    "/": ["./telas/**"],
    "/avaliacao": ["./telas/**"],
  },
};

export default nextConfig;
