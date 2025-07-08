#!/bin/bash
# 自动迁移脚本

# 定义要迁移的文件列表
MIGRATION_FILES=(
    "/Users/ricky/Downloads/PktMask/src/pktmask/core/pipeline/stages/mask_payload/stage.py"
    "/Users/ricky/Downloads/PktMask/tests/unit/test_infrastructure_basic.py"
    "/Users/ricky/Downloads/PktMask/tests/unit/test_pipeline_processor_adapter.py"
)

# 新旧导入路径映射
declare -A IMPORT_MAPPINGS
IMPORT_MAPPINGS["pktmask.core.adapters.processor_adapter"]=":"pktmask.adapters.processor_adapter"
IMPORT_MAPPINGS["pktmask.core.encapsulation.adapter"]=":"pktmask.adapters.encapsulation_adapter"
IMPORT_MAPPINGS["pktmask.domain.adapters.event_adapter"]=":"pktmask.adapters.event_adapter"
IMPORT_MAPPINGS["pktmask.domain.adapters.statistics_adapter"]=":"pktmask.adapters.statistics_adapter"
IMPORT_MAPPINGS["pktmask.stages.adapters.anon_compat"]=":"pktmask.adapters.compatibility.anon_compat"
IMPORT_MAPPINGS["pktmask.stages.adapters.dedup_compat"]=":"pktmask.adapters.compatibility.dedup_compat"

# 自动更新导入路径
for file in "${MIGRATION_FILES[@]}"; do
    echo "迁移文件: $file"
    for old_import in "${!IMPORT_MAPPINGS[@]}"; do
        new_import=${IMPORT_MAPPINGS[$old_import]}
        sed -i.bak "s/$old_import/$new_import/g" "$file"
    done
    echo "完成: $file"
    # 移除备份文件
    rm -f "$file.bak"
    echo "清除临时文件"
done

echo "所有文件迁移完成！"
