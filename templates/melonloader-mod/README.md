# MelonLoader Mod 模板

最小可编译的 MelonLoader Mod，只打一行日志。先确认它能加载，再加补丁。

## 1. 复制

```powershell
copy .\templates\melonloader-mod .\my-mod -Recurse
```

## 2. 指向你的 MelonLoader

```powershell
dotnet build .\my-mod\MyMod.csproj -c Release `
  -p:MelonLoaderDir="D:\Games\Iron Nest\MelonLoader"
```

或者设环境变量：

```powershell
$env:MELONLOADER_DIR = "D:\Games\Iron Nest\MelonLoader"
dotnet build .\my-mod\MyMod.csproj -c Release
```

`MelonLoaderDir` 里必须有 `MelonLoader.dll`。如果这里没有，说明 Loader 没装好。

## 3. 改身份

`Core.cs` 里的 `MelonInfo`：

```csharp
[assembly: MelonInfo(typeof(MyMod.Core), "MyMod", "0.1.0", "your-name")]
```

名字和版本随便改，类型必须是你的 `MelonMod` 子类。

## 4. 部署

把 `bin\Release\MyMod.dll` 复制到游戏的 `Mods\` 目录，启动游戏，看 `MelonLoader\Latest.log` 里有没有 `MyMod loaded.`。

## 5. 加 Harmony 补丁

模板默认只引用 `MelonLoader.dll`。要写补丁，再加 `0Harmony.dll`：

```xml
<Reference Include="0Harmony">
  <HintPath>$(MelonLoaderDir)\0Harmony.dll</HintPath>
  <Private>false</Private>
</Reference>
```

**不要**把 `0Harmony.dll` 复制到 `Mods`，Loader 自带。

需要调用游戏类型时，再加 `Il2CppAssemblies` 里的程序集：

```xml
<Reference Include="Assembly-CSharp">
  <HintPath>$(Il2CppAssembliesDir)\Assembly-CSharp.dll</HintPath>
  <Private>false</Private>
</Reference>
```

`Il2CppAssembliesDir` 由 Loader 首次启动后生成，路径通常是 `<GameRoot>\MelonLoader\Il2CppAssemblies`。

## 6. 目标框架

模板用 `net6.0`。你的 MelonLoader 版本如果要求 `net8.0`，改 `<TargetFramework>` 并装对应 SDK。不要盲目升到 `net10.0`，Loader 的运行时不一定认。

## 常见错误

| 错误 | 原因 |
|---|---|
| `MelonLoader.dll not found` | `MelonLoaderDir` 指错，或 Loader 没装 |
| `CS0246: MelonMod not found` | 没引用 `MelonLoader.dll`，或 TargetFramework 不匹配 |
| 游戏里没有日志 | DLL 没进 `Mods`，或 `MelonInfo` 的类型不是 `MelonMod` 子类 |
| 启动崩溃 | 补丁在场景加载前访问了游戏对象；先注释掉补丁验证模板本身 |
