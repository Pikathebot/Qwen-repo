using Microsoft.Graphics.Canvas;
using Microsoft.Graphics.Canvas.UI.Xaml;
using Windows.Graphics.DirectX;

namespace Jarvis_Glass;

/// <summary>
/// Loads the current desktop wallpaper into a CanvasBitmap once and shares it across every
/// LiquidGlassCanvas in the app — each panel refracts a crop of the same bitmap rather than
/// re-decoding the wallpaper file per panel. Re-load on demand (wallpaper change) via Invalidate().
///
/// The load is asynchronous, so the first paint of every panel necessarily happens before the
/// bitmap exists. <see cref="Loaded"/> fires once the attempt resolves — panels subscribe and
/// repaint, otherwise they would keep whatever they drew on that first (bitmap-less) frame
/// forever, which is exactly the bug that made every Tier A panel render as its fallback.
/// </summary>
public static class WallpaperBitmapCache
{
    /// <summary>
    /// Luminance standard deviation (0-255 scale) below which a wallpaper is treated as carrying
    /// no usable detail. Live-wallpaper tools (Wallpaper Engine and friends) set the real desktop
    /// wallpaper to a flat placeholder — on this machine, a solid black 2560x1600 JPEG — and then
    /// animate their own layer over it, which is not in the file we can read. Blurring a flat
    /// image just yields that flat colour, so panels sampling it turn into solid slabs. Below this
    /// threshold we report "no usable wallpaper" and the material falls back to its designed body.
    /// </summary>
    private const double MinUsefulStdDev = 6.0;

    private static CanvasBitmap? _bitmap;
    private static Task<CanvasBitmap?>? _loadTask;

    /// <summary>Raised once a load attempt resolves (success or not), so panels can repaint.</summary>
    public static event Action? Loaded;

    /// <summary>
    /// True when a wallpaper was loaded AND carries enough detail to be worth refracting.
    /// False both when there is no wallpaper file and when the one there is turns out flat.
    /// </summary>
    public static bool HasUsableWallpaper { get; private set; }

    public static Task<CanvasBitmap?> GetAsync(CanvasControl device)
    {
        if (_bitmap is not null)
        {
            return Task.FromResult<CanvasBitmap?>(_bitmap);
        }

        _loadTask ??= LoadAsync(device);
        return _loadTask;
    }

    /// <summary>Forces a re-sample on the next GetAsync — call after a wallpaper-change notification.</summary>
    public static void Invalidate()
    {
        _bitmap?.Dispose();
        _bitmap = null;
        _loadTask = null;
        HasUsableWallpaper = false;
    }

    private static async Task<CanvasBitmap?> LoadAsync(CanvasControl device)
    {
        try
        {
            var path = WallpaperReader.GetCurrentWallpaperPath();
            if (path is null)
            {
                return null;
            }

            var bitmap = await CanvasBitmap.LoadAsync(device, path);
            if (!HasUsableDetail(device, bitmap))
            {
                bitmap.Dispose();
                return null;
            }

            _bitmap = bitmap;
            HasUsableWallpaper = true;
            return bitmap;
        }
        catch
        {
            // Corrupt/unreadable wallpaper file — panels fall back to their designed body.
            return null;
        }
        finally
        {
            Loaded?.Invoke();
        }
    }

    /// <summary>
    /// Downsamples the wallpaper to a thumbnail and measures luminance spread. A thumbnail is
    /// enough — we are asking "is there any large-scale variation left after a heavy blur", which
    /// is precisely what surviving a downscale to 32px measures.
    /// </summary>
    private static bool HasUsableDetail(CanvasControl device, CanvasBitmap bitmap)
    {
        const int probe = 32;
        try
        {
            using var thumb = new CanvasRenderTarget(device, probe, probe, 96f,
                DirectXPixelFormat.B8G8R8A8UIntNormalized, CanvasAlphaMode.Premultiplied);
            using (var ds = thumb.CreateDrawingSession())
            {
                ds.Clear(Windows.UI.Color.FromArgb(255, 0, 0, 0));
                ds.DrawImage(bitmap, new Windows.Foundation.Rect(0, 0, probe, probe));
            }

            var pixels = thumb.GetPixelColors();
            double sum = 0, sumSq = 0;
            foreach (var p in pixels)
            {
                // Rec. 601 luma — cheap and adequate for a "is this flat?" question.
                var luma = 0.299 * p.R + 0.587 * p.G + 0.114 * p.B;
                sum += luma;
                sumSq += luma * luma;
            }

            var mean = sum / pixels.Length;
            var variance = Math.Max(0, sumSq / pixels.Length - mean * mean);
            return Math.Sqrt(variance) >= MinUsefulStdDev;
        }
        catch
        {
            // If the probe itself fails, assume the wallpaper is fine rather than losing it.
            return true;
        }
    }
}
