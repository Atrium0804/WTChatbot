<#
.SYNOPSIS
    Deploy de WTChatbot naar de Synology NAS (nas.fritz.box) via scp/ssh.

.DESCRIPTION
    Kopieert naar /volume1/docker/wtchatbot/ op de NAS:
      - app/docker-compose.nas.yml uit deze repo  -> docker-compose.yaml (NAS-variant, via NPM)
      - de app-source uit app/ van deze repo      -> app/ (build-context; de NAS buildt de image zelf)

    Usage:
      .\scripts\deploy-nas.ps1              # dry-run: toon wat WOULD worden gekopieerd (veilig, default)
      .\scripts\deploy-nas.ps1 -Apply       # echt scp-en naar de NAS
      .\scripts\deploy-nas.ps1 -Apply -Up   # scp, daarna `docker compose up -d --build`
                                            # (de NAS buildt zelf; kan een paar minuten duren)

    Secrets (.env) en data (data/) worden NOOIT gekopieerd — die leven alleen op de NAS.
    .env maak je handmatig aan op de NAS: MISTRAL_API_KEY + MISTRAL_AGENT_ID (zie app/README.md).
    Reverse proxy + HTTPS regelt NPM op de NAS: proxy host chat.famstieltjes.nl -> http://wtchatbot:8000.
#>

[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Up
)

$ErrorActionPreference = 'Stop'

$NasHost = 'beheerder@nas.fritz.box'
$NasRoot = '/volume1/docker'          # shell path op de NAS (NOT de /docker sftp chroot path)
$Docker  = 'sudo -n /usr/local/bin/docker'
$Service = 'wtchatbot'

$RepoDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)  # repo-root (script staat in scripts/)
$AppSrc  = Join-Path $RepoDir 'app'
Set-Location $RepoDir

if (-not (Test-Path (Join-Path $AppSrc 'main.py'))) {
    throw "app/ niet gevonden in '$AppSrc' — draai dit script vanuit de WTChatbot-repo."
}

if (-not $Apply) {
    Write-Host ">>> DRY RUN (use -Apply to write). <<<"
}

# File-map: repo-relative local pad -> remote pad onder $NasRoot.
$Files = @(
    @{ Local = 'app/docker-compose.nas.yml'; Remote = "$NasRoot/$Service/docker-compose.yaml" }
)

# App-source uit app/ wordt de build-context op de NAS.
# tests/, __pycache__/ en data/ zijn mappen en vallen af (-File); .env wordt expliciet uitgesloten.
$AppFiles = Get-ChildItem -Path $AppSrc -File -Force |
    Where-Object { $_.Name -ne '.env' } |
    ForEach-Object { $_.Name }
foreach ($f in $AppFiles) {
    $Files += @{ Local = "app/$f"; Remote = "$NasRoot/$Service/app/$f" }
}

function Send-One([string]$Local, [string]$Remote) {
    $remoteDir = $Remote.Substring(0, $Remote.LastIndexOf('/'))
    if ($Apply) {
        ssh $NasHost "mkdir -p `"$remoteDir`""
        # -O forces the legacy SCP protocol, which uses the real shell path (SFTP is chrooted differently).
        scp -O (Join-Path $RepoDir $Local) "${NasHost}:${Remote}"
        if ($LASTEXITCODE -ne 0) { throw "scp failed for $Local (exit $LASTEXITCODE)" }
        Write-Host "  sent: $Local -> $Remote"
    } else {
        Write-Host "  would send: $Local -> $Remote"
    }
}

foreach ($f in $Files) {
    Send-One $f.Local $f.Remote
}

# static/ (chat-UI) als hele map kopiëren.
if ($Apply) {
    ssh $NasHost "mkdir -p `"$NasRoot/$Service/app`""
    scp -O -r (Join-Path $AppSrc 'static') "${NasHost}:${NasRoot}/${Service}/app/"
    if ($LASTEXITCODE -ne 0) { throw "scp failed for app/static (exit $LASTEXITCODE)" }
    Write-Host "  sent: app/static -> $NasRoot/$Service/app/static"
} else {
    Write-Host "  would send: app/static -> $NasRoot/$Service/app/static"
}

if ($Apply -and $Up) {
    Write-Host ">>> Building + starting $Service on the NAS (build op de NAS kan een paar minuten duren)..."
    ssh $NasHost "cd $NasRoot/$Service && $Docker compose up -d --build"
    if ($LASTEXITCODE -ne 0) { throw "compose up failed for $Service (exit $LASTEXITCODE)" }
}

Write-Host "Done."
