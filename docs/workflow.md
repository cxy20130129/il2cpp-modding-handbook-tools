# 从零到第一个 Hook

这份流程假设你有一份正版单机 Unity IL2CPP 游戏，并且只在自己机器上做模组开发。

## 1. 确认是 IL2CPP

游戏目录里应该同时存在：

```text
<GameRoot>\GameAssembly.dll
<GameRoot>\<GameName>_Data\il2cpp_data\Metadata\global-metadata.dat
```

只有 `Assembly-CSharp.dll` 而没有 `GameAssembly.dll`，说明是 Mono 后端，不需要这套工具，直接 dnSpy/ILSpy 即可。

## 2. 备份，再动手

- 复制整个游戏目录做测试副本，或者至少备份 `GameAssembly.dll` 和 `global-metadata.dat`。
- 装 Mod Loader 之前先确认游戏能正常启动。
- 不要在有反作弊 / 联机校验的游戏上做这些事。

## 3. 选一个 Loader

| Loader | 适合 | 注意 |
|---|---|---|
| MelonLoader | 快速迭代、日志清晰、Mod 生态简单 | 对 Unity 版本敏感，先看 release notes 是否支持你的 Unity |
| BepInEx 6 (IL2CPP) | 需要更底层的预加载器、插件链 | 配置项更多，IL2CPP 版本仍在 bleeding edge |

**只选一个。** 两个同时装会互相抢 `version.dll` / `winhttp.dll`，排查起来是灾难。

## 4. Dump

```powershell
.\scripts\dump.ps1 `
  -GameAssembly "D:\Games\Iron Nest\GameAssembly.dll" `
  -Metadata     "D:\Games\Iron Nest\Iron Nest_Data\il2cpp_data\Metadata\global-metadata.dat" `
  -OutDir       ".\dumps\iron-nest"
```

产物：

| 文件 | 用途 |
|---|---|
| `dump.cs` | 全部类型 / 方法 / 字段签名和 RVA，搜索主力 |
| `script.json` | 方法地址表，给 IDA/Ghidra 用 |
| `stringliteral.json` | 字符串字面量，找 UI 文案和电报文本 |
| `DummyDll/` | 可被 dnSpy/ILSpy 打开的占位程序集 |

先确认 `dump.cs` 里能搜到你知道一定存在的类。搜不到，后面的步骤全是白费。

## 5. 建立编译环境

1. 启动一次装了 MelonLoader 的游戏，让它生成 `MelonLoader/Il2CppAssemblies/`。
2. 这个目录里的 `Assembly-CSharp.dll` 才是你编译 Mod 时该引用的程序集，不是游戏原目录里那个。
3. 把 `MelonLoader` 目录和 `Il2CppAssemblies` 目录的路径填进 Mod 的 csproj。

## 6. 先日志，后补丁

第一版 Mod 只做一件事：在 `OnInitializeMelon` 打一行日志，确认加载成功。

```csharp
public override void OnInitializeMelon()
{
    LoggerInstance.Msg("MyMod loaded.");
}
```

加载成功后再加 Harmony 补丁。一次只加一个补丁，一次只验证一个行为。同时改三处，崩了不知道是哪一处。

## 7. 验证补丁真的进了

- 看 `MelonLoader/Latest.log`，确认 `PatchAll` 没有报 `PatchException`。
- 在 Prefix 里打日志，确认方法被调用。
- 如果日志没出现，先确认方法有没有被 IL2CPP 内联，再确认你 patch 的是不是正确的重载。

## 8. 游戏更新后

RVA、TypeDefIndex、甚至方法签名都可能变。标准动作：

1. 删掉旧 `dumps/` 和 `MelonLoader/Il2CppAssemblies/`。
2. 重新 dump。
3. 重新搜索目标类型，核对签名。
4. 重新编译 Mod。

不要试图在旧 dump 上猜偏移。

## 排查表

| 现象 | 常见原因 | 处理 |
|---|---|---|
| `dump.cs` 里搜不到类型 | metadata 版本不支持 / 加密 / 搜错命名空间 | 升级 Il2CppDumper；试 Il2CppInspector；用 `find_string.py` 反查文案 |
| 编译报类型找不到 | 引用了游戏原目录的 DLL，而不是 `Il2CppAssemblies` | 改 HintPath，清 `obj/bin` 重编 |
| `TypeLoadException` | 程序集版本不匹配，或游戏更新后旧程序集残留 | 删除 `Il2CppAssemblies` 让 Loader 重新生成 |
| 补丁不触发 | 方法被内联 / 不是实际执行的重载 / patch 错类型 | patch 调用方；用 `--kind method` 列出所有重载；检查泛型实例 |
| 进游戏直接崩 | 补丁签名和运行时不一致，或过早访问游戏对象 | 先去掉补丁验证 Mod 能加载；把逻辑推迟到场景加载后 |
| 字符串搜不到 | 文案在 AssetBundle / 本地化表里，不在代码里 | 换资源解包工具，不要死磕 `stringliteral.json` |
