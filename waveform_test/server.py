"""Local stdio MCP entry point."""
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .report import analyze
from .storage import new_run

server = FastMCP("波形测试工具")


@server.tool()
def analyze_record(csv_file: str, output_directory: str, threshold_v: float, stage_gap_s: float = .35,
                   packet_gap_s: float = .05, stages: int | None = None,
                   baseline_v: float = 0, screen_file: str | None = None,
                   durations_file: str | None = None, profile_file: str | None = None) -> dict:
    """Analyze a local pulse CSV and save a report to a new directory. Paths belong to the server machine."""
    with new_run(output_directory) as out:
        return analyze(Path(csv_file),out,threshold_v,stage_gap_s,packet_gap_s,stages,baseline_v,screen_file,durations_file,profile_file)


@server.tool()
def list_scopes() -> list[str]:
    """List supported USB VISA resource addresses on this machine."""
    from .scope import devices
    return devices()


@server.tool()
def capture_record(output_directory: str, resource: str | None = None) -> str:
    """Freeze and export CH1 and the native screen, then restore acquisition. Choose a fresh directory."""
    from .scope import export
    with new_run(output_directory) as out:
        export(out, resource)
    return str(Path(output_directory).resolve())


def main():
    server.run(transport="stdio")
