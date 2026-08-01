$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run these commands first:" -ForegroundColor Red
    Write-Host "  py -m venv .venv"
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  pip install -r requirements.txt"
    exit 1
}

$wifiAddress = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.InterfaceAlias -match "Wi-Fi|Wireless"
    } |
    Select-Object -First 1 -ExpandProperty IPAddress

Write-Host ""
Write-Host "Starting Atlas Dashboard..." -ForegroundColor Cyan
Write-Host "Laptop: http://127.0.0.1:8000" -ForegroundColor Green

if ($wifiAddress) {
    Write-Host "Phone:  http://$wifiAddress`:8000" -ForegroundColor Green
    Write-Host "Your phone must be connected to the same Wi-Fi network." -ForegroundColor DarkGray
} else {
    Write-Host "Could not automatically find the Wi-Fi IPv4 address." -ForegroundColor Yellow
    Write-Host "Run ipconfig and open http://YOUR_IPV4_ADDRESS:8000 on the phone."
}

Write-Host ""
& ".\.venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8000
