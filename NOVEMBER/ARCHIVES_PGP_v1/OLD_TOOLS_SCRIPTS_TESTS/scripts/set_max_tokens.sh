#!/bin/bash
# Script to permanently set CLAUDE_CODE_MAX_OUTPUT_TOKENS in .venv

VENV_PATH="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1/.venv"
ACTIVATE_SCRIPT="${VENV_PATH}/bin/activate"
MAX_TOKENS=200000

echo "🔧 Setting CLAUDE_CODE_MAX_OUTPUT_TOKENS=${MAX_TOKENS} in .venv..."

# Check if .venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ ERROR: .venv not found at ${VENV_PATH}"
    exit 1
fi

# Check if activate script exists
if [ ! -f "$ACTIVATE_SCRIPT" ]; then
    echo "❌ ERROR: activate script not found at ${ACTIVATE_SCRIPT}"
    exit 1
fi

# Check if the variable is already set in activate script
if grep -q "export CLAUDE_CODE_MAX_OUTPUT_TOKENS" "$ACTIVATE_SCRIPT"; then
    echo "⚠️  CLAUDE_CODE_MAX_OUTPUT_TOKENS already set in activate script"
    echo "📝 Updating existing value to ${MAX_TOKENS}..."

    # Update existing value (works on both Linux and macOS)
    sed -i.bak "s/export CLAUDE_CODE_MAX_OUTPUT_TOKENS=.*/export CLAUDE_CODE_MAX_OUTPUT_TOKENS=${MAX_TOKENS}/" "$ACTIVATE_SCRIPT"

    echo "✅ Updated CLAUDE_CODE_MAX_OUTPUT_TOKENS=${MAX_TOKENS}"
else
    echo "📝 Adding CLAUDE_CODE_MAX_OUTPUT_TOKENS to activate script..."

    # Add the export statement before the final 'unset' commands
    cat >> "$ACTIVATE_SCRIPT" << EOF

# Set Claude Code max output tokens (added by set_max_tokens.sh)
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=${MAX_TOKENS}
EOF

    echo "✅ Added CLAUDE_CODE_MAX_OUTPUT_TOKENS=${MAX_TOKENS}"
fi

# Create backup
cp "$ACTIVATE_SCRIPT" "${ACTIVATE_SCRIPT}.backup-$(date +%Y%m%d-%H%M%S)"

echo ""
echo "✅ Configuration complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Deactivate current venv if active: deactivate"
echo "   2. Reactivate venv: source .venv/bin/activate"
echo "   3. Verify: echo \$CLAUDE_CODE_MAX_OUTPUT_TOKENS"
echo ""
echo "💡 The environment variable will now be set automatically every time you activate this venv!"
