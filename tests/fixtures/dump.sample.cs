// Synthetic fixture for find_type.py. Not a real game dump.
// Image: Assembly-CSharp.dll
// Namespace: IronNest.UI
public class TelegraphPanel : MonoBehaviour // TypeDefIndex: 1187
{
    // Fields
    private string currentText; // 0x18
    public float revealSpeed; // 0x20

    // Methods
    public void SetText(string text) { } // RVA: 0x1A2B3C0 Offset: 0x1A2B3C0 VA: 0x1A2B3C0
    private void Update() { } // RVA: 0x1A2B400 Offset: 0x1A2B400 VA: 0x1A2B400
}

// Namespace: IronNest.Gameplay
public class ArtilleryTimer : MonoBehaviour // TypeDefIndex: 1301
{
    public float remaining; // 0x18

    public void StartCountdown(float seconds) { } // RVA: 0x1A2C000 Offset: 0x1A2C000 VA: 0x1A2C000
}

// Namespace: IronNest.UI
public sealed class Outer // TypeDefIndex: 2000
{
    public class Inner // TypeDefIndex: 2001
    {
        public void Ping() { } // RVA: 0x1A2D000 Offset: 0x1A2D000 VA: 0x1A2D000
    }
}
