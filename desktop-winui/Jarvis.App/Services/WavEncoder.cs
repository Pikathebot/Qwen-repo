namespace Jarvis_App.Services;

/// <summary>Encodes captured mono float32 PCM samples as a 16-bit PCM WAV file in memory —
/// what /api/voice/listen expects (backend picks its decoder off the filename extension).</summary>
public static class WavEncoder
{
    public static byte[] EncodeMono16Bit(IReadOnlyList<float> samples, int sampleRate)
    {
        var dataSize = samples.Count * 2;
        using var stream = new MemoryStream(44 + dataSize);
        using var writer = new BinaryWriter(stream);

        writer.Write("RIFF"u8);
        writer.Write(36 + dataSize);
        writer.Write("WAVE"u8);

        writer.Write("fmt "u8);
        writer.Write(16); // PCM fmt chunk size
        writer.Write((short)1); // PCM
        writer.Write((short)1); // mono
        writer.Write(sampleRate);
        writer.Write(sampleRate * 2); // byte rate (mono, 16-bit)
        writer.Write((short)2); // block align
        writer.Write((short)16); // bits per sample

        writer.Write("data"u8);
        writer.Write(dataSize);

        foreach (var sample in samples)
        {
            var clamped = Math.Clamp(sample, -1f, 1f);
            writer.Write((short)(clamped * short.MaxValue));
        }

        return stream.ToArray();
    }
}
