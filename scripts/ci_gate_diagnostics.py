"""Publish only source-validated identifiers from the private failed CI gate."""

import ast
import builtins
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_LOG_BYTES = 256 * 1024
MAX_LOGS = 4
MAX_ENTRIES = 64
MAX_ANNOTATIONS = 20
MAX_SOURCE_FILES = 16
MAX_SOURCE_BYTES = 1024 * 1024
UNAVAILABLE = "Gate diagnostics unavailable; private log not published"


def annotation(message):
    return "::error::" + message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def summarize(text):
    targets = set(re.findall(r"^([a-z][a-z0-9-]*):", (ROOT / "Makefile").read_text(), re.M))
    tracked = set(
        subprocess.check_output(
            ["git", "ls-files", "--", "*.py"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).splitlines()
    )
    sources = {}
    exceptions = {
        name
        for name, value in vars(builtins).items()
        if isinstance(value, type) and issubclass(value, BaseException)
    }
    messages = []

    def source(relative):
        if relative in tracked and relative not in sources and len(sources) < MAX_SOURCE_FILES:
            sources[relative] = None
            path = ROOT / relative
            if path.resolve() == path and path.is_file():
                with path.open("rb") as handle:
                    data = handle.read(MAX_SOURCE_BYTES + 1)
                if len(data) > MAX_SOURCE_BYTES:
                    return None
                content = data.decode("utf-8")
                tree = ast.parse(content)
                sources[relative] = (tree, len(content.splitlines()))
                exceptions.update(
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ClassDef)
                    and any(
                        isinstance(base, ast.Name) and base.id in exceptions for base in node.bases
                    )
                )
        return sources.get(relative)

    # shortcut: make/unittest/Python traceback formats only; add formats after a real miss.
    for line in text.splitlines():
        message = None
        if match := re.fullmatch(
            r"make(?:\[\d+\])?: \*\*\* \[Makefile:\d+: ([a-z][a-z0-9-]*)\] Error \d+", line
        ):
            if match[1] in targets:
                message = "make target: " + match[1]
        elif match := re.fullmatch(
            r"(?:ERROR|FAIL): (test_\w+) \((\w+)\.(\w+)\.(test_\w+)\)", line
        ):
            method, module, cls, repeated = match.groups()
            if method == repeated and len(line) <= 300:
                for directory in ("development", "documentation"):
                    parsed = source(f"tests/{directory}/{module}.py")
                    if parsed and any(
                        isinstance(node, ast.ClassDef)
                        and node.name == cls
                        and any(
                            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and item.name == method
                            for item in node.body
                        )
                        for node in parsed[0].body
                    ):
                        message = f"unittest: {module}.{cls}.{method}"
        elif match := re.fullmatch(r'  File "([^"]+)", line (\d{1,6}), in .+', line):
            location = re.search(
                r"(?:^|/)((?:tests/(?:development|documentation)|ops|scripts|api/(?:src|tests)|cli/(?:src|tests))/[A-Za-z0-9_/.-]+\.py)$",
                match[1],
            )
            if (
                location
                and len(location[1]) <= 200
                and all(part not in ("", ".", "..") for part in location[1].split("/"))
            ):
                parsed = source(location[1])
                if parsed and 1 <= int(match[2]) <= parsed[1]:
                    message = f"source: {location[1]}:{int(match[2])}"
        elif match := re.match(r"^(?:<run_path>\.|[A-Za-z_][\w.]*\.)?([A-Za-z_]\w*):", line):
            if match[1] in exceptions:
                message = "exception: " + match[1]
        if message and len(message) <= 350 and message not in messages:
            messages.append(message)
    return messages


def private(info, kind):
    return kind(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077


def diagnostics(root):
    messages = []
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if not root.is_absolute() or root.resolve() != root:
        return [UNAVAILABLE]
    root_fd = os.open(root, directory_flags)
    try:
        if not private(os.fstat(root_fd), stat.S_ISDIR):
            return [UNAVAILABLE]
        logs = 0
        with os.scandir(root_fd) as entries:
            for index, entry in enumerate(entries):
                if index >= MAX_ENTRIES or logs >= MAX_LOGS:
                    break
                if not re.fullmatch(r"db-[0-9a-f]{16}", entry.name):
                    continue
                logs += 1
                try:
                    child = os.open(entry.name, directory_flags, dir_fd=root_fd)
                    try:
                        if not private(os.fstat(child), stat.S_ISDIR):
                            continue
                        fd = os.open(
                            "gate.log", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=child
                        )
                        with os.fdopen(fd, "rb") as log:
                            info = os.fstat(log.fileno())
                            if not private(info, stat.S_ISREG) or info.st_nlink != 1:
                                continue
                            offset = max(0, info.st_size - MAX_LOG_BYTES)
                            log.seek(offset)
                            data = log.read(MAX_LOG_BYTES)
                            if offset:
                                data = data.partition(b"\n")[2]
                            for message in summarize(data.decode("utf-8", errors="replace")):
                                if message not in messages:
                                    messages.append(message)
                    finally:
                        os.close(child)
                except OSError:
                    continue
    finally:
        os.close(root_fd)
    priority = {"make target": 0, "unittest": 1, "exception": 2, "source": 3}
    messages.sort(key=lambda message: priority[message.split(":", 1)[0]])
    return messages[:MAX_ANNOTATIONS] or [UNAVAILABLE]


if __name__ == "__main__":
    try:
        result = diagnostics(Path(sys.argv[1]))
    except (OSError, ValueError, SyntaxError, IndexError):
        result = [UNAVAILABLE]
    for message in result[:MAX_ANNOTATIONS] or [UNAVAILABLE]:
        print(annotation(message))
