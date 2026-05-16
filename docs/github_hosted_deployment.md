# GitHub-Hosted Deployment

This project deploys by publishing Docker images from GitHub-hosted Actions runners to GHCR, then pulling those images from the private Windows PC.

## Target Flow

```text
push to main
  -> GitHub-hosted runner runs CI
  -> GitHub-hosted runner builds Docker images
  -> images are pushed to GHCR
  -> private Windows PC runs deploy.ps1 on the regular deployment schedule
  -> docker compose pulls images and restarts services
  -> Caddy serves the existing domain
```

The private PC no longer needs to be registered as a GitHub Actions self-hosted runner.

## GitHub Actions

`.github/workflows/ci-cd.yml` runs on pushes to `main`.

- `ci` runs the release gate report.
- `build_and_push` builds and pushes these GHCR images:
  - `ghcr.io/<owner>/<repo>-ops-api:<sha>` and `latest`
  - `ghcr.io/<owner>/<repo>-trader:<sha>` and `latest`
  - `ghcr.io/<owner>/<repo>-web:<sha>` and `latest`

The workflow uses `GITHUB_TOKEN` with `packages: write` for GHCR publishing.

## Private PC Setup

Create the local runtime env file. Do not commit it.

```powershell
Copy-Item .env.runtime.example .env.runtime
notepad .env.runtime
```

At minimum, confirm these values:

```text
GITHUB_OWNER=shihaim
GITHUB_REPO=quant-trading
IMAGE_TAG=latest
POSTGRES_PASSWORD=<strong local password>
OPS_API_AUTH_SECRET=<strong local secret>
OPS_API_CREDENTIALS_ENCRYPTION_KEY=<strong local key>
OPS_API_CREDENTIALS_KEYRING_JSON=<valid keyring json>
```

Keep API keys, database passwords, and tokens only in `.env.runtime` or another local secret store. They must not be baked into Docker images.

## GHCR Access

If the GHCR packages are public, Docker can pull without login.

If they are private, log in once on the private PC using a GitHub PAT with `read:packages`.

```powershell
docker login ghcr.io -u shihaim
```

Enter the PAT as the password.

## Manual Deploy and Hotfix

Run this from the repository root for a one-time manual deploy, including hotfix releases that should not wait for the regular deployment window:

```powershell
powershell -ExecutionPolicy Bypass -File D:\quant-trading\deploy.ps1
```

The script:

1. Fails if `.env.runtime` is missing.
2. Pulls the configured GHCR images.
3. Runs `docker compose up -d --remove-orphans`.
4. Prunes unused Docker images.

## Windows Task Scheduler

Regular deployment schedule: every Saturday at 06:00.

Use these task settings:

```text
Program/script:
powershell.exe

Arguments:
-ExecutionPolicy Bypass -File D:\quant-trading\deploy.ps1

Start in:
D:\quant-trading
```

For urgent hotfixes, push the fix, wait for `ci` and `build_and_push` to publish the GHCR images, then run `deploy.ps1` manually instead of changing the schedule.

## Domain and Caddy

The domain still points to the private PC, not to GitHub.

```text
hosting.kr domain
  -> private PC public IP
  -> router forwards 80/443
  -> Caddy container
  -> web and ops-api containers
```

The active Caddy config is `infra/caddy/Caddyfile`.

## Remove the Self-Hosted Runner

After confirming scheduled deployment works:

1. In GitHub, remove the old runner from repository Settings -> Actions -> Runners.
2. On the private PC, stop and delete the old runner service.
3. Remove any obsolete runner work directory once you confirm it is not used by another project.
