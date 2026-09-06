using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Jarvis.Core.Api;
using Jarvis.Core.Models;
using Microsoft.UI.Dispatching;

namespace Jarvis_App.ViewModels;

/// <summary>Port of the Persona section of SettingsDialog.tsx: active persona, available list,
/// address-term/voice/reply-length overrides.</summary>
public partial class PersonaViewModel : ObservableObject
{
    private readonly JarvisApiClient _api;
    private readonly DispatcherQueue _dispatcher;

    [ObservableProperty]
    public partial PersonaStatus? Status { get; set; }

    public ObservableCollection<PersonaSummary> Available { get; } = new();

    public PersonaViewModel(JarvisApiClient api, DispatcherQueue dispatcher)
    {
        _api = api;
        _dispatcher = dispatcher;
    }

    [RelayCommand]
    public async Task RefreshAsync()
    {
        try
        {
            var status = await _api.FetchPersonaAsync().ConfigureAwait(false);
            _dispatcher.TryEnqueue(() =>
            {
                Status = status;
                Available.Clear();
                foreach (var persona in status.Available) Available.Add(persona);
            });
        }
        catch
        {
            // best-effort
        }
    }

    [RelayCommand]
    public async Task SelectAsync(PersonaSummary persona)
    {
        var status = await _api.SetPersonaAsync(persona.Id).ConfigureAwait(false);
        _dispatcher.TryEnqueue(() => Status = status);
    }

    public async Task SetAddressTermAsync(string addressTerm)
    {
        var status = await _api.SetPersonaOverridesAsync(new PersonaOverrides { AddressTerm = addressTerm }).ConfigureAwait(false);
        _dispatcher.TryEnqueue(() => Status = status);
    }

    [RelayCommand]
    public async Task ResetOverridesAsync()
    {
        var status = await _api.ClearPersonaOverridesAsync().ConfigureAwait(false);
        _dispatcher.TryEnqueue(() => Status = status);
    }
}
