$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $RepoRoot ".env.runtime"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing runtime env file: $EnvFile. Copy .env.runtime.example to .env.runtime and fill local secrets first."
}

Set-Location -LiteralPath $RepoRoot

docker compose --env-file $EnvFile pull
docker compose --env-file $EnvFile up -d --remove-orphans
docker image prune -f
