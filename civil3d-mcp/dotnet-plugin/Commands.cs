using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.ApplicationServices;

namespace Civil3DMCPPlugin
{
    public static class Commands
    {
        [CommandMethod("MCP_STATUS")]
        public static void ShowStatus()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            doc.Editor.WriteMessage(
                "\n[Civil3D-MCP] Bridge server running on http://localhost:3765\n" +
                "Use the Python MCP server (civil3d-mcp) to connect AI agents.\n");
        }
    }
}
