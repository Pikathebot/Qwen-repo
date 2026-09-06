using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Jarvis.Core.Api;
using Jarvis.Core.Models;
using Microsoft.UI.Dispatching;

namespace Jarvis_App.ViewModels;

/// <summary>Port of the Scheduled Routines section of SettingsDialog.tsx: list, create, toggle
/// enabled, remove, and test-run (POST /api/routines/{id}/run previews one immediately).</summary>
public partial class RoutinesViewModel : ObservableObject
{
    private readonly JarvisApiClient _api;
    private readonly DispatcherQueue _dispatcher;

    public ObservableCollection<Routine> Routines { get; } = new();

    public RoutinesViewModel(JarvisApiClient api, DispatcherQueue dispatcher)
    {
        _api = api;
        _dispatcher = dispatcher;
    }

    [RelayCommand]
    public async Task RefreshAsync()
    {
        try
        {
            var response = await _api.FetchRoutinesAsync().ConfigureAwait(false);
            _dispatcher.TryEnqueue(() =>
            {
                Routines.Clear();
                foreach (var routine in response.Routines) Routines.Add(routine);
            });
        }
        catch
        {
            // best-effort
        }
    }

    public async Task CreateAsync(string name, string time, RoutineKind kind, string? message)
    {
        var routine = await _api.CreateRoutineAsync(new RoutineInput
        {
            Name = name,
            Time = time,
            Kind = kind,
            Message = message,
            Enabled = true,
        }).ConfigureAwait(false);
        _dispatcher.TryEnqueue(() => Routines.Add(routine));
    }

    [RelayCommand]
    public async Task ToggleEnabledAsync(Routine routine)
    {
        var updated = await _api.UpdateRoutineAsync(routine.Id, new RoutineInput
        {
            Name = routine.Name,
            Time = routine.Time,
            Kind = routine.Kind,
            Message = routine.Message,
            Days = routine.Days,
            Enabled = !routine.Enabled,
        }).ConfigureAwait(false);

        _dispatcher.TryEnqueue(() =>
        {
            var index = Routines.IndexOf(routine);
            if (index >= 0) Routines[index] = updated;
        });
    }

    [RelayCommand]
    public async Task DeleteAsync(Routine routine)
    {
        await _api.DeleteRoutineAsync(routine.Id).ConfigureAwait(false);
        _dispatcher.TryEnqueue(() => Routines.Remove(routine));
    }

    [RelayCommand]
    public async Task RunNowAsync(Routine routine)
    {
        await _api.RunRoutineNowAsync(routine.Id).ConfigureAwait(false);
        // The preview arrives as an awareness observation over the SSE stream (kind: "routine:{id}"),
        // handled by AwarenessViewModel — nothing further to do here.
    }
}
