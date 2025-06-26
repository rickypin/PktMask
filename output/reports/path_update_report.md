# PktMask路径更新报告

**执行模式**: LIVE RUN (实际执行)
**总更改数**: 2

## 详细更改列表

- **src/pktmask/config/defaults.py**: mask_config.yaml -> config/default/mask_config.yaml
- **src/pktmask/config/settings.py**: mask_config.yaml -> config/default/mask_config.yaml

## 验证步骤

1. 运行测试: `python3 run_tests.py --quick`
2. 启动GUI: `python3 run_gui.py`
3. 运行示例: `cd examples && python3 basic_usage.py`
4. 检查配置: 验证配置文件正确加载
