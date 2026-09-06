using System.Runtime.InteropServices;
using Windows.Media;

namespace Jarvis_App.Services;

/// <summary>
/// AudioFrame's IMemoryBuffer doesn't expose a managed byte pointer directly — reading raw
/// samples out of an AudioGraph frame requires QI'ing its buffer reference for this classic
/// COM interface (the standard, documented pattern for AudioFrame PCM access in C#; there is no
/// higher-level managed API for it).
/// </summary>
[ComImport]
[Guid("5B0D3235-4DBA-4D44-865E-8F1D0E4FD04D")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal unsafe interface IMemoryBufferByteAccess
{
    void GetBuffer(out byte* buffer, out uint capacity);
}

/// <summary>Reads the 32-bit float PCM samples out of one AudioFrame into a managed float[].</summary>
internal static unsafe class AudioFrameReader
{
    public static float[] ReadSamples(AudioFrame frame)
    {
        using var buffer = frame.LockBuffer(Windows.Media.AudioBufferAccessMode.Read);
        using var reference = buffer.CreateReference();

        ((IMemoryBufferByteAccess)reference).GetBuffer(out var dataInBytes, out var capacityInBytes);
        var floatCount = (int)(capacityInBytes / sizeof(float));
        var samples = new float[floatCount];
        var floatPtr = (float*)dataInBytes;
        for (var i = 0; i < floatCount; i++)
        {
            samples[i] = floatPtr[i];
        }
        return samples;
    }
}
