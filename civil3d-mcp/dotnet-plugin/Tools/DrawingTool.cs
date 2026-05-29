using System;
using System.IO;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    public class DrawingTool
    {
        // ── New drawing from template ─────────────────────────────────────

        public object NewFromTemplate(JObject p)
        {
            var templatePath = p["template_path"]!.Value<string>()!;
            var outputPath   = p["output_path"]!.Value<string>()!;

            if (!File.Exists(templatePath))
                throw new FileNotFoundException($"Template not found: {templatePath}");

            var dir = Path.GetDirectoryName(outputPath)!;
            if (!string.IsNullOrEmpty(dir))
                Directory.CreateDirectory(dir);

            // Create new document from the specified template.
            // DocumentManager.Add activates the new document immediately.
            var docColl = Application.DocumentManager;
            Document newDoc = docColl.Add(templatePath);

            // Save to the requested output path
            newDoc.Database.SaveAs(outputPath, DwgVersion.Current);

            return new
            {
                output_path = outputPath,
                template    = Path.GetFileName(templatePath),
            };
        }

        // ── Save / Save As ────────────────────────────────────────────────

        public object SaveDrawing(JObject p)
        {
            var doc  = Application.DocumentManager.MdiActiveDocument;
            var path = p["path"]?.Value<string>();

            if (!string.IsNullOrEmpty(path))
            {
                var dir = Path.GetDirectoryName(path)!;
                if (!string.IsNullOrEmpty(dir))
                    Directory.CreateDirectory(dir);
                doc.Database.SaveAs(path, DwgVersion.Current);
                return new { saved_path = path };
            }

            // Normal save (overwrites current file)
            doc.Database.Save();
            return new { saved_path = doc.Name };
        }

        // ── Query active drawing info ─────────────────────────────────────

        public object GetDrawingInfo(JObject _)
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            return new
            {
                path     = doc.Name,
                modified = doc.Database.IsModified,
            };
        }
    }
}
