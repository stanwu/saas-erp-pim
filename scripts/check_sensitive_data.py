import re
import sys
from pathlib import Path


PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]"),
]


def scan_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings = []
    for index, line in enumerate(content.splitlines(), start=1):
        for pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{index}: potential sensitive data")
    return findings


def main() -> int:
    findings = []
    for file_name in sys.argv[1:]:
        path = Path(file_name)
        if path.is_file():
            findings.extend(scan_file(path))

    if findings:
        print("\n".join(findings))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
