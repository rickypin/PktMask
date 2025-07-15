#!/bin/bash
# Test all entry points

echo "=== Test GUI Launch ==="
echo "1. Test ./pktmask (press Ctrl+C to exit)"
timeout 3 ./pktmask 2>&1 | head -5 || true
echo ""

echo "2. Test python pktmask.py"
timeout 3 python pktmask.py 2>&1 | head -5 || true
echo ""

echo "3. Test python -m pktmask"
timeout 3 python -m pktmask 2>&1 | head -5 || true
echo ""

echo "4. Test run_gui.py (should show deprecation warning)"
python run_gui.py 2>&1 | head -10 &
PID=$!
sleep 2
kill $PID 2>/dev/null || true
echo ""

echo -e "\n=== Test CLI Commands ==="
echo "5. Test mask command help"
./pktmask mask --help | head -5
echo ""

echo -e "\n6. Test dedup command help"
./pktmask dedup --help | head -5
echo ""

echo -e "\n7. Test anon command help"
./pktmask anon --help | head -5
echo ""

echo -e "\n=== Testing Complete ==="
