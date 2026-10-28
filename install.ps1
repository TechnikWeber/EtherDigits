# EtherDigits installer for Windows 10 and 11.
#
#   powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/TechnikWeber/EtherDigits/main/install.ps1 | iex"
#
# Needs Python 3.10 or newer from python.org (with "Add python.exe to PATH") or `winget install Python.Python.3.12`.
# Installs to %LOCALAPPDATA%\EtherDigits-app and starts EtherDigits at every login. No admin rights needed.
# Set $env:ETHERDIGITS_NO_SERVICE = "1" before running to skip the autostart.
$ErrorActionPreference = "Stop"

$App = Join-Path $env:LOCALAPPDATA "EtherDigits-app"
$Zip = Join-Path $env:TEMP "etherdigits-main.zip"

function Find-Python {
    foreach ($cmd in @("py -3.13", "py -3.12", "py -3.11", "py -3.10", "python")) {
        $parts = $cmd.Split(" ")
        try {
            $ok = & $parts[0] $parts[1..9] -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
            if ($ok -eq "True") { return ,$parts }
        } catch { }
    }
    throw "Python 3.10 or newer is needed: winget install Python.Python.3.12"
}

$py = Find-Python
Write-Host "Fetching EtherDigits to $App"
Invoke-WebRequest "https://github.com/TechnikWeber/EtherDigits/archive/refs/heads/main.zip" -OutFile $Zip
$tmp = Join-Path $env:TEMP "etherdigits-unpack"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $Zip -DestinationPath $tmp
New-Item -ItemType Directory -Force -Path $App | Out-Null
# Keep the virtual environment, replace the program files.
Get-ChildItem $App -Exclude ".venv" | Remove-Item -Recurse -Force
Copy-Item (Join-Path $tmp "EtherDigits-main\*") $App -Recurse -Force
Remove-Item $tmp, $Zip -Recurse -Force

Write-Host "Setting up Python packages"
$venvPy = Join-Path $App ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { & $py[0] $py[1..9] -m venv (Join-Path $App ".venv") }
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r (Join-Path $App "requirements.txt")

Push-Location $App
try {
    if ($env:ETHERDIGITS_NO_SERVICE -ne "1") { & $venvPy -m etherdigits service install }
} finally { Pop-Location }

Write-Host ""
Write-Host "Done. Open http://127.0.0.1:8472/ in a browser."
Write-Host "Command line: $venvPy -m etherdigits --help"
Write-Host "For MP3 files and the internet stream install ffmpeg: winget install Gyan.FFmpeg"
