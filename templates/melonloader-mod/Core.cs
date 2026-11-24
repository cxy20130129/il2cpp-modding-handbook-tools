using MelonLoader;

[assembly: MelonInfo(typeof(MyMod.Core), "MyMod", "0.1.0", "your-name")]

namespace MyMod;

public sealed class Core : MelonMod
{
    public override void OnInitializeMelon()
    {
        LoggerInstance.Msg("MyMod loaded.");
    }
}
