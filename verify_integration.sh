#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "UFDR Integration Verification"
echo "=========================================="

MISSING=0

# Check extractors
echo -e "\n${YELLOW}Checking Extractor Files...${NC}"
for file in apps call_logs messages locations browsing; do
    if [ -f "realtime/worker/ufdr_${file}_extractor.py" ]; then
        echo -e "${GREEN}✓${NC} ufdr_${file}_extractor.py"
    else
        echo -e "${RED}✗${NC} ufdr_${file}_extractor.py MISSING"
        MISSING=$((MISSING + 1))
    fi
done

# Check database schemas
echo -e "\n${YELLOW}Checking Schema Files...${NC}"
for file in apps call_logs messages locations browsing; do
    if [ -f "realtime/utils/db/${file}_schema.sql" ]; then
        echo -e "${GREEN}✓${NC} ${file}_schema.sql"
    else
        echo -e "${RED}✗${NC} ${file}_schema.sql MISSING"
        MISSING=$((MISSING + 1))
    fi
done

# Check operations files
echo -e "\n${YELLOW}Checking Operations Files...${NC}"
for file in apps call_logs messages locations browsing; do
    if [ -f "realtime/utils/db/${file}_operations.py" ]; then
        echo -e "${GREEN}✓${NC} ${file}_operations.py"
    else
        echo -e "${RED}✗${NC} ${file}_operations.py MISSING"
        MISSING=$((MISSING + 1))
    fi
done

# Check tools
echo -e "\n${YELLOW}Checking Tool Files...${NC}"
for file in apps call_logs messages location browsing_history; do
    if [ -f "realtime/tools/${file}.py" ]; then
        echo -e "${GREEN}✓${NC} tools/${file}.py"
    else
        echo -e "${RED}✗${NC} tools/${file}.py MISSING"
        MISSING=$((MISSING + 1))
    fi
done

# Check key files
echo -e "\n${YELLOW}Checking Key Integration Files...${NC}"
KEY_FILES=(
    "realtime/worker/ingest_worker.py"
    "realtime/utils/prompts/Forensic_agent.py"
    "realtime/utils/ai/agent.py"
    "realtime/utils/db/connection.py"
    "realtime/utils/db/init_all_schemas.sql"
    "realtime/api/uploads/routes.py"
)

for file in "${KEY_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file MISSING"
        MISSING=$((MISSING + 1))
    fi
done

# Summary
echo -e "\n=========================================="
if [ $MISSING -eq 0 ]; then
    echo -e "${GREEN}✓ All files present! Integration successful!${NC}"
    echo "=========================================="
    exit 0
else
    echo -e "${RED}✗ $MISSING files missing!${NC}"
    echo "=========================================="
    exit 1
fi
