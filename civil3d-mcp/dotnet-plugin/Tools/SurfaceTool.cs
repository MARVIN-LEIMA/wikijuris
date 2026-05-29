using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    public class SurfaceTool
    {
        private static CivilDocument CivilDoc =>
            CivilApplication.ActiveDocument;

        private static Database AcDb =>
            Application.DocumentManager.MdiActiveDocument.Database;

        private TinSurface GetSurface(Transaction tr, string name)
        {
            foreach (ObjectId id in CivilDoc.GetSurfaceIds())
            {
                var surf = tr.GetObject(id, OpenMode.ForRead) as TinSurface;
                if (surf?.Name == name) return surf;
            }
            throw new System.Exception($"Surface '{name}' not found");
        }

        public object CreateTinSurface(JObject p)
        {
            var name = p["name"]!.Value<string>()!;
            var description = p["description"]?.Value<string>() ?? "";
            var layer = p["layer"]?.Value<string>() ?? "C-TOPO";

            using var tr = AcDb.TransactionManager.StartTransaction();

            var surfId = TinSurface.Create(name, AcDb);
            var surf = (TinSurface)tr.GetObject(surfId, OpenMode.ForWrite);
            surf.Description = description;

            // Ensure layer exists
            var lt = (LayerTable)tr.GetObject(AcDb.LayerTableId, OpenMode.ForWrite);
            if (!lt.Has(layer))
            {
                var ltr = new LayerTableRecord { Name = layer };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }
            surf.Layer = layer;

            tr.Commit();
            return new { name, handle = surfId.Handle.ToString() };
        }

        public object AddPoints(JObject p)
        {
            var name = p["surface"]!.Value<string>()!;
            var points = (JArray)p["points"]!;

            using var tr = AcDb.TransactionManager.StartTransaction();
            var surf = GetSurface(tr, name);
            surf.UpgradeOpen();

            var ptList = new List<Point3d>();
            foreach (var pt in points)
                ptList.Add(new Point3d(pt[0]!.Value<double>(),
                    pt[1]!.Value<double>(), pt[2]!.Value<double>()));

            surf.AddVertex(ptList.ToArray());
            tr.Commit();
            return new { added = ptList.Count };
        }

        public object AddBreaklines(JObject p)
        {
            var name = p["surface"]!.Value<string>()!;
            var lines = (JArray)p["lines"]!;
            var blType = p["type"]?.Value<string>() == "proximity"
                ? BreaklineType.Proximity
                : BreaklineType.Standard;

            using var tr = AcDb.TransactionManager.StartTransaction();
            var surf = GetSurface(tr, name);
            surf.UpgradeOpen();

            var desc = p["description"]?.Value<string>() ?? "Breaklines";
            var blId = surf.BreaklinesDefinition.AddBreaklines(desc, blType, 0.01, 0.01, 0.01);
            var bl = (SurfaceBreaklines)tr.GetObject(blId, OpenMode.ForWrite);

            foreach (JArray seg in lines)
            {
                var pts = new Point3dCollection();
                foreach (var pt in seg)
                    pts.Add(new Point3d(pt[0]!.Value<double>(),
                        pt[1]!.Value<double>(), pt[2]!.Value<double>()));
                bl.AddBreakline(pts);
            }

            tr.Commit();
            return new { breakline_group = desc };
        }

        public object AddBoundary(JObject p)
        {
            var name = p["surface"]!.Value<string>()!;
            var pts = (JArray)p["points"]!;
            var bdType = p["type"]?.Value<string>() switch
            {
                "hide" => SurfaceBoundaryType.Hide,
                "show" => SurfaceBoundaryType.Show,
                "data" => SurfaceBoundaryType.Data,
                _ => SurfaceBoundaryType.Outer
            };

            using var tr = AcDb.TransactionManager.StartTransaction();
            var surf = GetSurface(tr, name);
            surf.UpgradeOpen();

            var ptList = new Point3dCollection();
            foreach (var pt in pts)
                ptList.Add(new Point3d(pt[0]!.Value<double>(),
                    pt[1]!.Value<double>(), 0));

            surf.BoundariesDefinition.AddBoundaries(ptList,
                0.01, bdType, true);
            tr.Commit();
            return new { boundary_type = bdType.ToString() };
        }

        public object BuildSurface(JObject p)
        {
            var name = p["surface"]!.Value<string>()!;
            using var tr = AcDb.TransactionManager.StartTransaction();
            var surf = GetSurface(tr, name);
            surf.UpgradeOpen();
            surf.Rebuild();
            tr.Commit();
            return new { status = "rebuilt" };
        }

        public object GetElevation(JObject p)
        {
            var name = p["surface"]!.Value<string>()!;
            var x = p["x"]!.Value<double>();
            var y = p["y"]!.Value<double>();

            using var tr = AcDb.TransactionManager.StartTransaction();
            var surf = GetSurface(tr, name);
            double z = surf.FindElevationAtXY(x, y);
            tr.Commit();
            return new { x, y, elevation = z };
        }
    }
}
