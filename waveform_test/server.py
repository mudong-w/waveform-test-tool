"""Local stdio MCP entry point for the complete test workflow."""
from mcp.server.fastmcp import FastMCP
from .workflow import run_waveform_test

server = FastMCP("波形测试工具")
server.tool()(run_waveform_test)


def main():
    server.run(transport="stdio")
