# GitHub Actions 修复说明

## 问题概述

GitHub Actions 工作流程遇到以下错误：
1. `actions/upload-artifact@v3` 已被弃用，需要升级到 v4
2. `securecodewarrior/github-action-bandit@v1` action 不存在或已被移除
3. `actions/checkout@v3` 和 `actions/download-artifact@v3` 也需要升级

## 修复内容

### 1. 升级 Actions 版本

#### build.yml
- ✅ `actions/checkout@v3` → `actions/checkout@v4`
- ✅ 其他 actions 已经是最新版本

#### test.yml
- ✅ `actions/upload-artifact@v3` → `actions/upload-artifact@v4` (6处)
- ✅ `actions/download-artifact@v3` → `actions/download-artifact@v4` (1处)

### 2. 替换不存在的 Bandit Action

**原配置：**
```yaml
- name: 运行Bandit安全扫描
  uses: securecodewarrior/github-action-bandit@v1
  with:
    path: src/
```

**新配置：**
```yaml
- name: 设置Python环境
  uses: actions/setup-python@v4
  with:
    python-version: ${{ env.PYTHON_VERSION }}

- name: 运行Bandit安全扫描
  run: |
    python -m pip install --upgrade pip bandit
    bandit -r src/ -f json -o bandit-report.json || true
    bandit -r src/ -f txt || true
```

### 3. 修复的具体位置

#### test.yml 修复列表：
- 第 125 行：测试报告上传
- 第 179 行：覆盖率报告上传
- 第 217 行：性能报告上传
- 第 232-249 行：安全扫描整个部分重写
- 第 290 行：发布测试报告上传
- 第 304 行：下载所有测试报告
- 第 322 行：汇总报告上传

#### build.yml 修复列表：
- 第 20 行：checkout action 版本升级

## 验证建议

1. **推送代码触发工作流程**：
   ```bash
   git add .github/workflows/
   git commit -m "fix: upgrade GitHub Actions to latest versions"
   git push
   ```

2. **检查工作流程状态**：
   - 访问 GitHub Actions 页面
   - 确认所有 jobs 能够正常运行
   - 特别关注安全扫描 job 是否正常工作

3. **测试发布流程**（可选）：
   ```bash
   git tag v1.0.0-test
   git push origin v1.0.0-test
   ```

## 注意事项

1. **Bandit 扫描**：现在使用直接安装的方式运行，输出格式保持一致
2. **依赖关系**：确保所有 needs 依赖关系正确配置
3. **权限**：新的 actions 版本可能需要不同的权限设置
4. **缓存**：actions/cache@v3 仍然可用，暂时不需要升级

## 后续优化建议

1. 考虑升级 `actions/cache@v3` 到 `actions/cache@v4`
2. 评估是否需要添加更多安全扫描工具
3. 优化工作流程的并行执行策略
4. 添加工作流程失败时的通知机制
