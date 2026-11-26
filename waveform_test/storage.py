from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import json


@contextmanager
def new_run(target):
    target = Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError(f"输出目录已存在，请指定新目录: {target}")
    lock = target.with_name("." + target.name + ".lock")
    with lock.open("x"):
        pass
    try:
        with TemporaryDirectory(dir=target.parent) as tmp:
            stage = Path(tmp) / "run"
            stage.mkdir()
            yield stage
            if target.exists():
                raise FileExistsError(target)
            stage.rename(target)
    finally:
        lock.unlink(missing_ok=True)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
