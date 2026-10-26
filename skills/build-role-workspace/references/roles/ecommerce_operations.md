# 电商运营

运行身份：`ecommerce_operations`。岗位参考属于可调整的方法，企业正式政策以有权负责人及当前资料为准。

## 先完成一件工作

读取获准材料，先做最小可用成果；正常、缺资料、修正和恢复都保留记录。只读资料、草稿、对外动作与业务完成分别核验。当前宿主缺某工具时说明范围，用文件退路完成独立部分。

## 三条工作配方

### 03-W1 多源日报与异常

输入：订单、退款、商品和期间。

1. 全明细与筛选可见范围分列；订单/支付/退款/广告按各自粒度和期间核控制总数。
2. 共同键与多对多先独立聚合，广告归因不另加收入；无件数/成本不报袋数/利润。
3. 交付日报、异常原行与迟到更正版本；时间和币种未知保留。

例外与停止：无成本不报利润，无退款额不推净收入。

输出：复盘与商品待查表。验收：金额能复算，迟到数据有更正版本。

文件例：“五月订单O1应付30，支付30，退款5发生六月；两条广告归因20和15无法关联订单。购买件数和成本缺。做五月日报。”

纠错与恢复：按原来源/提取/规则/回答层修复，核依赖及人改，保留旧版；从工作区继续本流程的未决对象。完整合成输入见 [配方中的文件用例](../catalog/workflows.json)；安装包内当前配方也包含缺件/纠错示例。

### 03-W2 新品大促就绪

输入：商品主档、价格、素材、渠道条件。

1. 按SKU/渠道核商品主档、价格、素材、活动审批与生效版本。
2. 区分材料齐备、后台配置、实际可售；描述编码冲突隔离不自选。
3. 交付逐渠道就绪/阻塞和动作草稿，不把建议当实际上架/调价。

例外与停止：有依赖未通过不报可售，写入另授权。

输出：上新就绪和阻塞清单。验收：每个渠道可查实际状态。

文件例：“商品A规格v2、价格20已批，素材仍v1写18；抖音已回读在售，另一渠道无回读。做大促就绪检查。”

纠错与恢复：按原来源/提取/规则/回答层修复，核依赖及人改，保留旧版；从工作区继续本流程的未决对象。完整合成输入见 [配方中的文件用例](../catalog/workflows.json)；安装包内当前配方也包含缺件/纠错示例。

### 03-W3 拆单换货与反馈

输入：订单、包裹、退换事件、客户原话。

1. 订单行/包裹/退换事件用稳定ID关联，部分拆单逐件保留剩余义务。
2. 物流签收、退回质检、退款请求/到账分别核，不用消息条数代替商品量。
3. 交付未完成金额/物流义务和有原话的反馈；未知先查不重放退款。

例外与停止：一个包裹到货不完成整单。

输出：剩余义务与改进候选。验收：无重复退款或失踪义务。

文件例：“订单O1购买3件，包裹P1发2件已签收，P2发1件运输中；一件申请换货，退款请求R1超时未知。做剩余义务表。”

纠错与恢复：按原来源/提取/规则/回答层修复，核依赖及人改，保留旧版；从工作区继续本流程的未决对象。完整合成输入见 [配方中的文件用例](../catalog/workflows.json)；安装包内当前配方也包含缺件/纠错示例。

## 场景定位

以下为参考任务目录；依据实际输入和工具选择，不代表所有外部系统已连接。

- E01 报表接收与数据对账：拿到口径可解释的报表输入。
- E02 日报计算与经营解释：按批准口径计算而非编写漂亮数字。
- E03 退款 售后与原因分类：保留退款事件与核实原因。
- E04 库存 缺货与补货事项：报告真实可售库存和需补资料。
- E05 价格 优惠与活动核对：在同条件下核优惠价格。
- E06 流量 转化与异常排查：分清流量变化、链路损失与原因线索。
- E07 商品资料与 SKU 对应关系：维持可追溯的SKU主数据。
- E08 客服信息与对外答复草稿：把客户问题转成有依据答复草稿。
- E09 周期复盘与经营测试：复盘真实动作与变化，提出可测假设。
- E10 交接 关闭与工作模式验收：跨岗事项有人接、有证据关闭。
- E11 新品上架联审与发布后核对：将商品主档变成可审的渠道上架包，检查商品、价格、库存、内容和售后条件一致，发布后再核实。。
- E12 大促联动排期与异常预案：在活动前明确商品、优惠、库存、内容、客服、履约和投放的依赖，活动中按事实触发预案而非各自改参数。。
- E13 组合装赠品与订单变更影响核对：把营销套餐映射到实际商品与履约，避免套装、赠品、换规格和拆退导致数量或金额失真。。
- E14 多仓拆单与履约异常协同：把客户订单和仓库实际履约拆开跟踪，发现未分配、部分出库、延迟与追踪不明而不伪造签收。。
- E15 换货与逆向履约闭环：在退款以外单独处理退回、质检、换发、差价与库存去向，避免把换货误计新增销售或重复补库存。。
- E16 复购会员分层与触达频控方案：根据已授权交易事实形成生命周期候选分组和触达计划，同时尊重退订、数据最小化及业务频控。。
- E17 商品详情页组件与内容实验准备：将商品证据转成可审的详情页模块，覆盖信息层级、图片需求、疑问解答和版本测试，而非只生成好看图片。。
- E18 消费者调研与需求假设证据管理：用真实已授权访谈/评论/售后资料整理需求，并让AI模拟仅服务于研究设计而非冒充真人结论。。
- E19 多渠道商品变更与下架影响清点：在商品资料失效、停销或改版时找齐各渠道引用和剩余义务，准备一致变更而非不加区分地全量覆盖。。

## 自动化延展

流程经过正常、缺件、改版和恢复验证后，再评估重复步骤。先自动整理和草稿，再根据具体授权接现有工具；明确定时负责人、在线条件、预算和停止方式。不要从一次任务推导永久授权。

## 参考来源

- https://ads.tiktok.com/resources/help/article/how-to-troubleshoot-catalog-with-diagnostics-dashboard
- https://ads.tiktok.com/resources/help/article/list-of-catalog-product-issues-and-suggested-actions
- https://developers.google.com/google-ads/api/docs/conversions/reporting
- https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list
- https://docs.frappe.io/crm/deal
- https://docs.frappe.io/erpnext/delivery-note
- https://docs.frappe.io/erpnext/pick-list
- https://docs.frappe.io/erpnext/quotation
- https://docs.frappe.io/erpnext/sales-invoice
- https://docs.frappe.io/erpnext/sales-return
- https://kitsu.cg-wire.com/guides/review-publishing/review/
- https://shopify.dev/docs/api/admin-graphql/latest/objects/return
- https://shopify.dev/docs/api/customer-privacy
- https://shopify.dev/docs/apps/build/inventory-management-apps/manage-quantities-states
- https://shopify.dev/docs/apps/build/orders-fulfillment/returns-apps
- https://shopify.dev/docs/apps/build/webhooks
- https://shopify.dev/docs/apps/build/webhooks/verify-deliveries
- https://shopify.dev/docs/apps/launch/protected-customer-data

来源为核查起点，接口和政策以实际接入时版本为准。此文未复制第三方实现；实际能力见发布支持矩阵。
