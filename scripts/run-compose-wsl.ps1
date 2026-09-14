param([string]$Distro = "Ubuntu-24.04-OMX")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
# WSL's service processes alone may not keep the distribution alive.
# Keep this script/terminal running during the demo. Ctrl+C exits the keepalive, not the database.
$linuxPath = (& wsl -d $Distro -- wslpath -a $projectRoot).Trim()
if ($LASTEXITCODE -ne 0) { throw "Cannot resolve WSL project path." }
& wsl -d $Distro -u root --cd $linuxPath --exec docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "Compose startup failed." }
& wsl -d $Distro --exec sleep infinity
