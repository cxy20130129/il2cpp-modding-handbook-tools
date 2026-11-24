# Iron Nest BepInEx 6 模板

针对 Iron Nest Heavy Turret Simulator（Unity 6000.3.21f1 / IL2CPP / BepInEx 6.0.0-be.785）的最小插件骨架。**不是 MelonLoader 模板。**

## 前提

1. 游戏已经用 BepInEx 6 启动过一次，生成了 `BepInEx/interop/Assembly-CSharp.dll`。没有它就没有游戏类型可引用。
2. .NET SDK 6 或更高版本。
3. 把 `IronNestDir` 指向游戏根目录。

## 编译

```powershell
dotnet build .\BepInExMod.csproj -c Release -p:IronNestDir="C:\Games\Iron Nest Heavy Turret Simulator"
```

产物：

```text
bin\Release\net6.0\IronNestBepInExTemplate.dll
```

复制到 `BepInEx\plugins\`，启动游戏，看 `BepInEx\LogOutput.log`：

```text
[Info   :Iron Nest BepInEx Template] Iron Nest BepInEx template loaded
[Info   :Iron Nest BepInEx Template] [timer] Init(60)
[Info   :Iron Nest BepInEx Template] [timer] StartTimer
```

## 它做了什么

- Hook `CounterBatteryTimer` 的 `Init` / `StartTimer` / `AddTime` / `SetTime` / `PauseTimer` / `UnpauseTimer` / `PermanentlyStop`，只打日志，不改行为。
- Hook `FireMissionTokenProcessor.ProcessToken`，打印每次渲染的令牌命令。跑一遍任务就能拿到真实令牌语法——`dump.cs` 只有方法名，正则模式在 native `.cctor` 里，不能直接读出来。

确认日志能触发后，再在 Prefix/Postfix 里改参数。例如把初始时间锁成 60 秒：

```csharp
[HarmonyPatch(typeof(CounterBatteryTimer), "Init")]
internal static class Patch_TimerInit
{
    private static void Prefix(ref float InitalTime) => InitalTime = 60f;
}
```

## 常见坑

- **不要**把 `BepInEx/core` 或 `BepInEx/interop` 下的 DLL 一起复制到插件目录；它们由 BepInEx 在运行时提供。
- 游戏更新后重新 dump，RVA 会变；这里用的是类型/方法名 patch，只要名字不变就不用改代码。
- `0Harmony.dll` 在 `BepInEx/core`，不在 NuGet；本模板走本地引用，不联网也能编译。
- 如果 `CounterBatteryTimer` 解析不到，先启动一次游戏让 Il2CppInterop 重新生成 interop 程序集。
