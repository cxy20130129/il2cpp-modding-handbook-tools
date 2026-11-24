using BepInEx;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;

namespace IronNestModTemplate;

[BepInPlugin("dev.cxy.iron-nest-template", "Iron Nest BepInEx Template", "0.1.0")]
public sealed class Core : BasePlugin
{
    internal static ManualLogSource Logger;

    public override void Load()
    {
        Logger = Log;
        Harmony.CreateAndPatchAll(typeof(Core).Assembly, "dev.cxy.iron-nest-template");
        Logger.LogInfo("Iron Nest BepInEx template loaded");
    }
}

// Verified against dump.cs:11386 (TypeDefIndex 217).
[HarmonyPatch(typeof(CounterBatteryTimer), "Init")]
internal static class Patch_TimerInit
{
    private static void Prefix(float InitalTime) =>
        Core.Logger?.LogInfo($"[timer] Init({InitalTime:0.##})");
}

[HarmonyPatch(typeof(CounterBatteryTimer), "StartTimer")]
internal static class Patch_TimerStart
{
    private static void Prefix() => Core.Logger?.LogInfo("[timer] StartTimer");
}

[HarmonyPatch(typeof(CounterBatteryTimer), "AddTime")]
internal static class Patch_TimerAdd
{
    private static void Prefix(float seconds) =>
        Core.Logger?.LogInfo($"[timer] AddTime({seconds:0.##})");
}

[HarmonyPatch(typeof(CounterBatteryTimer), "SetTime")]
internal static class Patch_TimerSet
{
    private static void Prefix(float seconds) =>
        Core.Logger?.LogInfo($"[timer] SetTime({seconds:0.##})");
}

[HarmonyPatch(typeof(CounterBatteryTimer), "PauseTimer")]
internal static class Patch_TimerPause
{
    private static void Prefix() => Core.Logger?.LogInfo("[timer] PauseTimer");
}

[HarmonyPatch(typeof(CounterBatteryTimer), "UnpauseTimer")]
internal static class Patch_TimerUnpause
{
    private static void Prefix() => Core.Logger?.LogInfo("[timer] UnpauseTimer");
}

[HarmonyPatch(typeof(CounterBatteryTimer), "PermanentlyStop")]
internal static class Patch_TimerStop
{
    private static void Prefix() => Core.Logger?.LogInfo("[timer] PermanentlyStop");
}

// Runtime probe: teleprinter token commands are not recoverable from dump.cs alone.
// This tells you the exact command string the game asks the processor to render.
[HarmonyPatch(typeof(FireMissionTokenProcessor), "ProcessToken")]
internal static class Patch_TokenProbe
{
    private static void Prefix(FireMissionTokenProcessor.Command command)
    {
        if (command == null) return;
        Core.Logger?.LogInfo($"[token] cmd={command.Cmd} raw={command.Raw}");
    }
}
