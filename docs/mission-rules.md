# 任务规则：把「极限反炮兵」从逆向变成配置

`missions/extreme-counter-battery.json` 是「极限反炮兵」相对基础任务「炮兵入门」的字段差异。它由 `scripts/build_mission_rules.py` 从三份实测 dump 自动生成，BepInEx 插件在任务加载后按这份 JSON 改节点字段。

改电报文案、计时秒数、刷兵数量，只改 JSON，不用重新逆向、不用重新编译插件。

> **先读这段：规则不是完整复刻。**
> 它只改基础任务里**已有节点的标量字段**（8 条）。极限反炮兵的第二组 **+200 秒加时**、敌方铁巢插入、胜利条件连线、任务时限都不在规则内。JSON 的 `not_covered` 段落由生成器自动列出这些缺口。跑完补丁后的任务是「基础任务 + 8 处数值/文案改动」，不是完整的极限反炮兵。

## 1. 数据从哪来

| 文件 | 作用 |
|---|---|
| `examples/iron-nest/mission-dumps/structure_base.txt` | 基础任务「炮兵入门」52 个节点的完整参数 |
| `examples/iron-nest/mission-dumps/structure_new.txt` | 极限反炮兵 61 个节点的完整参数 |
| `examples/iron-nest/mission-dumps/result.txt` | 构建插件逐行打印的修改记录，作为证据附在规则里 |

这三份是插件构建任务时自己打印的明文，不是逆向猜出来的。重新生成规则：

```powershell
python .\scripts\build_mission_rules.py -o .\missions\extreme-counter-battery.json
```

游戏或插件更新后，重新产生这三份 dump 再跑一次脚本即可。

## 2. 规则文件格式

```json
{
  "mission": "ExtremeCounterBattery",
  "base_graph": "Artillery Introduction",
  "rules": [
    {
      "index": 11,
      "type": "State_StartTimer",
      "set": { "InitalTime": "60" },
      "was": { "InitalTime": "300" },
      "evidence": ["StartTimer before=300", "StartTimer -> 60"]
    }
  ]
}
```

| 键 | 含义 |
|---|---|
| `index` | **基础任务**里的节点下标（`NodeGraph.nodes` 的索引）。插件在基础任务上跑，这个下标才稳定。 |
| `type` | 节点类名，运行时校验。类型对不上就跳过并打日志，防止游戏更新后改错节点。 |
| `set` | 要写入的字段。键是 dump.cs 里的**真实 C# 字段名**，值是新值。 |
| `was` | 基础任务的原值，仅作记录和验证用，插件不读它。 |
| `evidence` | 来自 `result.txt` 的原文证据，方便追溯。 |

当前 8 条规则覆盖：

| 节点 | 字段 | 改前 → 改后 |
|---|---|---|
| `[1]` 步兵 | `NumberToSpawn` | 4 → 20 |
| `[4]` AllyGroup→补给仓库 | `ID`, `NumberToSpawn` | AllyGroup/20 → EnemyBunker/3 |
| `[5]` 炮兵主力 | `NumberToSpawn` | 3 → 8 |
| `[6]` 开幕电报 | `Text.Key` | 本地化键 → 中文富文本 |
| `[8]` 情报有误电报 | `Text.Key` | 本地化键 → 中文富文本 |
| `[11]` 反炮兵计时器 | `InitalTime` | 300 → 60 |
| `[15]` 击毁加时 | `Time` | 100 → 40 |
| `[32]` 观测员→FDC | `ID`, `NumberToSpawn` | AllySpotter/1 → EnemyFDC/2 |

## 3. 可配置字段与 C# 字段的对应

脚本按这张表把 dump 里的短参数名翻译成真实字段名（来自 `dump.cs`）：

| dump 参数 | C# 字段 | 类型 | 所在节点 |
|---|---|---|---|
| `id` | `ID` | string | `State_SpawnMapEntity` |
| `num` | `NumberToSpawn` | int | `State_SpawnMapEntity` |
| `init` | `InitalTime` | float | `State_StartTimer` |
| `time` | `Time` | float | `State_TimerAddTime` |
| `mod` | `ModifyType` | enum | `State_TimerAddTime` |
| `key` | `Text.Key` | string | `State_TeleprinterText` |
| `sec` | `InitialSeconds` | float | `State_GenericTimer` |
| `timer` | `TimerID` | string | `State_GenericTimer` |

`Text.Key` 是嵌套字段：先取节点的 `Text` 对象，再写它的 `Key`。插件同时把值写进 `Raw`，因为 `TextIdentifier.Get()` 可能优先读 Raw。本地化键和内联富文本都适用。

`ModifyType` 的合法值：`Add`、`Set`、`Subtract`、`Reset`（拼写来自游戏源码）。

## 4. 插件怎么应用规则

`templates/bepinex-mod/MissionPatch.cs` 里的 `Patch_MissionGraphBuild`：

```csharp
[HarmonyPatch(typeof(MissionGraph), "OnMissionLoaded")]
```

`OnMissionLoaded` 在游戏加载任务时调用，此时 `nodes` 已经就绪。补丁：

1. 找规则文件（依次查 `BepInEx/plugins/missions/`、`BepInEx/config/missions/`、游戏根 `missions/`、当前目录 `missions/`）。
2. 校验当前任务是不是规则对应的基础任务（比较 `MissionID`，忽略大小写和空格）。
3. 按 `index` 取节点，核对 `type`，逐字段反射写入。
4. 每个字段打一行日志：`[mission] [11] InitalTime: 300 -> 60`。

部署：

```powershell
# 编译
dotnet build .\templates\bepinex-mod\BepInExMod.csproj -c Release `
  -p:IronNestDir="C:\Games\Iron Nest Heavy Turret Simulator"

# 放插件和规则
copy .\templates\bepinex-mod\bin\Release\net6.0\IronNestBepInExTemplate.dll `
     "C:\Games\Iron Nest Heavy Turret Simulator\BepInEx\plugins"
mkdir "C:\Games\Iron Nest Heavy Turret Simulator\BepInEx\plugins\missions"
copy .\missions\extreme-counter-battery.json `
     "C:\Games\Iron Nest Heavy Turret Simulator\BepInEx\plugins\missions"
```

启动游戏，进「炮兵入门」，看 `BepInEx/LogOutput.log` 里的 `[mission]` 行。

## 5. 边界：规则改不了什么

JSON 规则**只改已有节点的标量字段**。以下改动做不到，仍由构建插件负责：

- **改连线**（`out` / `in`）：极限反炮兵把 StartTimer 接到"情报有误"电报之后，这类拓扑变化不是字段赋值。
- **插入节点**：FDC 暂停触发器 `[54]`/`[55]`、胜利条件链 `[57]`-`[58]`、铁巢 `[51]` 都是新节点。
- **删除节点**：基础任务 `[30]` 的 `TimerAddTime(500, Set)` 在极限版里被删掉。脚本检测到 `[30]` 在两份 dump 里类型不同，会跳过，不生成规则。
- **实体外观/角色/星级**：`[32]` 从 AllySpotter 改成 EnemyFDC 时，规则只改了 `ID` 和 `NumberToSpawn`；角色、血量、星级、图标仍来自基础任务的预制体配置。要完整替换需改这些字段或复制节点。

### 第二组 +200 秒加时是功能缺口

这条单独说清楚，因为它不像其它边界那样只是"外观差异"：

- 基础任务 `[30]` 是 `State_TimerAddTime time=500 mod=Set`，被挂在步兵数量事件后面。
- 极限反炮兵**删掉了这个节点**（`result.txt`: `removed TimerAdd(Set 500)`），另在 `[60]` 插入一个无名 `Node time=200 mod=Add`，挂在敌方铁巢歼灭事件 `[59]` 后面（`structure_new.txt:80`）。
- 规则生成器按 base/new 同索引比对，也只改已有节点，所以这条加时**没有任何规则**。补丁跑完后，任务里保留的是基础任务的 Set(500) 逻辑，+200 Add 不会出现。

这不是文档措辞问题，是实际行为差异。要补上它必须扩展规则格式（例如支持 `insert` 操作和 `in`/`out` 连线），超出当前设计。选择是不扩格式、在 JSON 的 `not_covered` 里显式声明缺口。

所以"配置化"的范围是**数值和文案**，不是完整任务图。复杂的任务变形仍需插件代码或重新 dump 后扩展规则格式。

## 6. 派生新任务

1. 复制 `missions/extreme-counter-battery.json`，改 `mission` / `base_graph` 和 `rules`。
2. 只写真正要改的字段，`set` 里的键必须是上表的 C# 字段名。
3. 编译好的插件从固定文件名读取，派生任务要么改 `RuleFileName`，要么把新规则放到搜索路径的第一个位置。
4. 游戏更新后用 `scripts/field_offsets.py` 和 `scripts/find_type.py` 核对字段名是否变了；反射写入失败会在日志里报 `cannot set <字段>`。

## 7. 验证清单

- [ ] `python -m unittest discover -s tests` 全过
- [ ] `dotnet build ... -c Release` 0 错误
- [ ] 规则文件里 `index` 都小于基础任务节点数（52）
- [ ] 进游戏后 `LogOutput.log` 里每个 `[mission]` 行的 `->` 右边与 JSON 的 `set` 一致
- [ ] 没有 `expected X, got Y` 或 `cannot set` 错误
