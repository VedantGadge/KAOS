#!/bin/bash
set -e
cd "$(dirname "$0")/.."
PREP_DIR="$(pwd)"
BUILD_DIR="$PREP_DIR/.build"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

for md in 00_README 01_ARCHITECTURE_AND_COMPONENTS 02_INTERVIEW_QUESTIONS; do
  echo "→ Converting $md.md ..."
  # 1. Markdown -> HTML body (GitHub-flavored)
  npx -y marked --gfm "$PREP_DIR/$md.md" > "$BUILD_DIR/$md.body.html"
  # 2. Wrap with styled template
  cat "$BUILD_DIR/template_head.html" "$BUILD_DIR/$md.body.html" > "$BUILD_DIR/$md.full.html"
  printf '\n</body></html>\n' >> "$BUILD_DIR/$md.full.html"
  # 3. HTML -> PDF via headless Chrome
  "$CHROME" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PREP_DIR/$md.pdf" \
    "file://$BUILD_DIR/$md.full.html" 2>/dev/null
  echo "  ✓ $md.pdf"
done
echo "Done."
