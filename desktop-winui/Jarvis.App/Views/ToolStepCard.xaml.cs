using System.Text.Json;
using Jarvis.Core.Models;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Windows.UI;

namespace Jarvis_App.Views;

/// <summary>Native port of ToolStepCard.tsx: collapsible inline tool call card with a status badge.</summary>
public sealed partial class ToolStepCard : UserControl
{
    public ToolStepCard(ToolStep step)
    {
        InitializeComponent();
        ToolName.Text = step.Tool;

        var (label, color) = step.Status switch
        {
            ToolStatus.Running => ("Running", Color.FromArgb(255, 251, 191, 36)),
            ToolStatus.Success => ("Completed", Color.FromArgb(255, 16, 185, 129)),
            ToolStatus.Error => ("Failed", Color.FromArgb(255, 244, 63, 94)),
            _ => ("Unknown", Color.FromArgb(255, 148, 163, 184)),
        };
        StatusText.Text = label;
        StatusText.Foreground = new SolidColorBrush(color);
        StatusBadge.Background = new SolidColorBrush(Color.FromArgb(30, color.R, color.G, color.B));

        try
        {
            ArgsText.Text = step.Args.Count > 0
                ? JsonSerializer.Serialize(step.Args, new JsonSerializerOptions { WriteIndented = true })
                : step.RawArgs ?? "";
        }
        catch
        {
            ArgsText.Text = step.RawArgs ?? "";
        }

        if (step.Result is null)
        {
            ResultLabel.Visibility = Microsoft.UI.Xaml.Visibility.Collapsed;
            ResultText.Visibility = Microsoft.UI.Xaml.Visibility.Collapsed;
        }
        else
        {
            try
            {
                ResultText.Text = JsonSerializer.Serialize(step.Result, new JsonSerializerOptions { WriteIndented = true });
            }
            catch
            {
                ResultText.Text = step.Result.ToString() ?? "";
            }
        }
    }
}
