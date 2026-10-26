# 仓储与物流

运行身份：`warehouse_logistics`。岗位参考属于可调整的方法，企业正式政策以有权负责人及当前资料为准。

## 先完成一件工作

读取获准材料，先做最小可用成果；正常、缺资料、修正和恢复都保留记录。只读资料、草稿、对外动作与业务完成分别核验。当前宿主缺某工具时说明范围，用文件退路完成独立部分。

## 三条工作配方

### 11-W1 到货到放行上架

输入：收货、批次、检验、库位。

1. 以采购/收货/批次/库位核实物收到，待检/合格/隔离分开。
2. 放行依据、系统上架和可售时点分别回证，批次剩余期不同于包装总期。
3. 交付收货到上架差异，无质量证据不自动放行或加库存。

例外与停止：系统数量不证明实物。

输出：到货与放行差异。验收：无质量证据不自动放行。

文件例：“批次B1实收20，合格12待检8，系统上架10；效期2025-06-30。做放行上架差异。”

纠错与恢复：按原来源/提取/规则/回答层修复，核依赖及人改，保留旧版；从工作区继续本流程的未决对象。完整合成输入见 [配方中的文件用例](../catalog/workflows.json)；安装包内当前配方也包含缺件/纠错示例。

### 11-W2 拣货到签收

输入：订单、预留、包裹、签收事件。

1. 用订单行实际数量、同一时点可用/预留与拣货事件ID核拣货，不重复扣减。
2. 部分发运按包裹及商品行关联到签收、拒收、丢失；乱序/重复通知不二次扣货。
3. 交付已拣/已发/已签与剩余义务；不以补货MOQ或采购预算替代履约核验。

例外与停止：部分签收不完成整单。

输出：履约异常。验收：重复通知不二次扣货。

文件例：“订单O1需10件，预留10，已拣8；包裹P1发5已签，P2发3运输中，P1签收消息重复两次。做履约异常表。”

纠错与恢复：按原来源/提取/规则/回答层修复，核依赖及人改，保留旧版；从工作区继续本流程的未决对象。完整合成输入见 [配方中的文件用例](../catalog/workflows.json)；安装包内当前配方也包含缺件/纠错示例。

### 11-W3 调拨盘点和追溯

输入：库间事件、快照、盘点、批次。

1. 按基础单位/批次/库位/同一时点核调拨发出、在途和目的库实收。
2. 实物盘点与系统影子余额桥接，重复扫描、撤销及损耗证据单列。
3. 交付批次追溯与差异，不靠补算造实物或直接改库存。

例外与停止：时点不齐暂不可比，不调平缺口。

输出：影子库存对账。验收：补算不产生写入，不虚构实物。

文件例：“A库期初50，调拨单T1发20到B，B实收15，5在途；A盘点28，系统30。做影子库存与批次追溯。”

纠错与恢复：按原来源/提取/规则/回答层修复，核依赖及人改，保留旧版；从工作区继续本流程的未决对象。完整合成输入见 [配方中的文件用例](../catalog/workflows.json)；安装包内当前配方也包含缺件/纠错示例。

## 场景定位

以下为参考任务目录；依据实际输入和工具选择，不代表所有外部系统已连接。

- WH-01 到货计划与实收核对：识别真实到货余量而不把累计快照重复相加。
- WH-02 验收、隔离与可用库存：把实收、待检、隔离与可用库存分开。
- WH-03 上架与库位安排：提供合规库位候选并验证实际上架。
- WH-04 订单分配、拣货与复核：防止重复分配并形成可核验拣货结果。
- WH-05 面单、发运与物流跟踪：准确表达包裹物流状态与异常，区分面单和交运。
- WH-06 仓间调拨与在途核对：核对源仓、在途和目标仓数量守恒。
- WH-07 盘点差异与库存调整：同一时点比对账实并形成可审调整证据。
- WH-08 退货、拒收与重新入库：让真实退回、检验与再次可用数量闭环。
- WH-09 库龄、缺货与补货建议：用确认口径提出库存和补货建议，不自动采购。
- WH-10 批次风险定位与召回证据准备：从指定风险批次追溯现存、在途、已发与退回去向，量化链路缺口，为专业召回决定准备证据。。
- WH-11 运输损坏与丢失索赔材料闭环：区别物流异常调查与正式索赔，把包裹、交接、损坏、价值和时效证据交给授权负责人。。

## 自动化延展

流程经过正常、缺件、改版和恢复验证后，再评估重复步骤。先自动整理和草稿，再根据具体授权接现有工具；明确定时负责人、在线条件、预算和停止方式。不要从一次任务推导永久授权。

## 参考来源

- https://docs.frappe.io/erpnext/batch
- https://docs.frappe.io/erpnext/delivery-note
- https://docs.frappe.io/erpnext/immutable-ledger-in-erpnext
- https://docs.frappe.io/erpnext/pick-list
- https://docs.frappe.io/erpnext/purchase-order
- https://docs.frappe.io/erpnext/sales-return
- https://docs.frappe.io/erpnext/stock-entry
- https://docs.frappe.io/erpnext/stock-reservation
- https://docs.frappe.io/framework/user/en/api/rest
- https://github.com/frappe/erpnext/blob/03afa43c7cfea9fc9b67488e3d9e309e194cd003/erpnext/stock/doctype/purchase_receipt/purchase_receipt.py
- https://github.com/frappe/erpnext/blob/03afa43c7cfea9fc9b67488e3d9e309e194cd003/erpnext/stock/doctype/quality_inspection/quality_inspection.py
- https://github.com/frappe/erpnext/blob/03afa43c7cfea9fc9b67488e3d9e309e194cd003/erpnext/stock/doctype/stock_entry/services/material_transfer.py
- https://github.com/frappe/erpnext/blob/03afa43c7cfea9fc9b67488e3d9e309e194cd003/erpnext/stock/doctype/stock_reservation_entry/stock_reservation_entry.py

来源为核查起点，接口和政策以实际接入时版本为准。此文未复制第三方实现；实际能力见发布支持矩阵。
