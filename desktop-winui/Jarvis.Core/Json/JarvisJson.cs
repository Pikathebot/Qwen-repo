using System.Text.Json;
using System.Text.Json.Serialization;

namespace Jarvis.Core.Json;

/// <summary>Shared System.Text.Json options for the backend contract: snake_case wire format
/// handled per-property via [JsonPropertyName], enums as lowercase strings.</summary>
public static class JarvisJson
{
    public static readonly JsonSerializerOptions Options = Create();

    private static JsonSerializerOptions Create()
    {
        var options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            // Explicit [JsonPropertyName] attributes on multi-word properties (SessionId ->
            // "session_id") always win over this, but single-word properties like Message/Mode/
            // Model have none, and without a policy they'd serialize as "Message"/"Mode" verbatim
            // — the backend's FastAPI models require lowercase and reject the mismatch as HTTP 422
            // "field required" (it never sees "message" at all). Caught live: sending a chat
            // message threw exactly this until this policy was added.
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        };
        options.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
        return options;
    }
}
