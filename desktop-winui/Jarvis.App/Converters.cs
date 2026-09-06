using Jarvis.Core.Models;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Media;
using Windows.UI;

namespace Jarvis_App;

public sealed class BoolToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language) =>
        value is true ? Visibility.Visible : Visibility.Collapsed;

    public object ConvertBack(object value, Type targetType, object parameter, string language) =>
        value is Visibility.Visible;
}

/// <summary>Right panel column width: 0 when closed, 360 when open — gives the overlay sheet
/// somewhere to spring open into without a fixed reserved gap when collapsed.</summary>
public sealed class BoolToPanelWidthConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language) =>
        new GridLength(value is true ? 368 : 0);

    public object ConvertBack(object value, Type targetType, object parameter, string language) =>
        throw new NotSupportedException();
}

/// <summary>Activity trace dot color: green=success, red=error, amber=running/other.</summary>
public sealed class ActivityStatusToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        var color = (value as string) switch
        {
            "success" => Color.FromArgb(255, 16, 185, 129),
            "error" => Color.FromArgb(255, 244, 63, 94),
            _ => Color.FromArgb(255, 251, 191, 36),
        };
        return new SolidColorBrush(color);
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language) =>
        throw new NotSupportedException();
}

/// <summary>Severity accent colors, ported from AwarenessTray.tsx's per-severity border/dot styling.</summary>
public sealed class SeverityToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language) =>
        new SolidColorBrush(SeverityColor(value as ObservationSeverity? ?? ObservationSeverity.Info));

    public object ConvertBack(object value, Type targetType, object parameter, string language) =>
        throw new NotSupportedException();

    public static Color SeverityColor(ObservationSeverity severity) => severity switch
    {
        ObservationSeverity.Critical => Color.FromArgb(255, 244, 63, 94),
        ObservationSeverity.Warning => Color.FromArgb(255, 251, 191, 36),
        ObservationSeverity.Notice => Color.FromArgb(255, 6, 182, 212),
        _ => Color.FromArgb(255, 148, 163, 184),
    };
}

/// <summary>Severity background tint (low-alpha version of the same accent color).</summary>
public sealed class SeverityToBackgroundConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        var color = SeverityToBrushConverter.SeverityColor(value as ObservationSeverity? ?? ObservationSeverity.Info);
        return new SolidColorBrush(Color.FromArgb(28, color.R, color.G, color.B));
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language) =>
        throw new NotSupportedException();
}
