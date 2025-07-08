#!/bin/bash
# 测试所有入口方式

echo "=== 测试 GUI 启动 ==="
echo "1. 测试 ./pktmask （按 Ctrl+C 退出）"
timeout 3 ./pktmask 2>&1 | head -5 || true
echo ""

echo "2. 测试 python pktmask.py"
timeout 3 python pktmask.py 2>&1 | head -5 || true
echo ""

echo "3. 测试 python -m pktmask"
timeout 3 python -m pktmask 2>&1 | head -5 || true
echo ""

echo "4. 测试 run_gui.py（应显示弃用警告）"
python run_gui.py 2>&1 | head -10 &
PID=$!
sleep 2
kill $PID 2>/dev/null || true
echo ""

echo -e "\n=== 测试 CLI 命令 ==="
echo "5. 测试 mask 命令帮助"
./pktmask mask --help | head -5
echo ""

echo -e "\n6. 测试 dedup 命令帮助"
./pktmask dedup --help | head -5
echo ""

echo -e "\n7. 测试 anon 命令帮助"
./pktmask anon --help | head -5
echo ""

echo -e "\n=== 测试完成 ==="
