$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")

Push-Location $repoRoot
try {
  docker compose -f infra/docker/docker-compose.yml ps
} finally {
  Pop-Location
}
