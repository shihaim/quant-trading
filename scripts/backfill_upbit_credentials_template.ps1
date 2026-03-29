param(
  [string]$BaseUrl = "http://127.0.0.1:18080",
  [Parameter(Mandatory = $true)][string]$Email,
  [Parameter(Mandatory = $true)][string]$Password,
  [Parameter(Mandatory = $true)][string]$AccessKey,
  [Parameter(Mandatory = $true)][string]$SecretKey
)

$ErrorActionPreference = "Stop"

Write-Host "[1/3] login: $Email"
$login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/auth/login" `
  -ContentType "application/json" `
  -Body (@{
      email = $Email
      password = $Password
    } | ConvertTo-Json)

$token = $login.access_token
if ([string]::IsNullOrWhiteSpace($token)) {
  throw "login succeeded but access_token is empty"
}

Write-Host "[2/3] upsert /api/me/credentials/upbit"
$upsert = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/me/credentials/upbit" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body (@{
      access_key = $AccessKey
      secret_key = $SecretKey
    } | ConvertTo-Json)

Write-Host "[3/3] verify /api/me/credentials/upbit"
$status = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/me/credentials/upbit" `
  -Headers @{ Authorization = "Bearer $token" }

if (-not $status.has_credentials) {
  throw "verification failed: has_credentials=false"
}
if (-not $status.is_valid) {
  throw "verification failed: is_valid=false"
}

Write-Host "completed"
Write-Host ("exchange={0} has_credentials={1} is_valid={2} key_version={3}" -f `
    $status.exchange, $status.has_credentials, $status.is_valid, $status.key_version)
