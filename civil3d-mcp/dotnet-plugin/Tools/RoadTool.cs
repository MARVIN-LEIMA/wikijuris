using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using Autodesk.Civil.DatabaseServices.Styles;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    public class RoadTool
    {
        private static CivilDocument CivilDoc =>
            CivilApplication.ActiveDocument;

        private static Database AcDb =>
            Application.DocumentManager.MdiActiveDocument.Database;

        private Alignment GetAlignment(Transaction tr, string name)
        {
            foreach (ObjectId id in CivilDoc.GetAlignmentIds())
            {
                var al = (Alignment)tr.GetObject(id, OpenMode.ForRead);
                if (al.Name == name) return al;
            }
            throw new System.Exception($"Alignment '{name}' not found");
        }

        // ── Alignment ──────────────────────────────────────────────────────

        public object CreateAlignment(JObject p)
        {
            var name = p["name"]!.Value<string>()!;
            var desc = p["description"]?.Value<string>() ?? "";
            var layer = p["layer"]?.Value<string>() ?? "C-ROAD-CNTR";
            var siteName = p["site"]?.Value<string>();

            using var tr = AcDb.TransactionManager.StartTransaction();

            ObjectId siteId = ObjectId.Null;
            if (siteName != null)
            {
                foreach (ObjectId id in CivilDoc.GetSiteIds())
                {
                    var s = (Site)tr.GetObject(id, OpenMode.ForRead);
                    if (s.Name == siteName) { siteId = id; break; }
                }
            }

            var alignStyle = CivilDoc.Styles.AlignmentStyles[0];
            var labelStyle = CivilDoc.Styles.LabelStyles.AlignmentLabelStyles
                .StationLabelStyles[0];

            var alId = Alignment.Create(AcDb, name, siteId, layer,
                alignStyle, labelStyle);
            var al = (Alignment)tr.GetObject(alId, OpenMode.ForWrite);
            al.Description = desc;
            tr.Commit();
            return new { name, handle = alId.Handle.ToString() };
        }

        public object AddTangent(JObject p)
        {
            var name = p["alignment"]!.Value<string>()!;
            var start = p["start"]!;
            var end = p["end"]!;

            using var tr = AcDb.TransactionManager.StartTransaction();
            var al = GetAlignment(tr, name);
            al.UpgradeOpen();

            al.Entities.AddFixedLine(
                new Point2d(start[0]!.Value<double>(), start[1]!.Value<double>()),
                new Point2d(end[0]!.Value<double>(), end[1]!.Value<double>()));
            tr.Commit();
            return new { alignment = name, type = "tangent" };
        }

        public object AddCurve(JObject p)
        {
            var name = p["alignment"]!.Value<string>()!;
            var radius = p["radius"]!.Value<double>();
            var passThrough = p["pass_through"]!;

            using var tr = AcDb.TransactionManager.StartTransaction();
            var al = GetAlignment(tr, name);
            al.UpgradeOpen();

            // Fixed curve through a point with specified radius
            var pt = new Point2d(
                passThrough[0]!.Value<double>(),
                passThrough[1]!.Value<double>());
            al.Entities.AddFreeArcBetweenEntities(
                al.Entities[al.Entities.Count - 1].EntityId,
                al.Entities.Count > 1
                    ? al.Entities[al.Entities.Count - 2].EntityId
                    : ObjectId.Null,
                radius,
                AlignmentCurveType.Arc);
            tr.Commit();
            return new { alignment = name, radius, type = "curve" };
        }

        // ── Profile ───────────────────────────────────────────────────────

        public object CreateProfileView(JObject p)
        {
            var alignName = p["alignment"]!.Value<string>()!;
            var origin = p["origin"]!;
            var name = p["name"]?.Value<string>() ?? $"{alignName}-PV";

            using var tr = AcDb.TransactionManager.StartTransaction();
            var al = GetAlignment(tr, alignName);

            var pvStyle = CivilDoc.Styles.ProfileViewStyles[0];
            var bandSetStyle = CivilDoc.Styles.ProfileViewBandSetStyles[0];

            var pvId = ProfileView.Create(al.ObjectId,
                new Point2d(origin[0]!.Value<double>(), origin[1]!.Value<double>()),
                name, pvStyle, bandSetStyle);
            tr.Commit();
            return new { name, handle = pvId.Handle.ToString() };
        }

        public object CreateLayoutProfile(JObject p)
        {
            var alignName = p["alignment"]!.Value<string>()!;
            var name = p["name"]!.Value<string>()!;
            var desc = p["description"]?.Value<string>() ?? "";

            using var tr = AcDb.TransactionManager.StartTransaction();
            var al = GetAlignment(tr, alignName);

            var profileStyle = CivilDoc.Styles.ProfileStyles[0];
            var labelStyle = CivilDoc.Styles.LabelStyles.ProfileLabelStyles
                .LineLabelStyles[0];

            var profId = Profile.CreateByLayout(name, al.ObjectId, al.SiteId,
                profileStyle, labelStyle);
            var prof = (Profile)tr.GetObject(profId, OpenMode.ForWrite);
            prof.Description = desc;
            tr.Commit();
            return new { name, handle = profId.Handle.ToString() };
        }

        public object AddPVI(JObject p)
        {
            var alignName = p["alignment"]!.Value<string>()!;
            var profileName = p["profile"]!.Value<string>()!;
            var station = p["station"]!.Value<double>();
            var elevation = p["elevation"]!.Value<double>();
            var curveLength = p["curve_length"]?.Value<double>();

            using var tr = AcDb.TransactionManager.StartTransaction();
            var al = GetAlignment(tr, alignName);

            ProfileLayout? layout = null;
            foreach (ObjectId pid in al.GetProfileIds())
            {
                var pr = tr.GetObject(pid, OpenMode.ForRead) as ProfileLayout;
                if (pr?.Name == profileName) { layout = pr; break; }
            }
            if (layout == null)
                throw new System.Exception($"Layout profile '{profileName}' not found");

            layout.UpgradeOpen();
            var pvi = layout.PVIs.AddPVI(station, elevation);

            if (curveLength.HasValue)
                pvi.SetCurveParameters(ProfileParabolaSymmetric.CreateByLength(
                    layout.ObjectId, pvi.ObjectId, curveLength.Value));

            tr.Commit();
            return new { station, elevation };
        }

        // ── Corridor ─────────────────────────────────────────────────────

        public object CreateAssembly(JObject p)
        {
            var name = p["name"]!.Value<string>()!;
            var x = p["x"]?.Value<double>() ?? 0;
            var y = p["y"]?.Value<double>() ?? 0;

            using var tr = AcDb.TransactionManager.StartTransaction();

            var assemblyStyle = CivilDoc.Styles.AssemblyStyles[0];
            var asmId = Assembly.Create(AcDb, new Point3d(x, y, 0),
                name, assemblyStyle);
            tr.Commit();
            return new { name, handle = asmId.Handle.ToString() };
        }

        public object CreateCorridor(JObject p)
        {
            var name = p["name"]!.Value<string>()!;
            var alignName = p["alignment"]!.Value<string>()!;
            var profileName = p["profile"]!.Value<string>()!;
            var assemblyName = p["assembly"]!.Value<string>()!;
            var surfaceName = p["target_surface"]?.Value<string>();

            using var tr = AcDb.TransactionManager.StartTransaction();
            var al = GetAlignment(tr, alignName);

            // Resolve profile
            ObjectId profileId = ObjectId.Null;
            foreach (ObjectId pid in al.GetProfileIds())
            {
                var pr = tr.GetObject(pid, OpenMode.ForRead) as Profile;
                if (pr?.Name == profileName) { profileId = pid; break; }
            }

            // Resolve assembly
            ObjectId assemblyId = ObjectId.Null;
            foreach (ObjectId aid in CivilDoc.GetAssemblyIds())
            {
                var asm = (Assembly)tr.GetObject(aid, OpenMode.ForRead);
                if (asm.Name == assemblyName) { assemblyId = aid; break; }
            }

            var corridorStyle = CivilDoc.Styles.CorridorStyles[0];
            var corrId = Corridor.Create(AcDb, name, corridorStyle);
            var corr = (Corridor)tr.GetObject(corrId, OpenMode.ForWrite);
            corr.AddBaseline(al.ObjectId, profileId, assemblyId);

            // Optionally attach a target surface
            if (surfaceName != null)
            {
                foreach (ObjectId sid in CivilDoc.GetSurfaceIds())
                {
                    var surf = (Surface)tr.GetObject(sid, OpenMode.ForRead);
                    if (surf.Name == surfaceName)
                    {
                        corr.AddTarget(surf.ObjectId);
                        break;
                    }
                }
            }

            corr.Rebuild();
            tr.Commit();
            return new { name, handle = corrId.Handle.ToString() };
        }
    }
}
