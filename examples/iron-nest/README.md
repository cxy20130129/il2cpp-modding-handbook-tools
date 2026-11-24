# Iron Nest 实战笔记

针对 Iron Nest: Heavy Turret Simulator（Unity 6 / IL2CPP）的搜索顺序和排查思路。

本机已完成一次真实 dump（Unity 6000.3.21f1 / metadata v39）。已验证的类型、字段偏移、RVA 和令牌处理器清单见 `docs/iron-nest-timer-and-tokens.md`；下面的搜索词是复现步骤，不是占位符。

## 1. 定位游戏文件

Steam → 库 → 右键游戏 → 管理 → 浏览本地文件。找：

```text
GameAssembly.dll
Iron Nest_Data\il2cpp_data\Metadata\global-metadata.dat
```

目录名以实际为准，不一定是 `Iron Nest_Data`。

## 2. Dump

```powershell
.\scripts\dump.ps1 `
  -GameAssembly "D:\SteamLibrary\steamapps\common\Iron Nest\GameAssembly.dll" `
  -Metadata     "D:\SteamLibrary\steamapps\common\Iron Nest\Iron Nest_Data\il2cpp_data\Metadata\global-metadata.dat" `
  -OutDir       ".\dumps\iron-nest"
```

## 3. 找电报 / 任务 / 计时器

按这个顺序搜，命中率从高到低：

```powershell
# 类名关键词
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs Telegraph --kind class
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs Radio --kind class
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs Mission --kind class
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs Artillery --kind class

# 方法名
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs SetText --kind method
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs Countdown --kind method
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs Remaining --kind method

# 文案反查：先找字符串，再找引用它的方法
python .\scripts\find_string.py .\dumps\iron-nest\stringliteral.json "artillery"
python .\scripts\find_string.py .\dumps\iron-nest\stringliteral.json "counter-battery"
```

搜索词建议：`Telegraph`、`Teletype`、`Radio`、`Message`、`Artillery`、`Counter`、`Mission`、`Objective`、`Timer`、`Countdown`、`Fire`、`Shell`。

### 已验证命中（2026-11-24）

```text
CounterBatteryTimer        dump.cs:11386  TypeDefIndex 217
FireMission                dump.cs:36430
FireMissionTokenProcessor  dump.cs:36800  TypeDefIndex 679
FireMissionCardPrinter     dump.cs:7772
ArtilleryComputer          dump.cs:7265
SleepyNodes.State_StartTimer     dump.cs:62703
SleepyNodes.State_TimerAddTime   dump.cs:62760
```

完整字段/RVA 表见 `docs/iron-nest-timer-and-tokens.md`。加载器是 BepInEx 6，模板在 `templates/bepinex-mod/`。

### 改任务内容：直接看 dump，不要逆向字符串

`mission-dumps/` 里有「极限反炮兵」的完整任务图 dump（插件构建时打印的明文）：

- `structure_new.txt`：61 个节点，含参数、连接关系、中文电报原文。
- `structure_base.txt`：基础任务「炮兵入门」52 节点，用来对照改了什么。
- `result.txt`：插件逐行修改记录（300→60 秒、+100→+40 秒、刷兵替换等）。
- `entities.txt`：构建后 37 个实体清单。

节点语法、过滤器写法、完整机制链拆解见 `docs/iron-nest-mission-graph.md`。**这条路不依赖进游戏、不依赖 GPU/内存、不需要视觉自动化**——低配机器上比开游戏跑日志快得多。

## 4. 自定义任务的最小闭环

按这个顺序做，每步都能单独验证：

1. **只读**：hook 电报组件的 `SetText`（或同类方法），Prefix 打日志，确认能截到原文。
2. **改写**：在 Prefix 里改 `text`，确认 UI 显示被替换。
3. **计时**：找到反炮兵计时器的启动方法，hook 后改参数或延迟调用，确认游戏逻辑跟着变。
4. **组合**：任务开始时同时改电报和计时器，做成一个开关，方便回退。

不要第一步就写「完整任务控制器」。先把一个字符串改掉。

## 5. 已知风险

- 游戏更新会改 RVA 和类型名，dump 必须重做。
- IL2CPP 可能内联短方法，`SetText` 这类一行方法尤其容易被内联；日志不触发时 patch 调用方。
- 电报文本可能来自本地化表而不是代码字面量，`stringliteral.json` 搜不到就去解 AssetBundle。
- 改任务逻辑只影响单机。不要碰联机 / 排行榜相关代码。

## 6. 记录模板

每次验证记一行，方便回滚：

```text
[2026-11-24] dump v1 | TelegraphPanel.SetText(string) | Prefix 改文案 | 生效 | 日志行 142
[2026-11-24] dump v1 | ArtilleryTimer.StartCountdown(float) | Prefix 延迟 5s | 崩溃 | 场景未加载
```
