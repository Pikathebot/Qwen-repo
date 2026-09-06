namespace Jarvis.Core.Sse;

/// <summary>One parsed "event: X\ndata: Y\n\n" packet. EventType defaults to "message" per the SSE spec.</summary>
public readonly record struct SseFrame(string EventType, string Data);
