using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    public class PointImportTool
    {
        private static CivilDocument CivilDoc =>
            CivilApplication.ActiveDocument;

        private static Database AcDb =>
            Application.DocumentManager.MdiActiveDocument.Database;

        // ── Import points from CSV ────────────────────────────────────────

        /// <summary>
        /// Imports COGO points from a PNEZD (or PENZD) ASCII CSV file.
        /// </summary>
        public object ImportPoints(JObject p)
        {
            var csvPath   = p["csv_path"]!.Value<string>()!;
            var format    = p["format"]?.Value<string>() ?? "PENZD";  // PENZD (E before N) or PNEZD
            var groupName = p["point_group"]?.Value<string>();
            var addToDwg  = p["add_to_drawing"]?.Value<bool>() ?? true;

            if (!File.Exists(csvPath))
                throw new FileNotFoundException($"CSV not found: {csvPath}");

            using var tr = AcDb.TransactionManager.StartTransaction();

            // Resolve import format
            var importManager = CivilDoc.Points;
            var importFileFormat = format.ToUpperInvariant() switch
            {
                "PENZD" => Autodesk.Civil.Settings.PointFileFormat.PENZD,
                _       => Autodesk.Civil.Settings.PointFileFormat.PNEZD,
            };

            // Import — returns collection of new CogoPoint ObjectIds
            var importedIds = importManager.ImportPoints(
                csvPath, importFileFormat,
                addToDrawing: addToDwg,
                useCurrentPointStyle: true,
                useCurrentPointLabelStyle: true);

            // Optionally add to a point group
            if (!string.IsNullOrEmpty(groupName))
            {
                var pg = EnsurePointGroup(tr, groupName);
                pg.UpgradeOpen();
                foreach (ObjectId id in importedIds)
                    pg.PointsIds.Add(id);
            }

            tr.Commit();
            return new { imported = importedIds.Count, group = groupName ?? "(none)" };
        }

        // ── Create figures / feature lines from .B/.E point codes ────────

        /// <summary>
        /// Reads all COGO points, groups them by figure code
        /// (.B&lt;CODE&gt; … &lt;CODE&gt; … .E&lt;CODE&gt;), and draws feature lines
        /// (when a site is given) or plain 3D polylines.
        /// </summary>
        public object CreateFigures(JObject p)
        {
            var layer      = p["layer"]?.Value<string>() ?? "C-SURV-FTRE";
            var siteName   = p["site"]?.Value<string>();
            var filterCodes= p["codes"] is JArray ca
                             ? ca.Select(t => t.Value<string>()!).ToHashSet(
                                   StringComparer.OrdinalIgnoreCase)
                             : null;

            using var tr = AcDb.TransactionManager.StartTransaction();

            // Gather all COGO points in insertion order
            var allPoints = new List<CogoPointData>();
            foreach (ObjectId id in CivilDoc.Points)
            {
                var cp = (CogoPoint)tr.GetObject(id, OpenMode.ForRead);
                allPoints.Add(new CogoPointData(
                    cp.PointNumber, cp.Easting, cp.Northing, cp.Elevation,
                    cp.RawDescription));
            }
            // Sort by point number so figure sequences are in survey order
            allPoints.Sort((a, b) => a.No.CompareTo(b.No));

            // Parse .B / .E codes into figure runs
            var figures = ParseFigures(allPoints, filterCodes);

            // Draw
            EnsureLayer(tr, layer);
            ObjectId siteId = ResolveSite(tr, siteName);
            int drawn = 0;

            foreach (var (code, pts) in figures)
            {
                if (pts.Count < 2) continue;

                if (!siteId.IsNull)
                    DrawFeatureLine(tr, siteId, layer, code, pts);
                else
                    Draw3DPolyline(tr, layer, pts);
                drawn++;
            }

            tr.Commit();
            return new { figures_drawn = drawn, layer };
        }

        // ── Point group ───────────────────────────────────────────────────

        public object CreatePointGroup(JObject p)
        {
            var name         = p["name"]!.Value<string>()!;
            var desc         = p["description"]?.Value<string>() ?? "";
            var includeCodes = p["include_codes"] is JArray ic
                               ? ic.Select(t => t.Value<string>()!).ToArray()
                               : Array.Empty<string>();
            var excludeCodes = p["exclude_codes"] is JArray ec
                               ? ec.Select(t => t.Value<string>()!).ToArray()
                               : Array.Empty<string>();
            var ptNums       = p["include_point_numbers"]?.Value<string>();

            using var tr = AcDb.TransactionManager.StartTransaction();
            var pg = EnsurePointGroup(tr, name);
            pg.UpgradeOpen();
            pg.Description = desc;

            var qf = pg.QueryFilter;
            if (includeCodes.Length > 0)
            {
                qf.RawDescriptionOperator = Autodesk.Civil.FilterOperator.Include;
                qf.RawDescriptions = string.Join(",", includeCodes);
            }
            if (excludeCodes.Length > 0)
            {
                // Civil 3D uses Exclude operator on a secondary filter
                qf.ExcludeRawDescriptions = string.Join(",", excludeCodes);
            }
            if (!string.IsNullOrEmpty(ptNums))
            {
                qf.NumberOperator = Autodesk.Civil.FilterOperator.Include;
                qf.Numbers = ptNums;
            }
            pg.SetQueryFilter(qf);
            pg.Update();
            tr.Commit();
            return new { name, point_count = pg.PointsIds.Count };
        }

        // ── Helpers ───────────────────────────────────────────────────────

        private record CogoPointData(uint No, double X, double Y, double Z, string Desc);

        /// <summary>
        /// Parses the .B/.E code convention into ordered figure lists.
        /// Returns dict[code → ordered point list].
        /// </summary>
        private static Dictionary<string, List<Point3d>> ParseFigures(
            List<CogoPointData> pts, HashSet<string>? filterCodes)
        {
            var figures = new Dictionary<string, List<Point3d>>(
                StringComparer.OrdinalIgnoreCase);
            var openFigs = new Dictionary<string, List<Point3d>>(
                StringComparer.OrdinalIgnoreCase);

            foreach (var cp in pts)
            {
                var d = (cp.Desc ?? "").Trim();
                if (string.IsNullOrEmpty(d)) continue;

                string code;
                bool begin = false, end = false;

                if (d.StartsWith(".B", StringComparison.OrdinalIgnoreCase))
                {
                    code = d[2..]; begin = true;
                }
                else if (d.StartsWith(".E", StringComparison.OrdinalIgnoreCase))
                {
                    code = d[2..]; end = true;
                }
                else
                {
                    code = d;
                }

                if (filterCodes != null && !filterCodes.Contains(code)) continue;

                var pt3d = new Point3d(cp.X, cp.Y, cp.Z);

                if (begin)
                {
                    var list = new List<Point3d> { pt3d };
                    openFigs[code] = list;
                }
                else if (end)
                {
                    if (openFigs.TryGetValue(code, out var list))
                    {
                        list.Add(pt3d);
                        var key = $"{code}_{figures.Count}";
                        figures[key] = list;
                        openFigs.Remove(code);
                    }
                }
                else
                {
                    if (openFigs.TryGetValue(code, out var list))
                        list.Add(pt3d);
                }
            }

            // Close any unclosed figures
            foreach (var (code, list) in openFigs)
                if (list.Count >= 2)
                    figures[$"{code}_{figures.Count}"] = list;

            return figures;
        }

        private static void Draw3DPolyline(Transaction tr, string layer,
            List<Point3d> pts)
        {
            var pl = new Polyline3d(Poly3dType.SimplePoly,
                new Point3dCollection(pts.ToArray()), false)
            { Layer = layer };
            var ms = (BlockTableRecord)tr.GetObject(
                SymbolUtilityServices.GetBlockModelSpaceId(AcDb),
                OpenMode.ForWrite);
            ms.AppendEntity(pl);
            tr.AddNewlyCreatedDBObject(pl, true);
        }

        private static void DrawFeatureLine(Transaction tr, ObjectId siteId,
            string layer, string name, List<Point3d> pts)
        {
            var flStyle = CivilDoc.Styles.FeatureLineStyles[0];
            var flId = FeatureLine.Create(siteId, name, flStyle);
            var fl = (FeatureLine)tr.GetObject(flId, OpenMode.ForWrite);
            fl.Layer = layer;
            foreach (var pt in pts)
                fl.InsertPI(fl.Length, pt, FeatureLinePointType.PIPoint);
        }

        private static ObjectId ResolveSite(Transaction tr, string? name)
        {
            if (string.IsNullOrEmpty(name)) return ObjectId.Null;
            foreach (ObjectId id in CivilDoc.GetSiteIds())
            {
                var s = (Site)tr.GetObject(id, OpenMode.ForRead);
                if (s.Name == name) return id;
            }
            return ObjectId.Null;
        }

        private static PointGroup EnsurePointGroup(Transaction tr, string name)
        {
            foreach (ObjectId id in CivilDoc.PointGroups)
            {
                var pg = (PointGroup)tr.GetObject(id, OpenMode.ForRead);
                if (pg.Name == name) return pg;
            }
            var newId = PointGroup.Create(AcDb, name);
            return (PointGroup)tr.GetObject(newId, OpenMode.ForRead);
        }

        private static void EnsureLayer(Transaction tr, string name)
        {
            var lt = (LayerTable)tr.GetObject(AcDb.LayerTableId,
                OpenMode.ForWrite);
            if (!lt.Has(name))
            {
                var ltr = new LayerTableRecord { Name = name };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }
        }
    }
}
