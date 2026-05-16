param(
  [string]$BaseUrl = "http://127.0.0.1:28080",
  [string]$AdminEmail = "admin@example.com",
  [string]$MemberEmail = "member@example.com",
  [string]$Password = "strong-pass-123",
  [switch]$SkipSignup
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
  param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Path,
    [hashtable]$Headers = @{},
    $Body = $null
  )

  $uri = "$BaseUrl$Path"
  $status = 0
  $content = ""

  $params = @{
    Method      = $Method
    Uri         = $uri
    Headers     = $Headers
    ErrorAction = "Stop"
  }

  # Windows PowerShell 5.x: avoid script execution warning prompt.
  if ($PSVersionTable.PSVersion.Major -lt 6) {
    $params["UseBasicParsing"] = $true
  }

  if ($null -ne $Body) {
    $params["ContentType"] = "application/json"
    $params["Body"] = ($Body | ConvertTo-Json -Depth 20 -Compress)
  }

  try {
    if ($PSVersionTable.PSVersion.Major -ge 7) {
      $resp = Invoke-WebRequest @params -SkipHttpErrorCheck
    } else {
      $resp = Invoke-WebRequest @params
    }
    $status = [int]$resp.StatusCode
    $content = [string]$resp.Content
  } catch {
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
      $content = [string]$_.ErrorDetails.Message
    }

    if ((-not $content) -and $_.Exception.Response) {
      try {
        $status = [int]$_.Exception.Response.StatusCode
      } catch {
        $status = 0
      }
      try {
        $stream = $_.Exception.Response.GetResponseStream()
        if ($stream) {
          $reader = New-Object System.IO.StreamReader($stream)
          $content = $reader.ReadToEnd()
          $reader.Close()
        }
      } catch {
        # ignore
      }
    }

    if ($status -eq 0 -and $_.Exception.Response) {
      try {
        $status = [int]$_.Exception.Response.StatusCode
      } catch {
        # ignore
      }
    }

    if ($status -eq 0 -and -not $content) {
      throw
    }
  }

  $json = $null
  if ($content) {
    try {
      $json = $content | ConvertFrom-Json
    } catch {
      $json = [pscustomobject]@{ raw = $content }
    }
  }

  [pscustomobject]@{
    Status = $status
    Json   = $json
    Raw    = $content
  }
}

function Assert-Status {
  param(
    [string]$Label,
    [int]$Actual,
    [int[]]$Expected
  )
  if ($Expected -notcontains $Actual) {
    throw "$Label failed: expected [$($Expected -join ',')], got $Actual"
  }
}

function Show-Result {
  param(
    [string]$Label,
    $Resp
  )
  $err = ""
  $msg = ""
  $rep = ""
  if ($Resp.Json) {
    try { $err = [string]$Resp.Json.error } catch {}
    try { $msg = [string]$Resp.Json.message } catch {}
    try { $rep = [string]$Resp.Json.replacement } catch {}
  }
  Write-Host ("{0} => status={1}, error={2}, message={3}, replacement={4}" -f $Label, $Resp.Status, $err, $msg, $rep)
}

Write-Host "[1/9] unauthorized baseline"
$r = Invoke-Json -Method GET -Path "/api/me"
Show-Result "GET /api/me (no token)" $r
Assert-Status -Label "unauthorized baseline" -Actual $r.Status -Expected @(401)

if (-not $SkipSignup) {
  Write-Host "[2/9] signup accounts"
  $adminSignup = Invoke-Json -Method POST -Path "/api/auth/signup" -Body @{
    email = $AdminEmail
    password = $Password
    display_name = "Admin"
  }
  Show-Result "signup admin" $adminSignup
  Assert-Status -Label "signup admin" -Actual $adminSignup.Status -Expected @(201, 409)

  $memberSignup = Invoke-Json -Method POST -Path "/api/auth/signup" -Body @{
    email = $MemberEmail
    password = $Password
    display_name = "Member"
  }
  Show-Result "signup member" $memberSignup
  Assert-Status -Label "signup member" -Actual $memberSignup.Status -Expected @(201, 409)
} else {
  Write-Host "[2/9] signup skipped"
}

Write-Host "[3/9] login admin"
$adminLogin = Invoke-Json -Method POST -Path "/api/auth/login" -Body @{
  email = $AdminEmail
  password = $Password
}
Show-Result "login admin" $adminLogin
Assert-Status -Label "login admin" -Actual $adminLogin.Status -Expected @(200)
$adminToken = [string]$adminLogin.Json.access_token
if ([string]::IsNullOrWhiteSpace($adminToken)) {
  throw "login admin returned empty access_token"
}

if (-not [bool]$adminLogin.Json.user.is_admin) {
  throw "login admin is_admin=false. Check users.is_admin for $AdminEmail"
}

Write-Host "[4/9] force member baseline role=member (for repeatable run)"
$memberLookup = Invoke-Json -Method POST -Path "/api/auth/login" -Body @{
  email = $MemberEmail
  password = $Password
}
Assert-Status -Label "member lookup login" -Actual $memberLookup.Status -Expected @(200)
$memberId = [int]$memberLookup.Json.user.id

$setMember = Invoke-Json -Method POST -Path "/api/admin/users/$memberId/role" -Headers @{ Authorization = "Bearer $adminToken" } -Body @{
  role = "member"
}
Show-Result "set member role=member" $setMember
Assert-Status -Label "set member role" -Actual $setMember.Status -Expected @(200)

Write-Host "[5/9] login member and verify boundary"
$memberLogin = Invoke-Json -Method POST -Path "/api/auth/login" -Body @{
  email = $MemberEmail
  password = $Password
}
Assert-Status -Label "login member" -Actual $memberLogin.Status -Expected @(200)
$memberTokenOld = [string]$memberLogin.Json.access_token
if ([string]::IsNullOrWhiteSpace($memberTokenOld)) {
  throw "login member returned empty access_token"
}

if ([bool]$memberLogin.Json.user.is_admin) {
  throw "member login returned is_admin=true before promotion"
}

$forbidden = Invoke-Json -Method GET -Path "/api/admin/users/runtime-summary" -Headers @{ Authorization = "Bearer $memberTokenOld" }
Show-Result "member -> /api/admin/users/runtime-summary" $forbidden
Assert-Status -Label "member runtime-summary deny" -Actual $forbidden.Status -Expected @(403)

Write-Host "[6/9] verify admin runtime summary"
$runtimeSummary = Invoke-Json -Method GET -Path "/api/admin/users/runtime-summary" -Headers @{ Authorization = "Bearer $adminToken" }
Show-Result "admin -> /api/admin/users/runtime-summary" $runtimeSummary
Assert-Status -Label "admin runtime-summary allow" -Actual $runtimeSummary.Status -Expected @(200)

Write-Host "[7/9] verify legacy alias retirement"
$legacyOpsSummary = Invoke-Json -Method GET -Path "/api/ops/summary" -Headers @{ Authorization = "Bearer $adminToken" }
Show-Result "GET /api/ops/summary" $legacyOpsSummary
Assert-Status -Label "legacy ops summary retired" -Actual $legacyOpsSummary.Status -Expected @(410)

$legacyAdminSummary = Invoke-Json -Method GET -Path "/api/admin/summary" -Headers @{ Authorization = "Bearer $adminToken" }
Show-Result "GET /api/admin/summary" $legacyAdminSummary
Assert-Status -Label "legacy admin summary retired" -Actual $legacyAdminSummary.Status -Expected @(410)

$legacyRotate = Invoke-Json -Method POST -Path "/api/ops/credentials/rotate" -Headers @{ Authorization = "Bearer $adminToken" } -Body @{
  dry_run = $true
  target_key_version = "v2"
}
Show-Result "POST /api/ops/credentials/rotate" $legacyRotate
Assert-Status -Label "legacy rotate retired" -Actual $legacyRotate.Status -Expected @(410)

Write-Host "[8/9] promote member -> admin and verify session revocation"
$promote = Invoke-Json -Method POST -Path "/api/admin/users/$memberId/role" -Headers @{ Authorization = "Bearer $adminToken" } -Body @{
  role = "admin"
}
Show-Result "promote member role=admin" $promote
Assert-Status -Label "promote member role" -Actual $promote.Status -Expected @(200)

$oldTokenCheck = Invoke-Json -Method GET -Path "/api/me" -Headers @{ Authorization = "Bearer $memberTokenOld" }
Show-Result "old member token after promotion" $oldTokenCheck
Assert-Status -Label "old token revoked" -Actual $oldTokenCheck.Status -Expected @(401)

if ([string]$oldTokenCheck.Json.message -ne "session_revoked") {
  throw "expected old token message=session_revoked, got '$([string]$oldTokenCheck.Json.message)'"
}

Write-Host "[9/9] re-login promoted member and verify admin access"
$memberRelogin = Invoke-Json -Method POST -Path "/api/auth/login" -Body @{
  email = $MemberEmail
  password = $Password
}
Assert-Status -Label "member re-login" -Actual $memberRelogin.Status -Expected @(200)

if (-not [bool]$memberRelogin.Json.user.is_admin) {
  throw "member re-login is_admin=false after promotion"
}

$memberTokenNew = [string]$memberRelogin.Json.access_token
$memberAdminAccess = Invoke-Json -Method GET -Path "/api/admin/users/runtime-summary" -Headers @{ Authorization = "Bearer $memberTokenNew" }
Show-Result "promoted member -> /api/admin/users/runtime-summary" $memberAdminAccess
Assert-Status -Label "promoted member admin access" -Actual $memberAdminAccess.Status -Expected @(200)

Write-Host "Smoke test passed."
