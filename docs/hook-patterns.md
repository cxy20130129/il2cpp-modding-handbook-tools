# Harmony 补丁模式

以下代码是**模式示例**，类型名和方法名来自具体游戏，直接复制编译不过。先 dump，再把占位符换成真实签名。

## 1. Prefix：改参数 / 拦执行

```csharp
[HarmonyPatch(typeof(TelegraphPanel), nameof(TelegraphPanel.SetText))]
internal static class TelegraphTextPatch
{
    private static void Prefix(ref string text)
    {
        text = "[INTERCEPTED] " + text;
    }
}
```

- `ref string text` 的参数名必须和目标方法一致，否则 Harmony 找不到。
- 返回 `bool` 并返回 `false` 可以跳过原方法；只改参数就不要返回 `bool`。

## 2. Postfix：改返回值

```csharp
[HarmonyPatch(typeof(ArtilleryTimer), nameof(ArtilleryTimer.GetRemainingTime))]
internal static class TimerReadPatch
{
    private static void Postfix(ref float __result)
    {
        __result = Math.Max(0f, __result - 5f);
    }
}
```

`__result` 是 Harmony 的保留名，类型必须和目标返回值一致。

## 3. 按重载精确指定

```csharp
[HarmonyPatch(typeof(TelegraphPanel), nameof(TelegraphPanel.SetText),
    new[] { typeof(string), typeof(float) })]
```

同名重载很常见。dump 里用 `find_type.py <name> --kind method` 看清楚参数再写。

## 4. 属性 / getter

```csharp
[HarmonyPatch(typeof(MissionState), "get_IsComplete")]
```

IL2CPP 的属性访问器在 dump 里通常显示为 `get_X` / `set_X`。也可以用：

```csharp
[HarmonyPatch(typeof(MissionState), nameof(MissionState.IsComplete), MethodType.Getter)]
```

## 5. 字段访问

如果 `DummyDll` 里字段是 public，直接访问；否则用 `Traverse`：

```csharp
var timer = Traverse.Create(instance).Field<float>("remaining").Value;
```

字段偏移在游戏更新后会变，`Traverse` 按名字找比硬编码偏移安全。

## 6. 协程 / 计时器

不要 patch `Update` 去每帧改状态。优先找真正推进状态的方法（`Tick`、`Countdown`、`SetRemaining`），在状态变更点做一次修改。

如果只能 patch 协程，注意它是编译器生成的状态机，方法名可能是 `<Countdown>d__12.MoveNext`，直接从 dump 里搜 `MoveNext` 很难定位。更稳的做法是 patch 启动协程的业务方法。

## 7. 泛型与接口

IL2CPP 会为每个泛型实例生成独立代码。patch 开放泛型方法通常无效，必须指定具体实例：

```csharp
[HarmonyPatch(typeof(Container<string>), nameof(Container<string>.Add))]
```

接口方法同理，patch 实际实现类，不要 patch 接口。

## 常见坑

| 坑 | 说明 |
|---|---|
| 方法被内联 | IL2CPP 可能把短方法内联，补丁不触发。patch 调用方，或换一个更大的方法 |
| `nameof` 编译不过 | 目标类型不在引用程序集里，或字段/方法被裁剪。用字符串名 |
| 参数名不匹配 | Prefix/Postfix 的参数按名字注入，写错就是静默不生效 |
| `PatchAll` 抛异常 | 通常是目标方法找不到。加 `try/catch` 或在 `OnInitializeMelon` 里逐个 patch 并打日志 |
| 打包了 `0Harmony.dll` | Loader 已自带，重复打包会导致类型冲突 |
| 在 `OnApplicationStart` 访问游戏对象 | 场景还没加载，容易空引用。改到场景加载完成后再执行 |
