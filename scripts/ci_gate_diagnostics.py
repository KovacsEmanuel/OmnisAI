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
MAX_OUTER_BYTES = 64 * 1024
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

    # shortcut: make/unittest/pytest/Python frames only; add formats after a real miss.
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
        elif match := re.match(
            r"^(?:FAILED|ERROR) ([A-Za-z0-9_/.-]+\.py)((?:::[A-Za-z_]\w*){1,2})(?=\[| - |$)",
            line,
        ):
            parsed = source(match[1])
            names = match[2].split("::")[1:]
            nodes = parsed[0].body if parsed else []
            if len(names) == 2:
                nodes = [
                    item
                    for node in nodes
                    if isinstance(node, ast.ClassDef) and node.name == names[0]
                    for item in node.body
                ]
            if names[-1].startswith("test_") and any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == names[-1]
                for node in nodes
            ):
                message = f"pytest: {match[1]}{match[2]}"
        elif match := (
            re.fullmatch(r'  File "([^"]+)", line (\d{1,6}), in .+', line)
            or re.fullmatch(r"([A-Za-z0-9_/.-]+\.py):(\d{1,6}):(?: .*)?", line)
        ):
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


def unavailable(reason):
    return [f"{UNAVAILABLE} ({reason})"]


def private_file(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        info = os.fstat(fd)
        if not private(info, stat.S_ISREG) or info.st_nlink != 1:
            raise ValueError("Unsafe file")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def diagnostics(root, outer):
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if not root.is_absolute() or root.resolve() != root:
        return unavailable("root-unsafe")
    try:
        root_fd = os.open(root, directory_flags)
    except OSError:
        return unavailable("root-unsafe")
    try:
        if not private(os.fstat(root_fd), stat.S_ISDIR):
            return unavailable("root-unsafe")
        if outer.parent != root or not re.fullmatch(r"ci-outer\.[A-Za-z0-9]{8}", outer.name):
            return unavailable("outer-unsafe")
        try:
            with private_file(root_fd, outer.name) as capture:
                data = capture.read(MAX_OUTER_BYTES + 1)
        except (OSError, ValueError):
            return unavailable("outer-unsafe")
        if len(data) > MAX_OUTER_BYTES:
            return unavailable("outer-bounds")
        markers = [
            line
            for line in data.splitlines(keepends=True)
            if line.startswith(b"CANONICAL_GATE_BEGIN")
        ]
        if not markers:
            return unavailable("locator-missing")
        if len(markers) != 1:
            return unavailable("locator-duplicate")
        if not markers[0].endswith(b"\n"):
            return unavailable("locator-truncated")
        match = re.fullmatch(
            r"CANONICAL_GATE_BEGIN target=check-components log=([^\r\n]+)\n",
            markers[0].decode("utf-8", errors="replace"),
        )
        if not match:
            return unavailable("locator-invalid")
        if not match[1].startswith(str(root) + "/"):
            return unavailable("locator-foreign")
        location = re.fullmatch(re.escape(str(root)) + r"/(db-[0-9a-f]{16})/gate\.log", match[1])
        if not location:
            return unavailable("locator-invalid")
        try:
            child = os.open(location[1], directory_flags, dir_fd=root_fd)
            try:
                if not private(os.fstat(child), stat.S_ISDIR):
                    return unavailable("log-unsafe")
                with private_file(child, "gate.log") as log:
                    offset = max(0, os.fstat(log.fileno()).st_size - MAX_LOG_BYTES)
                    log.seek(offset)
                    data = log.read(MAX_LOG_BYTES)
                    if offset:
                        data = data.partition(b"\n")[2]
            finally:
                os.close(child)
        except (OSError, ValueError):
            return unavailable("log-unsafe")
    finally:
        os.close(root_fd)
    messages = summarize(data.decode("utf-8", errors="replace"))
    priority = {"make target": 0, "unittest": 1, "pytest": 1, "exception": 2, "source": 3}
    messages.sort(key=lambda message: priority[message.split(":", 1)[0]])
    return messages[:MAX_ANNOTATIONS] or unavailable("log-unclassified")


if __name__ == "__main__":
    try:
        result = diagnostics(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError, SyntaxError, IndexError, subprocess.SubprocessError):
        result = unavailable("reporter-failed")
    for message in result[:MAX_ANNOTATIONS] or [UNAVAILABLE]:
        print(annotation(message))
