"""Encoding and token checks for Kindle Windows launchers (Linux-safe)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

PS1_FILES = (
    SCRIPTS / "kindle_capture.ps1",
    SCRIPTS / "kindle_capture_gui.ps1",
)
BAT_FILES = (
    ROOT / "KindleCapture.bat",
    SCRIPTS / "KindleCapture.bat",
    SCRIPTS / "KindleCapture-Right.bat",
    SCRIPTS / "KindleCapture-Left.bat",
)

UTF8_BOM = b"\xef\xbb\xbf"

# Tokens that break Windows PowerShell 5.1 in this project.
FORBIDDEN_IN_PS1 = (
    "$IsWindows",
    "$matches",
    "右めくり",
    "左めくり",
)

_REQUIRES_PARAMS = frozenset(
    {
        "version",
        "modules",
        "pssnapin",
        "shellid",
        "runasadministrator",
        "psedition",
        "assembly",
    }
)


class CheckError(Exception):
    pass


def has_crlf(data: bytes) -> bool:
    if b"\n" not in data:
        return True
    return b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")


def _assert_requires_params(path: Path, text: str) -> None:
    normalized = text.replace("\r\n", "\n")
    for match in re.finditer(r"(?im)^#requires\b(.*)$", normalized):
        rest = match.group(1)
        for pm in re.finditer(r"-([A-Za-z]+)", rest):
            name = pm.group(1).lower()
            if name not in _REQUIRES_PARAMS:
                raise CheckError(
                    f"{path}: #Requires -{pm.group(1)} is not valid in Windows PowerShell 5.1"
                )


def assert_ps1(path: Path) -> None:
    raw = path.read_bytes()
    if not raw.startswith(UTF8_BOM):
        raise CheckError(f"{path}: missing UTF-8 BOM")
    body = raw[len(UTF8_BOM) :]
    if not has_crlf(body):
        raise CheckError(f"{path}: not CRLF")
    try:
        text = body.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CheckError(f"{path}: non-ASCII body ({exc})") from exc
    lowered = text.lower()
    for token in FORBIDDEN_IN_PS1:
        haystack = lowered if token.isascii() else text
        needle = token.lower() if token.isascii() else token
        if needle in haystack:
            raise CheckError(f"{path}: forbidden token {token!r}")
    _assert_requires_params(path, text)
    if "GetApartmentState()" not in text:
        raise CheckError(f"{path}: missing STA relaunch (do not use #Requires -STA)")
    if path.name == "kindle_capture.ps1":
        if "ReferencedAssemblies $drawing" not in text:
            raise CheckError(f"{path}: Add-Type must pass System.Drawing assembly path")
        if '"KindleWin" -as [type]' not in text:
            raise CheckError(f"{path}: missing KindleWin type guard")
        if '$env:OS -ne "Windows_NT"' not in text:
            raise CheckError(f"{path}: missing $env:OS Windows check")
        if "$found =" not in text:
            raise CheckError(f"{path}: Resolve-KindleWindow must not use $matches")
        for token in (
            "KindleDpi",
            "SetProcessDpiAwarenessContext",
            "CapturePhysicalScreen",
            "ContentFingerprint",
            "FingerprintsMatch",
            "FocusWindow",
            "GetConsoleWindow",
            "SendTurnKey",
            "AttachThreadInput",
            "SelfTest",
            "Invoke-KindleAdvance",
            "TapKey",
            "Get-StableKindleFingerprint",
        ):
            if token not in text:
                raise CheckError(f"{path}: missing {token}")


def assert_bat(path: Path) -> None:
    raw = path.read_bytes()
    if raw.startswith(UTF8_BOM):
        raise CheckError(f"{path}: BAT should be ASCII without BOM")
    if not has_crlf(raw):
        raise CheckError(f"{path}: not CRLF")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CheckError(f"{path}: non-ASCII ({exc})") from exc
    if path.name == "KindleCapture.bat" and path.parent.name == "scripts":
        if "kindle_capture_gui.ps1" in text:
            raise CheckError(f"{path}: default launcher must not call the GUI script")
        if "choice /c RL" not in text:
            raise CheckError(f"{path}: default launcher must use cmd CHOICE")
        right_at = text.lower().find(":right")
        left_at = text.lower().find(":left")
        errorlevel2_at = text.lower().find("if errorlevel 2")
        if errorlevel2_at < 0 or right_at < 0 or left_at < 0:
            raise CheckError(f"{path}: CHOICE must branch on errorlevel 2 before 1")
        if errorlevel2_at > min(right_at, left_at):
            raise CheckError(f"{path}: if errorlevel 2 must come before labels")
        if "-STA" not in text:
            raise CheckError(f"{path}: powershell.exe must be started with -STA")
    elif path.name in {"KindleCapture-Right.bat", "KindleCapture-Left.bat"}:
        if "-STA" not in text:
            raise CheckError(f"{path}: powershell.exe must be started with -STA")


# CP932 lead bytes (JIS X 0208). A following 0x22 is consumed as a trail byte.
_CP932_LEAD = frozenset(range(0x81, 0xA0)) | frozenset(range(0xE0, 0xFD))


def visible_ascii_quotes_under_cp932_dbcs(data: bytes) -> int:
    """Count 0x22 bytes that a CP932 DBCS walker does not swallow as trail bytes."""
    count = 0
    i = 0
    while i < len(data):
        b = data[i]
        if b in _CP932_LEAD and i + 1 < len(data):
            i += 2
            continue
        if b == 0x22:
            count += 1
        i += 1
    return count


def cp932_quote_swallow_reproduced(utf8_no_bom: bytes) -> bool:
    """True when a CP932 DBCS walk hides an ASCII quote that UTF-8 still shows.

    Windows PowerShell 5.1 reads -File as system ANSI. On Japanese Windows that
    is CP932. A UTF-8 sequence such as 右めくり (ends with E3 82 8A) can make
    the closing quote 0x22 a trail byte, so the parser stays inside the string.
    Python's cp932 codec raises instead of swallowing, so this uses a DBCS walk.
    """
    utf8_quotes = utf8_no_bom.decode("utf-8").count('"')
    return visible_ascii_quotes_under_cp932_dbcs(utf8_no_bom) != utf8_quotes


def sample_broken_gui_line() -> bytes:
    return (
        '$btnRight.Text = "Right  /  右めくり"\n'
        '$btnRight.Add_Click({ $script:chosen = "Right"; $form.Close() })\n'
    ).encode("utf-8")


def check_all() -> list[str]:
    errors: list[str] = []
    for path in PS1_FILES:
        try:
            assert_ps1(path)
        except CheckError as exc:
            errors.append(str(exc))
    for path in BAT_FILES:
        try:
            assert_bat(path)
        except CheckError as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    broken = sample_broken_gui_line()
    if not cp932_quote_swallow_reproduced(broken):
        print("WARN: CP932 quote-swallow sample did not reproduce on this Python")
    errors = check_all()
    if errors:
        print("FAIL")
        for item in errors:
            print(" -", item)
        return 1
    print("OK: Kindle launcher encoding and PS 5.1 tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
