using Microsoft.UI.Xaml;

namespace TennisBettingWinUI;

public sealed partial class MainWindow : Window
{
    public MainWindow()
    {
        this.InitializeComponent();

        // Set window title and size
        Title = "Tennis Betting System";

        // Set minimum size
        var appWindow = this.AppWindow;
        appWindow.Resize(new Windows.Graphics.SizeInt32(1400, 900));
    }
}
