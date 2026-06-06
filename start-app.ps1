$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPort = 8000
$FrontendPort = 5174
$BackendLog = Join-Path $Root "backend.log"
$BackendErrLog = Join-Path $Root "backend-error.log"
$FrontendLog = Join-Path $Root "frontend.log"
$FrontendErrLog = Join-Path $Root "frontend-error.log"

function Stop-PortProcess {
  param([int]$Port)
  $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
  $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($processId in $processIds) {
    if ($processId -and $processId -ne $PID) {
      Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
  }
}

function Wait-Http {
  param(
    [string]$Url,
    [int]$Seconds = 20
  )
  $deadline = (Get-Date).AddSeconds($Seconds)
  do {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 600
    }
  } while ((Get-Date) -lt $deadline)
  return $false
}

function Start-HiddenProcess {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$StdoutPath,
    [string]$StderrPath
  )
  function Quote-Arg {
    param([string]$Value)
    if ($Value -match '[\s"]') {
      return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
  }
  $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $startInfo.FileName = $FilePath
  $startInfo.Arguments = ($ArgumentList | ForEach-Object { Quote-Arg $_ }) -join " "
  $startInfo.WorkingDirectory = $WorkingDirectory
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $startInfo
  [void]$process.Start()
  $process.BeginOutputReadLine()
  $process.BeginErrorReadLine()
  Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action {
    if ($EventArgs.Data) { Add-Content -LiteralPath $Event.MessageData.StdoutPath -Value $EventArgs.Data }
  } -MessageData @{ StdoutPath = $StdoutPath } | Out-Null
  Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action {
    if ($EventArgs.Data) { Add-Content -LiteralPath $Event.MessageData.StderrPath -Value $EventArgs.Data }
  } -MessageData @{ StderrPath = $StderrPath } | Out-Null
  return $process
}

Set-Location $Root

Write-Host "Restarting Nepal Form Autofill locally..." -ForegroundColor Cyan
Stop-PortProcess -Port $BackendPort
Stop-PortProcess -Port $FrontendPort
Start-Sleep -Seconds 1

if (-not (Test-Path (Join-Path $Root "node_modules"))) {
  Write-Host "Installing frontend packages..." -ForegroundColor Yellow
  npm install
}

Write-Host "Starting backend on http://127.0.0.1:$BackendPort" -ForegroundColor Cyan
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe -and (Test-Path "C:\Users\user\python.exe")) {
  $pythonExe = "C:\Users\user\python.exe"
}
if (-not $pythonExe) {
  Write-Host "Python was not found on PATH." -ForegroundColor Red
  exit 1
}
Start-HiddenProcess -FilePath $pythonExe -ArgumentList @(
  "-m", "uvicorn", "backend.main:app",
  "--host", "127.0.0.1",
  "--port", "$BackendPort"
) -WorkingDirectory $Root -StdoutPath $BackendLog -StderrPath $BackendErrLog | Out-Null

Write-Host "Starting frontend on http://127.0.0.1:$FrontendPort" -ForegroundColor Cyan
$npmExe = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmExe) {
  Write-Host "npm.cmd was not found on PATH." -ForegroundColor Red
  exit 1
}
Start-HiddenProcess -FilePath $npmExe -ArgumentList @(
  "run", "dev", "--",
  "--host", "127.0.0.1",
  "--port", "$FrontendPort",
  "--strictPort"
) -WorkingDirectory $Root -StdoutPath $FrontendLog -StderrPath $FrontendErrLog | Out-Null

$backendOk = Wait-Http -Url "http://127.0.0.1:$BackendPort/api/health"
$frontendOk = Wait-Http -Url "http://127.0.0.1:$FrontendPort"

if (-not $backendOk) {
  Write-Host "Backend did not start. See $BackendLog" -ForegroundColor Red
  exit 1
}

if (-not $frontendOk) {
  Write-Host "Frontend did not start. See $FrontendLog" -ForegroundColor Red
  exit 1
}

$Url = "http://127.0.0.1:$FrontendPort"
Write-Host "Ready: $Url" -ForegroundColor Green
try {
  Start-Process $Url
} catch {
  Write-Host "Open $Url in your browser." -ForegroundColor Yellow
}
