FROM node:22-alpine AS build

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.18.0 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json

RUN pnpm install --frozen-lockfile

COPY apps/web apps/web

RUN pnpm --filter @papercraft/web build

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production

RUN corepack enable && corepack prepare pnpm@10.18.0 --activate

COPY --from=build /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY --from=build /app/node_modules node_modules
COPY --from=build /app/apps/web apps/web

EXPOSE 3000

CMD ["pnpm", "--filter", "@papercraft/web", "start", "--hostname", "0.0.0.0", "--port", "3000"]
