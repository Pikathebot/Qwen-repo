using Jarvis.Core.Models;
using Jarvis_App.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;

namespace Jarvis_App.Views;

/// <summary>Native port of AwarenessTray.tsx.</summary>
public sealed partial class AwarenessTray : UserControl
{
    public AwarenessViewModel ViewModel { get; }

    public AwarenessTray(AwarenessViewModel viewModel)
    {
        ViewModel = viewModel;
        InitializeComponent();
        ViewModel.Observations.CollectionChanged += (_, _) => UpdateDismissAllLink();
        UpdateDismissAllLink();
    }

    private void UpdateDismissAllLink()
    {
        DismissAllLink.Visibility = ViewModel.Observations.Count > 1 ? Visibility.Visible : Visibility.Collapsed;
        DismissAllLink.Text = $"dismiss all ({ViewModel.Observations.Count})";
    }

    private void DismissObservation_Click(object sender, RoutedEventArgs e)
    {
        if (sender is FrameworkElement { Tag: Observation observation })
        {
            ViewModel.Dismiss(observation);
        }
    }

    private void DismissAll_Tapped(object sender, TappedRoutedEventArgs e) => ViewModel.DismissAll();
}
