#
# BrainDock Windows Build Script (PowerShell)
#
# This script builds the Windows executable using PyInstaller.
# It sets up dependencies and creates the final application.
#
# Usage:
#   $env:GEMINI_API_KEY="your-key"
#   $env:STRIPE_SECRET_KEY="your-key"
#   $env:STRIPE_PUBLISHABLE_KEY="your-key"
#   $env:STRIPE_PRICE_ID="your-id"
#   .\build\build_windows.ps1
#
# Or in one line:
#   $env:GEMINI_API_KEY="key"; $env:STRIPE_SECRET_KEY="key"; $env:STRIPE_PUBLISHABLE_KEY="key"; $env:STRIPE_PRICE_ID="id"; .\build\build_windows.ps1
#
# The built app will be in: dist\BrainDock\
#

$ErrorActionPreference = "Stop"

# Script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "=================================================" -ForegroundColor Blue
Write-Host "        BrainDock Windows Build Script" -ForegroundColor Blue
Write-Host "=================================================" -ForegroundColor Blue
Write-Host ""

# Change to project root
Set-Location $ProjectRoot
Write-Host "Project root: $ProjectRoot" -ForegroundColor Green
Write-Host ""

# Check Python version
try {
    $PythonVersion = python --version 2>&1
    Write-Host "Python version: $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python not found. Please install Python 3.9 or higher." -ForegroundColor Red
    exit 1
}

# Check if GEMINI_API_KEY is set (required)
if (-not $env:GEMINI_API_KEY) {
    Write-Host "Error: GEMINI_API_KEY environment variable is required." -ForegroundColor Red
    Write-Host ""
    Write-Host 'Usage: $env:GEMINI_API_KEY="key"; $env:STRIPE_SECRET_KEY="key"; .\build\build_windows.ps1'
    exit 1
}

Write-Host ""
Write-Host "Gemini API key detected - will be embedded in build." -ForegroundColor Green

# Check OpenAI key (optional)
if ($env:OPENAI_API_KEY) {
    Write-Host "OpenAI API key detected - will be embedded in build." -ForegroundColor Green
} else {
    Write-Host "Note: OpenAI API key not provided (optional - Gemini is primary)." -ForegroundColor Yellow
}

# Check Stripe keys (optional but recommended)
if ($env:STRIPE_SECRET_KEY) {
    Write-Host "Stripe keys detected - will be embedded in build." -ForegroundColor Green
} else {
    Write-Host "Warning: Stripe keys not provided. Payment features will be disabled." -ForegroundColor Yellow
}

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
Write-Host "Dependencies installed." -ForegroundColor Green

# Generate icons if they don't exist
Write-Host ""
Write-Host "Checking icons..." -ForegroundColor Yellow
if (-not (Test-Path "$ScriptDir\icon.ico")) {
    Write-Host "Generating icons..."
    python "$ScriptDir\create_icons.py"
} else {
    Write-Host "Icons already exist." -ForegroundColor Green
}

# Clean previous builds
Write-Host ""
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "$ProjectRoot\dist\BrainDock") {
    Remove-Item -Recurse -Force "$ProjectRoot\dist\BrainDock"
}
if (Test-Path "$ProjectRoot\build\BrainDock") {
    Remove-Item -Recurse -Force "$ProjectRoot\build\BrainDock"
}
# Clean previously generated bundled_keys.py (will be regenerated with fresh keys)
if (Test-Path "$ProjectRoot\bundled_keys.py") {
    Remove-Item -Force "$ProjectRoot\bundled_keys.py"
}
Write-Host "Cleaned." -ForegroundColor Green

# Generate bundled_keys.py with embedded API keys
Write-Host ""
Write-Host "Generating bundled_keys.py with embedded keys..." -ForegroundColor Yellow

$BundledKeys = "$ProjectRoot\bundled_keys.py"
$BundledKeysTemplate = "$ProjectRoot\bundled_keys_template.py"

if (Test-Path $BundledKeysTemplate) {
    # Read template
    $content = Get-Content $BundledKeysTemplate -Raw
    
    # Replace placeholders with actual values (handle special regex characters)
    $content = $content -replace '%%OPENAI_API_KEY%%', ($env:OPENAI_API_KEY -replace '\$', '$$$$')
    $content = $content -replace '%%GEMINI_API_KEY%%', ($env:GEMINI_API_KEY -replace '\$', '$$$$')
    $content = $content -replace '%%STRIPE_SECRET_KEY%%', ($env:STRIPE_SECRET_KEY -replace '\$', '$$$$')
    $content = $content -replace '%%STRIPE_PUBLISHABLE_KEY%%', ($env:STRIPE_PUBLISHABLE_KEY -replace '\$', '$$$$')
    $content = $content -replace '%%STRIPE_PRICE_ID%%', ($env:STRIPE_PRICE_ID -replace '\$', '$$$$')
    
    # Write bundled_keys.py (UTF-8 without BOM for Python compatibility)
    [System.IO.File]::WriteAllText($BundledKeys, $content, [System.Text.UTF8Encoding]::new($false))
    
    Write-Host "bundled_keys.py generated with embedded keys." -ForegroundColor Green
} else {
    Write-Host "Error: Bundled keys template not found at $BundledKeysTemplate" -ForegroundColor Red
    exit 1
}

# Run PyInstaller
Write-Host ""
Write-Host "Running PyInstaller..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..."
Write-Host ""

pyinstaller "$ScriptDir\braindock.spec" `
    --distpath "$ProjectRoot\dist" `
    --workpath "$ProjectRoot\build\pyinstaller-work" `
    --noconfirm

# Check if build succeeded
if (Test-Path "$ProjectRoot\dist\BrainDock") {
    Write-Host ""
    Write-Host "=================================================" -ForegroundColor Green
    Write-Host "        Build Successful!" -ForegroundColor Green
    Write-Host "=================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "App folder: $ProjectRoot\dist\BrainDock" -ForegroundColor Blue
    Write-Host ""
    
    # Create ZIP archive
    Write-Host "Creating ZIP archive..." -ForegroundColor Yellow
    
    $Version = "1.0.0"
    $ZipName = "BrainDock-$Version-Windows.zip"
    $ZipPath = "$ProjectRoot\dist\$ZipName"
    
    # Remove existing ZIP if present
    if (Test-Path $ZipPath) {
        Remove-Item -Force $ZipPath
    }
    
    # Create ZIP
    Compress-Archive -Path "$ProjectRoot\dist\BrainDock" -DestinationPath $ZipPath
    
    if (Test-Path $ZipPath) {
        $ZipSize = (Get-Item $ZipPath).Length / 1MB
        Write-Host ""
        Write-Host "ZIP archive: $ZipPath" -ForegroundColor Blue
        Write-Host ("ZIP size: {0:N1} MB" -f $ZipSize) -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To test:" -ForegroundColor Yellow
        Write-Host "  Expand-Archive -Path `"$ZipPath`" -DestinationPath `"$ProjectRoot\dist\test`""
        Write-Host "  & `"$ProjectRoot\dist\test\BrainDock\BrainDock.exe`""
        Write-Host ""
        Write-Host "To distribute:" -ForegroundColor Yellow
        Write-Host "  Upload $ZipName to GitHub Releases"
    } else {
        Write-Host "Warning: Failed to create ZIP archive" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "=================================================" -ForegroundColor Red
    Write-Host "        Build Failed!" -ForegroundColor Red
    Write-Host "=================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the output above for errors."
    exit 1
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
