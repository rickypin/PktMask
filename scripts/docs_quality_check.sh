#!/bin/bash

# PktMask Documentation Quality Check Script
# Created: 2025-07-25
# Purpose: Automated quality assurance for documentation

set -e

echo "🔍 PktMask Documentation Quality Check"
echo "======================================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_ISSUES=0
BROKEN_LINKS=0
OUTDATED_REFS=0
EMPTY_DOCS=0

echo -e "${BLUE}📊 Document Statistics${NC}"
echo "----------------------"

# Count documents
TOTAL_DOCS=$(find docs/ -name "*.md" | wc -l)
TOTAL_SIZE=$(du -sh docs/ | cut -f1)
echo "Total documents: $TOTAL_DOCS"
echo "Total size: $TOTAL_SIZE"
echo ""

echo -e "${BLUE}🔗 Checking Internal Links${NC}"
echo "----------------------------"

# Check for broken internal links
find docs/ -name "*.md" -exec grep -l "\[.*\](.*\.md)" {} \; | while read file; do
    grep -o "\[.*\](.*\.md)" "$file" | while read link; do
        target=$(echo "$link" | sed 's/.*(\(.*\))/\1/')
        # Check relative to file directory
        if [[ ! -f "$(dirname "$file")/$target" && ! -f "docs/$target" ]]; then
            echo -e "${RED}❌ Broken link: $file -> $target${NC}"
            ((BROKEN_LINKS++))
            ((TOTAL_ISSUES++))
        fi
    done
done

if [ $BROKEN_LINKS -eq 0 ]; then
    echo -e "${GREEN}✅ No broken internal links found${NC}"
fi
echo ""

echo -e "${BLUE}⚠️  Checking for Outdated References${NC}"
echo "---------------------------------------"

# Check for outdated references
OUTDATED_PATTERNS="mask_payload_v2|BaseProcessor|ProcessingStep|ProcessorStageAdapter"

if grep -r "$OUTDATED_PATTERNS" docs/ --include="*.md" -q; then
    echo -e "${RED}❌ Found outdated references:${NC}"
    grep -r "$OUTDATED_PATTERNS" docs/ --include="*.md" | head -5 | while read line; do
        echo -e "${YELLOW}  $line${NC}"
        ((OUTDATED_REFS++))
        ((TOTAL_ISSUES++))
    done
else
    echo -e "${GREEN}✅ No outdated references found${NC}"
fi
echo ""

echo -e "${BLUE}📄 Checking for Empty Documents${NC}"
echo "--------------------------------"

# Check for empty or very small documents
find docs/ -name "*.md" -size -100c | while read file; do
    lines=$(wc -l < "$file")
    if [ $lines -lt 5 ]; then
        echo -e "${YELLOW}⚠️  Possibly empty document: $file ($lines lines)${NC}"
        ((EMPTY_DOCS++))
    fi
done

if [ $EMPTY_DOCS -eq 0 ]; then
    echo -e "${GREEN}✅ No empty documents found${NC}"
fi
echo ""

echo -e "${BLUE}📁 Directory Structure Validation${NC}"
echo "-----------------------------------"

# Check if expected directories exist
EXPECTED_DIRS=("docs/dev/architecture" "docs/dev/testing" "docs/dev/cleanup" "docs/dev/analysis" "docs/archive/completed-projects")

for dir in "${EXPECTED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -name "*.md" | wc -l)
        echo -e "${GREEN}✅ $dir ($count documents)${NC}"
    else
        echo -e "${RED}❌ Missing directory: $dir${NC}"
        ((TOTAL_ISSUES++))
    fi
done
echo ""

echo -e "${BLUE}🎯 README File Validation${NC}"
echo "---------------------------"

# Check for README files in key directories
README_DIRS=("docs/dev/architecture" "docs/dev/testing" "docs/dev/cleanup" "docs/dev/analysis")

for dir in "${README_DIRS[@]}"; do
    if [ -f "$dir/README.md" ]; then
        echo -e "${GREEN}✅ $dir/README.md exists${NC}"
    else
        echo -e "${RED}❌ Missing: $dir/README.md${NC}"
        ((TOTAL_ISSUES++))
    fi
done
echo ""

echo -e "${BLUE}📈 Cleanup Effectiveness${NC}"
echo "-------------------------"

# Calculate cleanup effectiveness
ARCHITECTURE_DOCS=$(find docs/dev/architecture/ -name "*.md" | wc -l)
TESTING_DOCS=$(find docs/dev/testing/ -name "*.md" | wc -l)
CLEANUP_DOCS=$(find docs/dev/cleanup/ -name "*.md" | wc -l)
ANALYSIS_DOCS=$(find docs/dev/analysis/ -name "*.md" | wc -l)
ARCHIVED_DOCS=$(find docs/archive/completed-projects/ -name "*.md" | wc -l)

echo "Architecture documents: $ARCHITECTURE_DOCS"
echo "Testing documents: $TESTING_DOCS"
echo "Cleanup documents: $CLEANUP_DOCS"
echo "Analysis documents: $ANALYSIS_DOCS"
echo "Archived documents: $ARCHIVED_DOCS"
echo ""

echo -e "${BLUE}📋 Summary${NC}"
echo "----------"

if [ $TOTAL_ISSUES -eq 0 ]; then
    echo -e "${GREEN}🎉 All quality checks passed!${NC}"
    echo -e "${GREEN}Documentation is in excellent condition.${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Found $TOTAL_ISSUES issues that need attention:${NC}"
    [ $BROKEN_LINKS -gt 0 ] && echo -e "${RED}  - $BROKEN_LINKS broken links${NC}"
    [ $OUTDATED_REFS -gt 0 ] && echo -e "${RED}  - $OUTDATED_REFS outdated references${NC}"
    [ $EMPTY_DOCS -gt 0 ] && echo -e "${YELLOW}  - $EMPTY_DOCS potentially empty documents${NC}"
    echo ""
    echo -e "${YELLOW}Please review and fix these issues.${NC}"
    exit 1
fi
