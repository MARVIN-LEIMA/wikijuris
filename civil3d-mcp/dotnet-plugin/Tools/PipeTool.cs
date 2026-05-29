using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin.Tools
{
    public class PipeTool
    {
        private static CivilDocument CivilDoc =>
            CivilApplication.ActiveDocument;

        private static Database AcDb =>
            Application.DocumentManager.MdiActiveDocument.Database;

        private Network GetNetwork(Transaction tr, string name)
        {
            foreach (ObjectId id in CivilDoc.GetPipeNetworkIds())
            {
                var net = (Network)tr.GetObject(id, OpenMode.ForRead);
                if (net.Name == name) return net;
            }
            throw new System.Exception($"Pipe network '{name}' not found");
        }

        public object CreateNetwork(JObject p)
        {
            var name = p["name"]!.Value<string>()!;
            var desc = p["description"]?.Value<string>() ?? "";
            var referenceAlignmentName = p["alignment"]?.Value<string>();

            using var tr = AcDb.TransactionManager.StartTransaction();

            ObjectId alignId = ObjectId.Null;
            if (referenceAlignmentName != null)
            {
                foreach (ObjectId id in CivilDoc.GetAlignmentIds())
                {
                    var al = (Alignment)tr.GetObject(id, OpenMode.ForRead);
                    if (al.Name == referenceAlignmentName) { alignId = id; break; }
                }
            }

            var netId = Network.Create(AcDb, name);
            var net = (Network)tr.GetObject(netId, OpenMode.ForWrite);
            net.Description = desc;
            if (!alignId.IsNull) net.ReferenceAlignmentId = alignId;

            tr.Commit();
            return new { name, handle = netId.Handle.ToString() };
        }

        public object AddStructure(JObject p)
        {
            var networkName = p["network"]!.Value<string>()!;
            var partFamilyName = p["part_family"]?.Value<string>() ?? "Concrete Rectangular Structure";
            var partSizeName = p["part_size"]?.Value<string>() ?? "30x48 Box";
            var x = p["x"]!.Value<double>();
            var y = p["y"]!.Value<double>();
            var rimElev = p["rim_elevation"]?.Value<double>() ?? double.NaN;
            var sumpElev = p["sump_elevation"]?.Value<double>() ?? double.NaN;
            var rotation = p["rotation"]?.Value<double>() ?? 0;

            using var tr = AcDb.TransactionManager.StartTransaction();
            var net = GetNetwork(tr, networkName);
            net.UpgradeOpen();

            // Resolve part family / size from part catalog
            var partFamilyId = CivilDoc.Styles.PipeNetworkCatalog
                .GetStructurePartFamilyId(partFamilyName);
            var partSizeId = CivilDoc.Styles.PipeNetworkCatalog
                .GetStructurePartSizeId(partFamilyId, partSizeName);

            var structId = net.AddStructure(partFamilyId, partSizeId,
                new Point3d(x, y, double.IsNaN(rimElev) ? 0 : rimElev),
                rotation, false);

            if (!double.IsNaN(rimElev) || !double.IsNaN(sumpElev))
            {
                var struc = (Structure)tr.GetObject(structId, OpenMode.ForWrite);
                if (!double.IsNaN(rimElev)) struc.RimElevation = rimElev;
                if (!double.IsNaN(sumpElev)) struc.SumpElevation = sumpElev;
            }

            tr.Commit();
            return new { handle = structId.Handle.ToString(), x, y };
        }

        public object AddPipe(JObject p)
        {
            var networkName = p["network"]!.Value<string>()!;
            var partFamilyName = p["part_family"]?.Value<string>() ?? "Concrete Pipe";
            var partSizeName = p["part_size"]?.Value<string>() ?? "12 inch Concrete Pipe";
            var startPt = p["start"]!;
            var endPt = p["end"]!;
            var startStructureHandle = p["start_structure"]?.Value<string>();
            var endStructureHandle = p["end_structure"]?.Value<string>();

            using var tr = AcDb.TransactionManager.StartTransaction();
            var net = GetNetwork(tr, networkName);
            net.UpgradeOpen();

            var partFamilyId = CivilDoc.Styles.PipeNetworkCatalog
                .GetPipePartFamilyId(partFamilyName);
            var partSizeId = CivilDoc.Styles.PipeNetworkCatalog
                .GetPipePartSizeId(partFamilyId, partSizeName);

            var sp = new Point3d(startPt[0]!.Value<double>(),
                startPt[1]!.Value<double>(), startPt[2]?.Value<double>() ?? 0);
            var ep = new Point3d(endPt[0]!.Value<double>(),
                endPt[1]!.Value<double>(), endPt[2]?.Value<double>() ?? 0);

            var pipeId = net.AddLinePipe(partFamilyId, partSizeId, sp, ep);

            // Connect to structures if provided
            if (startStructureHandle != null)
            {
                var sId = AcDb.GetObjectId(false,
                    new Handle(System.Convert.ToInt64(startStructureHandle, 16)), 0);
                var pipe = (Pipe)tr.GetObject(pipeId, OpenMode.ForWrite);
                pipe.ConnectToStructure(sId, ConnectorPositionType.Start, true);
            }
            if (endStructureHandle != null)
            {
                var eId = AcDb.GetObjectId(false,
                    new Handle(System.Convert.ToInt64(endStructureHandle, 16)), 0);
                var pipe = (Pipe)tr.GetObject(pipeId, OpenMode.ForWrite);
                pipe.ConnectToStructure(eId, ConnectorPositionType.End, true);
            }

            tr.Commit();
            return new { handle = pipeId.Handle.ToString() };
        }

        public object SetSlope(JObject p)
        {
            var pipeHandle = p["pipe"]!.Value<string>()!;
            var slope = p["slope"]!.Value<double>();

            using var tr = AcDb.TransactionManager.StartTransaction();
            var id = AcDb.GetObjectId(false,
                new Handle(System.Convert.ToInt64(pipeHandle, 16)), 0);
            var pipe = (Pipe)tr.GetObject(id, OpenMode.ForWrite);
            pipe.Slope = slope;
            tr.Commit();
            return new { slope };
        }
    }
}
