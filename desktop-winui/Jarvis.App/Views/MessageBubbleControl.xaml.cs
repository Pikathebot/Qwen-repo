using System.ComponentModel;
using System.Text.Json;
using Jarvis.Core.Models;
using Jarvis_App.Rendering;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace Jarvis_App.Views;

/// <summary>
/// Native port of MessageBubble.tsx. Renders whichever of the three variants (system/user/
/// assistant) the bound ChatMessage.Role calls for, re-rendering markdown content whenever it
/// changes (i.e. on every streamed token) via MarkdownRenderer. Relies on classic
/// Binding/DataContext propagation from the hosting ListView's DataTemplate — see the note on
/// MainWindow.xaml's MessageList template.
/// </summary>
public sealed partial class MessageBubbleControl : UserControl
{
    public event Action<PendingConfirmation>? ApproveRequested;
    public event Action<PendingConfirmation>? DenyRequested;

    private ChatMessage? _message;

    public MessageBubbleControl()
    {
        InitializeComponent();
        DataContextChanged += (_, _) => Bind(DataContext as ChatMessage);
    }

    private void Bind(ChatMessage? message)
    {
        if (_message is not null)
        {
            _message.PropertyChanged -= OnMessagePropertyChanged;
        }
        _message = message;
        if (_message is not null)
        {
            _message.PropertyChanged += OnMessagePropertyChanged;
        }
        Render();
    }

    private void OnMessagePropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName is nameof(ChatMessage.Content) or nameof(ChatMessage.IsStreaming))
        {
            DispatcherQueue.TryEnqueue(Render);
        }
    }

    private void Render()
    {
        var message = _message;
        if (message is null) return;

        SystemPill.Visibility = Visibility.Collapsed;
        UserRow.Visibility = Visibility.Collapsed;
        AssistantRow.Visibility = Visibility.Collapsed;

        switch (message.Role)
        {
            case MessageRole.System:
                SystemPill.Visibility = Visibility.Visible;
                SystemText.Text = message.Content;
                break;

            case MessageRole.User:
                UserRow.Visibility = Visibility.Visible;
                UserText.Text = message.Content;
                break;

            default:
                AssistantRow.Visibility = Visibility.Visible;
                RenderAssistant(message);
                break;
        }
    }

    private void RenderAssistant(ChatMessage message)
    {
        ContentHost.Content = MarkdownRenderer.Render(message.Content, message.IsStreaming);
        StreamingCaret.Visibility = message.IsStreaming ? Visibility.Visible : Visibility.Collapsed;

        RenderToolSteps(message);
        RenderConfirmation(message);
        RenderMetadata(message);
    }

    private void RenderToolSteps(ChatMessage message)
    {
        if (message.ToolSteps.Count == 0)
        {
            ToolStepsHost.Visibility = Visibility.Collapsed;
            return;
        }
        ToolStepsHost.Visibility = Visibility.Visible;
        ToolStepsHost.Items.Clear();
        foreach (var step in message.ToolSteps)
        {
            ToolStepsHost.Items.Add(new ToolStepCard(step));
        }
    }

    private void RenderConfirmation(ChatMessage message)
    {
        var confirmation = message.PendingConfirmations.FirstOrDefault();
        if (confirmation is null)
        {
            ConfirmationBanner.Visibility = Visibility.Collapsed;
            return;
        }

        ConfirmationBanner.Visibility = Visibility.Visible;
        ConfirmationBanner.Tag = confirmation;
        ConfirmationTitle.Text = $"I need your approval to run: {confirmation.Tool}" +
            (string.IsNullOrEmpty(confirmation.RiskTier) ? "" : $" ({confirmation.RiskTier})");
        ConfirmationReason.Text = confirmation.Reason ?? "";
        try
        {
            ConfirmationArgs.Text = JsonSerializer.Serialize(confirmation.ArgsRaw, new JsonSerializerOptions { WriteIndented = true });
        }
        catch
        {
            ConfirmationArgs.Text = confirmation.ArgsRaw.ToString();
        }
    }

    private void RenderMetadata(ChatMessage message)
    {
        if (string.IsNullOrEmpty(message.Model) && string.IsNullOrEmpty(message.Provider))
        {
            MetadataFooter.Visibility = Visibility.Collapsed;
            return;
        }
        MetadataFooter.Visibility = Visibility.Visible;
        MetadataFooter.Text = string.Join(" · ", new[] { message.Provider, message.Model }.Where(s => !string.IsNullOrEmpty(s)));
    }

    private void ApproveButton_Click(object sender, RoutedEventArgs e)
    {
        if (ConfirmationBanner.Tag is PendingConfirmation confirmation)
        {
            ApproveRequested?.Invoke(confirmation);
        }
    }

    private void DenyButton_Click(object sender, RoutedEventArgs e)
    {
        if (ConfirmationBanner.Tag is PendingConfirmation confirmation)
        {
            DenyRequested?.Invoke(confirmation);
        }
    }
}
