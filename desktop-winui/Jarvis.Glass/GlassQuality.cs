namespace Jarvis_Glass;

/// <summary>
/// Rendering tier for the glass material system. "Full" and "Reduced" both describe the future
/// Tier A shader path (Phase 1a of the plan); today's GlassPanel implementation is "System" only
/// (SystemBackdropElement Acrylic). The enum and controller below exist so callers — Settings'
/// "Glass quality" control, and the governor-driven auto-degrade the plan calls for — have a
/// stable surface to bind to as Tier A lands, without another round of API changes.
/// </summary>
public enum GlassQuality
{
    /// <summary>Animated shader glass at full frame rate. (Tier A, not yet implemented.)</summary>
    Full,

    /// <summary>Shader glass, redrawn only on change rather than continuously. (Tier A, not yet implemented.)</summary>
    Reduced,

    /// <summary>SystemBackdropElement acrylic, no per-panel canvas. Today's only implemented tier.</summary>
    System,
}

public enum GlassQualityMode
{
    Auto,
    Full,
    System,
}

/// <summary>
/// Auto-degrade policy: demotes glass quality while the GPU is actually busy, using the same
/// breach/recovery-count shape as ResourceGovernor (3 sustained breaches to demote, 2 recovery
/// samples to promote back), so the glass never fights the 4060's 8GB VRAM budget for tokens/sec.
///
/// Note what "busy" deliberately does *not* mean: a model merely being resident. Jarvis keeps a
/// model loaded essentially all the time, so treating that alone as pressure pinned every panel
/// to Tier B permanently and the shader tier never rendered at all. A loaded model instead
/// *lowers the bar* for what counts as busy — inference and glass are then genuinely competing.
/// </summary>
public sealed class GlassQualityController
{
    private const int BreachesToDemote = 3;
    private const int RecoveriesToPromote = 2;

    private int _breachStreak;
    private int _recoveryStreak;

    public GlassQualityMode Mode { get; set; } = GlassQualityMode.Auto;
    // Starts at the top tier: the policy's job is to take quality away when the machine needs it,
    // not to make every launch begin with a visible upgrade from flat acrylic.
    public GlassQuality Current { get; private set; } = GlassQuality.Full;

    public event Action<GlassQuality>? QualityChanged;

    /// <param name="gpuUtilPercent">Current GPU utilization, from GovernorTelemetry.Metrics.GpuUtilPercent.</param>
    /// <param name="modelLoaded">Whether an inference model is currently loaded (llama-server running).</param>
    /// <param name="transparencyEffectsEnabled">Settings > Personalization > Colors > Transparency effects.</param>
    /// <param name="batterySaverActive">Whether Battery Saver is on (Acrylic is disabled by Windows in this state).</param>
    public void Evaluate(double gpuUtilPercent, bool modelLoaded, bool transparencyEffectsEnabled, bool batterySaverActive)
    {
        if (Mode == GlassQualityMode.System)
        {
            SetQuality(GlassQuality.System);
            return;
        }

        if (!transparencyEffectsEnabled || batterySaverActive)
        {
            // Hard floor: the OS itself will not render acrylic/shader glass here regardless of mode.
            SetQuality(GlassQuality.System);
            return;
        }

        // Busy on its own account, or moderately busy while inference is also holding the card.
        var underPressure = gpuUtilPercent >= 80.0 || (modelLoaded && gpuUtilPercent >= 50.0);

        if (underPressure)
        {
            _recoveryStreak = 0;
            _breachStreak++;
            if (_breachStreak >= BreachesToDemote && Current == GlassQuality.Full)
            {
                SetQuality(GlassQuality.Reduced);
            }
        }
        else
        {
            _breachStreak = 0;
            _recoveryStreak++;
            if (_recoveryStreak >= RecoveriesToPromote && Current != GlassQuality.Full && Mode == GlassQualityMode.Auto)
            {
                SetQuality(GlassQuality.Full);
            }
        }
    }

    private void SetQuality(GlassQuality quality)
    {
        if (quality == Current)
        {
            return;
        }
        Current = quality;
        QualityChanged?.Invoke(quality);
    }
}
