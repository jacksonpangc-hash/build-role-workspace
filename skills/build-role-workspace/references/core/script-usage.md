# 包内脚本接口

Python 3.10+标准库，无网络调用与运行依赖。以下命令由Agent执行；当前目录设为Skill目录，路径换成当前获准位置。先阅读脚本的`--help`，不要把示例路径当真实数据。

## 本地工作区

`python3 scripts/workspace.py init --workspace ./private-work --role ecommerce_operations --goal 月复盘`

初始化只创建新workspace.json和results；已有索引则拒绝，改用status继续。工作区不得放入共享Skill，真实使用时选择用户自己的约定位置。

`python3 scripts/workspace.py ingest --workspace ./private-work --root ./authorized-inputs`

只读登记所有非隐藏文件，文本提取限UTF8与默认8MiB；其他格式由宿主处理，不自动读宏或解包归档。源和工作区嵌套时排除工作区，避免重复自我导入。重新导入产生源版本，并标记相关产物stale；撤回来源不因再导入恢复权限。

`python3 scripts/workspace.py search --workspace ./private-work --query 退款`

只查当前有效源，返回路径、哈希、行和引文。关键词按空格分词且同一行全部命中；中文同义词由Agent适当扩大，不宣称语义搜索。源在磁盘改变后暂不引用，先重新登记。

status读取持久索引；它不验证真实业务系统。每次重用结果前检查source_refs及源版本。save接受--name、--input和可选--ref；替换已有文件必须提供实际当前--expected-hash，先读取用户修改。update接受JSON文件及--revision，冲突则重新读取合并。rule接受JSON文件，其中active要求owner、scope、approval_ref及source_refs；这些字段仅记录证据，不证明批准人权力。feedback接受--issue、--layer及可选--ref。revoke接受--ref并使关联产物受限。

## 数值

`python3 scripts/reconcile.py rate normalized.csv --numerator conversions --denominator clicks --key sku --context currency,period`

输入明确列名和粒度，缺失、非有限数、负计数、重复业务键及混合上下文报错；分母零输出null。`--key`和`--context`可为逗号分隔字段。不要删除context约束来混算不同单位。带千分位等源值先以有记录的映射规范化，保留原行。

`python3 scripts/reconcile.py compare left.csv right.csv --key id --amount amount --currency currency`

按业务键和币种精确比较，不猜多对多，不跨币种净额；输出matched、difference、missing_left或missing_right。

## 动作

`python3 scripts/actions.py --object-id SKU-1 --version v1 --operation stock-proposal --parameters params.json`

输出固定身份的离线提案，无执行器。真实动作由获准宿主工具承担；结果未知先查询，参数/版本变化要重验证。无需通过此脚本才能执行业务；它只在稳定记录与去重有价值时使用。

## 升级附属工具

`python3 scripts/discovery.py scan ./authorized-inputs --exclude ./authorized-inputs/results` 列包括隐藏文件的目录与ZIP成员，输出覆盖和限制；不读取成员语义。`extract <archive> <member> <new-work-copy> --sha256 <member-hash> --container-sha256 <outer-hash>` 只复制选定成员，目标必须不存在。未支持RAR/7z，不静默解包。

`python3 scripts/records.py --workspace ./private-work --scope company-project put context current --value context.json` 建新记录。已有记录加 `--expected-revision <当前整数>`；依赖可重复指定 `--depends definition:sales`。get/history/revoke使用相同kind/name；撤回不可被put默默恢复。新scope从空记录开始，必须由当前授权选择，不能遍历其他公司。模板见 [私有工作约定](../../templates/private-context.md)。

Python API `Records.observe_file(kind,name,path,expected_revision=None)` 对明确授权原件保存file_ref，get时核源当前哈希；新提取/规则/结果用dependencies传 `kind:name` 列表。仅保存path文本不会自动监视磁盘。无常驻服务，运行get时才检查。

`python3 scripts/planning.py bridge ./normalized.json` 接收逐商品id、budget_quantity/price、actual_quantity/price。`inventory ./scenario.json` 的必需字段见 `inventory` 函数required及 [合成情景](../catalog/inventory-example.json)。所有缺字段返回insufficient_data和null数量。示例全部是教学情景，不是企业政策。

`quality.relation(left,right,key)`、`metric(numerator,denominator,kind)`、`expand_bundles(lines,recipes)` 与 `ledger.Ledger(root,scope)` 是包内Python接口，无CLI执行器。动作先用make_action构造，再register/event/decision；序号连续，结果/关闭需receipt。记录一致性与真实权限分开。

删除旧依赖或移除/替换file_ref的来源路径时，用 `--provenance-change-ref <实际重做依据>`；受限记录仍拒绝。Python的read()返回可展示快照，未遮蔽磁盘读取仅为内部持久化细节；工作区JSON始终受用户文件权限保护。

库存输出必须连同daily_projection、planning_shortages、candidate_timing_feasible和decision解释。candidate_quantity只指全期净缺口取整，不能单独抽取为下单指令。无均匀日需求可比口径应先保存新的需求日程定义，不强行调用本简化接口。
