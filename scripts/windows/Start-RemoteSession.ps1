[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Server,

    [string]$PairingCode,

    [string]$ClientPath,

    [string]$ClientUrl,

    [string]$ExpectedSha256
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-RscDownload {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    Write-Host 'Downloading the temporary RemoteSessionControl client (~64 MB)...'
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & $curl.Source --fail --location --retry 3 --retry-delay 2 --connect-timeout 15 --progress-bar --output $Destination $Url
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
            throw "Client download failed (curl exit code $LASTEXITCODE)."
        }
        return
    }

    Write-Host 'curl.exe was not found; falling back to Invoke-WebRequest.'
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

function Resolve-RscClient {
    param(
        [string]$Path,
        [string]$Url,
        [string]$Sha256
    )

    if ($Path) {
        $resolved = (Resolve-Path -LiteralPath $Path).Path
    }
    elseif ($Url) {
        if (-not $Url.StartsWith('https://', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'ClientUrl must use HTTPS.'
        }

        $workDir = Join-Path $env:TEMP 'RemoteSessionControl'
        New-Item -ItemType Directory -Force -Path $workDir | Out-Null
        $resolved = Join-Path $workDir 'RemoteSessionControl-Client.exe'

        $download = $true
        if ($Sha256 -and (Test-Path -LiteralPath $resolved)) {
            $actual = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
            $expected = $Sha256.Trim().ToLowerInvariant()
            if ($actual -eq $expected) {
                $download = $false
                Write-Host 'Using the already downloaded verified client.'
            }
        }

        if ($download) {
            Invoke-RscDownload -Url $Url -Destination $resolved
        }
    }
    else {
        throw 'Provide either -ClientPath or -ClientUrl.'
    }

    if ($Sha256) {
        $actual = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
        $expected = $Sha256.Trim().ToLowerInvariant()
        if ($actual -ne $expected) {
            Remove-Item -LiteralPath $resolved -Force -ErrorAction SilentlyContinue
            throw "Client SHA-256 verification failed. Expected $expected but got $actual."
        }
        Write-Host 'Client SHA-256 verified.'
    }

    return $resolved
}

if (-not $Server.StartsWith('https://', [System.StringComparison]::OrdinalIgnoreCase) -and
    -not $Server.StartsWith('http://127.0.0.1', [System.StringComparison]::OrdinalIgnoreCase) -and
    -not $Server.StartsWith('http://localhost', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Use HTTPS for remote servers. Plain HTTP is accepted only for localhost testing.'
}

if (-not $PairingCode) {
    $PairingCode = Read-Host 'Pairing code'
}
$PairingCode = $PairingCode.Trim().ToUpperInvariant()
if (-not $PairingCode) {
    throw 'Pairing code is required.'
}

$client = Resolve-RscClient -Path $ClientPath -Url $ClientUrl -Sha256 $ExpectedSha256

Write-Host ''
Write-Host 'Starting a visible, temporary RemoteSessionControl session client.'
Write-Host 'The client will still ask for local consent before the session is activated.'
Write-Host 'No service, startup entry, scheduled task, or permanent background persistence is installed.'
Write-Host ''

$arguments = @('--server', $Server, '--pairing-code', $PairingCode)
$process = Start-Process -FilePath $client -ArgumentList $arguments -PassThru

# Do not retain the one-time pairing code in this launcher longer than needed.
$PairingCode = $null

Write-Host "Client started (PID $($process.Id)). You may close this PowerShell window."
Write-Host 'The separate client process remains visible and is still bounded by the server-side session expiry.'
