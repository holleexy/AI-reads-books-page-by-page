#Requires -Version 5.1
#Requires -STA
# Capture Kindle for PC pages by screenshot + left/right page-turn.
# Runs on Windows only. Does not read Kindle files or remove DRM.
# ASCII only so Windows PowerShell 5.1 can parse -File as system ANSI.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/kindle_capture.ps1 -ListWindows
#   powershell -ExecutionPolicy Bypass -File scripts/kindle_capture.ps1 -Direction Right
#   powershell -ExecutionPolicy Bypass -File scripts/kindle_capture.ps1 -Direction Left

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
    [int]$IntervalMs = 1200,
    [int]$MaxPages = 2500,
    [int]$StopOnDuplicate = 3,
    [string]$Crop = "0,0,0,0",
    [switch]$ListWindows,
    [switch]$CopyFromScreen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    Write-Error "This script runs on Windows only."
    exit 1
}

Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type -AssemblyName System.Drawing | Out-Null

$native = @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class KindleWin {
    public const uint PW_RENDERFULLCONTENT = 2;
    public const int SW_RESTORE = 9;

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

    public const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    public const uint MOUSEEVENTF_LEFTUP = 0x0004;

    public static void ClickTurnSide(IntPtr hwnd, bool nextOnRight) {
        RECT r;
        if (!GetWindowRect(hwnd, out r)) {
            throw new InvalidOperationException("GetWindowRect failed");
        }
        int width = r.Right - r.Left;
        int height = r.Bottom - r.Top;
        int x = nextOnRight
            ? r.Left + (int)(width * 0.88)
            : r.Left + (int)(width * 0.12);
        int y = r.Top + (int)(height * 0.50);
        SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, UIntPtr.Zero);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, UIntPtr.Zero);
    }

    public static Bitmap CaptureWindow(IntPtr hwnd, bool copyFromScreen) {
        RECT r;
        if (!GetWindowRect(hwnd, out r)) {
            throw new InvalidOperationException("GetWindowRect failed");
        }
        int w = r.Right - r.Left;
        int h = r.Bottom - r.Top;
        if (w <= 0 || h <= 0) {
            throw new InvalidOperationException("Window size is empty");
        }
        Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp)) {
            if (copyFromScreen) {
                g.CopyFromScreen(r.Left, r.Top, 0, 0, new Size(w, h), CopyPixelOperation.SourceCopy);
            } else {
                IntPtr hdc = g.GetHdc();
                try {
                    if (!PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)) {
                        PrintWindow(hwnd, hdc, 0);
                    }
                } finally {
                    g.ReleaseHdc(hdc);
                }
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

$cropVals = Parse-Crop $Crop
if ([string]::IsNullOrWhiteSpace($Keys)) {
    $Keys = if ($Direction -eq "Left") { "{LEFT}" } else { "{RIGHT}" }
}
$nextOnRight = $Direction -eq "Right"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$win = Resolve-KindleWindow
$hwnd = $win.MainWindowHandle
if ($hwnd -eq [IntPtr]::Zero) {
    throw "Kindle window handle is zero. Open the book and try again."
}
Write-Host ("Target: pid={0} name={1} title={2}" -f $win.Id, $win.ProcessName, $win.MainWindowTitle)
Write-Host ("Output: {0}" -f $OutDir)
Write-Host ("Turn: direction={0} keys={1} method={2}" -f $Direction, $Keys, $TurnMethod)
Write-Host ("Focus Kindle, wait {0}s, then capture starts. Ctrl+C to stop." -f $StartDelaySec)

[KindleWin]::ShowWindow($hwnd, 9) | Out-Null
[KindleWin]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Seconds $StartDelaySec

$useScreen = [bool]$CopyFromScreen
$prevHash = ""
$dup = 0
$page = 0

while ($page -lt $MaxPages) {
    $page++
    [KindleWin]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 150

    $bmp = [KindleWin]::CaptureWindow($hwnd, $useScreen)
    try {
        if (-not $useScreen -and [KindleWin]::MostlyBlack($bmp, 0.92)) {
            Write-Host "PrintWindow looks black; switching to CopyFromScreen"
            $useScreen = $true
            $bmp.Dispose()
            $bmp = [KindleWin]::CaptureWindow($hwnd, $true)
        }
        $cropped = [KindleWin]::Crop($bmp, $cropVals[0], $cropVals[1], $cropVals[2], $cropVals[3])
    } finally {
        $bmp.Dispose()
    }

    $path = Join-Path $OutDir ("{0:D4}.png" -f $page)
    $cropped.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $cropped.Dispose()

    $hash = (Get-FileHash -Algorithm SHA256 -Path $path).Hash
    if ($hash -eq $prevHash) {
        $dup++
        Write-Host ("page {0}: duplicate {1}/{2}" -f $page, $dup, $StopOnDuplicate)
        if ($dup -ge $StopOnDuplicate) {
            Write-Host "Same image repeated; treating as end of book."
            break
        }
    } else {
        $dup = 0
        $prevHash = $hash
        Write-Host ("page {0}: saved {1}" -f $page, $path)
    }

    [KindleWin]::SetForegroundWindow($hwnd) | Out-Null
    if ($TurnMethod -eq "Key" -or $TurnMethod -eq "Both") {
        [System.Windows.Forms.SendKeys]::SendWait($Keys)
    }
    if ($TurnMethod -eq "Click" -or $TurnMethod -eq "Both") {
        [KindleWin]::ClickTurnSide($hwnd, $nextOnRight)
    }
    Start-Sleep -Milliseconds $IntervalMs
}

Write-Host ("Done. {0} files in {1}" -f $page, $OutDir)
Write-Host "Next: copy the folder to Linux, then images_to_pdf.py and ocrmypdf."
