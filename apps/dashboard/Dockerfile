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
EXPOSE 3000
CMD ["node", "server.js"]
