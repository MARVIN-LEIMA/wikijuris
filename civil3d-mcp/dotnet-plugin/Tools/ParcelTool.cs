using System.Collections.Generic;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    public class ParcelTool
    {
        private static CivilDocument CivilDoc =>
            CivilApplication.ActiveDocument;

        private static Database AcDb =>
            Application.DocumentManager.MdiActiveDocument.Database;

        public object CreateSite(JObject p)
        {
            var name = p["name"]!.Value<string>()!;
            var desc = p["description"]?.Value<string>() ?? "";

            using var tr = AcDb.TransactionManager.StartTransaction();

            var siteId = Site.Create(AcDb, name);
            var site = (Site)tr.GetObject(siteId, OpenMode.ForWrite);
            site.Description = desc;
            tr.Commit();
            return new { name, handle = siteId.Handle.ToString() };
        }

        public object CreateFromPolyline(JObject p)
        {
            var siteName = p["site"]!.Value<string>()!;
            var pts = (JArray)p["points"]!;
            var layer = p["layer"]?.Value<string>() ?? "C-PROP";

            using var tr = AcDb.TransactionManager.StartTransaction();

            // Find site
            ObjectId siteId = ObjectId.Null;
            foreach (ObjectId id in CivilDoc.GetSiteIds())
            {
                var s = (Site)tr.GetObject(id, OpenMode.ForRead);
                if (s.Name == siteName) { siteId = id; break; }
            }
            if (siteId.IsNull)
                throw new System.Exception($"Site '{siteName}' not found");

            // Build the boundary polyline
            var pl = new Polyline { Closed = true, Layer = layer };
            for (int i = 0; i < pts.Count; i++)
            {
                var pt = pts[i]!;
                pl.AddVertexAt(i,
                    new Point2d(pt[0]!.Value<double>(), pt[1]!.Value<double>()),
                    0, 0, 0);
            }
            var ms = (BlockTableRecord)tr.GetObject(
                SymbolUtilityServices.GetBlockModelSpaceId(AcDb), OpenMode.ForWrite);
            var plId = ms.AppendEntity(pl);
            tr.AddNewlyCreatedDBObject(pl, true);

            // Create parcel from the polyline
            var parcelIds = Parcel.CreateFromPolyline(AcDb, siteId,
                new ObjectIdCollection(new[] { plId }));

            tr.Commit();
            return new { site = siteName, parcels_created = parcelIds.Count };
        }

        public object Subdivide(JObject p)
        {
            // Subdivision creates new parcels by adding segment lines into a site
            var siteName = p["site"]!.Value<string>()!;
            var lines = (JArray)p["segment_lines"]!;
            var layer = p["layer"]?.Value<string>() ?? "C-PROP";

            using var tr = AcDb.TransactionManager.StartTransaction();

            ObjectId siteId = ObjectId.Null;
            foreach (ObjectId id in CivilDoc.GetSiteIds())
            {
                var s = (Site)tr.GetObject(id, OpenMode.ForRead);
                if (s.Name == siteName) { siteId = id; break; }
            }
            if (siteId.IsNull)
                throw new System.Exception($"Site '{siteName}' not found");

            var ms = (BlockTableRecord)tr.GetObject(
                SymbolUtilityServices.GetBlockModelSpaceId(AcDb), OpenMode.ForWrite);

            var addedIds = new ObjectIdCollection();
            foreach (JArray seg in lines)
            {
                var start = new Point3d(seg[0]![0]!.Value<double>(),
                    seg[0]![1]!.Value<double>(), 0);
                var end = new Point3d(seg[1]![0]!.Value<double>(),
                    seg[1]![1]!.Value<double>(), 0);
                var line = new Line(start, end) { Layer = layer };
                var lid = ms.AppendEntity(line);
                tr.AddNewlyCreatedDBObject(line, true);
                addedIds.Add(lid);
            }

            // Adding segment lines to the site triggers subdivision
            Parcel.CreateFromPolyline(AcDb, siteId, addedIds);
            tr.Commit();
            return new { site = siteName, segments_added = addedIds.Count };
        }
    }
}
