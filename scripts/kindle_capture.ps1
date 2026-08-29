#Requires -Version 5.1
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
    [string]$TurnMethod = "Key",
    [string]$Keys = "",
    [int]$StartDelaySec = 5,
    [int]$IntervalMs = 1200,
    [int]$MaxPages = 2500,
    [int]$StopOnDuplicate = 3,
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
    public const uint KEYEVENTF_KEYUP = 0x0002;
    public const byte VK_LEFT = 0x25;
    public const byte VK_RIGHT = 0x27;
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

    public static void SendTurnKey(bool nextOnRight) {
        byte vk = nextOnRight ? VK_RIGHT : VK_LEFT;
        keybd_event(vk, 0, 0, UIntPtr.Zero);
        keybd_event(vk, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
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

    public static void ClickTurnSide(IntPtr hwnd, bool nextOnRight) {
        RECT r = GetCaptureRect(hwnd);
        int width = r.Right - r.Left;
        int height = r.Bottom - r.Top;
        int x = nextOnRight
            ? r.Left + (int)(width * 0.94)
            : r.Left + (int)(width * 0.06);
        int y = r.Top + (int)(height * 0.50);
        SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, UIntPtr.Zero);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, UIntPtr.Zero);
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
Write-Host ("Capture: {0}; stop when the same page content repeats {1} times." -f ($(if ($FullScreen) { "full screen" } else { "Kindle window" }), $StopOnDuplicate))
Write-Host ("Focus Kindle, wait {0}s, then capture starts. Ctrl+C to stop." -f $StartDelaySec)

[KindleWin]::FocusWindow($hwnd)
Start-Sleep -Seconds $StartDelaySec

$useScreen = $true
if (-not $CopyFromScreen) {
    # Default is screen copy so GPU-composited Kindle pages are complete.
    $useScreen = $true
}
$prevFp = $null
$streak = 0
$page = 0
$saved = 0
$consoleHwnd = [KindleWin]::GetConsoleWindow()
$hidConsole = $false
if ($FullScreen -and ($consoleHwnd -ne [IntPtr]::Zero)) {
    [KindleWin]::ShowWindow($consoleHwnd, 6) | Out-Null
    $hidConsole = $true
}

try { while ($page -lt $MaxPages) {
    $page++
    [KindleWin]::FocusWindow($hwnd)
    Start-Sleep -Milliseconds 150

    $bmp = Get-PageBitmap $hwnd $useScreen $phys
    try {
        $cropped = [KindleWin]::Crop($bmp, $cropVals[0], $cropVals[1], $cropVals[2], $cropVals[3])
    } finally {
        $bmp.Dispose()
    }

    if ($page -eq 1) {
        Write-Host ("First frame: {0}x{1}" -f $cropped.Width, $cropped.Height)
        if ($phys[0] -gt ($phys[2] + 10) -and $cropped.Width -le $phys[2]) {
            Write-Host "WARNING: capture width still matches logical pixels; page may be cropped."
        }
    }

    $fp = [KindleWin]::ContentFingerprint($cropped)
    $similar = ($null -ne $prevFp) -and [KindleWin]::FingerprintsMatch($prevFp, $fp)
    if ($similar) {
        $streak++
    } else {
        $streak = 1
        $prevFp = $fp
    }

    $path = Join-Path $OutDir ("{0:D4}.png" -f $page)
    $cropped.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $cropped.Dispose()
    $saved++

    if ($similar) {
        Write-Host ("page {0}: same content {1}/{2} {3}" -f $page, $streak, $StopOnDuplicate, $path)
        if (($StopOnDuplicate -gt 0) -and ($streak -ge $StopOnDuplicate)) {
            Write-Host "Same image repeated; treating as end of book."
            break
        }
    } else {
        Write-Host ("page {0}: saved {1}" -f $page, $path)
    }

    [KindleWin]::FocusWindow($hwnd)
    if ($TurnMethod -eq "Key" -or $TurnMethod -eq "Both") {
        if (($Keys -eq "{RIGHT}") -or ($Keys -eq "{LEFT}")) {
            [KindleWin]::SendTurnKey($nextOnRight)
        } else {
            [System.Windows.Forms.SendKeys]::SendWait($Keys)
        }
    }
    # Skip click on a repeated page. Kindle toggles chrome on tap, which
    # used to make SHA256 hashes alternate so the 3-page stop never fired.
    if (-not $similar -and ($TurnMethod -eq "Click" -or $TurnMethod -eq "Both")) {
        [KindleWin]::ClickTurnSide($hwnd, $nextOnRight)
    }
    Start-Sleep -Milliseconds $IntervalMs
} } finally {
    if ($hidConsole) {
        [KindleWin]::ShowWindow($consoleHwnd, 9) | Out-Null
    }
}

Write-Host ("Done. {0} files in {1}" -f $saved, $OutDir)
Write-Host "Next: copy the folder to Linux, then images_to_pdf.py and ocrmypdf."
