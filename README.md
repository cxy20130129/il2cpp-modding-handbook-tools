# il2cpp-modding-handbook-tools

`il2cpp-modding-handbook` 的配套工具集：把 Unity IL2CPP 游戏从「找不到类」到「跑通第一个 Hook」之间的脏活固定成可复用脚本。

不绑定具体游戏。示例用 Iron Nest: Heavy Turret Simulator，但脚本只依赖 Il2CppDumper 的标准输出。

## 这里有什么

| 路径 | 用途 |
|---|---|
| `scripts/check_env.ps1` | 检查 Python / .NET / Il2CppDumper / MelonLoader 是否就位 |
| `scripts/dump.ps1` | 调 Il2CppDumper，校验输入输出，失败就停 |
| `scripts/find_type.py` | 在 `dump.cs` 里按类名、方法名、字段名搜索，带行号和 RVA |
| `scripts/find_string.py` | 在 `stringliteral.json` 里搜字符串字面量，定位 UI 文案和电报文本 |
| `templates/melonloader-mod/` | 能直接 `dotnet build` 的 MelonLoader Mod 骨架 |
| `docs/workflow.md` | 从拿到游戏到验证 Hook 的完整流程 |
| `docs/toolchain.md` | 工具链版本、常见报错、选型建议 |
| `docs/hook-patterns.md` | Harmony 补丁的几种常用写法与坑 |
| `examples/iron-nest/` | Iron Nest 的具体搜索词和排查顺序 |

## 快速开始

前提：Windows、Python 3.10+、.NET SDK 8+、一份正版游戏。

**Unity 6 / metadata v39 必须用 v39 fork**：官方 Il2CppDumper v6.7.46 只支持到 metadata v31，遇到 Unity 6000.x 会报 `not a supported version[39]`。本仓库已内置 `tools/Il2CppDumper-v39`（roytu/Il2CppDumper 的 `v39` 分支，已编译好 net8.0 版本），`dump.ps1` 会优先用它。重建命令：

```powershell
cd .\tools\Il2CppDumper-v39
dotnet build Il2CppDumper/Il2CppDumper.csproj -c Release -f net8.0
```

记得把 `Il2CppDumper/config.json` 里的 `RequireAnyKey` 设为 `false`，否则非交互运行会卡在 "Press any key to exit..."。

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

# 5. 建 Mod
copy .\templates\melonloader-mod .\my-mod -Recurse
# 改 MyMod.csproj 里的 MelonLoaderDir，然后：
dotnet build .\my-mod\MyMod.csproj -c Release
```

## 输出示例

```text
$ python scripts/find_type.py dumps/iron-nest/dump.cs Telegraph --kind class
dump.cs:18422  [class] IronNest.UI.TelegraphPanel : MonoBehaviour  // TypeDefIndex: 1187

$ python scripts/find_type.py dumps/iron-nest/dump.cs SetText --kind method
IronNest.UI.TelegraphPanel  (dump.cs:18422)
  dump.cs:18440  [method] public void SetText(string text)  // RVA: 0x1A2B3C0 Offset: 0x1A2B3C0 VA: 0x1A2B3C0
```

## 边界

- 仓库里**没有**游戏 DLL、`global-metadata.dat`、资源文件、Il2CppDumper 二进制。自己准备。
- 不做反作弊绕过、不做联机作弊、不分发破解内容。只针对单机模组开发。
- 游戏更新后 RVA 会变，重新 dump 是常规操作，不是脚本坏了。
- `find_type.py` 按 Il2CppDumper 的标准 `dump.cs` 格式解析。换用 Il2CppInspector 或自定义输出格式时需要改解析规则。

## 状态

早期版本。Python 脚本在合成 `dump.cs` 样本上通过单元测试；PowerShell 脚本只做了静态校验，未在真实游戏上跑通全流程。第一次用请按 `docs/workflow.md` 逐步验证。

## 许可证

MIT。见 `LICENSE`。
