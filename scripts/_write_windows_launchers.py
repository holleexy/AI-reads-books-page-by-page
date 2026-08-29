#!/usr/bin/env python3
"""Rewrite Kindle Windows launchers with PS 5.1-safe encodings.

.ps1  : UTF-8 with BOM, CRLF, ASCII body
.bat  : ASCII, CRLF
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def crlf(text: str) -> bytes:
    body = text.replace("\r\n", "\n").replace("\n", "\r\n")
    if not body.endswith("\r\n"):
        body += "\r\n"
    return body.encode("ascii")


def write_ps1(path: Path, text: str) -> None:
    path.write_bytes(b"\xef\xbb\xbf" + crlf(text))


def write_bat(path: Path, text: str) -> None:
    path.write_bytes(crlf(text))


KINDLE_CAPTURE = r'''#Requires -Version 5.1
# Capture Kindle for PC pages by screenshot + left/right page-turn.
# Runs on Windows only. Does not read Kindle files or remove DRM.
# ASCII only so Windows PowerShell 5.1 can parse -File as system ANSI.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/kindle_capture.ps1 -ListWindows
#   powershell -ExecutionPolicy Bypass -File scripts/kindle_capture.ps1 -Direction Right
#   powershell -ExecutionPolicy Bypass -File scripts/kindle_capture.ps1 -Direction Left
#   powershell -ExecutionPolicy Bypass -File scripts/kindle_capture.ps1 -SelfTest

[CmdletBinding()]
param(
    [string]$OutDir = $(Join-Path $env:USERPROFILE "Downloads\kindle_pages"),
    [string]$Title = "Kindle",
    [string]$ProcessName = "Kindle",
    [ValidateSet("Right", "Left")]
    [string]$Direction = "Right",
    [ValidateSet("Key", "Click", "Both")]
    [string]$TurnMethod = "Both",
    [string]$Keys = "",
    [int]$StartDelaySec = 5,
    [int]$IntervalMs = 2000,
    [int]$RenderWaitMs = 400,
    [int]$MaxPages = 2500,
    [int]$StopOnDuplicate = 4,
    [string]$Crop = "0,0,0,0",
    [switch]$ListWindows,
    [switch]$CopyFromScreen,
    [switch]$FullScreen,
    [switch]$SelfTest
)

# STA is requested on powershell.exe. The #Requires STA flag is not valid in 5.1.
if ($MyInvocation.MyCommand.Path) {
    if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne "STA") {
        $exe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        $pass = @()
        foreach ($name in $PSBoundParameters.Keys) {
            $value = $PSBoundParameters[$name]
            if ($value -is [System.Management.Automation.SwitchParameter]) {
                if ($value) { $pass += ("-" + $name) }
            } else {
                $pass += ("-" + $name)
                $pass += [string]$value
            }
        }
        & $exe -NoProfile -STA -ExecutionPolicy Bypass -File $MyInvocation.MyCommand.Path @pass
        exit $LASTEXITCODE
    }
}

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    Write-Error "This script runs on Windows only."
    exit 1
}

# Per-monitor DPI must be set before WinForms caches the virtualized size.
# Unaware capture on a 200% display only gets the top-left quarter.
$dpiType = @"
using System;
using System.Runtime.InteropServices;
public static class KindleDpi {
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int v);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    public static bool Enable() {
        try { if (SetProcessDpiAwarenessContext(new IntPtr(-4))) return true; } catch {}
        try { if (SetProcessDpiAwarenessContext(new IntPtr(-3))) return true; } catch {}
        try { if (SetProcessDpiAwareness(2) == 0) return true; } catch {}
        try { return SetProcessDPIAware(); } catch {}
        return false;
    }
}
"@
if (-not ("KindleDpi" -as [type])) {
    Add-Type -TypeDefinition $dpiType
}
$dpiOk = [KindleDpi]::Enable()

Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type -AssemblyName System.Drawing | Out-Null

$native = @"
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class KindleWin {
    public const uint PW_RENDERFULLCONTENT = 2;
    public const int SW_RESTORE = 9;
    public const int DWMWA_EXTENDED_FRAME_BOUNDS = 9;
    public const int HORZRES = 8;
    public const int VERTRES = 10;
    public const int LOGPIXELSX = 88;
    public const int DESKTOPVERTRES = 117;
    public const int DESKTOPHORZRES = 118;
    public const uint SRCCOPY = 0x00CC0020;
    public const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    public const uint MOUSEEVENTF_LEFTUP = 0x0004;
    public const uint MOUSEEVENTF_WHEEL = 0x0800;
    public const uint KEYEVENTF_KEYUP = 0x0002;
    public const uint WM_KEYDOWN = 0x0100;
    public const uint WM_KEYUP = 0x0101;
    public const byte VK_LEFT = 0x25;
    public const byte VK_UP = 0x26;
    public const byte VK_RIGHT = 0x27;
    public const byte VK_DOWN = 0x28;
    public const byte VK_PRIOR = 0x21;
    public const byte VK_NEXT = 0x22;
    public const byte VK_SPACE = 0x20;
    public const int FP_SIZE = 32;

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, IntPtr pid);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
    [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr hwnd, IntPtr hdc);
    [DllImport("gdi32.dll")] public static extern int GetDeviceCaps(IntPtr hdc, int index);
    [DllImport("gdi32.dll")] public static extern bool BitBlt(IntPtr hdcDest, int nXDest, int nYDest, int nWidth, int nHeight, IntPtr hdcSrc, int nXSrc, int nYSrc, uint dwRop);
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr hwnd, int attr, out RECT rect, int size);

    public static int[] PhysicalScreenSize() {
        IntPtr hdc = GetDC(IntPtr.Zero);
        try {
            return new int[] {
                GetDeviceCaps(hdc, DESKTOPHORZRES),
                GetDeviceCaps(hdc, DESKTOPVERTRES),
                GetDeviceCaps(hdc, HORZRES),
                GetDeviceCaps(hdc, VERTRES),
                GetDeviceCaps(hdc, LOGPIXELSX)
            };
        } finally {
            ReleaseDC(IntPtr.Zero, hdc);
        }
    }

    public static void FocusWindow(IntPtr hwnd) {
        if (hwnd == IntPtr.Zero) {
            return;
        }
        if (IsIconic(hwnd)) {
            ShowWindow(hwnd, SW_RESTORE);
        }
        IntPtr fg = GetForegroundWindow();
        uint self = GetCurrentThreadId();
        uint fgTid = GetWindowThreadProcessId(fg, IntPtr.Zero);
        uint destTid = GetWindowThreadProcessId(hwnd, IntPtr.Zero);
        bool attachedFg = false;
        bool attachedDest = false;
        try {
            if (fg != IntPtr.Zero && fgTid != 0 && fgTid != self) {
                attachedFg = AttachThreadInput(self, fgTid, true);
            }
            if (destTid != 0 && destTid != self && destTid != fgTid) {
                attachedDest = AttachThreadInput(self, destTid, true);
            }
            BringWindowToTop(hwnd);
            SetForegroundWindow(hwnd);
        } finally {
            if (attachedDest) {
                AttachThreadInput(self, destTid, false);
            }
            if (attachedFg) {
                AttachThreadInput(self, fgTid, false);
            }
        }
    }

    public static RECT GetCaptureRect(IntPtr hwnd) {
        RECT r;
        int size = Marshal.SizeOf(typeof(RECT));
        if (DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, out r, size) != 0) {
            if (!GetWindowRect(hwnd, out r)) {
                throw new InvalidOperationException("GetWindowRect failed");
            }
        }
        return r;
    }

    public static void ClickAt(IntPtr hwnd, double fx, double fy) {
        RECT r = GetCaptureRect(hwnd);
        int width = r.Right - r.Left;
        int height = r.Bottom - r.Top;
        int x = r.Left + (int)(width * fx);
        int y = r.Top + (int)(height * fy);
        SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, UIntPtr.Zero);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, UIntPtr.Zero);
    }

    public static void ClickTurnSide(IntPtr hwnd, bool nextOnRight) {
        ClickAt(hwnd, nextOnRight ? 0.94 : 0.06, 0.50);
    }

    public static void WheelAt(IntPtr hwnd, double fx, double fy, int delta) {
        RECT r = GetCaptureRect(hwnd);
        int width = r.Right - r.Left;
        int height = r.Bottom - r.Top;
        int x = r.Left + (int)(width * fx);
        int y = r.Top + (int)(height * fy);
        SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_WHEEL, 0, 0, unchecked((uint)delta), UIntPtr.Zero);
    }

    public static void TapKey(byte vk) {
        keybd_event(vk, 0, 0, UIntPtr.Zero);
        keybd_event(vk, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
    }

    public static void SendTurnKey(bool nextOnRight) {
        TapKey(nextOnRight ? VK_RIGHT : VK_LEFT);
    }

    public static void PostKey(IntPtr hwnd, int vk) {
        PostMessage(hwnd, WM_KEYDOWN, (IntPtr)vk, IntPtr.Zero);
        PostMessage(hwnd, WM_KEYUP, (IntPtr)vk, IntPtr.Zero);
    }

    public static Bitmap CaptureRect(int left, int top, int w, int h) {
        if (w <= 0 || h <= 0) {
            throw new InvalidOperationException("Capture size is empty");
        }
        Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp)) {
            g.CopyFromScreen(left, top, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
        }
        return bmp;
    }

    public static Bitmap CapturePhysicalScreen() {
        IntPtr hdc = GetDC(IntPtr.Zero);
        try {
            int w = GetDeviceCaps(hdc, DESKTOPHORZRES);
            int h = GetDeviceCaps(hdc, DESKTOPVERTRES);
            if (w <= 0 || h <= 0) {
                throw new InvalidOperationException("Physical screen size is empty");
            }
            Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
            using (Graphics g = Graphics.FromImage(bmp)) {
                IntPtr dest = g.GetHdc();
                try {
                    BitBlt(dest, 0, 0, w, h, hdc, 0, 0, SRCCOPY);
                } finally {
                    g.ReleaseHdc(dest);
                }
            }
            return bmp;
        } finally {
            ReleaseDC(IntPtr.Zero, hdc);
        }
    }

    public static Bitmap CaptureWindow(IntPtr hwnd, bool copyFromScreen) {
        RECT r = GetCaptureRect(hwnd);
        int w = r.Right - r.Left;
        int h = r.Bottom - r.Top;
        if (w <= 0 || h <= 0) {
            throw new InvalidOperationException("Window size is empty");
        }
        if (copyFromScreen) {
            return CaptureRect(r.Left, r.Top, w, h);
        }
        Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp)) {
            IntPtr hdc = g.GetHdc();
            try {
                if (!PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)) {
                    PrintWindow(hwnd, hdc, 0);
                }
            } finally {
                g.ReleaseHdc(hdc);
            }
        }
        return bmp;
    }

    public static Bitmap Crop(Bitmap src, int left, int top, int right, int bottom) {
        int w = src.Width - left - right;
        int h = src.Height - top - bottom;
        if (w <= 10 || h <= 10) {
            throw new InvalidOperationException("Crop removed the whole window");
        }
        Rectangle rect = new Rectangle(left, top, w, h);
        return src.Clone(rect, src.PixelFormat);
    }

    public static bool MostlyBlack(Bitmap bmp, double threshold) {
        int sample = 0;
        int dark = 0;
        int stepX = Math.Max(1, bmp.Width / 40);
        int stepY = Math.Max(1, bmp.Height / 40);
        for (int y = 0; y < bmp.Height; y += stepY) {
            for (int x = 0; x < bmp.Width; x += stepX) {
                Color c = bmp.GetPixel(x, y);
                sample++;
                if (c.R < 18 && c.G < 18 && c.B < 18) dark++;
            }
        }
        return sample > 0 && (double)dark / sample >= threshold;
    }

    public static byte[] ContentFingerprint(Bitmap bmp) {
        int left = bmp.Width * 6 / 100;
        int top = bmp.Height * 6 / 100;
        int rightPad = bmp.Width * 6 / 100;
        int bottomPad = bmp.Height * 8 / 100;
        int innerW = bmp.Width - left - rightPad;
        int innerH = bmp.Height - top - bottomPad;
        if (innerW < 16 || innerH < 16) {
            left = 0;
            top = 0;
            innerW = bmp.Width;
            innerH = bmp.Height;
        }
        byte[] fp = new byte[FP_SIZE * FP_SIZE];
        using (Bitmap small = new Bitmap(FP_SIZE, FP_SIZE, PixelFormat.Format32bppArgb)) {
            using (Graphics g = Graphics.FromImage(small)) {
                g.InterpolationMode = InterpolationMode.HighQualityBilinear;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.DrawImage(
                    bmp,
                    new Rectangle(0, 0, FP_SIZE, FP_SIZE),
                    new Rectangle(left, top, innerW, innerH),
                    GraphicsUnit.Pixel
                );
            }
            for (int y = 0; y < FP_SIZE; y++) {
                for (int x = 0; x < FP_SIZE; x++) {
                    Color c = small.GetPixel(x, y);
                    fp[y * FP_SIZE + x] = (byte)((c.R * 30 + c.G * 59 + c.B * 11) / 100);
                }
            }
        }
        return fp;
    }

    public static bool FingerprintsMatch(byte[] a, byte[] b) {
        if (a == null || b == null || a.Length != b.Length || a.Length == 0) {
            return false;
        }
        int sum = 0;
        int inkA = 0;
        int inkB = 0;
        for (int i = 0; i < a.Length; i++) {
            sum += Math.Abs(a[i] - b[i]);
            if (a[i] < 235) inkA++;
            if (b[i] < 235) inkB++;
        }
        int mad = sum / a.Length;
        int inkDiff = Math.Abs(inkA - inkB) * 100 / a.Length;
        return mad <= 8 && inkDiff <= 6;
    }
}
"@

if (-not ("KindleWin" -as [type])) {
    $drawing = [System.Drawing.Bitmap].Assembly.Location
    Add-Type -TypeDefinition $native -ReferencedAssemblies $drawing
}

function Get-CaptureWindows {
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero -and $_.MainWindowTitle } |
        Select-Object Id, ProcessName, MainWindowTitle, MainWindowHandle
}

function Resolve-KindleWindow {
    $found = @(Get-CaptureWindows | Where-Object {
        $_.ProcessName -like "*$ProcessName*" -or $_.MainWindowTitle -like "*$Title*"
    })
    if ($found.Count -eq 0) {
        throw "Kindle window not found. Open the book in Kindle for PC, or pass -ListWindows / -Title."
    }
    if ($found.Count -gt 1) {
        Write-Host "Multiple windows matched; using the first:"
        Write-Host ($found | Select-Object Id, ProcessName, MainWindowTitle | Out-String)
    }
    return $found[0]
}

function Parse-Crop([string]$spec) {
    $parts = @($spec.Split(",") | ForEach-Object { [int]$_.Trim() })
    if ($parts.Count -ne 4) {
        throw "Crop must be L,T,R,B (example: 80,50,80,40)"
    }
    return $parts
}

if ($ListWindows) {
    Write-Host (Get-CaptureWindows | Select-Object Id, ProcessName, MainWindowTitle | Out-String)
    return
}

function Invoke-KindleSelfTest {
    $phys = [KindleWin]::PhysicalScreenSize()
    Write-Host ("physical={0}x{1} logical={2}x{3} logpixels={4} dpiAware={5}" -f $phys[0], $phys[1], $phys[2], $phys[3], $phys[4], $dpiOk)
    if ($phys[0] -lt 100 -or $phys[1] -lt 100) {
        throw "PhysicalScreenSize returned an empty display"
    }
    $screen = [KindleWin]::CapturePhysicalScreen()
    try {
        if ($screen.Width -ne $phys[0] -or $screen.Height -ne $phys[1]) {
            throw ("Physical capture {0}x{1} != {2}x{3}" -f $screen.Width, $screen.Height, $phys[0], $phys[1])
        }
        Write-Host ("ok physical capture {0}x{1}" -f $screen.Width, $screen.Height)
    } finally {
        $screen.Dispose()
    }

    $white = [System.Drawing.Color]::White
    $black = [System.Drawing.Color]::Black
    $navy = [System.Drawing.Color]::Navy
    $red = [System.Drawing.Color]::Red
    $a = New-Object System.Drawing.Bitmap 200, 200
    $g = [System.Drawing.Graphics]::FromImage($a)
    $g.Clear($white)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $black), 0, 0, 200, 8)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $navy), 80, 80, 40, 40)
    $g.Dispose()
    $b = New-Object System.Drawing.Bitmap 200, 200
    $g = [System.Drawing.Graphics]::FromImage($b)
    $g.Clear($white)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $navy), 80, 80, 40, 40)
    $g.Dispose()
    $c = New-Object System.Drawing.Bitmap 200, 200
    $g = [System.Drawing.Graphics]::FromImage($c)
    $g.Clear($white)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $red), 20, 80, 160, 40)
    $g.Dispose()
    $d = New-Object System.Drawing.Bitmap 200, 200
    $g = [System.Drawing.Graphics]::FromImage($d)
    $g.Clear($white)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $navy), 60, 50, 80, 90)
    $g.Dispose()
    $blank = New-Object System.Drawing.Bitmap 200, 200
    $g = [System.Drawing.Graphics]::FromImage($blank)
    $g.Clear($white)
    $g.Dispose()
    try {
        $fa = [KindleWin]::ContentFingerprint($a)
        $fb = [KindleWin]::ContentFingerprint($b)
        $fc = [KindleWin]::ContentFingerprint($c)
        $fd = [KindleWin]::ContentFingerprint($d)
        $fblank = [KindleWin]::ContentFingerprint($blank)
        if (-not [KindleWin]::FingerprintsMatch($fa, $fb)) {
            throw "top-bar-only change should match"
        }
        if ([KindleWin]::FingerprintsMatch($fa, $fc)) {
            throw "different content should not match"
        }
        if ([KindleWin]::FingerprintsMatch($fblank, $fd)) {
            throw "sparse white page vs diagram must not match"
        }
        Write-Host "ok fingerprint match/mismatch"
    } finally {
        $a.Dispose()
        $b.Dispose()
        $c.Dispose()
        $d.Dispose()
        $blank.Dispose()
    }
    Write-Host "SELFTEST OK"
}

function Get-PageBitmap($hwnd, $useScreen, $phys) {
    if ($FullScreen) {
        $scr = [System.Windows.Forms.Screen]::FromHandle($hwnd)
        $bounds = $scr.Bounds
        $stillVirtual = ($phys[0] -gt ($phys[2] + 10)) -and ($bounds.Width -eq $phys[2])
        if ($stillVirtual -or $bounds.Width -lt 100 -or $bounds.Height -lt 100) {
            Write-Host "Capturing physical screen (DPI-virtualized Bounds would crop the page)"
            return [KindleWin]::CapturePhysicalScreen()
        }
        return [KindleWin]::CaptureRect($bounds.X, $bounds.Y, $bounds.Width, $bounds.Height)
    }
    $bmp = [KindleWin]::CaptureWindow($hwnd, [bool]$useScreen)
    if (-not $useScreen -and [KindleWin]::MostlyBlack($bmp, 0.92)) {
        Write-Host "PrintWindow looks black; switching to CopyFromScreen"
        $script:useScreen = $true
        $bmp.Dispose()
        $bmp = [KindleWin]::CaptureWindow($hwnd, $true)
    }
    return $bmp
}

$cropVals = Parse-Crop $Crop
if ([string]::IsNullOrWhiteSpace($Keys)) {
    $Keys = if ($Direction -eq "Left") { "{LEFT}" } else { "{RIGHT}" }
}
$nextOnRight = $Direction -eq "Right"

if ($SelfTest) {
    Invoke-KindleSelfTest
    return
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$win = Resolve-KindleWindow
$hwnd = $win.MainWindowHandle
if ($hwnd -eq [IntPtr]::Zero) {
    throw "Kindle window handle is zero. Open the book and try again."
}
$phys = [KindleWin]::PhysicalScreenSize()
Write-Host ("Target: pid={0} name={1} title={2}" -f $win.Id, $win.ProcessName, $win.MainWindowTitle)
Write-Host ("Output: {0}" -f $OutDir)
Write-Host ("Turn: direction={0} keys={1} method={2}" -f $Direction, $Keys, $TurnMethod)
Write-Host ("Display: physical={0}x{1} logical={2}x{3} dpiAware={4}" -f $phys[0], $phys[1], $phys[2], $phys[3], $dpiOk)
Write-Host ("Capture: {0}; retry turns until page content changes, then stop after {1} full ladders." -f ($(if ($FullScreen) { "full screen" } else { "Kindle window" }), $StopOnDuplicate))
Write-Host ("Focus Kindle, wait {0}s, then capture starts. Ctrl+C to stop." -f $StartDelaySec)

[KindleWin]::FocusWindow($hwnd)
Start-Sleep -Seconds $StartDelaySec

$script:useScreen = $true
if (-not $CopyFromScreen) {
    # Default is screen copy so GPU-composited Kindle pages are complete.
    $script:useScreen = $true
}
$peekPath = Join-Path $OutDir "_peek.png"
$consoleHwnd = [KindleWin]::GetConsoleWindow()
$hidConsole = $false
if ($FullScreen -and ($consoleHwnd -ne [IntPtr]::Zero)) {
    [KindleWin]::ShowWindow($consoleHwnd, 6) | Out-Null
    $hidConsole = $true
}

function Get-KindleFrameFingerprint {
    [KindleWin]::FocusWindow($hwnd)
    $bmp = Get-PageBitmap $hwnd $script:useScreen $phys
    try {
        $cropped = [KindleWin]::Crop($bmp, $cropVals[0], $cropVals[1], $cropVals[2], $cropVals[3])
    } finally {
        $bmp.Dispose()
    }
    $fp = [KindleWin]::ContentFingerprint($cropped)
    $cropped.Save($peekPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $cropped.Dispose()
    return $fp
}

function Get-StableKindleFingerprint {
    $f1 = Get-KindleFrameFingerprint
    $tries = 0
    while ($tries -lt 8) {
        Start-Sleep -Milliseconds $RenderWaitMs
        $f2 = Get-KindleFrameFingerprint
        if ([KindleWin]::FingerprintsMatch($f1, $f2)) {
            return $f1
        }
        $f1 = $f2
        $tries++
    }
    return $f1
}

function Invoke-KindleAdvance([string]$method) {
    [KindleWin]::FocusWindow($hwnd)
    Start-Sleep -Milliseconds 80
    $side = 0.94
    if (-not $nextOnRight) {
        $side = 0.06
    }
    $vkArrow = [byte]0x27
    $vkPage = [byte]0x22
    $vkVert = [byte]0x28
    $vkPostArrow = 0x27
    $vkPostPage = 0x22
    $wheel = -360
    if (-not $nextOnRight) {
        $vkArrow = [byte]0x25
        $vkPage = [byte]0x21
        $vkVert = [byte]0x26
        $vkPostArrow = 0x25
        $vkPostPage = 0x21
        $wheel = 360
    }
    switch ($method) {
        "arrow-key" {
            if (($Keys -eq "{RIGHT}") -or ($Keys -eq "{LEFT}")) {
                [KindleWin]::SendTurnKey($nextOnRight)
            } else {
                [System.Windows.Forms.SendKeys]::SendWait($Keys)
            }
        }
        "page-key" { [KindleWin]::TapKey($vkPage) }
        "arrow-post" { [KindleWin]::PostKey($hwnd, $vkPostArrow) }
        "page-post" { [KindleWin]::PostKey($hwnd, $vkPostPage) }
        "space" { [KindleWin]::TapKey([byte]0x20) }
        "line" {
            [KindleWin]::TapKey($vkVert)
            [KindleWin]::TapKey($vkVert)
        }
        "focus" { [KindleWin]::ClickAt($hwnd, 0.50, 0.55) }
        "focus-arrow" {
            [KindleWin]::ClickAt($hwnd, 0.50, 0.55)
            Start-Sleep -Milliseconds 80
            [KindleWin]::TapKey($vkArrow)
        }
        "click-side" { [KindleWin]::ClickAt($hwnd, $side, 0.50) }
        "click-low" { [KindleWin]::ClickAt($hwnd, $side, 0.66) }
        "click-high" { [KindleWin]::ClickAt($hwnd, $side, 0.38) }
        "wheel" { [KindleWin]::WheelAt($hwnd, 0.50, 0.55, $wheel) }
    }
}

$methods = @("arrow-key", "page-key", "arrow-post", "page-post", "space", "line", "focus-arrow", "click-side", "wheel", "click-low", "click-high")
if ($TurnMethod -eq "Key") {
    $methods = @("arrow-key", "page-key", "arrow-post", "page-post", "line", "space")
}
if ($TurnMethod -eq "Click") {
    $methods = @("focus", "click-side", "click-low", "click-high", "wheel")
}

$page = 0
try {
    $fp = Get-StableKindleFingerprint
    $page = 1
    $path = Join-Path $OutDir ("{0:D4}.png" -f $page)
    Copy-Item -Force $peekPath $path
    $peekBmp = New-Object System.Drawing.Bitmap $peekPath
    try {
        Write-Host ("First frame: {0}x{1}" -f $peekBmp.Width, $peekBmp.Height)
        if ($phys[0] -gt ($phys[2] + 10) -and $peekBmp.Width -le $phys[2]) {
            Write-Host "WARNING: capture width still matches logical pixels; page may be cropped."
        }
    } finally {
        $peekBmp.Dispose()
    }
    Write-Host ("page {0}: saved {1}" -f $page, $path)
    $stalls = 0

    while ($page -lt $MaxPages) {
        $moved = $false
        foreach ($method in $methods) {
            Invoke-KindleAdvance $method
            $wait = $IntervalMs
            if ($stalls -gt 0) {
                $wait = $IntervalMs + (400 * $stalls)
            }
            Start-Sleep -Milliseconds $wait
            $nextFp = Get-StableKindleFingerprint
            if (-not [KindleWin]::FingerprintsMatch($fp, $nextFp)) {
                $fp = $nextFp
                $moved = $true
                $stalls = 0
                Write-Host ("advanced with {0}" -f $method)
                break
            }
            Write-Host ("no change after {0}; trying another turn" -f $method)
        }
        if (-not $moved) {
            $stalls++
            Write-Host ("still the same page after a full turn ladder ({0}/{1})" -f $stalls, $StopOnDuplicate)
            if (($StopOnDuplicate -gt 0) -and ($stalls -ge $StopOnDuplicate)) {
                Write-Host "Page did not change after retries; treating as end of book."
                break
            }
            continue
        }
        $page++
        $path = Join-Path $OutDir ("{0:D4}.png" -f $page)
        Copy-Item -Force $peekPath $path
        Write-Host ("page {0}: saved {1}" -f $page, $path)
    }
} finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $peekPath
    if ($hidConsole) {
        [KindleWin]::ShowWindow($consoleHwnd, 9) | Out-Null
    }
}

Write-Host ("Done. {0} files in {1}" -f $page, $OutDir)
Write-Host "Next: copy the folder to Linux, then images_to_pdf.py and ocrmypdf."
'''

KINDLE_CAPTURE_GUI = r'''#Requires -Version 5.1
# Optional ASCII WinForms chooser. The default path is KindleCapture.bat (cmd CHOICE).
# Keep this file ASCII-only. Windows PowerShell 5.1 misparses UTF-8 Japanese without BOM.
# STA is requested on powershell.exe. The #Requires STA flag is not valid in 5.1.

if ($MyInvocation.MyCommand.Path) {
    if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne "STA") {
        $exe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
        & $exe -NoProfile -STA -ExecutionPolicy Bypass -File $MyInvocation.MyCommand.Path
        exit $LASTEXITCODE
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:chosen = $null

$form = New-Object System.Windows.Forms.Form
$form.Text = "Kindle capture"
$form.Size = New-Object System.Drawing.Size(460, 240)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false

$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(20, 20)
$label.Size = New-Object System.Drawing.Size(400, 50)
$label.Text = "Open the book in Kindle for PC, then click a button.`nCapture starts after 5 seconds. Ctrl+C stops it."
$form.Controls.Add($label)

$btnRight = New-Object System.Windows.Forms.Button
$btnRight.Location = New-Object System.Drawing.Point(20, 90)
$btnRight.Size = New-Object System.Drawing.Size(190, 70)
$btnRight.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$btnRight.Text = "Right"
$btnRight.Add_Click({ $script:chosen = "Right"; $form.Close() })
$form.Controls.Add($btnRight)

$btnLeft = New-Object System.Windows.Forms.Button
$btnLeft.Location = New-Object System.Drawing.Point(230, 90)
$btnLeft.Size = New-Object System.Drawing.Size(190, 70)
$btnLeft.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$btnLeft.Text = "Left"
$btnLeft.Add_Click({ $script:chosen = "Left"; $form.Close() })
$form.Controls.Add($btnLeft)

[void]$form.ShowDialog()
if (-not $script:chosen) {
    exit 0
}

$capture = Join-Path $PSScriptRoot "kindle_capture.ps1"
& $capture -Direction $script:chosen
if ($null -ne $LASTEXITCODE) {
    exit $LASTEXITCODE
}
'''

ROOT_BAT = r'''@echo off
call "%~dp0scripts\KindleCapture.bat"
'''

SCRIPTS_BAT = r'''@echo off
setlocal
cd /d "%~dp0"
title Kindle capture
echo Open the Kindle book, then choose direction.
echo R = Right page-turn
echo L = Left page-turn
choice /c RL /n /m "Press R or L: "
if errorlevel 255 goto :eof
if errorlevel 2 goto LEFT
if errorlevel 1 goto RIGHT
goto :eof

:RIGHT
set DIR=Right
goto RUN

:LEFT
set DIR=Left
goto RUN

:RUN
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0kindle_capture.ps1" -Direction %DIR%
echo.
pause
'''

RIGHT_BAT = r'''@echo off
setlocal
cd /d "%~dp0"
title Kindle capture Right
echo Open the Kindle book, then wait. Right-turn capture starts in 5 seconds.
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0kindle_capture.ps1" -Direction Right
echo.
pause
'''

LEFT_BAT = r'''@echo off
setlocal
cd /d "%~dp0"
title Kindle capture Left
echo Open the Kindle book, then wait. Left-turn capture starts in 5 seconds.
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0kindle_capture.ps1" -Direction Left
echo.
pause
'''


def main() -> None:
    write_ps1(SCRIPTS / "kindle_capture.ps1", KINDLE_CAPTURE)
    write_ps1(SCRIPTS / "kindle_capture_gui.ps1", KINDLE_CAPTURE_GUI)
    write_bat(ROOT / "KindleCapture.bat", ROOT_BAT)
    write_bat(SCRIPTS / "KindleCapture.bat", SCRIPTS_BAT)
    write_bat(SCRIPTS / "KindleCapture-Right.bat", RIGHT_BAT)
    write_bat(SCRIPTS / "KindleCapture-Left.bat", LEFT_BAT)
    print("wrote Windows launchers")


if __name__ == "__main__":
    main()
