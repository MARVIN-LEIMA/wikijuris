using System;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.Geometry;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    public class CadPrimitivesTool
    {
        // ── helpers ────────────────────────────────────────────────────────

        private static Database Db =>
            Application.DocumentManager.MdiActiveDocument.Database;

        private static string EnsureLayer(Transaction tr, string layerName,
            short colorIndex = 7)
        {
            var lt = (LayerTable)tr.GetObject(Db.LayerTableId, OpenMode.ForRead);
            if (!lt.Has(layerName))
            {
                lt.UpgradeOpen();
                var ltr = new LayerTableRecord
                {
                    Name = layerName,
                    Color = Color.FromColorIndex(ColorMethod.ByAci, colorIndex)
                };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }
            return layerName;
        }

        private static ObjectId AddToModelSpace(Transaction tr, Entity entity)
        {
            var ms = (BlockTableRecord)tr.GetObject(
                SymbolUtilityServices.GetBlockModelSpaceId(Db), OpenMode.ForWrite);
            var id = ms.AppendEntity(entity);
            tr.AddNewlyCreatedDBObject(entity, true);
            return id;
        }

        private static Point3d ToPoint3d(JToken t) =>
            new(t[0]!.Value<double>(), t[1]!.Value<double>(),
                t.Count() > 2 ? t[2]!.Value<double>() : 0);

        // ── public API ─────────────────────────────────────────────────────

        public object DrawPoint(JObject p)
        {
            var pt = ToPoint3d(p["point"]!);
            var layer = p["layer"]?.Value<string>() ?? "0";

            using var tr = Db.TransactionManager.StartTransaction();
            EnsureLayer(tr, layer);
            var dbpt = new DBPoint(pt) { Layer = layer };
            var id = AddToModelSpace(tr, dbpt);
            tr.Commit();
            return new { handle = id.Handle.ToString() };
        }

        public object DrawLine(JObject p)
        {
            var start = ToPoint3d(p["start"]!);
            var end = ToPoint3d(p["end"]!);
            var layer = p["layer"]?.Value<string>() ?? "0";

            using var tr = Db.TransactionManager.StartTransaction();
            EnsureLayer(tr, layer);
            var line = new Line(start, end) { Layer = layer };
            var id = AddToModelSpace(tr, line);
            tr.Commit();
            return new { handle = id.Handle.ToString() };
        }

        public object DrawPolyline(JObject p)
        {
            var pts = (JArray)p["points"]!;
            var closed = p["closed"]?.Value<bool>() ?? false;
            var layer = p["layer"]?.Value<string>() ?? "0";
            var elevation = p["elevation"]?.Value<double>() ?? 0;

            using var tr = Db.TransactionManager.StartTransaction();
            EnsureLayer(tr, layer);

            var pl = new Polyline { Layer = layer, Elevation = elevation, Closed = closed };
            for (int i = 0; i < pts.Count; i++)
            {
                var pt = pts[i]!;
                pl.AddVertexAt(i,
                    new Point2d(pt[0]!.Value<double>(), pt[1]!.Value<double>()),
                    0, 0, 0);
            }

            var id = AddToModelSpace(tr, pl);
            tr.Commit();
            return new { handle = id.Handle.ToString(), vertices = pts.Count };
        }

        public object DrawArc(JObject p)
        {
            var center = ToPoint3d(p["center"]!);
            var radius = p["radius"]!.Value<double>();
            var startAngle = p["start_angle"]!.Value<double>() * Math.PI / 180;
            var endAngle = p["end_angle"]!.Value<double>() * Math.PI / 180;
            var layer = p["layer"]?.Value<string>() ?? "0";

            using var tr = Db.TransactionManager.StartTransaction();
            EnsureLayer(tr, layer);
            var arc = new Arc(center, radius, startAngle, endAngle) { Layer = layer };
            var id = AddToModelSpace(tr, arc);
            tr.Commit();
            return new { handle = id.Handle.ToString() };
        }

        public object DrawCircle(JObject p)
        {
            var center = ToPoint3d(p["center"]!);
            var radius = p["radius"]!.Value<double>();
            var layer = p["layer"]?.Value<string>() ?? "0";

            using var tr = Db.TransactionManager.StartTransaction();
            EnsureLayer(tr, layer);
            var circle = new Circle(center, Vector3d.ZAxis, radius) { Layer = layer };
            var id = AddToModelSpace(tr, circle);
            tr.Commit();
            return new { handle = id.Handle.ToString() };
        }

        public object DrawText(JObject p)
        {
            var pt = ToPoint3d(p["position"]!);
            var text = p["text"]!.Value<string>()!;
            var height = p["height"]?.Value<double>() ?? 2.5;
            var layer = p["layer"]?.Value<string>() ?? "0";
            var rotation = (p["rotation"]?.Value<double>() ?? 0) * Math.PI / 180;

            using var tr = Db.TransactionManager.StartTransaction();
            EnsureLayer(tr, layer);
            var mtext = new MText
            {
                Location = pt,
                TextHeight = height,
                Layer = layer,
                Rotation = rotation,
                Contents = text
            };
            var id = AddToModelSpace(tr, mtext);
            tr.Commit();
            return new { handle = id.Handle.ToString() };
        }

        public object CreateLayer(JObject p)
        {
            var name = p["name"]!.Value<string>()!;
            var colorIndex = p["color"]?.Value<short>() ?? 7;
            var linetype = p["linetype"]?.Value<string>() ?? "Continuous";

            using var tr = Db.TransactionManager.StartTransaction();

            var lt = (LayerTable)tr.GetObject(Db.LayerTableId, OpenMode.ForWrite);
            if (!lt.Has(name))
            {
                var ltr = new LayerTableRecord
                {
                    Name = name,
                    Color = Color.FromColorIndex(ColorMethod.ByAci, colorIndex)
                };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }
            tr.Commit();
            return new { layer = name };
        }
    }
}
