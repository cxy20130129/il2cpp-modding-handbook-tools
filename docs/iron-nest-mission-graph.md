# Iron Nest：任务图节点语法与「极限反炮兵」拆解

数据来源：2026-11-24 本机 `Extreme Counter Battery 8.7.0` 插件构建任务时打印的 dump，原始文件在 `examples/iron-nest/mission-dumps/`。游戏本体 Unity 6000.3.21f1 / metadata v39。

这份文档记录**从运行中的任务图直接读出来的明文结构**，不含推测。行号和节点编号对应 2026-11-24 的构建，游戏或插件更新后要重新 dump。

## 1. 为什么这份数据比逆向字符串有用

之前想拿令牌语法，走的是反汇编 native `.cctor`（`0x4190A0`）、在 `stringliteral.json` 里翻明文的路子——正则在 native 代码里拼，明文不在 dump.cs，死路。

真正的捷径：**插件把任务图节点连参数一起打印了出来**。`structure_new.txt` 就是「极限反炮兵」的完整节点图，`result.txt` 是插件对基础任务做的每一处修改的逐行记录。不用进游戏、不用等日志、不用玩一遍任务。

拿这份数据的方法：让构建插件把自己的 `MissionGraph` 节点遍历打印。字段在 `FireMissionTokenProcessor` / `GraphNode` 上，见 `iron-nest-timer-and-tokens.md`。

## 2. 节点通用格式

```text
[编号] Node name='<节点类>' <参数...> | out: <后继编号> in: <前驱编号>
```

- `name='X(Clone)'`：Unity 实例化后的节点名，`(Clone)` 是 `Instantiate` 副本。基础任务里没有 `(Clone)`，说明那是原始预制体节点。
- `out` / `in`：节点图的边。**`-` 表示没有连接**。`out` 可以多个（分支），`in` 也可以多个（汇合）。
- 部分节点 `name` 为空（如 `[52] Node | out: 11 in: 8`）——这些是插件新插入的无名 `GameObject` 容器，靠 `in/out` 串进主链。

## 3. 节点类型速查表

### 状态节点（State_*，主动作）

| 节点 | 关键参数 | 作用 |
|---|---|---|
| `State_Start` | — | 图入口 |
| `State_End` | — | 图终点，任务完成 |
| `State_WaitSeconds` | — | 等待，时长在节点其他字段（本次 dump 未打印） |
| `State_TeleprinterText` | `key='<字符串键或原文>'` | 电传打字机电报。`key` 可以是本地化键（`STR_MISSION_ARTILLERY_3`），也可以直接是带富文本的中文原文（见 4.1） |
| `State_ClearTeleprinter` | — | 清空电报屏 |
| `State_ClearSignalAlarm` | — | 关警报 |
| `State_SendSceneNotification` | — | 场景通知 |
| `State_StartTimer` | `init=<秒>` `prefab=True` | 启动反炮兵计时器，`init` 是初始秒数 |
| `State_PauseTimer` / `State_UnpauseTimer` / `State_StopTimer` | — | 暂停 / 恢复 / 停止计时器 |
| `State_TimerAddTime` | `time=<秒>` `mod=Add\|Set\|Subtract\|Reset` | 改计时器，见 `iron-nest-timer-and-tokens.md` |
| `State_GenericTimer` | `timer='MissionTime'` `sec=<秒>` | 通用计时器，插件用它做 46000 秒的任务时限 |
| `State_SpawnMapEntity` | `id=<实体ID>` `num=<数量>` | 刷兵，`id` 对应 `entities.txt` 里的实体 |
| `State_SetTurretLocation` | — | 重定位玩家炮塔 |
| `State_AddRequisitionPoints` | — | 加请求点数 |
| `State_SplitBranch` / `State_ConditionBranch` | — | 分支 / 条件分支 |

### 事件节点（Event_*，等待触发）

| 节点 | 关键参数 | 作用 |
|---|---|---|
| `Event_ShellLanded` | — | 第一发炮弹落地 |
| `Event_TimeInterval` | — | 定时间隔触发 |
| `Event_EntityDestroyed` | `destroyed=<数量>` `lookup=All\|Any\|Count` `once=True\|False` `filter=[Role:Contains:Graph:'':role=<角色>;]` | 歼灭事件，见 4.2 |

## 4. 关键语法细节

### 4.1 电报文本直接内嵌

极限反炮兵的开幕电报（`structure_new.txt` 节点 `[06]`）不用本地化键，直接把富文本塞进 `key`：

```text
key='
. . .
. . .
<i><b><smallcaps>最高统帅部</smallcaps>致<smallcaps>铁巢：</smallcaps></b></i>
敌军部署大量兵力，试图重夺雷阿尔城。据情报，敌人还部署了少量火炮。
至少摧毁所有敌方火炮和 5 支步兵。
.
<b>注意：</b>反炮兵将在第一发炮弹落地后开始计时。
.
<i><b><smallcaps>光荣归于卡斯蒂利亚! ! !</smallcaps></b></i>
  - - -'
```

富文本标签：`<i>` 斜体、`<b>` 粗体、`<smallcaps>` 小型大写、`.` 单独一行是空行、`  - - -` 是落款分隔。自定义电报直接照这个格式写。

其余电报走本地化键：`STR_MISSION_ARTILLERY_1` 到 `_10`。`result.txt` 记录 `teleprinters=10 intro=True alert=True startTimer=True`——10 个电报节点，开场、警报、计时器奖励各路都有。

### 4.2 歼灭事件过滤器语法

```text
filter[Role:Contains:Graph:'':role=Artillery;]
```

拆解：`Role` 字段 `Contains` 值 `Graph:''` 里的 `role=Artillery`。多个条件用 `;` 分隔，可以叠加否定：

```text
filter[Role:Contains:Graph:'':role=EnemyGroup1;Role:NotContains:Graph:'':role=Artillery;]
```

`lookup` 三种模式：
- `All`：全部指定角色都被消灭
- `Any`：任意一个被消灭
- `Count`：`destroyed` 数量达到阈值

`once=True` 只触发一次，`False` 可重复。

## 5. 极限反炮兵 vs 基础反炮兵：插件做了什么

`result.txt` 是插件作者在构建时打印的逐行修改记录，对照 `structure_base.txt`（基础任务「炮兵入门」，52 节点）和 `structure_new.txt`（极限反炮兵，61 节点）：

| 项 | 基础任务 | 极限反炮兵 | 来源 |
|---|---|---|---|
| 初始计时 | 300 秒 | **60 秒** | `StartTimer before=300` → `-> 60` |
| 击毁火炮加时 | +100 秒 | **+40 秒** | `TimerAdd before: Time=100` → `+40` |
| 第二组加时 | 500 秒 Set | 200 秒 Add | `[60] Node time=200 mod=Add` — **建节点+删旧节点，不在 JSON 规则内**，见 `docs/mission-rules.md` 第 5 节 |
| 步兵 | 4 个（改 20） | 20 个 | `spawn[0]` |
| 炮兵 | 3 + 2 | 8 + 2 | `spawn[4]` / `spawn[5]` |
| 碉堡→补给仓库 | 无 | 3 个 | `spawn[3]` 改自 FinalHarvest |
| FDC | 无 | 2 个 | `spawn[7]` 改自 FinalHarvest |
| 敌方铁巢 | 无 | 1 个（hp4 arm1 5星） | `iron nest via CopyNode: ok` |
| 任务时限 | — | 46000 秒 | `[49] State_GenericTimer sec=46000` |

**核心机制链**（按 `in/out` 串）：

```text
[00] Start
 → [22] 清电报 → [23] 清警报 → [19] 定位炮塔 → [48] 场景通知
 → [49] GenericTimer(46000) → [01] 刷20步兵 → [02][03] 刷观测员
 → [04] 刷3补给 → [05] 刷8炮兵 → [32] 刷2 FDC
 → [51] 刷敌方铁巢 → [50] 通知 → [06] 开幕电报
 → [43] 分支 → [44] 等待 → [42] 场景通知
 → [07] 等待 → [08] "情报有误/敌方铁巢测距/紧急转移"电报
 → [52] 无名节点 → [11] StartTimer(60) → [10] 电报 STR_MISSION_ARTILLERY_3
```

注意 `[11] StartTimer` 的 `in` 是 `[52]`，而 `[52]` 的 `in` 是 `[08]`——**计时器不是任务一开始就走，是"情报有误"电报之后才启动**。但开幕电报里写"第一发炮弹落地后开始计时"，另有 `[09] Event_ShellLanded → [53]` 挂在旁边。两条链的关系要看插件实际连线，dump 里 `[53]` 无 out，说明那条事件链在本次构建中没接进主流程。

### 加时逻辑

```text
[12] Event_EntityDestroyed(all 炮兵) → [28] PauseTimer → [33] WaitSeconds → [13] 电报_5
[14] Event_EntityDestroyed(any 炮兵, 可重复) → [15] TimerAddTime(+40) → [16] 电报_4
[25] 刷2伏兵炮兵 → [29] UnpauseTimer → [24] 电报_6 → [27] 电报_7 → [21] Event(all 炮兵) → [20] StopTimer
```

打掉一门炮 → +40 秒；全打完 → 暂停计时 → 刷 2 门伏兵 → 恢复计时 → 打完停表。这就是任务名的由来：极限时间 + 反炮兵。

## 6. 实体清单

`entities.txt` 记录构建后的 37 个实体实例：

| 实体 | 数量 | 角色 |
|---|---|---|
| `EnemyInfantry` | 20 | Enemy, Infantry |
| `EnemyArtillery` | 8 + 2 | Target, Artillery（两组不同 role 组合） |
| `EnemyBunker` → 补给仓库 | 3 | Enemy, Fortification, 3星 |
| `EnemyFDC` → 炮兵指挥中心 | 2 | Target, EnemyGroup1, 3星 |
| `EnemyIronNest` | 1 | Target, EnemyGroup3, Artillery, hp4 arm1 5星 |
| `AllySpotter` | 3 | Spotter |

区域（zone）：`spotter1`/`spotter2`/`ally`/`enemy`/`Turret`/`spotter3`，形状 `Single` 或 `Composite`（多 region）。刷兵用 `locType=Zone|Relative`、`rel=Self|ContextEntity`、`fuzzy=True`。

## 7. 复现方法

1. 保留 `Extreme Counter Battery` 插件，它构建任务时会往 `MissionDump/` 写这四个文件。
2. 若插件不写，用 BepInEx 插件 hook 任务构建入口，遍历 `MissionGraph` 节点，按上面第 3 节的字段格式化输出。
3. dump 比玩游戏可靠：不依赖进关、不依赖 GPU/内存、不依赖视觉自动化。

`templates/bepinex-mod/` 的模板已能编译，扩展它即可打印节点。
