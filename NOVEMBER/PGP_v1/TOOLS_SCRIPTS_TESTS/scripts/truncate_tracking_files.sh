#!/bin/bash
################################################################################
# Truncate Tracking Files (PROGRESS.md, DECISIONS.md, BUGS.md)
# Purpose: Move older entries to archive files to maintain token limits
# Target: Keep files at 35-40% of token window (~8,750-10,000 tokens per file)
# Date: 2025-11-18
################################################################################

set -e  # Exit on error

# Configuration
BASE_DIR="/mnt/c/Users/YossTech/Desktop/2025/TelegramFunnel/NOVEMBER/PGP_v1"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BASE_DIR}/TOOLS_SCRIPTS_TESTS/logs/truncate_backup_${TIMESTAMP}"

echo "🔧 Truncation Tool for Tracking Files"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "📍 Base Directory: ${BASE_DIR}"
echo "📦 Backup Directory: ${BACKUP_DIR}"
echo ""

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Function to backup file
backup_file() {
    local file_path=$1
    local file_name=$(basename "$file_path")
    cp "$file_path" "${BACKUP_DIR}/${file_name}.backup"
    echo "✅ Backed up: ${file_name}"
}

# Function to count lines
count_lines() {
    local file_path=$1
    if [ -f "$file_path" ]; then
        wc -l < "$file_path"
    else
        echo "0"
    fi
}

echo "📊 Current File Statistics:"
echo "───────────────────────────────────────────────────────────────────"
PROGRESS_LINES=$(count_lines "${BASE_DIR}/PROGRESS.md")
DECISIONS_LINES=$(count_lines "${BASE_DIR}/DECISIONS.md")
BUGS_LINES=$(count_lines "${BASE_DIR}/BUGS.md")

echo "   PROGRESS.md:  ${PROGRESS_LINES} lines"
echo "   DECISIONS.md: ${DECISIONS_LINES} lines"
echo "   BUGS.md:      ${BUGS_LINES} lines"
echo ""

# Backup all files before truncation
echo "💾 Creating backups..."
backup_file "${BASE_DIR}/PROGRESS.md"
backup_file "${BASE_DIR}/DECISIONS.md"
backup_file "${BASE_DIR}/BUGS.md"
echo ""

################################################################################
# PROGRESS.md Truncation
# Keep entries from 2025-11-18 and 2025-01-18 (recent sessions)
# Archive entries from 2025-11-16 and 2025-11-15 (older sessions)
################################################################################

echo "📝 Processing PROGRESS.md..."
echo "───────────────────────────────────────────────────────────────────"

# Find line number where 2025-11-16 entries start (after 2025-11-18 entries)
# We'll keep approximately the top 450 lines (recent work)
PROGRESS_KEEP_LINES=450

# Extract content to archive (everything after line 450)
tail -n +${PROGRESS_KEEP_LINES} "${BASE_DIR}/PROGRESS.md" > /tmp/progress_to_archive.txt

# Extract content to keep (first 450 lines)
head -n ${PROGRESS_KEEP_LINES} "${BASE_DIR}/PROGRESS.md" > /tmp/progress_truncated.txt

# Prepend archived content to PROGRESS_ARCH.md (if it exists)
if [ -f "${BASE_DIR}/PROGRESS_ARCH.md" ]; then
    # Combine: new archives + old archives
    cat /tmp/progress_to_archive.txt "${BASE_DIR}/PROGRESS_ARCH.md" > /tmp/progress_arch_new.txt
    mv /tmp/progress_arch_new.txt "${BASE_DIR}/PROGRESS_ARCH.md"
else
    # Create new archive file
    mv /tmp/progress_to_archive.txt "${BASE_DIR}/PROGRESS_ARCH.md"
fi

# Replace PROGRESS.md with truncated version
mv /tmp/progress_truncated.txt "${BASE_DIR}/PROGRESS.md"

ARCHIVED_PROGRESS=$((PROGRESS_LINES - PROGRESS_KEEP_LINES))
echo "   ✅ Kept: ${PROGRESS_KEEP_LINES} lines (recent entries)"
echo "   📦 Archived: ${ARCHIVED_PROGRESS} lines → PROGRESS_ARCH.md"
echo ""

################################################################################
# DECISIONS.md Truncation
# Keep entries from 2025-01-18 and recent 2025-11-18 decisions
# Archive older 2025-11-16 entries
################################################################################

echo "📝 Processing DECISIONS.md..."
echo "───────────────────────────────────────────────────────────────────"

# Keep approximately the top 500 lines (recent decisions)
DECISIONS_KEEP_LINES=500

# Extract content to archive
tail -n +${DECISIONS_KEEP_LINES} "${BASE_DIR}/DECISIONS.md" > /tmp/decisions_to_archive.txt

# Extract content to keep
head -n ${DECISIONS_KEEP_LINES} "${BASE_DIR}/DECISIONS.md" > /tmp/decisions_truncated.txt

# Prepend archived content to DECISIONS_ARCH.md
if [ -f "${BASE_DIR}/DECISIONS_ARCH.md" ]; then
    cat /tmp/decisions_to_archive.txt "${BASE_DIR}/DECISIONS_ARCH.md" > /tmp/decisions_arch_new.txt
    mv /tmp/decisions_arch_new.txt "${BASE_DIR}/DECISIONS_ARCH.md"
else
    mv /tmp/decisions_to_archive.txt "${BASE_DIR}/DECISIONS_ARCH.md"
fi

# Replace DECISIONS.md with truncated version
mv /tmp/decisions_truncated.txt "${BASE_DIR}/DECISIONS.md"

ARCHIVED_DECISIONS=$((DECISIONS_LINES - DECISIONS_KEEP_LINES))
echo "   ✅ Kept: ${DECISIONS_KEEP_LINES} lines (recent decisions)"
echo "   📦 Archived: ${ARCHIVED_DECISIONS} lines → DECISIONS_ARCH.md"
echo ""

################################################################################
# BUGS.md Truncation
# BUGS.md is only 315 lines - keep all (well within token limits)
################################################################################

echo "📝 Processing BUGS.md..."
echo "───────────────────────────────────────────────────────────────────"

if [ ${BUGS_LINES} -lt 500 ]; then
    echo "   ℹ️  BUGS.md (${BUGS_LINES} lines) is within limits - no truncation needed"
else
    # If BUGS.md grows beyond 500 lines, truncate it
    BUGS_KEEP_LINES=200

    tail -n +${BUGS_KEEP_LINES} "${BASE_DIR}/BUGS.md" > /tmp/bugs_to_archive.txt
    head -n ${BUGS_KEEP_LINES} "${BASE_DIR}/BUGS.md" > /tmp/bugs_truncated.txt

    if [ -f "${BASE_DIR}/BUGS_ARCH.md" ]; then
        cat /tmp/bugs_to_archive.txt "${BASE_DIR}/BUGS_ARCH.md" > /tmp/bugs_arch_new.txt
        mv /tmp/bugs_arch_new.txt "${BASE_DIR}/BUGS_ARCH.md"
    else
        mv /tmp/bugs_to_archive.txt "${BASE_DIR}/BUGS_ARCH.md"
    fi

    mv /tmp/bugs_truncated.txt "${BASE_DIR}/BUGS.md"

    ARCHIVED_BUGS=$((BUGS_LINES - BUGS_KEEP_LINES))
    echo "   ✅ Kept: ${BUGS_KEEP_LINES} lines"
    echo "   📦 Archived: ${ARCHIVED_BUGS} lines → BUGS_ARCH.md"
fi
echo ""

################################################################################
# Summary
################################################################################

echo "═══════════════════════════════════════════════════════════════════"
echo "✅ Truncation Complete"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

NEW_PROGRESS_LINES=$(count_lines "${BASE_DIR}/PROGRESS.md")
NEW_DECISIONS_LINES=$(count_lines "${BASE_DIR}/DECISIONS.md")
NEW_BUGS_LINES=$(count_lines "${BASE_DIR}/BUGS.md")

echo "📊 New File Statistics:"
echo "───────────────────────────────────────────────────────────────────"
echo "   PROGRESS.md:  ${PROGRESS_LINES} → ${NEW_PROGRESS_LINES} lines (-$((PROGRESS_LINES - NEW_PROGRESS_LINES)))"
echo "   DECISIONS.md: ${DECISIONS_LINES} → ${NEW_DECISIONS_LINES} lines (-$((DECISIONS_LINES - NEW_DECISIONS_LINES)))"
echo "   BUGS.md:      ${BUGS_LINES} → ${NEW_BUGS_LINES} lines (no change)"
echo ""

PROGRESS_ARCH_LINES=$(count_lines "${BASE_DIR}/PROGRESS_ARCH.md")
DECISIONS_ARCH_LINES=$(count_lines "${BASE_DIR}/DECISIONS_ARCH.md")

echo "📦 Archive File Statistics:"
echo "───────────────────────────────────────────────────────────────────"
echo "   PROGRESS_ARCH.md:  ${PROGRESS_ARCH_LINES} lines"
echo "   DECISIONS_ARCH.md: ${DECISIONS_ARCH_LINES} lines"
if [ -f "${BASE_DIR}/BUGS_ARCH.md" ]; then
    BUGS_ARCH_LINES=$(count_lines "${BASE_DIR}/BUGS_ARCH.md")
    echo "   BUGS_ARCH.md:      ${BUGS_ARCH_LINES} lines"
fi
echo ""

echo "💾 Backup Location: ${BACKUP_DIR}"
echo "   • PROGRESS.md.backup"
echo "   • DECISIONS.md.backup"
echo "   • BUGS.md.backup"
echo ""

echo "✨ Truncation complete! Files are now within token limits."
echo ""
