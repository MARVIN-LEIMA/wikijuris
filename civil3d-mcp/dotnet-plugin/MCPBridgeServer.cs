using System;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Autodesk.AutoCAD.ApplicationServices;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Civil3DMCPPlugin
{
    /// <summary>
    /// Embedded HTTP server that bridges the Python MCP server to Civil 3D's .NET API.
    /// Accepts POST /api/execute with {"tool": "…", "params": {…}} JSON bodies.
    /// All Civil 3D API calls are marshalled back to the AutoCAD main thread via
    /// Application.MainWindow.Invoke so locking is handled correctly.
    /// </summary>
    public class MCPBridgeServer
    {
        private readonly int _port;
        private HttpListener? _listener;
        private CancellationTokenSource? _cts;
        private readonly CommandDispatcher _dispatcher = new();

        public MCPBridgeServer(int port) => _port = port;

        public void Start()
        {
            _cts = new CancellationTokenSource();
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://localhost:{_port}/");
            _listener.Start();
            Task.Run(() => ListenLoop(_cts.Token));
        }

        public void Stop()
        {
            _cts?.Cancel();
            _listener?.Stop();
        }

        private async Task ListenLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    var ctx = await _listener!.GetContextAsync();
                    _ = Task.Run(() => HandleRequest(ctx), ct);
                }
                catch (HttpListenerException) when (ct.IsCancellationRequested) { break; }
                catch (Exception ex)
                {
                    LogError(ex);
                }
            }
        }

        private async Task HandleRequest(HttpListenerContext ctx)
        {
            ctx.Response.Headers.Add("Access-Control-Allow-Origin", "*");
            ctx.Response.ContentType = "application/json; charset=utf-8";

            if (ctx.Request.HttpMethod == "OPTIONS")
            {
                ctx.Response.StatusCode = 204;
                ctx.Response.Close();
                return;
            }

            try
            {
                if (ctx.Request.Url?.AbsolutePath != "/api/execute")
                {
                    await WriteJson(ctx, 404, new { error = "Not found" });
                    return;
                }

                using var reader = new StreamReader(ctx.Request.InputStream,
                    ctx.Request.ContentEncoding ?? Encoding.UTF8);
                var body = await reader.ReadToEndAsync();
                var req = JObject.Parse(body);

                var tool = req["tool"]?.Value<string>()
                    ?? throw new ArgumentException("Missing 'tool' field");
                var @params = req["params"] as JObject ?? new JObject();

                // Execute on the AutoCAD main thread
                object? result = null;
                Exception? error = null;
                var done = new ManualResetEventSlim(false);

                Application.MainWindow.Invoke(new Action(() =>
                {
                    try { result = _dispatcher.Execute(tool, @params); }
                    catch (Exception ex) { error = ex; }
                    finally { done.Set(); }
                }));

                done.Wait(TimeSpan.FromSeconds(30));

                if (error is not null)
                    await WriteJson(ctx, 500, new { error = error.Message });
                else
                    await WriteJson(ctx, 200, new { ok = true, result });
            }
            catch (Exception ex)
            {
                await WriteJson(ctx, 400, new { error = ex.Message });
            }
        }

        private static async Task WriteJson(HttpListenerContext ctx, int status, object payload)
        {
            var json = JsonConvert.SerializeObject(payload);
            var bytes = Encoding.UTF8.GetBytes(json);
            ctx.Response.StatusCode = status;
            ctx.Response.ContentLength64 = bytes.Length;
            await ctx.Response.OutputStream.WriteAsync(bytes, 0, bytes.Length);
            ctx.Response.Close();
        }

        private static void LogError(Exception ex) =>
            Application.DocumentManager.MdiActiveDocument?.Editor
                .WriteMessage($"\n[Civil3D-MCP] Error: {ex.Message}");
    }
}
