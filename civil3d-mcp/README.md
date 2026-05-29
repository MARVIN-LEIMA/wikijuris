# Civil 3D MCP Plugin

让 AI Agent（Claude Code / Open Code）通过 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 直接操控 Autodesk Civil 3D，自动绘制 CAD 图元、创建曲面、地块、管道网络和道路。

---

## 架构总览

```
┌─────────────────────────────────┐
│  AI Agent (Claude Code)         │
│  MCP Client                     │
└───────────────┬─────────────────┘
                │ MCP 协议 (stdio)
┌───────────────▼─────────────────┐
│  Python MCP Server              │
│  civil3d-mcp                    │
│  (civil3d_mcp.server)           │
└───────────────┬─────────────────┘
                │ HTTP JSON  localhost:3765
┌───────────────▼─────────────────┐
│  C# Civil 3D Plugin             │
│  Civil3DMCPPlugin.dll           │
│  (MCPBridgeServer)              │
└───────────────┬─────────────────┘
                │ Civil 3D .NET API
┌───────────────▼─────────────────┐
│  Autodesk Civil 3D              │
│  (AutoCAD + Civil API)          │
└─────────────────────────────────┘
```

**两个组件：**

| 组件 | 技术栈 | 职责 |
|------|--------|------|
| `dotnet-plugin/` | C# .NET Framework 4.8 | 作为 AutoCAD 插件运行在 Civil 3D 进程内，暴露 HTTP 桥接 API |
| `python-server/` | Python 3.10+ | MCP 服务器，将 MCP 工具调用转发到 C# 桥接 |

---

## 目录结构

```
civil3d-mcp/
├── .mcp.json                          # Claude Code MCP 配置
├── python-server/
│   ├── pyproject.toml
│   └── src/civil3d_mcp/
│       ├── server.py                  # MCP 服务器入口
│       ├── bridge_client.py           # HTTP 客户端 → C# 桥接
│       └── tools/
│           ├── cad_primitives.py      # 点、线、弧、圆、多段线、文字
│           ├── surfaces.py            # TIN 曲面
│           ├── parcels.py             # 地块
│           ├── pipes.py               # 管道网络
│           └── roads.py               # 路线、纵断面、廊道
└── dotnet-plugin/
    ├── Civil3DMCPPlugin.csproj
    ├── PluginApplication.cs           # IExtensionApplication 入口
    ├── MCPBridgeServer.cs             # 嵌入式 HTTP 服务器
    ├── CommandDispatcher.cs           # 工具路由
    ├── Commands.cs                    # AutoCAD 命令 (MCP_STATUS)
    └── Tools/
        ├── CadPrimitivesTool.cs
        ├── SurfaceTool.cs
        ├── ParcelTool.cs
        ├── PipeTool.cs
        └── RoadTool.cs
```

---

## 快速开始

### 1. 编译 C# 插件

```bash
# 需要安装 .NET SDK 6+ 和 Civil 3D 2022+
# 将 Civil 3D 安装目录传入 MSBuild 属性
cd civil3d-mcp/dotnet-plugin
dotnet build -p:CivilRoot="C:\Program Files\Autodesk\AutoCAD 2024\AEC" -c Release
```

### 2. 加载插件到 Civil 3D

在 Civil 3D 命令行执行：
```
NETLOAD
```
选择 `bin\Release\Civil3DMCPPlugin.dll`。

或将 `civil3dmcp.pkgdef` 安装到 Civil 3D 插件目录实现自动加载。

验证插件已加载：
```
MCP_STATUS
```
输出应显示 `Bridge server running on http://localhost:3765`。

### 3. 安装 Python MCP 服务器

```bash
cd civil3d-mcp/python-server
pip install -e .
```

### 4. 配置 Claude Code

将 `.mcp.json` 复制到项目根目录（已包含），或添加到 `~/.claude/mcp.json`：

```json
{
  "mcpServers": {
    "civil3d": {
      "command": "civil3d-mcp",
      "env": {
        "CIVIL3D_BRIDGE_URL": "http://localhost:3765"
      }
    }
  }
}
```

---

## 可用 MCP 工具

### CAD 图元

| 工具 | 说明 |
|------|------|
| `create_layer` | 创建图层 |
| `draw_point` | 绘制点 |
| `draw_line` | 绘制直线 |
| `draw_polyline` | 绘制多段线 |
| `draw_arc` | 绘制圆弧 |
| `draw_circle` | 绘制圆 |
| `draw_text` | 添加文字注释 |

### TIN 曲面

| 工具 | 说明 |
|------|------|
| `create_tin_surface` | 创建空 TIN 曲面 |
| `add_surface_points` | 添加高程点 |
| `add_surface_breaklines` | 添加特征线 |
| `add_surface_boundary` | 添加边界 |
| `build_surface` | 重建/更新曲面 |
| `get_surface_elevation` | 查询某点高程 |

### 地块

| 工具 | 说明 |
|------|------|
| `create_parcel_site` | 创建用地 |
| `create_parcel_from_polyline` | 从多边形创建地块 |
| `subdivide_parcel` | 添加分割线细分地块 |

### 管道网络

| 工具 | 说明 |
|------|------|
| `create_pipe_network` | 创建管道网络 |
| `add_structure` | 添加检查井/集水坑 |
| `add_pipe` | 添加管道段 |
| `set_pipe_slope` | 设置管道坡度 |

### 道路（路线 + 纵断面 + 廊道）

| 工具 | 说明 |
|------|------|
| `create_alignment` | 创建水平路线 |
| `add_alignment_tangent` | 添加直线段 |
| `add_alignment_curve` | 添加曲线段 |
| `create_profile_view` | 创建纵断面图 |
| `create_layout_profile` | 创建设计纵断面 |
| `add_profile_pvi` | 添加变坡点 |
| `create_assembly` | 创建横断面装配 |
| `create_corridor` | 创建道路廊道 |

---

## 使用示例

以下提示词可让 Claude Code 自动完成道路设计：

```
使用 civil3d MCP 工具完成以下操作：
1. 创建名为 "地形" 的 TIN 曲面，添加以下高程点：
   (0,0,10), (100,0,12), (100,100,15), (0,100,11)，然后建模。
2. 创建路线 "主干路"，从 (10,50) 到 (90,50)，添加直线段。
3. 为 "主干路" 创建设计纵断面 "主干路-FG"，
   在 0+000 添加 PVI(高程=11)，在 0+080 添加 PVI(高程=13，竖曲线长=20)。
4. 创建横断面装配 "标准路幅"。
5. 用路线 + 纵断面 + 装配创建廊道 "主干路廊道"，目标曲面为 "地形"。
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CIVIL3D_BRIDGE_URL` | `http://localhost:3765` | C# 桥接服务器地址 |
| `CIVIL3D_BRIDGE_TIMEOUT` | `30` | 请求超时（秒） |

---

## 系统要求

- Autodesk Civil 3D 2022 或更高版本（包含 AutoCAD 2022+）
- .NET Framework 4.8（Civil 3D 自带）
- Python 3.10+
- Claude Code CLI 或任何 MCP 兼容客户端
