$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Version = "2.3.0"
$Venv = Join-Path $PSScriptRoot ".venv-build"
$ReleaseRoot = Join-Path $PSScriptRoot "release"
$ReleaseDir = Join-Path $ReleaseRoot "BooruGet-$Version-win64"
$Icon = Join-Path $PSScriptRoot "assets\booruget.ico"

Write-Host "== BooruGet $Version Windows Build ==" -ForegroundColor Cyan

if (-not (Test-Path $Venv)) {
    py -3 -m venv $Venv
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-dev.txt

Write-Host "Running tests..." -ForegroundColor Cyan
& $Python -m unittest discover -s tests -v

Write-Host "Generating Windows icon..." -ForegroundColor Cyan
& $Python -c "from PIL import Image; Image.open(r'assets/booruget.png').save(r'assets/booruget.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

Remove-Item -Recurse -Force "build", "dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $ReleaseDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $ReleaseDir | Out-Null

Write-Host "Building GUI executable..." -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "BooruGet" `
    --version-file "version_info.txt" `
    --icon $Icon `
    --add-data "assets;assets" `
    "BooruGet-GUI.py"

Write-Host "Building CLI executable..." -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean --onefile --console `
    --name "BooruGet-CLI" `
    --version-file "version_info.txt" `
    --icon $Icon `
    "BooruGet.py"

Copy-Item "dist\BooruGet.exe" $ReleaseDir
Copy-Item "dist\BooruGet-CLI.exe" $ReleaseDir
Copy-Item "README.md" $ReleaseDir
Copy-Item "CHANGELOG.md" $ReleaseDir
Copy-Item "NOTICE.md" $ReleaseDir
Copy-Item "booruget.ini.example" $ReleaseDir

$Zip = Join-Path $ReleaseRoot "BooruGet-$Version-win64.zip"
Remove-Item $Zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$ReleaseDir\*" -DestinationPath $Zip -CompressionLevel Optimal

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  $ReleaseDir\BooruGet.exe"
Write-Host "  $ReleaseDir\BooruGet-CLI.exe"
Write-Host "  $Zip"
