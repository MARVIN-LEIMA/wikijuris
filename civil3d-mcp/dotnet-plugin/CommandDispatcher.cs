using System;
using Newtonsoft.Json.Linq;
using Civil3DMCPPlugin.Tools;

namespace Civil3DMCPPlugin
{
    /// <summary>
    /// Routes MCP tool names to the appropriate handler class.
    /// </summary>
    public class CommandDispatcher
    {
        private readonly CadPrimitivesTool _primitives = new();
        private readonly SurfaceTool _surface = new();
        private readonly ParcelTool _parcel = new();
        private readonly PipeTool _pipe = new();
        private readonly RoadTool _road = new();
        private readonly PointImportTool _points = new();

        public object? Execute(string tool, JObject p) => tool switch
        {
            // ── CAD primitives ──────────────────────────────────────────────
            "draw_point"        => _primitives.DrawPoint(p),
            "draw_line"         => _primitives.DrawLine(p),
            "draw_polyline"     => _primitives.DrawPolyline(p),
            "draw_arc"          => _primitives.DrawArc(p),
            "draw_circle"       => _primitives.DrawCircle(p),
            "draw_text"         => _primitives.DrawText(p),
            "create_layer"      => _primitives.CreateLayer(p),

            // ── Surfaces ─────────────────────────────────────────────────────
            "create_tin_surface"         => _surface.CreateTinSurface(p),
            "add_surface_points"         => _surface.AddPoints(p),
            "add_surface_breaklines"     => _surface.AddBreaklines(p),
            "add_surface_boundary"       => _surface.AddBoundary(p),
            "get_surface_elevation"      => _surface.GetElevation(p),
            "build_surface"              => _surface.BuildSurface(p),

            // ── Parcels ───────────────────────────────────────────────────────
            "create_parcel_site"         => _parcel.CreateSite(p),
            "create_parcel_from_polyline"=> _parcel.CreateFromPolyline(p),
            "subdivide_parcel"           => _parcel.Subdivide(p),

            // ── Pipe networks ─────────────────────────────────────────────────
            "create_pipe_network"        => _pipe.CreateNetwork(p),
            "add_pipe"                   => _pipe.AddPipe(p),
            "add_structure"              => _pipe.AddStructure(p),
            "set_pipe_slope"             => _pipe.SetSlope(p),

            // ── Roads ─────────────────────────────────────────────────────────
            "create_alignment"           => _road.CreateAlignment(p),
            "add_alignment_tangent"      => _road.AddTangent(p),
            "add_alignment_curve"        => _road.AddCurve(p),
            "create_profile_view"        => _road.CreateProfileView(p),
            "create_layout_profile"      => _road.CreateLayoutProfile(p),
            "add_profile_pvi"            => _road.AddPVI(p),
            "create_assembly"            => _road.CreateAssembly(p),
            "create_corridor"            => _road.CreateCorridor(p),

            // ── Points & linework ─────────────────────────────────────────────
            "import_points"              => _points.ImportPoints(p),
            "create_figures"             => _points.CreateFigures(p),
            "create_point_group"         => _points.CreatePointGroup(p),

            _ => throw new NotSupportedException($"Unknown tool: '{tool}'")
        };
    }
}
