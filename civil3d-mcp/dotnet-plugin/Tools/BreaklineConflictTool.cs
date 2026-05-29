using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    /// <summary>
    /// Detects and auto-fixes crossing / overlapping 3-D breaklines (Polyline3d objects)
    /// that would cause TIN surface artefacts in Civil 3D.
    ///
    /// Fix strategy
    /// ────────────
    /// For each pair of crossing segments, a shared vertex is inserted in BOTH
    /// polylines at the XY intersection point.  Each polyline keeps its own
    /// interpolated Z so that the survey data is preserved.  When the two Z values
    /// are within z_snap_mm they are averaged (snapped) to a single elevation.
    ///
    /// Result: breaklines share a common vertex at every crossing → Civil 3D's TIN
    /// triangulator can enforce both breaklines without ambiguity.
    /// </summary>
    public class BreaklineConflictTool
    {
        private static Database AcDb =>
            Application.DocumentManager.MdiActiveDocument.Database;

        // ── Public API ────────────────────────────────────────────────────

        public object CheckConflicts(JObject p)
        {
            var layers    = ParseLayers(p);
            var tolerance = p["tolerance_m"]?.Value<double>() ?? 0.001;

            using var tr = AcDb.TransactionManager.StartTransaction();
            var lines = CollectPolylines(tr, layers);
            var conflicts = FindConflicts(tr, lines, tolerance);
            tr.Commit();

            return new
            {
                total_conflicts = conflicts.Count,
                conflicts = conflicts.Select(c => new
                {
                    type           = c.Type.ToString(),
                    line1_handle   = c.Line1.Handle.ToString(),
                    line1_segment  = c.Seg1,
                    line2_handle   = c.Line2.Handle.ToString(),
                    line2_segment  = c.Seg2,
                    x              = Math.Round(c.XY.X, 3),
                    y              = Math.Round(c.XY.Y, 3),
                    z_line1        = Math.Round(c.Z1, 3),
                    z_line2        = Math.Round(c.Z2, 3),
                    z_diff_mm      = Math.Round(Math.Abs(c.Z1 - c.Z2) * 1000, 1),
                }).ToList(),
            };
        }

        public object FixConflicts(JObject p)
        {
            var layers     = ParseLayers(p);
            var tolerance  = p["tolerance_m"]?.Value<double>() ?? 0.001;
            var zSnapMm    = p["z_snap_mm"]?.Value<double>()    ?? 10.0;
            var zSnapM     = zSnapMm / 1000.0;

            using var tr = AcDb.TransactionManager.StartTransaction();
            var lines     = CollectPolylines(tr, layers);
            var conflicts = FindConflicts(tr, lines, tolerance);

            if (conflicts.Count == 0)
            {
                tr.Commit();
                return new { fixed_count = 0, lines_modified = 0, message = "No conflicts found." };
            }

            // Group splits per polyline handle
            var splitsById = new Dictionary<long, List<SegSplit>>();

            foreach (var c in conflicts)
            {
                // Z for the shared vertex
                double z1 = c.Z1, z2 = c.Z2;
                if (Math.Abs(z1 - z2) <= zSnapM)
                    z1 = z2 = (z1 + z2) / 2.0;

                var pt1 = new Point3d(c.XY.X, c.XY.Y, z1);
                var pt2 = new Point3d(c.XY.X, c.XY.Y, z2);

                AddSplit(splitsById, c.Line1.Id.OldIdPtr.ToInt64(), c.Seg1, c.T1, pt1);
                AddSplit(splitsById, c.Line2.Id.OldIdPtr.ToInt64(), c.Seg2, c.T2, pt2);
            }

            int linesModified = 0;
            var ms = (BlockTableRecord)tr.GetObject(
                SymbolUtilityServices.GetBlockModelSpaceId(AcDb), OpenMode.ForWrite);

            foreach (var (_, line) in lines)
            {
                long key = line.Id.OldIdPtr.ToInt64();
                if (!splitsById.TryGetValue(key, out var splits)) continue;

                RebuildPolyline(tr, ms, line, splits);
                linesModified++;
            }

            tr.Commit();
            return new
            {
                fixed_count   = conflicts.Count,
                lines_modified = linesModified,
                vertices_added = conflicts.Count * 2,
            };
        }

        // ── Geometry ──────────────────────────────────────────────────────

        private enum ConflictType { Crossing }

        private record ConflictInfo(
            Polyline3d Line1, int Seg1, double T1,
            Polyline3d Line2, int Seg2, double T2,
            Point2d XY, double Z1, double Z2,
            ConflictType Type);

        private record SegSplit(int SegIdx, double T, Point3d Vertex);

        /// <summary>
        /// Returns t ∈ (eps, 1-eps) and s ∈ (eps, 1-eps) if segments cross.
        /// </summary>
        private static bool SegmentsIntersect(
            Point3d a, Point3d b,
            Point3d c, Point3d d,
            out double t, out double s)
        {
            const double EPS = 1e-9;
            double dx1 = b.X - a.X, dy1 = b.Y - a.Y;
            double dx2 = d.X - c.X, dy2 = d.Y - c.Y;
            double denom = dx1 * dy2 - dy1 * dx2;
            t = s = 0;
            if (Math.Abs(denom) < EPS) return false;          // parallel / collinear

            double cx = c.X - a.X, cy = c.Y - a.Y;
            t = (cx * dy2 - cy * dx2) / denom;
            s = (cx * dy1 - cy * dx1) / denom;

            const double EDGE = 1e-7;
            return t > EDGE && t < 1 - EDGE && s > EDGE && s < 1 - EDGE;
        }

        private static double InterpZ(Point3d start, Point3d end, double t) =>
            start.Z + t * (end.Z - start.Z);

        // ── Collection helpers ────────────────────────────────────────────

        /// <summary>Returns all Polyline3d objects on the target layer(s).</summary>
        private static Dictionary<ObjectId, Polyline3d> CollectPolylines(
            Transaction tr, HashSet<string>? layers)
        {
            var result = new Dictionary<ObjectId, Polyline3d>();
            var ms = (BlockTableRecord)tr.GetObject(
                SymbolUtilityServices.GetBlockModelSpaceId(AcDb), OpenMode.ForRead);
            foreach (ObjectId id in ms)
            {
                if (!(tr.GetObject(id, OpenMode.ForRead) is Polyline3d pl)) continue;
                if (pl.IsErased) continue;
                if (layers != null && !layers.Contains(pl.Layer)) continue;
                result[id] = pl;
            }
            return result;
        }

        private static Point3d[] GetVertices(Transaction tr, Polyline3d pl)
        {
            var pts = new List<Point3d>();
            foreach (ObjectId vtxId in pl)
            {
                var vtx = (PolylineVertex3d)tr.GetObject(vtxId, OpenMode.ForRead);
                pts.Add(vtx.Position);
            }
            return pts.ToArray();
        }

        // ── Conflict detection ────────────────────────────────────────────

        private static List<ConflictInfo> FindConflicts(
            Transaction tr, Dictionary<ObjectId, Polyline3d> lines, double zTol)
        {
            var ids  = lines.Keys.ToArray();
            var verts = ids.ToDictionary(id => id, id => GetVertices(tr, lines[id]));
            var result = new List<ConflictInfo>();

            for (int i = 0; i < ids.Length; i++)
            for (int j = i + 1; j < ids.Length; j++)
            {
                var id1 = ids[i]; var pts1 = verts[id1];
                var id2 = ids[j]; var pts2 = verts[id2];

                for (int si = 0; si < pts1.Length - 1; si++)
                for (int sj = 0; sj < pts2.Length - 1; sj++)
                {
                    if (!SegmentsIntersect(pts1[si], pts1[si + 1],
                                           pts2[sj], pts2[sj + 1],
                                           out double t, out double s))
                        continue;

                    double z1 = InterpZ(pts1[si], pts1[si + 1], t);
                    double z2 = InterpZ(pts2[sj], pts2[sj + 1], s);
                    if (Math.Abs(z1 - z2) < zTol) continue; // same elevation — OK

                    var xy = new Point2d(
                        pts1[si].X + t * (pts1[si + 1].X - pts1[si].X),
                        pts1[si].Y + t * (pts1[si + 1].Y - pts1[si].Y));

                    result.Add(new ConflictInfo(
                        lines[id1], si, t,
                        lines[id2], sj, s,
                        xy, z1, z2, ConflictType.Crossing));
                }
            }
            return result;
        }

        // ── Polyline reconstruction ───────────────────────────────────────

        private static void AddSplit(Dictionary<long, List<SegSplit>> dict,
            long key, int seg, double t, Point3d pt)
        {
            if (!dict.TryGetValue(key, out var list))
                dict[key] = list = new List<SegSplit>();
            list.Add(new SegSplit(seg, t, pt));
        }

        /// <summary>
        /// Deletes the original polyline and creates a new one with split vertices
        /// inserted at the appropriate positions.
        /// </summary>
        private static void RebuildPolyline(Transaction tr, BlockTableRecord ms,
            Polyline3d original, List<SegSplit> splits)
        {
            var pts = new List<Point3d>(GetVertices(tr, original));
            var layer = original.Layer;

            // Group splits by segment, sorted by T within each segment
            var bySeg = splits
                .GroupBy(s => s.SegIdx)
                .ToDictionary(g => g.Key, g => g.OrderBy(s => s.T).ToList());

            var newPts = new List<Point3d>();
            for (int i = 0; i < pts.Count; i++)
            {
                newPts.Add(pts[i]);
                if (i < pts.Count - 1 && bySeg.TryGetValue(i, out var segs))
                    newPts.AddRange(segs.Select(s => s.Vertex));
            }

            // Erase original and create replacement
            original.UpgradeOpen();
            original.Erase(true);

            var newPl = new Polyline3d(
                Poly3dType.SimplePoly,
                new Point3dCollection(newPts.ToArray()),
                false)
            { Layer = layer };

            ms.AppendEntity(newPl);
            tr.AddNewlyCreatedDBObject(newPl, true);
        }

        // ── Utility ───────────────────────────────────────────────────────

        private static HashSet<string>? ParseLayers(JObject p)
        {
            if (p["layers"] is not JArray arr || arr.Count == 0) return null;
            return arr.Select(t => t.Value<string>()!).ToHashSet(
                StringComparer.OrdinalIgnoreCase);
        }
    }
}
