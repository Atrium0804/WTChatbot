<#
.SYNOPSIS
    Deploy de WTChatbot naar de Synology NAS (standaard beheerder@famstieltjes.nl, zie -NasHost) via scp/ssh.

.DESCRIPTION
    Kopieert naar /volume1/docker/wtchatbot/ op de NAS:
      - app/docker-compose.nas.yml uit deze repo  -> docker-compose.yaml (NAS-variant, via NPM)
      - de app-source uit app/ van deze repo      -> app/ (build-context; de NAS buildt de image zelf)
        (losse bestanden + de mappen static/ en prompts/; in totaal 5 ssh/scp-verbindingen)

    Usage:
      .\scripts\deploy-nas.ps1              # dry-run: toon wat WOULD worden gekopieerd (veilig, default)
      .\scripts\deploy-nas.ps1 -Apply       # echt scp-en naar de NAS
      .\scripts\deploy-nas.ps1 -Apply -Up   # scp, daarna `docker compose up -d --build`
                                            # (de NAS buildt zelf; kan een paar minuten duren)
      .\scripts\deploy-nas.ps1 -Apply -NasPort 2222   # bij afwijkende ssh-poort (default 22)
      .\scripts\deploy-nas.ps1 -Apply -NasHost beheerder@nas.fritz.box   # andere ssh-target (default beheerder@famstieltjes.nl)

    Secrets (.env) en data (data/) worden NOOIT gekopieerd — die leven alleen op de NAS.
    .env maak je handmatig aan op de NAS: MISTRAL_API_KEY + MISTRAL_AGENT_ID (zie app/README.md).
    Reverse proxy + HTTPS regelt NPM op de NAS: proxy host chat.famstieltjes.nl -> http://wtchatbot:8000.
#>

[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Up,
    [int]$NasPort = 22,   # ssh-poort van de NAS (default 22)
    [string]$NasHost = 'beheerder@nas.fritz.box'   # ssh-target (user@host)
)

$ErrorActionPreference = 'Stop'

# $NasHost komt uit -NasHost --nas-port 271
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

$RemoteApp = "$NasRoot/$Service/app"

# App-source uit app/ wordt de build-context op de NAS: alle losse bestanden
# plus de mappen die de app runtime nodig heeft. tests/, __pycache__/ en data/
# gaan niet mee; .env wordt expliciet uitgesloten.
$AppFiles = Get-ChildItem -Path $AppSrc -File -Force |
    Where-Object { $_.Name -ne '.env' } |
    ForEach-Object { $_.FullName }
$AppDirs = @('static', 'prompts') | ForEach-Object { Join-Path $AppSrc $_ }

# Niet-interactief (BatchMode, -n: geen stdin van de console) en met timeouts,
# zodat een haperende verbinding afbreekt in plaats van eindeloos te hangen.
$SshOpts = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=4')

function Invoke-Remote([string]$Command, [string]$What) {
    ssh -n @SshOpts -p $NasPort $NasHost $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" }
}

function Send-Scp([string[]]$Sources, [string]$Remote, [switch]$Recurse) {
    # -O forces the legacy SCP protocol, which uses the real shell path (SFTP is chrooted differently).
    # scp gebruikt -P (hoofdletter) voor de poort; ssh gebruikt -p.
    $scpArgs = @('-O') + $SshOpts + @('-P', $NasPort)
    if ($Recurse) { $scpArgs += '-r' }
    scp @scpArgs @Sources "${NasHost}:${Remote}"
    if ($LASTEXITCODE -ne 0) { throw "scp failed for $($Sources -join ', ') (exit $LASTEXITCODE)" }
}

$Compose = Join-Path $AppSrc 'docker-compose.nas.yml'
if ($Apply) {
    Invoke-Remote "mkdir -p `"$RemoteApp`"" 'mkdir'
    Send-Scp @($Compose) "$NasRoot/$Service/docker-compose.yaml"
    Write-Host "  sent: app/docker-compose.nas.yml -> $NasRoot/$Service/docker-compose.yaml"
    Send-Scp $AppFiles "$RemoteApp/"
    Write-Host "  sent: $($AppFiles.Count) bestanden uit app/ -> $RemoteApp/"
    Send-Scp $AppDirs "$RemoteApp/" -Recurse
    Write-Host "  sent: app/static, app/prompts -> $RemoteApp/"
} else {
    Write-Host "  would send: app/docker-compose.nas.yml -> $NasRoot/$Service/docker-compose.yaml"
    foreach ($f in $AppFiles) { Write-Host "  would send: app/$(Split-Path -Leaf $f) -> $RemoteApp/" }
    Write-Host "  would send: app/static, app/prompts -> $RemoteApp/"
}

if ($Apply -and $Up) {
    Write-Host ">>> Building + starting $Service on the NAS (build op de NAS kan een paar minuten duren)..."
    Invoke-Remote "cd $NasRoot/$Service && $Docker compose up -d --build" 'compose up'
}

Write-Host "Done."
