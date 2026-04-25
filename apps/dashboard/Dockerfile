# Phase 0 stub — multistage build, final image target < 1GB

FROM node:20-slim AS builder
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-slim AS final
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /build/.next/standalone ./
COPY --from=builder /build/.next/static ./.next/static
COPY --from=builder /build/public ./public

# Run as non-root to limit blast radius if the container is compromised.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 3000
CMD ["node", "server.js"]
