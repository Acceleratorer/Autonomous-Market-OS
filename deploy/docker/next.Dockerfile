FROM node:24-bookworm-slim AS dependencies

WORKDIR /app
COPY apps/web/next-operator/package.json apps/web/next-operator/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

FROM dependencies AS builder

WORKDIR /app
COPY apps/web/next-operator/ ./
RUN pnpm run typecheck && pnpm run build

FROM node:24-bookworm-slim AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
RUN corepack enable && corepack install --global pnpm@11.25.0
COPY --from=dependencies /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./package.json

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD node -e "fetch('http://127.0.0.1:3000/healthz').then((r) => { if (!r.ok) process.exit(1); }).catch(() => process.exit(1))"

CMD ["pnpm", "run", "start:container"]
