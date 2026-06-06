$ErrorActionPreference = "Stop"

Write-Host "Installing free local OCR dependencies..." -ForegroundColor Cyan

npm install

$tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $tesseract -and -not (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) {
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if ($winget) {
    winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
  } else {
    Write-Host "Skipping native Tesseract. Tesseract.js will be used through Node instead." -ForegroundColor Yellow
  }
}

python -m pip install -r backend\requirements.txt

Write-Host "Free OCR setup complete. Restart the app with npm run start:local." -ForegroundColor Green
