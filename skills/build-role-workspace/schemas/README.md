# 数据契约

legacy-v1为原9个契约的兼容参考，不要静默加字段或状态。scripts/workspace.py维护的是独立workspace_index，record_type=workspace_index、format_version=1，不冒充旧project_state。新旧记录通过project_id及显式映射关联。旧契约不由workspace.py自动迁移；见references/core/upgrade-and-portability.md。
