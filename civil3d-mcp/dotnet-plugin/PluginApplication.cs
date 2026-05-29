using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.ApplicationServices;

[assembly: ExtensionApplication(typeof(Civil3DMCPPlugin.PluginApplication))]

namespace Civil3DMCPPlugin
{
    public class PluginApplication : IExtensionApplication
    {
        private MCPBridgeServer? _server;

        public void Initialize()
        {
            Application.DocumentManager.MdiActiveDocument?.Editor
                .WriteMessage("\n[Civil3D-MCP] Plugin loading…");

            _server = new MCPBridgeServer(port: 3765);
            _server.Start();

            Application.DocumentManager.MdiActiveDocument?.Editor
                .WriteMessage("\n[Civil3D-MCP] Bridge server listening on http://localhost:3765");
        }

        public void Terminate()
        {
            _server?.Stop();
        }
    }
}
