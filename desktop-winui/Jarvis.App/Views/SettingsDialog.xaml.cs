using Jarvis.Core.Api;
using Jarvis.Core.Models;
using Jarvis_App.Services;
using Jarvis_App.ViewModels;
using Jarvis_Glass;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace Jarvis_App.Views;

/// <summary>Native port of SettingsDialog.tsx (backend/model info, persona, proactive-actions
/// toggle, plus a Glass quality control that doesn't exist in the original — see the plan's
/// auto-degrade decision).</summary>
public sealed partial class SettingsDialog : ContentDialog
{
    private readonly JarvisApiClient _api;
    private readonly GovernorViewModel _governor;
    private readonly GlassQualityService _glassQuality;

    public PersonaViewModel PersonaViewModel { get; }
    public RoutinesViewModel RoutinesViewModel { get; }

    public SettingsDialog(
        JarvisApiClient api,
        GovernorViewModel governor,
        PersonaViewModel personaViewModel,
        RoutinesViewModel routinesViewModel,
        GlassQualityService glassQuality)
    {
        _api = api;
        _governor = governor;
        _glassQuality = glassQuality;
        PersonaViewModel = personaViewModel;
        RoutinesViewModel = routinesViewModel;
        InitializeComponent();
        Loaded += SettingsDialog_Loaded;
    }

    private async void SettingsDialog_Loaded(object sender, RoutedEventArgs e)
    {
        BackendText.Text = string.IsNullOrEmpty(_governor.ActiveBackend) ? "Offline" : _governor.ActiveBackend;
        // Set before subscribing, so seeding the current mode doesn't count as a user change.
        GlassQualityCombo.SelectedIndex = _glassQuality.Controller.Mode switch
        {
            GlassQualityMode.Full => 1,
            GlassQualityMode.System => 2,
            _ => 0,
        };
        GlassQualityCombo.SelectionChanged += GlassQuality_SelectionChanged;
        ModelText.Text = _governor.ConfiguredModel;

        await PersonaViewModel.RefreshAsync();
        RefreshPersonaHighlight();
        AddressTermBox.PlaceholderText = PersonaViewModel.Status?.Active.AddressTerm ?? "sir";

        await RoutinesViewModel.RefreshAsync();

        try
        {
            var awareness = await _api.FetchAwarenessStatusAsync();
            ProactiveActionsToggle.IsOn = awareness.Monitor.ActionsEnabled;
        }
        catch
        {
            // leave default
        }
    }

    private void GlassQuality_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        _glassQuality.SetMode(GlassQualityCombo.SelectedIndex switch
        {
            1 => GlassQualityMode.Full,
            2 => GlassQualityMode.System,
            _ => GlassQualityMode.Auto,
        });
    }

    private void RefreshPersonaHighlight()
    {
        var activeId = PersonaViewModel.Status?.ActiveId;
        foreach (var item in PersonaList.Items)
        {
            var container = PersonaList.ContainerFromItem(item) as ListViewItem;
            if (container?.ContentTemplateRoot is not FrameworkElement root) continue;
            var badge = root.FindName("ActiveBadge") as FrameworkElement;
            if (badge is not null && item is PersonaSummary summary)
            {
                badge.Visibility = summary.Id == activeId ? Visibility.Visible : Visibility.Collapsed;
            }
        }
    }

    private async void PersonaItem_Tapped(object sender, Microsoft.UI.Xaml.Input.TappedRoutedEventArgs e)
    {
        if (sender is FrameworkElement { Tag: PersonaSummary persona })
        {
            await PersonaViewModel.SelectAsync(persona);
            RefreshPersonaHighlight();
        }
    }

    private async void ApplyAddressTerm_Click(object sender, RoutedEventArgs e)
    {
        var text = AddressTermBox.Text.Trim();
        if (string.IsNullOrEmpty(text)) return;
        await PersonaViewModel.SetAddressTermAsync(text);
        AddressTermBox.Text = "";
        AddressTermBox.PlaceholderText = text;
    }

    private async void ResetOverrides_Click(object sender, RoutedEventArgs e)
    {
        await PersonaViewModel.ResetOverridesAsync();
        AddressTermBox.PlaceholderText = PersonaViewModel.Status?.Active.AddressTerm ?? "sir";
    }

    private async void ProactiveActionsToggle_Toggled(object sender, RoutedEventArgs e)
    {
        try
        {
            await _api.UpdateAwarenessConfigAsync(new AwarenessConfigPatch { ActionsEnabled = ProactiveActionsToggle.IsOn });
        }
        catch
        {
            // best-effort; toggle stays as the user left it visually
        }
    }

    private async void AddRoutine_Click(object sender, RoutedEventArgs e)
    {
        var name = RoutineNameBox.Text.Trim();
        if (string.IsNullOrEmpty(name)) return;
        var time = RoutineTimePicker.Time;

        var kind = (RoutineKindCombo.SelectedItem as ComboBoxItem)?.Content as string == "message"
            ? RoutineKind.Message
            : RoutineKind.Briefing;

        await RoutinesViewModel.CreateAsync(name, $"{time.Hours:D2}:{time.Minutes:D2}", kind, RoutineMessageBox.Text);
        RoutineNameBox.Text = "";
        RoutineMessageBox.Text = "";
    }

    private async void RunRoutine_Click(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement { Tag: Routine routine })
        {
            await RoutinesViewModel.RunNowAsync(routine);
        }
    }

    private async void RemoveRoutine_Click(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement { Tag: Routine routine })
        {
            await RoutinesViewModel.DeleteAsync(routine);
        }
    }
}
