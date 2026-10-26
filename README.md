# 岗位知识库助手 · build-role-workspace

**公开测试版 / prerelease：0.2.0-rc.4。** 同一个Skill帮助不同岗位把获准资料变成报告、差异核对、脚本或交接，并保存来源、定义和修改供下次继续。

目前提供14岗按需方法、198场景、42配方、6应用组合和8法务参考。这些是参考覆盖，不代表企业系统已连接或全部岗位生产验收通过。**真人完整流程、真实跨岗位接收、专业认可及效率收益仍未通过或未验证。** 最终完整成品目标继续保留。

## 开始使用

1. 到[预发布页](https://github.com/jacksonpangc-hash/build-role-workspace/releases/tag/v0.2.0-rc.4)下载Skill ZIP和SHA256SUMS，核对校验值。
2. 让支持Agent Skills的宿主将解压的build-role-workspace目录放到新的技能位置；已有同名目录先保留，不直接覆盖。Codex个人位置常用 ~/.codex/skills/。
3. 在新会话中说：请用 $build-role-workspace 读取这个获准目录，整理项目的进度、未完成事项和交接，保存来源与下次能继续的记录。缺资料请说明，不反复索要。

[开始页](skills/build-role-workspace/START_HERE.md) · [使用指南](docs/user-guide.md) · [完整自有合成示例](examples/synthetic/complete-example.md)

可选Python辅助脚本要求3.10+且仅用标准库。文档、表格、音画读取由宿主能力决定；没有新平台、网络执行器或后台调度要求。工作区、公司规则和业务结果保存在使用者私有目录，不上传本仓库。

## 验证、反馈与维护

运行 python3 -m unittest discover -s tests -v。构建运行 python3 tools/build_release.py --output dist；公开清单、来源和已审核字节必须相符，构建不会自动认可修改。

[支持与限制](docs/release/support-matrix.md) · [验收范围](docs/release/acceptance-report.md) · [兼容与回退](docs/compatibility.md) · [贡献与问题报告](CONTRIBUTING.md) · [安全报告](SECURITY.md)

一般问题使用仓库Issues，附版本、宿主、最小合成复现和预期/实际；不要附私有资料。敏感问题按SECURITY.md的私密渠道报告。

原创内容采用[MIT](LICENSE)，署名build-role-workspace contributors；[第三方说明](THIRD_PARTY_NOTICES.md)保留相应义务。旧rc.2有内容边界缺陷，未作为本公开测试版资产分发；其修复历史及未通过状态在变更记录中保留。
