"""Drive the original HTML editor in a private, local Chromium instance."""
from contextlib import closing
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import shutil
import subprocess
import time
from urllib.request import ProxyHandler, build_opener

from PIL import Image
from websocket import create_connection


def browser_path():
    configured = os.environ.get("WAVEFORM_BROWSER")
    if configured:
        if Path(configured).is_file():
            return configured
        raise ValueError("WAVEFORM_BROWSER 指向的浏览器文件不存在")
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        if variable in os.environ:
            for path in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"):
                candidate = Path(os.environ[variable]) / path
                if candidate.is_file():
                    return str(candidate)
    for name in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        if executable := shutil.which(name):
            return executable
    for name in ("Microsoft Edge", "Google Chrome", "Chromium"):
        candidate = Path("/Applications") / (name + ".app") / "Contents/MacOS" / name
        if candidate.is_file():
            return str(candidate)
    raise ValueError("未找到 Edge、Chrome 或 Chromium。请安装浏览器，或用 WAVEFORM_BROWSER 指定可执行文件。")


def wait_for(read, description, process):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("标定浏览器意外退出")
        if value := read():
            return value
        time.sleep(.08)
    raise ValueError(f"原版标定工具超时：{description}")


class EditorTab:
    def __init__(self, connection):
        self.connection = connection
        self.ids = count(1)

    def call(self, method, **params):
        ident = next(self.ids)
        self.connection.send(json.dumps(dict(id=ident, method=method, params=params)))
        while True:
            reply = json.loads(self.connection.recv())
            if reply.get("id") == ident:
                if "error" in reply:
                    raise ValueError(f"{method}: {reply['error']}")
                return reply["result"]

    def evaluate(self, expression):
        response = self.call("Runtime.evaluate",expression=expression,returnByValue=True)
        if "exceptionDetails" in response:
            raise ValueError(f"标定工具界面操作失败：{response['exceptionDetails']['text']}")
        return response["result"].get("value")

    def load_file(self, selector, path):
        root = self.call("DOM.getDocument")["root"]["nodeId"]
        node = self.call("DOM.querySelector",nodeId=root,selector=selector)["nodeId"]
        self.call("DOM.setFileInputFiles",nodeId=node,files=[str(path.resolve())])


def export_marked_png(screen, project, count, destination):
    editor = Path(__file__).parent / "annotator" / "示波器标定画图工具.html"
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        profile = folder / "profile"
        process = subprocess.Popen([
            browser_path(), "--headless=new", "--disable-gpu", "--disable-extensions",
            "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
            "--no-first-run", "--disable-background-networking", "--disable-component-update",
            "--user-data-dir="+str(profile), editor.resolve().as_uri(),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            portfile = profile / "DevToolsActivePort"
            def port_number():
                if portfile.exists():
                    lines = portfile.read_text(encoding="ascii").splitlines()
                    if lines and lines[0].isdigit():
                        return int(lines[0])
            port = wait_for(port_number,"等待浏览器启动",process)
            opener = build_opener(ProxyHandler({}))
            def editor_address():
                with opener.open(f"http://127.0.0.1:{port}/json/list", timeout=3) as response:
                    tabs = json.load(response)
                return next((t["webSocketDebuggerUrl"] for t in tabs if t["type"]=="page" and
                             t["url"]==editor.resolve().as_uri()), None)
            address = wait_for(editor_address,"打开编辑器",process)
            with closing(create_connection(address,timeout=15,suppress_origin=True,http_no_proxy=["127.0.0.1"])) as ws:
                tab = EditorTab(ws)
                tab.call("Browser.setDownloadBehavior",behavior="allow",downloadPath=str(folder.resolve()))
                wait_for(lambda: tab.evaluate("document.readyState==='complete' && !!document.querySelector('#btnDownload')"),"加载界面",process)
                tab.load_file("#fileInput",screen)
                wait_for(lambda: tab.evaluate("document.querySelector('#hudFileName').textContent") == screen.name,"导入底图",process)
                tab.load_file("#jsonInput",project)
                wait_for(lambda: tab.evaluate("document.querySelector('#toast').textContent") == f"已载入 {count} 个自定义标注对象","载入标注",process)
                tab.evaluate("document.querySelector('#btnDownload').click()")
                output = folder / (screen.stem+"_标注.png")
                wait_for(lambda: output.exists() and output.stat().st_size>0,"导出 PNG",process)
                with Image.open(output) as exported, Image.open(screen) as original:
                    if exported.format!="PNG" or exported.size!=original.size:
                        raise ValueError("标定工具导出的图像格式或尺寸异常")
                    exported.verify()
                shutil.copyfile(output, destination)
                ws.send(json.dumps({"id":0,"method":"Browser.close"}))
        finally:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
