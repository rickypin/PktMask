# English-Only Coding Policy

**Document Version**: 1.0  
**Effective Date**: 2025-01-24  
**Scope**: All PktMask project development  
**Authority**: Technical Debt Resolution Initiative  

## Policy Statement

All code documentation, comments, docstrings, and user-facing text in the PktMask project **MUST** be written in English. This policy addresses the mixed language documentation technical debt identified in the comprehensive code review and ensures international collaboration standards.

## Rationale

### Technical Debt Impact
- **International Collaboration Barriers**: Chinese comments prevent non-Chinese developers from understanding code
- **Maintenance Confusion**: Mixed languages create cognitive overhead for developers
- **Documentation Inconsistency**: Reduces code quality and professional standards
- **Knowledge Transfer Issues**: Impedes team onboarding and code reviews

### Business Benefits
- **Global Accessibility**: Enables international developer contributions
- **Professional Standards**: Aligns with industry best practices
- **Maintainability**: Reduces long-term maintenance costs
- **Quality Assurance**: Improves code review effectiveness

## Policy Requirements

### 1. Code Documentation (MANDATORY)

#### 1.1 Module Docstrings
```python
# ✅ CORRECT - English docstring
"""
Unified Deduplication Stage - Pure StageBase Implementation

Completely removes BaseProcessor dependency, directly integrates SHA256 hash 
deduplication algorithm. Eliminates adapter layer, unified StageStats format return.
"""

# ❌ INCORRECT - Chinese docstring
"""
统一去重阶段 - 纯StageBase实现

完全移除BaseProcessor依赖，直接集成SHA256哈希去重算法。
消除适配器层，统一返回StageStats格式。
"""
```

#### 1.2 Function and Method Docstrings
```python
# ✅ CORRECT - English docstring with proper PEP 257 format
def process_file(self, input_path: Path, output_path: Path) -> StageStats:
    """Process input file and generate deduplicated output.
    
    Args:
        input_path: Path to input PCAP/PCAPNG file
        output_path: Path for deduplicated output file
        
    Returns:
        StageStats: Processing statistics and results
        
    Raises:
        ProcessingError: If file processing fails
        ValidationError: If input file is invalid
    """

# ❌ INCORRECT - Chinese docstring
def process_file(self, input_path: Path, output_path: Path) -> StageStats:
    """处理输入文件并生成去重输出
    
    参数:
        input_path: 输入PCAP/PCAPNG文件路径
        output_path: 去重输出文件路径
    """
```

#### 1.3 Inline Comments
```python
# ✅ CORRECT - English comments
# Deduplication processing with memory monitoring and error handling
for packet in packets:
    packet_hash = self._generate_packet_hash(packet)  # Generate SHA256 hash
    if packet_hash not in self._packet_hashes:        # Check for duplicates
        unique_packets.append(packet)

# ❌ INCORRECT - Chinese comments  
# 去重处理 with memory monitoring and error handling
for packet in packets:
    packet_hash = self._generate_packet_hash(packet)  # 生成SHA256哈希
    if packet_hash not in self._packet_hashes:        # 检查重复
        unique_packets.append(packet)
```

### 2. User-Facing Text (MANDATORY)

#### 2.1 GUI Text and Labels
```python
# ✅ CORRECT - English GUI text
CHECKBOX_REMOVE_DUPES = "Remove Dupes"
CHECKBOX_ANONYMIZE_IPS = "Anonymize IPs" 
CHECKBOX_MASK_PAYLOADS = "Mask Payloads"
TOOLTIP_REMOVE_DUPES = "Remove duplicate packets based on content hash to reduce file size."

# ❌ INCORRECT - Chinese GUI text
CHECKBOX_REMOVE_DUPES = "去重处理"
TOOLTIP_REMOVE_DUPES = "基于内容哈希去除重复数据包以减少文件大小。"
```

#### 2.2 Log Messages
```python
# ✅ CORRECT - English log messages
self.logger.info(f"Selected input directory: {dir_path}")
self.logger.error(f"Processing failed: {e}")
self.logger.debug("MaskingStage specific cleanup completed")

# ❌ INCORRECT - Chinese log messages
self.logger.info(f"选择输入目录: {dir_path}")
self.logger.error(f"处理失败: {e}")
```

#### 2.3 Error Messages
```python
# ✅ CORRECT - English error messages
raise ProcessingError("Failed to process packet: invalid format")
raise ValidationError("Input file does not exist or is not accessible")

# ❌ INCORRECT - Chinese error messages
raise ProcessingError("处理数据包失败: 格式无效")
raise ValidationError("输入文件不存在或无法访问")
```

### 3. Configuration and Constants (MANDATORY)

#### 3.1 Enumeration Values
```python
# ✅ CORRECT - English enum descriptions
class ProcessingStepType(Enum):
    """Processing stage type enumeration (based on unified StageBase architecture)"""
    
    ANONYMIZE_IPS = "anonymize_ips"  # UnifiedIPAnonymizationStage
    REMOVE_DUPES = "remove_dupes"   # UnifiedDeduplicationStage
    MASK_PAYLOADS = "mask_payloads" # MaskingStage (dual-module)

# ❌ INCORRECT - Chinese enum descriptions
class ProcessingStepType(Enum):
    """处理阶段类型枚举（基于统一StageBase架构）"""
```

### 4. Documentation Files (MANDATORY)

#### 4.1 Technical Documentation
- All `.md` files must be written in English
- API documentation must use English terminology
- Code examples must have English comments
- Architecture diagrams must use English labels

#### 4.2 README and Setup Instructions
- Installation instructions in English
- Usage examples with English descriptions
- Troubleshooting guides in English

## Implementation Guidelines

### 1. Translation Standards

#### Technical Terminology Mapping
| Chinese Term | English Translation | Context |
|--------------|-------------------|---------|
| 去重 | Deduplication | Packet processing |
| 匿名化 | Anonymization | IP address processing |
| 载荷掩码 | Payload Masking | Data masking |
| 序列号 | Sequence Number | TCP processing |
| 保留规则 | Keep Rules | Masking rules |
| 统计信息 | Statistics | Processing metrics |
| 错误恢复 | Error Recovery | Error handling |
| 性能监控 | Performance Monitoring | System monitoring |
| 资源清理 | Resource Cleanup | Memory management |

#### Documentation Style Guidelines
1. **Clarity**: Use clear, concise English
2. **Consistency**: Maintain consistent terminology
3. **Technical Accuracy**: Preserve precise technical meaning
4. **Professional Tone**: Use professional, formal language
5. **PEP 257 Compliance**: Follow Python docstring conventions

### 2. Quality Assurance Process

#### Pre-Commit Validation
1. **Automated Scanning**: Check for Chinese characters in code
2. **Lint Integration**: Include language checks in code linting
3. **Review Requirements**: Mandate English-only code reviews

#### Continuous Integration
1. **CI/CD Pipeline**: Automated Chinese character detection
2. **Build Failures**: Fail builds containing Chinese text
3. **Documentation Validation**: Verify English-only documentation

## Enforcement Mechanisms

### 1. Automated Checks

#### Pre-commit Hook Example
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for Chinese characters in staged files
if git diff --cached --name-only | grep -E '\.(py|md|txt|yml|yaml|json)$' | xargs grep -l '[\u4e00-\u9fff]'; then
    echo "❌ Error: Chinese characters found in staged files"
    echo "Please translate all Chinese text to English before committing"
    exit 1
fi

echo "✅ Language check passed"
```

#### CI/CD Pipeline Integration
```yaml
# .github/workflows/language-check.yml
name: Language Compliance Check

on: [push, pull_request]

jobs:
  language-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check for Chinese characters
        run: |
          if find . -name "*.py" -o -name "*.md" | xargs grep -l '[\u4e00-\u9fff]'; then
            echo "❌ Chinese characters found in codebase"
            exit 1
          fi
          echo "✅ English-only compliance verified"
```

### 2. Code Review Requirements

#### Review Checklist
- [ ] All comments and docstrings are in English
- [ ] User-facing text uses English
- [ ] Log messages are in English
- [ ] Error messages are in English
- [ ] Configuration values use English descriptions

#### Review Guidelines
1. **Mandatory Review**: All code changes must be reviewed for language compliance
2. **Rejection Criteria**: Code with Chinese text must be rejected
3. **Translation Assistance**: Reviewers should help with accurate translations

## Exceptions and Special Cases

### 1. Limited Exceptions (RARE)

#### Test Data
- Test files may contain Chinese characters as test data
- Must be clearly marked as test data
- Should not contain Chinese comments or documentation

#### External Dependencies
- Third-party libraries with Chinese text are acceptable
- Must be documented as external dependencies
- Should not influence internal code standards

### 2. Migration Period

#### Existing Code
- Legacy Chinese text should be translated during regular maintenance
- New features must comply immediately
- Critical bug fixes may temporarily bypass for urgent releases

## Compliance Monitoring

### 1. Regular Audits

#### Monthly Reviews
- Scan entire codebase for Chinese characters
- Generate compliance reports
- Track translation progress

#### Quarterly Assessments
- Review policy effectiveness
- Update translation guidelines
- Assess developer compliance

### 2. Metrics and Reporting

#### Key Performance Indicators
- **Compliance Rate**: Percentage of files with English-only content
- **Translation Progress**: Number of files translated per month
- **Violation Detection**: Number of Chinese text instances found
- **Developer Adoption**: Percentage of developers following policy

#### Reporting Dashboard
- Real-time compliance status
- Translation progress tracking
- Violation trend analysis
- Developer compliance scores

## Training and Support

### 1. Developer Training

#### Onboarding Requirements
- English-only policy explanation
- Translation best practices
- Technical terminology training
- Tool usage instructions

#### Ongoing Support
- Translation assistance resources
- Technical writing guidelines
- Code review training
- Policy update notifications

### 2. Resources and Tools

#### Translation Tools
- Technical terminology dictionary
- Automated translation suggestions
- Code comment templates
- Documentation examples

#### Validation Tools
- Chinese character detection scripts
- Automated compliance checking
- CI/CD integration guides
- Pre-commit hook templates

## Policy Updates and Maintenance

### 1. Version Control
- Policy changes require formal approval
- Version history maintained
- Change notifications to all developers
- Implementation timeline communication

### 2. Feedback and Improvement
- Regular policy effectiveness reviews
- Developer feedback collection
- Continuous improvement process
- Best practice sharing

## Conclusion

This English-Only Coding Policy ensures PktMask maintains professional standards, enables international collaboration, and eliminates technical debt associated with mixed language documentation. Compliance is mandatory for all new code and strongly encouraged for existing code maintenance.

**Effective immediately, all new code contributions must comply with this policy.**
