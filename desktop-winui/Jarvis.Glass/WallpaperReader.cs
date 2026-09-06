using System.Runtime.InteropServices;
using System.Text;

namespace Jarvis_Glass;

/// <summary>
/// Reads the current desktop wallpaper path, for the "sampled wallpaper" backdrop decision in the
/// plan: the shell draws the user's real wallpaper (dimmed/tinted) as its own backdrop and Tier A
/// glass refracts that, rather than an arbitrary app gradient. Falls back to the solid desktop
/// background color when there is no wallpaper file (slideshow/solid-color desktops report an
/// empty path here).
/// </summary>
public static class WallpaperReader
{
    private const int SpiGetDeskWallpaper = 0x0073;
    private const int MaxPath = 260;

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SystemParametersInfoW(int uiAction, int uiParam, StringBuilder pvParam, int fWinIni);

    /// <summary>Full path to the current wallpaper bitmap, or null if none is set (solid color / slideshow gap).</summary>
    public static string? GetCurrentWallpaperPath()
    {
        var buffer = new StringBuilder(MaxPath);
        if (!SystemParametersInfoW(SpiGetDeskWallpaper, MaxPath, buffer, 0))
        {
            return null;
        }

        var path = buffer.ToString();
        return string.IsNullOrWhiteSpace(path) || !File.Exists(path) ? null : path;
    }
}
