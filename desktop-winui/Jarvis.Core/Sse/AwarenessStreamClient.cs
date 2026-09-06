using System.Runtime.CompilerServices;
using System.Text.Json;
using Jarvis.Core.Json;
using Jarvis.Core.Models;

namespace Jarvis.Core.Sse;

public abstract record AwarenessStreamEvent;

public sealed record AwarenessReadyEvent(AwarenessStatus Status) : AwarenessStreamEvent;

public sealed record AwarenessObservationEvent(Observation Observation, bool Speak) : AwarenessStreamEvent;

/// <summary>
/// Port of the EventSource consumer implied by useAwareness.ts, against GET /api/awareness/stream
/// (backend/app/routers/awareness.py). .NET has no EventSource, so this reads the raw stream with
/// SseReader. ":"-prefixed keepalive comments (sent every 20s) are already dropped by SseReader.
/// </summary>
public sealed class AwarenessStreamClient
{
    private readonly HttpClient _http;

    public AwarenessStreamClient(HttpClient http)
    {
        _http = http;
    }

    public async IAsyncEnumerable<AwarenessStreamEvent> ConnectAsync(
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "/api/awareness/stream");
        request.Headers.Accept.Add(new System.Net.Http.Headers.MediaTypeWithQualityHeaderValue("text/event-stream"));

        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);

        await foreach (var frame in SseReader.ReadFramesAsync(stream, ct).ConfigureAwait(false))
        {
            if (string.IsNullOrEmpty(frame.Data))
            {
                continue;
            }

            switch (frame.EventType)
            {
                case "ready":
                {
                    var status = TryDeserialize<AwarenessStatus>(frame.Data);
                    if (status is not null)
                    {
                        yield return new AwarenessReadyEvent(status);
                    }
                    break;
                }
                case "observation":
                {
                    var observation = TryDeserialize<Observation>(frame.Data);
                    if (observation is not null)
                    {
                        yield return new AwarenessObservationEvent(observation, observation.Speak ?? false);
                    }
                    break;
                }
            }
        }
    }

    private static T? TryDeserialize<T>(string json) where T : class
    {
        try
        {
            return JsonSerializer.Deserialize<T>(json, JarvisJson.Options);
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
