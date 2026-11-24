# 工具链

> Iron Nest 本机环境：Unity 6000.3.21f1 / metadata v39 / BepInEx 6.0.0-be.785。官方 Il2CppDumper 不支持 v39，用仓库内置的 `tools/Il2CppDumper-v39`；Mod 用 `templates/bepinex-mod/`。

## 核心工具

| 工具 | 作用 | 备注 |
|---|---|---|
| [Il2CppDumper](https://github.com/Perfare/Il2CppDumper) | 解析 `GameAssembly.dll` + `global-metadata.dat`，产出 `dump.cs` / `script.json` / `DummyDll` | 首选。metadata 版本不支持时先升级它 |
| [Il2CppInspector](https://github.com/djkaty/Il2CppInspector) | 另一套 IL2CPP 解析器，输出格式不同 | Il2CppDumper 失败时的备选；本仓库脚本不直接解析它的输出 |
| [MelonLoader](https://github.com/LavaGang/MelonLoader) | IL2CPP Mod Loader，生成 `Il2CppAssemblies` | 版本必须匹配 Unity 版本 |
| [BepInEx](https://github.com/BepInEx/BepInEx) | 另一套 Loader，IL2CPP 支持在 6.x | 与 MelonLoader 二选一 |
| [Harmony](https://github.com/pardeike/Harmony) | 运行时方法补丁 | MelonLoader 自带 `0Harmony.dll`，不要重复打包 |
| [ILSpy](https://github.com/icsharpcode/ILSpy) / dnSpy | 读 `DummyDll`，看类型继承和字段布局 | 只读，不要用它直接改 IL2CPP 程序集 |

## 版本矩阵（按你的环境填）

| 组件 | 你的版本 | 检查方式 |
|---|---|---|
| Unity | 游戏 `globalgamemanagers` 或日志里看 | `Player.log` 第一行 |
| IL2CPP metadata | dump 日志会打印 | 报 `unsupported metadata version` 就升级 dumper |
| MelonLoader | Loader 启动日志 | 必须支持当前 Unity 大版本 |
| .NET SDK | `dotnet --version` | Mod 模板默认 `net6.0`，按 Loader 要求调整 |

## 目录约定

```text
<GameRoot>/
├─ GameAssembly.dll
├─ <GameName>_Data/
│  └─ il2cpp_data/Metadata/global-metadata.dat
├─ MelonLoader/
│  ├─ MelonLoader.dll
│  ├─ 0Harmony.dll
│  ├─ Il2CppInterop.Runtime.dll
│  └─ Il2CppAssemblies/        # 首次启动后生成
└─ Mods/                       # 编译好的 Mod 放这里
```

## 常见报错

**`unsupported metadata version`**
Il2CppDumper 太旧。换最新 release；仍然不行就试 Il2CppInspector。

**`GameAssembly.dll` 找不到 `il2cpp_*` 导出**
游戏可能加壳或改了导出表。先确认不是保护壳；这类游戏不在本仓库讨论范围。

**`dotnet build` 报 `MSB3644` / 找不到 reference assemblies**
项目目标框架和本机 SDK 不匹配。Mod 模板用 `net6.0`，装 .NET 6 SDK；或者把 `TargetFramework` 改成你已安装的版本。

**MelonLoader 生成了空的 `Il2CppAssemblies`**
Loader 版本不支持当前 Unity，或者游戏启动时还没走到生成阶段。看 `Latest.log`，不要手工造 DLL。

## 不放进仓库的东西

- `GameAssembly.dll`、`global-metadata.dat`、任何游戏资源
- `DummyDll/`、`Il2CppAssemblies/`、`dumps/`
- Il2CppDumper / MelonLoader 的二进制压缩包

`.gitignore` 已经覆盖这些路径。提交前用 `git status` 再确认一遍。
