# apps/web

Next.js frontend for the AI PaperCraft Studio MVP.

Implemented demo flow:

- create a project
- upload one source image
- choose generation parameters
- create a generation task
- poll task status
- display mock 3D preview, paper-net data, PDF export, and assembly metadata
- render the mock paper-net JSON as a simple page and part list

Local commands:

```bash
pnpm --filter @papercraft/web dev
pnpm --filter @papercraft/web build
pnpm --filter @papercraft/web typecheck
docker compose -f infra/docker/docker-compose.yml up -d --build web
```

The frontend proxies `/backend/*` to the FastAPI service. By default it targets
`http://localhost:8000` when run directly, and `http://host.docker.internal:8000`
when only the web service is run through Docker Compose. In the full Compose
stack it targets `http://api:8000`. Override with `NEXT_PUBLIC_API_BASE_URL`
when needed.
