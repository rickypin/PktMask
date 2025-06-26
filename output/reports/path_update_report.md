# PktMask路径更新报告

**执行模式**: LIVE RUN (实际执行)
**总更改数**: 7

## 详细更改列表

- **examples/basic_usage.py**: output/ -> output/processed/
- **examples/basic_usage.py**: examples/output/ -> examples/output/
- **examples/advanced_usage.py**: output/ -> output/processed/
- **examples/advanced_usage.py**: examples/output/ -> examples/output/
- **examples/performance_testing.py**: output/ -> output/processed/
- **examples/performance_testing.py**: examples/output/ -> examples/output/
- **run_tests.py**: reports/ -> output/reports/

## 验证步骤

1. 运行测试: `python3 run_tests.py --quick`
2. 启动GUI: `python3 run_gui.py`
3. 运行示例: `cd examples && python3 basic_usage.py`
4. 检查配置: 验证配置文件正确加载
