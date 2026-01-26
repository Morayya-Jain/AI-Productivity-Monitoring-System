#!/bin/bash
#
# BrainDock macOS Build Script
#
# This script builds the macOS .app bundle using PyInstaller.
# It sets up a clean virtual environment, installs dependencies,
# and creates the final application bundle.
#
# Usage:
#   GEMINI_API_KEY=your-key ./build/build_macos.sh
#
# The built app will be in: dist/BrainDock.app
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}        BrainDock macOS Build Script${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"
echo -e "${GREEN}Project root:${NC} $PROJECT_ROOT"
echo ""

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This script is for macOS only.${NC}"
    echo "For Windows builds, use GitHub Actions or build on a Windows machine."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo -e "${GREEN}Python version:${NC} $PYTHON_VERSION"

# Check if Python 3.9+ is available
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 9 ]]; then
    echo -e "${RED}Error: Python 3.9 or higher is required.${NC}"
    exit 1
fi

# Create/activate virtual environment
VENV_DIR="$PROJECT_ROOT/.venv-build"
echo ""
echo -e "${YELLOW}Setting up virtual environment...${NC}"

if [[ -d "$VENV_DIR" ]]; then
    echo "Using existing virtual environment at $VENV_DIR"
else
    echo "Creating new virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}Virtual environment activated.${NC}"

# Upgrade pip
echo ""
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
echo -e "${GREEN}Dependencies installed.${NC}"

# Generate icons if they don't exist
echo ""
echo -e "${YELLOW}Checking icons...${NC}"
if [[ ! -f "$SCRIPT_DIR/icon.icns" ]]; then
    echo "Generating icons..."
    python3 "$SCRIPT_DIR/create_icons.py"
else
    echo -e "${GREEN}Icons already exist.${NC}"
fi

# Set bundled Gemini API key (required)
if [[ -z "$GEMINI_API_KEY" ]]; then
    echo -e "${RED}Error: GEMINI_API_KEY environment variable is required.${NC}"
    echo ""
    echo "Usage: GEMINI_API_KEY=key [OPENAI_API_KEY=key] STRIPE_SECRET_KEY=key STRIPE_PUBLISHABLE_KEY=key STRIPE_PRICE_ID=id ./build/build_macos.sh"
    exit 1
fi

echo ""
echo -e "${GREEN}Gemini API key detected - will be embedded in build.${NC}"

# Set bundled OpenAI API key (optional - for fallback/alternative)
if [[ -n "$OPENAI_API_KEY" ]]; then
    echo -e "${GREEN}OpenAI API key detected - will be embedded in build.${NC}"
else
    echo -e "${YELLOW}Note: OpenAI API key not provided (optional - Gemini is primary).${NC}"
fi

# Set bundled Stripe keys (optional but recommended)
if [[ -n "$STRIPE_SECRET_KEY" ]]; then
    echo -e "${GREEN}Stripe keys detected - will be embedded in build.${NC}"
else
    echo -e "${YELLOW}Warning: Stripe keys not provided. Payment features will be disabled.${NC}"
fi

# Generate bundled_keys.py with embedded API keys
# This module is imported by config.py to get the actual key values
echo ""
echo -e "${YELLOW}Generating bundled_keys.py with embedded keys...${NC}"

BUNDLED_KEYS="$PROJECT_ROOT/bundled_keys.py"
BUNDLED_KEYS_TEMPLATE="$PROJECT_ROOT/bundled_keys_template.py"

if [[ -f "$BUNDLED_KEYS_TEMPLATE" ]]; then
    # Copy template and replace placeholders with actual values
    cp "$BUNDLED_KEYS_TEMPLATE" "$BUNDLED_KEYS"
    
    # Use sed to replace placeholders (handle special characters in keys)
    # We use | as delimiter since keys might contain /
    sed -i '' "s|%%OPENAI_API_KEY%%|${OPENAI_API_KEY:-}|g" "$BUNDLED_KEYS"
    sed -i '' "s|%%GEMINI_API_KEY%%|${GEMINI_API_KEY}|g" "$BUNDLED_KEYS"
    sed -i '' "s|%%STRIPE_SECRET_KEY%%|${STRIPE_SECRET_KEY:-}|g" "$BUNDLED_KEYS"
    sed -i '' "s|%%STRIPE_PUBLISHABLE_KEY%%|${STRIPE_PUBLISHABLE_KEY:-}|g" "$BUNDLED_KEYS"
    sed -i '' "s|%%STRIPE_PRICE_ID%%|${STRIPE_PRICE_ID:-}|g" "$BUNDLED_KEYS"
    
    echo -e "${GREEN}bundled_keys.py generated with embedded keys.${NC}"
else
    echo -e "${RED}Error: Bundled keys template not found at $BUNDLED_KEYS_TEMPLATE${NC}"
    exit 1
fi


# Clean previous builds
echo ""
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf "$PROJECT_ROOT/dist/BrainDock"
rm -rf "$PROJECT_ROOT/dist/BrainDock.app"
rm -rf "$PROJECT_ROOT/build/BrainDock"
# Clean previously generated bundled_keys.py (will be regenerated with fresh keys)
rm -f "$PROJECT_ROOT/bundled_keys.py"
echo -e "${GREEN}Cleaned.${NC}"

# Run PyInstaller
echo ""
echo -e "${YELLOW}Running PyInstaller...${NC}"
echo "This may take a few minutes..."
echo ""

pyinstaller "$SCRIPT_DIR/braindock.spec" \
    --distpath "$PROJECT_ROOT/dist" \
    --workpath "$PROJECT_ROOT/build/pyinstaller-work" \
    --noconfirm

# Check if build succeeded
if [[ -d "$PROJECT_ROOT/dist/BrainDock.app" ]]; then
    echo ""
    echo -e "${GREEN}=================================================${NC}"
    echo -e "${GREEN}        App Bundle Created!${NC}"
    echo -e "${GREEN}=================================================${NC}"
    echo ""
    echo -e "App bundle: ${BLUE}$PROJECT_ROOT/dist/BrainDock.app${NC}"
    
    # Show app size
    APP_SIZE=$(du -sh "$PROJECT_ROOT/dist/BrainDock.app" | cut -f1)
    echo -e "App size: ${YELLOW}$APP_SIZE${NC}"
    echo ""
    
    # Create DMG
    echo -e "${YELLOW}Creating DMG installer...${NC}"
    
    # Version for filename
    VERSION="1.0.0"
    DMG_NAME="BrainDock-${VERSION}-macOS.dmg"
    DMG_PATH="$PROJECT_ROOT/dist/$DMG_NAME"
    
    # Clean up any existing DMG
    rm -f "$DMG_PATH"
    
    # Generate DMG background image with arrow
    echo -e "${YELLOW}Generating DMG background...${NC}"
    python3 "$SCRIPT_DIR/create_dmg_background.py"
    DMG_BACKGROUND="$SCRIPT_DIR/dmg_background.png"
    
    if [[ ! -f "$DMG_BACKGROUND" ]]; then
        echo -e "${RED}Error: Failed to generate DMG background${NC}"
        exit 1
    fi
    echo -e "${GREEN}DMG background generated.${NC}"
    
    # Check if create-dmg is installed
    if ! command -v create-dmg &> /dev/null; then
        echo ""
        echo -e "${YELLOW}Installing create-dmg via Homebrew...${NC}"
        if command -v brew &> /dev/null; then
            brew install create-dmg
        else
            echo -e "${RED}Error: Homebrew not found. Please install create-dmg manually:${NC}"
            echo "  brew install create-dmg"
            echo ""
            echo "Or install Homebrew first: https://brew.sh"
            exit 1
        fi
    fi
    
    echo -e "${YELLOW}Creating styled DMG with create-dmg...${NC}"
    
    # Create the DMG using create-dmg with professional styling
    # Icon positions: BrainDock.app at (180, 190), Applications at (480, 190)
    # These match the background image layout
    create-dmg \
        --volname "BrainDock" \
        --volicon "$SCRIPT_DIR/icon.icns" \
        --background "$DMG_BACKGROUND" \
        --window-pos 200 120 \
        --window-size 660 400 \
        --icon-size 100 \
        --icon "BrainDock.app" 180 190 \
        --hide-extension "BrainDock.app" \
        --app-drop-link 480 190 \
        --no-internet-enable \
        "$DMG_PATH" \
        "$PROJECT_ROOT/dist/BrainDock.app"
    
    # Check if DMG was created
    if [[ -f "$DMG_PATH" ]]; then
        DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
        echo ""
        echo -e "${GREEN}=================================================${NC}"
        echo -e "${GREEN}        Build Successful!${NC}"
        echo -e "${GREEN}=================================================${NC}"
        echo ""
        echo -e "DMG installer: ${BLUE}$DMG_PATH${NC}"
        echo -e "DMG size: ${YELLOW}$DMG_SIZE${NC}"
        echo ""
        echo -e "${YELLOW}To test:${NC}"
        echo "  open \"$DMG_PATH\""
        echo ""
        echo -e "${YELLOW}To distribute:${NC}"
        echo "  Upload $DMG_NAME to GitHub Releases"
        echo ""
        echo -e "${YELLOW}User experience:${NC}"
        echo "  1. User downloads $DMG_NAME"
        echo "  2. Double-clicks to mount"
        echo "  3. Sees BrainDock icon with arrow pointing to Applications"
        echo "  4. Drags BrainDock to Applications folder"
        echo "  5. Ejects the DMG"
        echo "  6. Launches from Applications (right-click > Open first time)"
    else
        echo -e "${RED}Error: Failed to create DMG${NC}"
        exit 1
    fi
    
else
    echo ""
    echo -e "${RED}=================================================${NC}"
    echo -e "${RED}        Build Failed!${NC}"
    echo -e "${RED}=================================================${NC}"
    echo ""
    echo "Check the output above for errors."
    exit 1
fi

# Deactivate virtual environment
deactivate

echo ""
echo -e "${GREEN}Done!${NC}"
