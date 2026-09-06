using System.Text.Json.Serialization;

namespace Jarvis.Core.Models;

/// <summary>"info" | "notice" | "warning" | "critical"</summary>
public enum ObservationSeverity
{
    Info,
    Notice,
    Warning,
    Critical,
}

public sealed class Observation
{
    public string Id { get; set; } = "";
    public long Seq { get; set; }
    public string Kind { get; set; } = "";
    public ObservationSeverity Severity { get; set; }
    public string Title { get; set; } = "";
    public string Detail { get; set; } = "";
    public string Spoken { get; set; } = "";
    public Dictionary<string, object?> Data { get; set; } = new();
    public double Timestamp { get; set; }
    public bool Acknowledged { get; set; }
    public bool Resolved { get; set; }
    public bool? Speak { get; set; }
}

public sealed class AwarenessSnapshot
{
    [JsonPropertyName("cpu_percent")]
    public double CpuPercent { get; set; }

    [JsonPropertyName("ram_percent")]
    public double RamPercent { get; set; }

    [JsonPropertyName("ram_used_mb")]
    public double RamUsedMb { get; set; }

    [JsonPropertyName("ram_total_mb")]
    public double RamTotalMb { get; set; }

    [JsonPropertyName("gpu_available")]
    public bool GpuAvailable { get; set; }

    [JsonPropertyName("gpu_name")]
    public string? GpuName { get; set; }

    [JsonPropertyName("gpu_util_percent")]
    public double GpuUtilPercent { get; set; }

    [JsonPropertyName("vram_used_mb")]
    public double VramUsedMb { get; set; }

    [JsonPropertyName("vram_total_mb")]
    public double VramTotalMb { get; set; }

    [JsonPropertyName("vram_free_mb")]
    public double VramFreeMb { get; set; }

    [JsonPropertyName("vram_util_percent")]
    public double VramUtilPercent { get; set; }

    [JsonPropertyName("gpu_temp_c")]
    public double? GpuTempC { get; set; }

    [JsonPropertyName("disk_free_gb")]
    public double DiskFreeGb { get; set; }

    [JsonPropertyName("disk_total_gb")]
    public double DiskTotalGb { get; set; }

    [JsonPropertyName("disk_percent")]
    public double DiskPercent { get; set; }

    [JsonPropertyName("battery_percent")]
    public double? BatteryPercent { get; set; }

    [JsonPropertyName("battery_plugged")]
    public bool? BatteryPlugged { get; set; }

    [JsonPropertyName("governor_status")]
    public string GovernorStatus { get; set; } = "";

    public bool Throttled { get; set; }

    [JsonPropertyName("throttle_reasons")]
    public List<string> ThrottleReasons { get; set; } = new();

    [JsonPropertyName("model_unloaded")]
    public bool ModelUnloaded { get; set; }

    [JsonPropertyName("heavy_apps")]
    public List<string> HeavyApps { get; set; } = new();

    public double Timestamp { get; set; }
}

public sealed class AwarenessMonitorStatus
{
    public bool Enabled { get; set; }
    public bool Running { get; set; }

    [JsonPropertyName("poll_seconds")]
    public double PollSeconds { get; set; }

    [JsonPropertyName("restate_cooldown_seconds")]
    public double RestateCooldownSeconds { get; set; }

    [JsonPropertyName("min_speak_severity")]
    public ObservationSeverity MinSpeakSeverity { get; set; }

    [JsonPropertyName("actions_enabled")]
    public bool ActionsEnabled { get; set; }

    [JsonPropertyName("actionable_kinds")]
    public List<string> ActionableKinds { get; set; } = new();

    [JsonPropertyName("active_conditions")]
    public List<string> ActiveConditions { get; set; } = new();

    public int Subscribers { get; set; }

    [JsonPropertyName("latest_seq")]
    public long LatestSeq { get; set; }

    public Dictionary<string, double> Thresholds { get; set; } = new();
}

public sealed class AwarenessStatus
{
    public AwarenessSnapshot Snapshot { get; set; } = new();
    public AwarenessMonitorStatus Monitor { get; set; } = new();
}

public sealed class Briefing
{
    public string Text { get; set; } = "";
    public string Spoken { get; set; } = "";

    [JsonPropertyName("persona_id")]
    public string PersonaId { get; set; } = "";

    public AwarenessSnapshot Snapshot { get; set; } = new();
}
