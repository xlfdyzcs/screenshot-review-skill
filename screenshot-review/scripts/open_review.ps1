param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [ValidateRange(0, 65535)]
    [int]$Port = 0,
    [string]$LogDirectory,
    [switch]$Foreground,
    [switch]$Open
)

$ErrorActionPreference = 'Stop'
$artifactRoot = (Resolve-Path -LiteralPath $Root).Path
$manifestPath = Join-Path $artifactRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Saved review does not exist: $artifactRoot"
}
$expected = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$expectedJson = $expected | ConvertTo-Json -Depth 100 -Compress
$runner = Join-Path $PSScriptRoot 'review.py'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3 is required. Install it or add it to PATH.' }
$pythonPath = $python.Source
$url = $null
if ($Port -gt 0) {
    $url = "http://127.0.0.1:$Port/"
    try {
        $existing = Invoke-RestMethod -Uri ($url + 'manifest.json') -TimeoutSec 2
    } catch { $existing = $null }
    if ($existing) {
        if (($existing | ConvertTo-Json -Depth 100 -Compress) -ne $expectedJson) {
            throw "Port $Port serves another review. Choose a different -Port or omit it."
        }
        Write-Output "Review already running: $url"
        if ($Open) { Start-Process $url }
        return
    }
}
if ($Foreground) {
    & $pythonPath $runner serve --root $artifactRoot --port $Port | ForEach-Object {
        Write-Output $_
        if ($Open) {
            try { $notice = $_ | ConvertFrom-Json } catch { $notice = $null }
            if ($notice.url) { Start-Process $notice.url }
        }
    }
    exit $LASTEXITCODE
}
if (-not $LogDirectory) { $LogDirectory = Join-Path $artifactRoot '.review-server' }
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$runId = [guid]::NewGuid().ToString('N')
$stdoutPath = Join-Path $LogDirectory "$runId.out.log"
$stderrPath = Join-Path $LogDirectory "$runId.err.log"
$arguments = @('-u', ('"' + $runner + '"'), 'serve', '--root', ('"' + $artifactRoot + '"'), '--port', "$Port")
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
$ready = $false
for ($attempt = 0; $attempt -lt 50; $attempt++) {
    if ($process.HasExited) { throw "Review server failed. See $stderrPath" }
    try {
        $notice = Get-Content -LiteralPath $stdoutPath -TotalCount 1 -Encoding UTF8 | ConvertFrom-Json
        if ($notice.url) {
            $url = $notice.url
            $reply = Invoke-RestMethod -Uri ($url + 'manifest.json') -TimeoutSec 1
            if (($reply | ConvertTo-Json -Depth 100 -Compress) -eq $expectedJson) {
                $ready = $true
                break
            }
        }
    } catch { }
    Start-Sleep -Milliseconds 100
}
if (-not $ready) { throw "Review server did not become ready. See $stderrPath" }
Write-Output "Review running: $url (PID $($process.Id))"
if ($Open) { Start-Process $url }
