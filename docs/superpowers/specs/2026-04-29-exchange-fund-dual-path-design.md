# 场内/场外基金双通道修复设计

## 背景
当前项目并非完全不支持场内基金，而是把场内 ETF/LOF 与场外基金混在同一套字段和判定逻辑里，导致以下问题：

1. 是否“场内”依赖 quote 是否成功返回，而不是基金类型本身。
2. 后端 `valuation` / `marketPrice` 语义错位：实际是“valuation≈现价，marketPrice≈净值”。
3. 前端 `exchange` tab 用 `fund.price > 0` 判断场内，导致 quote 失败或被清零时基金直接消失。
4. 场内现价与净值差异过大时，后端直接把 `valuation` / `valuationRate` / `premiumRate` 清零，用户感知为“场内基金拿不到”。
5. 前后端 secid 规则不一致，fallback 路径容易漏掉部分场内代码。

## 目标
本次修复的目标是：

- 场内 ETF/LOF 不再因为 quote 失败而从结果中消失。
- 场内/场外识别基于明确规则，而不是接口命中结果。
- 后端内部数据语义统一，前端展示继续兼容现有 UI。
- `exchange` tab 使用显式类型标记，不再依赖 `price > 0`。
- 保留异常保护，但不把整只基金“清空”。

## 非目标
本次不做以下事情：

- 不重做整套前端 UI/表格结构。
- 不一次性重命名所有历史字段并强制前端全量迁移。
- 不重构通知系统全部逻辑，只修与场内/场外判定直接相关的输入数据。

## 方案对比

### 方案 A：最小补丁
只修 `exchange` 过滤、secid 规则、空值回退。

- 优点：改动小、风险低。
- 缺点：字段语义继续混乱，后续还会反复出问题。

### 方案 B：双通道修复（采用）
显式区分场内 ETF/LOF 与场外基金，拆分后端取数链路，并向前端补充明确类型标记。

- 优点：能解决当前场内基金丢失问题，同时控制改动范围。
- 缺点：需要改后端、前端和少量类型定义。

### 方案 C：彻底重构
重定义 DTO、前端模型、监控输入、历史数据字段。

- 优点：最干净。
- 缺点：改动面过大，不适合当前快速修复。

## 设计概览
采用双通道方案：

1. **分类固定化**：先判断基金是否场内交易，不再依赖 quote 是否命中。
2. **后端分链路取数**：
   - 场内：行情接口 + 净值接口/HTML 解析
   - 场外：净值接口/AKShare
3. **结果对象显式带类型**：新增 `isExchangeTraded` 字段。
4. **前端按类型过滤**：`exchange` tab 使用 `isExchangeTraded`。
5. **异常保底**：场内 quote 失败时保留基金，并尽量返回净值和限制信息。

## 详细设计

### 1. 基金类型识别
新增一个统一函数，例如：

- `is_exchange_traded_fund(code: str, name: str = "") -> bool`

判定规则优先级：

1. 代码规则优先：典型场内代码段（如 5xxxx、15xxxx 非 159xxx、159xxx、16xxxx、部分 12xxxx/50xxxx/51xxxx/52xxxx/53xxxx/58xxxx/59xxxx）。
2. 名称辅助：包含 `ETF` 或 `LOF` 时强化判断。
3. 结果在一次请求内固定，不因 quote 成败改变。

该函数将被后端主流程、历史数据、必要的前端 fallback 共同复用或对齐。

### 2. 后端数据模型语义
保持现有接口字段，避免前端大面积重写，但明确内部语义：

- `valuation`: 现价（对场内）/ 当前净值（对场外）
- `valuationRate`: 对应上面数值的涨跌幅
- `marketPrice`: 净值（优先展示基金净值）
- `marketPriceRate`: 净值涨跌幅
- `premiumRate`: 仅当场内现价与净值都有效时计算
- `isExchangeTraded`: 新增，明确是否场内交易

说明：字段名仍不理想，但这次先做到“语义稳定且前端兼容”，而不是一次性破坏式改名。

### 3. 后端主流程改造
在 `get_qdii_funds()` 中：

1. 初始化每只基金时写入 `isExchangeTraded`。
2. 场内基金和场外基金分开收集代码。
3. 场内基金：
   - 尝试取 quote，成功则填入 `valuation` / `valuationRate`
   - 再取 NAV，填入 `marketPrice` / `marketPriceRate`
4. 场外基金：
   - 直接走 NAV 路径
   - `valuation` 与 `marketPrice` 可同值，或保持当前前端兼容策略下的合理赋值
5. 所有基金不因任一路径失败而丢失。

### 4. 溢价率与异常保护
保留异常保护，但改策略：

当前问题是价差超过 50% 直接把现价和涨跌幅清零，造成“场内消失”。

改为：

- 如果现价与净值差异超过阈值：
  - 不删除基金
  - 不清空 `isExchangeTraded`
  - 仅将 `premiumRate` 置 0，或将现价标记为不可信但保留原始值
- 前端仍可看到该基金，至少能看到净值与基础信息

推荐做法：
- 保留 `valuation`
- 将 `premiumRate` 置 0
- 日志记录异常价差，便于后续追查

### 5. 历史数据与 1 年涨跌幅
当前 `is_exchange_traded = fund.get("valuation", 0) > 0` 是错误信号源。

改为：

- 用显式 `isExchangeTraded` 决定历史数据路径
- 场内 ETF/LOF 走交易价格历史数据（若现有实现可用）
- 场外基金走累计净值历史数据

如果现有历史 ETF 路径仍不稳定，本次至少先把“是否场内”的判断改正确，避免因 `valuation=0` 导致错误分支。

### 6. 前端改造
前端最小必要修改：

1. `FundData` 增加 `isExchangeTraded?: boolean`
2. `mapFundDataToFund()` 把该标记传入 UI 模型
3. `Fund` 类型增加 `isExchangeTraded: boolean`
4. `exchange` tab 过滤从 `fund.price > 0` 改为 `fund.isExchangeTraded`
5. 前端 fallback 的 secid 规则与后端对齐，避免两边判断不一致

展示层仍保留：
- 现价 = `price`
- 净值 = `netValue`
- 溢价率 = `premiumRate`

## 数据流

### 场内基金
1. 基于代码/名称识别为场内
2. 请求行情接口获取现价/涨跌幅
3. 请求净值或 HTML 页面获取 NAV/限购
4. 合并结果：
   - `valuation` = 现价
   - `marketPrice` = 净值
   - `premiumRate` = (现价 - 净值) / 净值
   - `isExchangeTraded` = true
5. 即使行情失败，也仍返回基金记录与 `isExchangeTraded=true`

### 场外基金
1. 基于代码/名称识别为场外
2. 请求净值数据
3. 合并结果：
   - `valuation` = 当前净值
   - `marketPrice` = 当前净值
   - `premiumRate` = 0
   - `isExchangeTraded` = false

## 兼容性
- `/api/funds` 返回结构向后兼容，新增字段 `isExchangeTraded`。
- 前端旧字段映射可继续工作。
- 监控、触发器等消费 `FundData` 的地方只需容忍新增字段，不要求立刻重写。

## 错误处理
- 行情接口失败：场内基金保留，返回净值侧数据和 `isExchangeTraded=true`。
- HTML/NAV 解析失败：保留行情与基础信息，不把基金删除。
- 两边都失败：保留基础基金记录，数值字段为 0，但类型仍明确。
- 异常记录写日志，便于区分“接口无数据”和“合并策略清空”。

## 测试策略

### 后端验证
至少验证这些代码：
- 场内 ETF：`513100`, `513300`, `159659`, `159696`, `159501`, `513870`, `159941`
- 场外/LOF 对照：`160213`, `161128`, `161226`

检查点：
- 响应中所有基金都存在
- 场内基金 `isExchangeTraded=true`
- 场内基金即使 quote 失败也不会消失
- `exchange` tab 所需字段不依赖 `valuation > 0`
- 溢价率异常时基金仍可见

### 前端验证
- `exchange` tab 可稳定看到预置场内基金
- `all` / `nasdaq` tab 不受影响
- 现价、净值、溢价率列仍正常显示
- 监控开关和触发器设置不因新增字段失效

## 实施边界
预计涉及文件：
- `server.py`
- `App.tsx`
- `types.ts`
- `types/fund.ts`
- `services/fundService.ts`

必要时可新增一个小型辅助函数区域，但不做大规模重构。

## 风险
1. 东方财富行情接口本身偶发断连，修复后仍可能出现“现价为空”，但不应再导致基金消失。
2. 现有字段命名历史包袱仍在，后续如果继续演进，建议第二阶段做真正 DTO 清理。
3. 1 年涨跌幅的 ETF 历史链路如果本身有缺陷，本次只能先修分类依据，未必一次解决全部历史表现问题。

## 验收标准
满足以下条件即视为本次修复成功：

1. 预置场内基金在 `/api/funds` 中稳定返回，不因 quote 失败而缺失。
2. 前端 `exchange` tab 显示基于 `isExchangeTraded`，不再基于 `price > 0`。
3. 场内基金不会因价差保护逻辑而从 UI 中“消失”。
4. 场外基金原有展示基本不回退。
5. 接口字段保持兼容，现有页面可继续工作。
