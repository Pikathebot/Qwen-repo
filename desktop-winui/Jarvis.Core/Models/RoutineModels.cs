using System.Text.Json.Serialization;

namespace Jarvis.Core.Models;

/// <summary>"briefing" | "message"</summary>
public enum RoutineKind
{
    Briefing,
    Message,
}

public sealed class Routine
{
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";

    /// <summary>"HH:MM", 24-hour local time.</summary>
    public string Time { get; set; } = "";

    public RoutineKind Kind { get; set; }
    public string Message { get; set; } = "";

    /// <summary>0=Mon .. 6=Sun; empty = every day.</summary>
    public List<int> Days { get; set; } = new();

    public bool Enabled { get; set; }

    [JsonPropertyName("last_fired_date")]
    public string? LastFiredDate { get; set; }
}

public sealed class RoutineSchedulerStatus
{
    public bool Enabled { get; set; }
    public bool Running { get; set; }

    [JsonPropertyName("check_seconds")]
    public double CheckSeconds { get; set; }

    public int Count { get; set; }
}

public sealed class RoutinesResponse
{
    public List<Routine> Routines { get; set; } = new();
    public RoutineSchedulerStatus Scheduler { get; set; } = new();
}

public sealed class RoutineInput
{
    public string Name { get; set; } = "";
    public string Time { get; set; } = "";
    public RoutineKind Kind { get; set; }
    public string? Message { get; set; }
    public List<int>? Days { get; set; }
    public bool? Enabled { get; set; }
}
