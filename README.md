# il2cpp-modding-handbook-tools

`il2cpp-modding-handbook` 的配套工具集：把 Unity IL2CPP 游戏从「找不到类」到「跑通第一个 Hook」之间的脏活固定成可复用脚本。

不绑定具体游戏。示例用 Iron Nest: Heavy Turret Simulator，但脚本只依赖 Il2CppDumper 的标准输出。

## 这里有什么

| 路径                           | 用途                                                 |
| ---------------------------- | -------------------------------------------------- |
| `scripts/check_env.ps1`      | 检查 Python / .NET / Il2CppDumper / BepInEx / MelonLoader 是否就位 |
| `scripts/dump.ps1`           | 调 Il2CppDumper，校验输入输出，失败就停                         |
| `scripts/find_type.py`       | 在 `dump.cs` 里按类名、方法名、字段名搜索，带行号和 RVA                |
| `scripts/find_string.py`     | 在 `stringliteral.json` 里搜字符串字面量，定位 UI 文案和电报文本      |
| `scripts/disasm_method.py`   | 按 RVA 反汇编 native 方法，解析字符串引用                           |
| `scripts/field_offsets.py`   | 提取类的字段偏移表，支持正则和 Markdown/JSON/CSV 输出             |
| `templates/bepinex-mod/`     | BepInEx 6 IL2CPP 插件骨架，已用本机 Iron Nest 编译验证              |
| `templates/melonloader-mod/` | 能直接 `dotnet build` 的 MelonLoader Mod 骨架            |
| `docs/workflow.md`           | 从拿到游戏到验证 Hook 的完整流程                                |
| `docs/toolchain.md`          | 工具链版本、常见报错、选型建议                                    |
| `docs/hook-patterns.md`      | Harmony 补丁的几种常用写法与坑                                |
| `docs/field-offsets.md`      | 字段偏移怎么读、增量/静态/常量的坑、偏移能做什么不能做什么        |
| `docs/iron-nest-timer-and-tokens.md` | 反炮兵计时器与任务令牌的实测类表、偏移和 RVA             |
| `docs/iron-nest-mission-graph.md` | 任务图节点语法、事件过滤器、极限反炮兵完整拆解（实测）      |
| `examples/iron-nest/`        | Iron Nest 的具体搜索词和排查顺序                              |
| `examples/iron-nest/mission-dumps/` | 极限反炮兵任务图/实体/构建日志的实测 dump 原文            |

## 快速开始

前提：Windows、Python 3.10+、.NET SDK 8+、一份正版游戏。

**Unity 6 / metadata v39 必须用 v39 fork**：官方 Il2CppDumper v6.7.46 只支持到 metadata v31，遇到 Unity 6000.x 会报 `not a supported version[39]`。首次使用先准备 fork（第三方二进制不入库）：

```powershell
mkdir tools
git clone -b v39 --depth 1 https://github.com/roytu/Il2CppDumper.git tools\Il2CppDumper-v39
cd tools\Il2CppDumper-v39
dotnet build Il2CppDumper\Il2CppDumper.csproj -c Release -f net8.0
cd ..\..
```

`dump.ps1` 会优先找这个 v39 版本，并自动把它的 `RequireAnyKey` 改成 `false`，避免卡在按键提示。

```powershell
# 1. 检查环境
.\scripts\check_env.ps1

# 2.  dump（路径换成你的游戏）
.\scripts\dump.ps1 `
  -GameAssembly "D:\SteamLibrary\steamapps\common\Iron Nest\GameAssembly.dll" `
  -Metadata     "D:\SteamLibrary\steamapps\common\Iron Nest\Iron Nest_Data\il2cpp_data\Metadata\global-metadata.dat" `
  -OutDir       ".\dumps\iron-nest"

# 3. 找类
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs Telegraph --kind class
python .\scripts\find_type.py .\dumps\iron-nest\dump.cs OnFire --kind method

# 4. 找文案
python .\scripts\find_string.py .\dumps\iron-nest\stringliteral.json "artillery"

# 5. 看字段布局（直接生成可贴进文档的偏移表）
python .\scripts\field_offsets.py .\dumps\iron-nest\dump.cs CounterBatteryTimer --format markdown

# 6. 建 Mod（Iron Nest 用 BepInEx 6，不是 MelonLoader）
copy .\templates\bepinex-mod .\my-mod -Recurse
dotnet build .\my-mod\BepInExMod.csproj -c Release `
  -p:IronNestDir="D:\Games\Iron Nest Heavy Turret Simulator"
# 把 bin\Release\net6.0\IronNestBepInExTemplate.dll 放进 BepInEx\plugins
```

Iron Nest 的实测结论见两份文档：

- `docs/iron-nest-timer-and-tokens.md`：计时器字段偏移、RVA、任务令牌处理器。
- `docs/iron-nest-mission-graph.md`：**想改任务内容从这里入手**。节点语法、电报富文本格式、歼灭事件过滤器、极限反炮兵的完整节点链，附实测 dump 原文。这份数据由插件构建任务时打印，不用进游戏、不用视觉自动化。

其它游戏如果用的是 MelonLoader，仍可用 `templates/melonloader-mod/`。

## 输出示例

```text
$ python scripts/find_type.py dumps/iron-nest/dump.cs Telegraph --kind class
dump.cs:18422  [class] IronNest.UI.TelegraphPanel  |  public class TelegraphPanel : MonoBehaviour // TypeDefIndex: 1187

$ python scripts/find_type.py dumps/iron-nest/dump.cs SetText --kind method
IronNest.UI.TelegraphPanel  (dump.cs:18422)  // TypeDefIndex: 1187
  dump.cs:18440  [method] public void SetText(string text)  // RVA: 0x1A2B3C0 Offset: 0x1A2B3C0 VA: 0x1A2B3C0
```

## 边界

- 仓库里**没有**游戏 DLL、`global-metadata.dat`、资源文件、Il2CppDumper 二进制。自己准备。
- 不做反作弊绕过、不做联机作弊、不分发破解内容。只针对单机模组开发。
- 游戏更新后 RVA 会变，重新 dump 是常规操作，不是脚本坏了。
- `find_type.py` 按 Il2CppDumper 的标准 `dump.cs` 格式解析。换用 Il2CppInspector 或自定义输出格式时需要改解析规则。

## 状态

早期版本。Python 脚本在合成 `dump.cs` 样本上通过单元测试；v39 dumper 已在真实 Iron Nest 上跑出 `dump.cs`；BepInEx 模板已对真实游戏的 interop 程序集编译通过（0 警告 0 错误）。`dump.ps1` 的封装路径尚未从头复跑，第一次用请按 `docs/workflow.md` 逐步验证。

## 许可证

MIT。见 `LICENSE`。
