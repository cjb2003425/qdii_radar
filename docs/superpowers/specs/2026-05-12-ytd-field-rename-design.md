# QDII Radar YTD 字段重命名设计

## 背景
当前系统已经把原 `oneYearChange` 的业务语义改成了“今年来（YTD）”，但字段名仍保留旧名字：
- `oneYearChange`
- `oneYearChangeAvailable`

这会持续误导维护者和调用方。

用户已确认本次采用**直接切换**：
- 后端只返回新字段
- 前端只读取新字段
- 不保留旧字段兼容层

## 目标
1. 用语义正确的字段名替换旧字段名
2. 前后端统一改为：
   - `ytdChange`
   - `ytdChangeAvailable`
3. 删除代码、类型、注释、测试、文档中的旧字段引用

## 非目标
1. 不保留向后兼容字段
2. 不新增第二套并存字段
3. 不改动 YTD 的计算口径
4. 不调整其他接口字段

## 方案选择
采用 **直接切换**。

### 原因
- 语义最干净
- 不继续背字段历史包袱
- 项目内前后端都在同仓，可一次性完成重构

### 代价
- 会破坏任何仍依赖旧字段名的外部调用方
- 必须确保仓内所有使用点同步完成替换

## 设计
### 后端
#### API 返回字段
`/api/funds` 中：
- 删除 `oneYearChange`
- 删除 `oneYearChangeAvailable`
- 改为返回：
  - `ytdChange`
  - `ytdChangeAvailable`

#### 内部变量与注释
与返回字段直接相关的赋值、占位值、缓存装配逻辑都同步改名。

可以暂时保留函数名 `get_one_year_change()` 以控制改动范围，
也可以顺手重命名为 `get_ytd_change()`；本次推荐一起改掉仓内显式命名，避免再留混乱源。

### 前端
#### 数据映射
所有从后端读取该字段的位置统一改为：
- `data.ytdChange`
- `data.ytdChangeAvailable`

#### 展示与排序
排序列仍表示“今年来”，但内部排序字段改为 `ytdChange`。

### 类型
统一替换：
- `oneYearChange?: number` → `ytdChange?: number`
- `oneYearChangeAvailable?: boolean` → `ytdChangeAvailable?: boolean`

涉及：
- `types.ts`
- `types/fund.ts`
- 前端 Fund/FundData 映射类型

### 测试
测试断言和 monkeypatch 名称同步替换为新字段名。

重点覆盖：
1. 缓存命中返回 `ytdChange`
2. 冷缓存小请求同步补算 `ytdChange`
3. 大请求仍走后台刷新
4. UI 排序/映射继续正常

### 文档
同步更新：
- `CLAUDE.md`
- 设计文档中对字段名的说明
- 任何仍提到 `oneYearChange` 的仓内说明

## 风险与缓解
### 风险 1：漏改调用点
- 缓解：全仓 grep 替换并跑测试

### 风险 2：前后端字段不一致
- 缓解：优先修改类型和映射层，再跑接口/前端相关测试

### 风险 3：外部调用方断裂
- 缓解：本次明确接受直接切换，不做兼容

## 实施步骤
1. 全仓检索 `oneYearChange` / `oneYearChangeAvailable`
2. 后端响应字段改名为 `ytdChange` / `ytdChangeAvailable`
3. 前端映射、排序、展示改名
4. 类型和测试改名
5. 文档改名
6. 运行测试与接口抽查

## 验收标准
1. 仓内不再有业务字段 `oneYearChange` / `oneYearChangeAvailable`
2. `/api/funds` 返回 `ytdChange` / `ytdChangeAvailable`
3. 页面“今年来”列展示与排序正常
4. 测试通过
