# Iron Nest：反炮兵计时器与任务令牌实测笔记

来源：本机 `C:\Games\Iron Nest Heavy Turret Simulator`，Unity 6000.3.21f1，metadata v39，`dump.cs` 28 MB。行号对应 2026-11-24 的 dump；游戏更新后要重新 dump。

这份文档只记录**从 dump 里直接读出来的事实**和明确标注的推断。不确定的地方留给运行时探针验证。

## 1. 加载器是 BepInEx 6，不是 MelonLoader

`BepInEx/LogOutput.log` 显示：

```text
BepInEx 6.0.0-be.785
Running under Unity 6000.3.21f1
Loading [Extreme Counter Battery 8.7.0]
```

`BepInEx/interop/Assembly-CSharp.dll` 已经生成。写插件用 `BepInEx.Unity.IL2CPP.BasePlugin` + Harmony，见 `templates/bepinex-mod/`。

## 2. CounterBatteryTimer（`dump.cs:11386`，TypeDefIndex 217）

`[DisallowMultipleComponent] [AddComponentMenu("Missions/Counter Battery Timer")]`，全局命名空间，`MonoBehaviour`。

### 字段偏移

| 偏移 | 字段 | 说明 |
|---|---|---|
| `0x20` | `float totalDurationSeconds` | Inspector 配置的初始时长 |
| `0x28` | `UnityEvent onTimerStarted` | 真正启动时触发 |
| `0x30` | `CounterBatteryTimer.SecondsChangedEvent onTimerTick` | `UnityEvent<float>`，每帧传剩余秒数 |
| `0x38` | `UnityEvent onTimerExpired` | 归零时触发，在失败 UI 之前 |
| `0x40` | `UnityEvent onTimerPermanentlyStopped` | 永久停止后不再接受加时/启动 |
| `0x48` | `UnityEvent onTimerPaused` | 暂停 |
| `0x50` | `UnityEvent onTimerUnpaused` | 恢复 |
| `0x58` | `bool verbose` | 调试日志开关 |
| `0x5C` | `float _remainingSeconds` | 运行时剩余 |
| `0x60` | `bool _running` | 运行时状态 |
| `0x61` | `bool _expired` | 是否已归零 |
| `0x62` | `bool _permanentlyStopped` | 是否已永久停止 |
| `0x68` | `double endTime` | 基于绝对时间的到期点 |

静态单例 `Instance` 的后备字段 `<Instance>k__BackingField` 在 `0x0`（静态存储）。

### 方法与 RVA

| 方法 | RVA | 用途 |
|---|---|---|
| `get_Instance` / `set_Instance` | `0x519330` / `0x5193D0` | 单例访问 |
| `get_TimeRemaining` | `0x519380` | 读剩余秒数 |
| `get_IsRunning` | `0x3EDBA0` | — |
| `get_IsExpired` | `0x5064D0` | — |
| `get_IsPermanentlyStopped` | `0x519370` | — |
| `Awake` / `OnDestroy` / `OnEnable` | `0x5186F0` / `0x518950` / `0x518A20` | 生命周期 |
| `ResetRuntimeState` | `0x518A20` | 与 `OnEnable` 同 RVA，可能被内联/共用 |
| `Update` | `0x519140` | 每帧更新并触发 `onTimerTick` |
| `Init(float InitalTime)` | `0x518750` | 注意游戏源码把 Initial 拼成了 **Inital** |
| `StartTimer()` | `0x518E50` | 首次启动 |
| `AddTime(float seconds)` | `0x518300` | 加时 |
| `SetTime(float seconds)` | `0x518C80` | 直接设置剩余时间 |
| `PauseTimer()` / `UnpauseTimer()` | `0x518A90` / `0x518FE0` | 暂停/恢复 |
| `PermanentlyStop()` | `0x518BF0` | 永久停止 |

从插件里改时间最稳的入口是 `CounterBatteryTimer.Instance.SetTime(60f)` / `AddTime(40f)`；Hook 用 `Init` / `StartTimer` 的 Prefix 改参数。别 patch `Update`，日志会刷屏。

### 任务图怎么驱动它

| 节点类 | dump.cs | 关键字段 | 入口 RVA |
|---|---|---|---|
| `SleepyNodes.State_StartTimer` | 62703 | `InitalTime` `0x48`，`Prefab_BatteryTimer` `0x50`，`spawnedTimer` `0x58` | `OnEnter` `0x4E8FC0` |
| `SleepyNodes.State_TimerAddTime` | 62760 | `ModifyType` `0x48`，`Time` `0x4C` | `OnEnter` `0x4E9BE0` |
| `SleepyNodes.State_PauseTimer` | 62678 | `To` `0x40` | `OnEnter` `0x4E6C30`，`OnExecute` `0x4E6D10` |
| `SleepyNodes.State_UnpauseTimer` | 62784 | `To` `0x40` | `OnEnter` `0x4EA6A0`，`OnExecute` `0x4EA780` |
| `SleepyNodes.State_StopTimer` | 62728 | `RemoveFromScene` `0x48`，`RemoveFromSceneDelay` `0x4C` | `OnEnter` `0x4E91E0` |

`State_TimerAddTime.ModifyTypes`（`dump.cs:62746`）：`Add=0`、`Set=1`、`Subtract=2`、`Reset=3`。你的 `MissionDump/result.txt` 里 `TimerAdd(artillery) -> +40`、`TimerAdd before: Time=500 modify=Set` 就是这两类节点。

现有 `BepInEx/plugins/CustomMissionMod.dll` 里能直接提取到 `Patch_TimerInit`、`Patch_TimerStart`、`Patch_PauseTimer`、`Patch_TimerAddTime`、`Patch_TimerSetTime`、`Patch_CardPopulate`、`Patch_CardInit`、`Patch_MissionGraphUpdate`，说明这些入口已被实际验证过。

## 3. FireMissionTokenProcessor（`dump.cs:36800`，TypeDefIndex 679）

静态类，负责把任务文本里的令牌替换成坐标/方位/剩余时间等。正则字段：

- `tokenRegex` `0x0`
- `parametereRegex` `0x8`（原文拼写如此）
- `parameterePartRegex` `0x10`

### 入口

| 方法 | RVA |
|---|---|
| `ParseCommand(string)` | `0x416370` |
| `ParseParameter(string)` | `0x4168B0` |
| `ProcessBlock(string, Dictionary<string, GridReference>)` | `0x416F40` |
| `ProcessLine(string, int, LineEvalContext)` | `0x417130` |
| `ProcessToken(Command, LineEvalContext)` | `0x417480` |

### 已实现的格式器（即可能的令牌名）

| 方法 | RVA | 推断的令牌 |
|---|---|---|
| `FormatBearing` | `0x414170` | `bearing` |
| `FormatDistance` | `0x4146E0` | `distance` |
| `FormatGrid` | `0x414990` | `grid` |
| `FormatRegion` | `0x414D20` | `region` |
| `FormatRemaining` | `0x4151D0` | `remaining` |
| `FormatTimer` | `0x4154F0` | `timer` |
| `FormatDirection` | `0x414420` | `direction` |

对应小写字符串确实存在于 `stringliteral.json`：`bearing` `0x28ADF98`、`distance` `0x284A6C8`、`grid` `0x2868118`、`region` `0x28309F0`、`remaining` `0x2831030`、`timer` `0x28536D0`、`direction` `0x2849990`。

**注意**：正则分隔符和参数语法在 native `.cctor`（`0x4190A0`）里构造，字符串字面量不直接出现在 `dump.cs` 或 GameAssembly.dll 的明文里。上面只是命令名推断，不是完整语法。用 `templates/bepinex-mod/` 的 `Patch_TokenProbe` 跑一遍任务，`cmd=` 日志会给出真实命令串。

### 数据结构

- `Command`（`dump.cs:36646`）：`Raw` `0x10`、`Cmd` `0x18`、`Modifiers` `0x20`、`Parameters` `0x28`。
- `Command.Parameter`（36604）：`Ids` `0x10`、`Index` `0x18`、`Options` `0x20`、`RandomFlagSeen` `0x28`。
- `Command.Option`（36619）：`Symbol` `0x10`、`Value` `0x18`。
- `Command.OptionSynbols`（36632，拼写错误是原游戏的）：静态 `Index`、`Add`、`Subtract`。`FormatTimer` 里分别有 lambda 检查 Add/Subtract，推断 `+N`/`-N` 是相对当前时间增减，`Index` 用于选择第几个实体。
- `LineEvalContext`（36586）：`Raw`、`LineIndex`、`SelectedIds`、`LocationContextKeys`、`noActiveMatchFound`、`implicatedRoles`、`FromPos`。

辅助解析：`TryResolveRelativePosition` `0x418610`、`TryResolveSpecialPosition` `0x418E60`、`TryResolveLocationContextKey` `0x417920`、`TryResolvePointPositionOnly` `0x417F60`、`TryResolveParameterToEntity` `0x418460`、`TryResolvePosition` `0x418730`、`TryResolveRoleToRandomEntity` `0x418860`、`StableHash` `0x4178C0`。

## 4. 射击任务卡

- `FireMissionCard`（`dump.cs:7706`）：`Apply(string distanceToTarget, string bearingToTarget, string gunElevation, string powderCharge, string shellType, string gunSelection)`，RVA `0x4FA490`。
- `FireMissionCardPrinter`（`dump.cs:7772`）：持有 `ArtilleryComputer`、`fireMissionCardPrefab`、`bearingDial`、`shellTypeDial`、`gunDial`、`targetSplitFlipDisplay`、纹理列表等。

电报文本本身不在 `dump.cs` 的这几个类里；你的 `MissionDump/result.txt` 显示 intro/alert 被替换（len 227/146），但原文需要从任务资源或运行时截获。

## 5. 最小验证路径

1. 复制 `templates/bepinex-mod` 到游戏插件目录外的工作区，按模板 README 设置 `IronNestDir` 编译。
2. DLL 放进 `BepInEx/plugins`，启动一次，确认 `[timer] Init(60)` 这类日志出现。
3. 跑一遍「极限反炮兵」，看 `[token] cmd=...` 日志，补全令牌语法表。
4. 确认后再把 Prefix 改成改参数；先改 `Init` 的时间，别动 `Update`。

所有操作只针对单机。排行榜/联机提交相关代码不要碰。
