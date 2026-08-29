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
    [switch]$CopyFromScreen
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
    public const uint MOUSEEVENTF_WHEEL = 0x0800;
    public const uint KEYEVENTF_KEYUP = 0x0002;
    public const uint WM_KEYDOWN = 0x0100;
    public const uint WM_KEYUP = 0x0101;

    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

    public static void ClickAt(IntPtr hwnd, double fx, double fy) {
        RECT r;
        if (!GetWindowRect(hwnd, out r)) {
            throw new InvalidOperationException("GetWindowRect failed");
        }
        int width = r.Right - r.Left;
        int height = r.Bottom - r.Top;
        int x = r.Left + (int)(width * fx);
        int y = r.Top + (int)(height * fy);
        SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, UIntPtr.Zero);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, UIntPtr.Zero);
    }

    public static void ClickTurnSide(IntPtr hwnd, bool nextOnRight) {
        ClickAt(hwnd, nextOnRight ? 0.90 : 0.10, 0.50);
    }

    public static void WheelAt(IntPtr hwnd, double fx, double fy, int delta) {
        RECT r;
        if (!GetWindowRect(hwnd, out r)) {
            throw new InvalidOperationException("GetWindowRect failed");
        }
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

    public static void PostKey(IntPtr hwnd, int vk) {
        PostMessage(hwnd, WM_KEYDOWN, (IntPtr)vk, IntPtr.Zero);
        PostMessage(hwnd, WM_KEYUP, (IntPtr)vk, IntPtr.Zero);
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

$script:useScreen = [bool]$CopyFromScreen
$peekPath = Join-Path $OutDir "_peek.png"

function Get-KindleFrameHash {
    [KindleWin]::SetForegroundWindow($hwnd) | Out-Null
    $bmp = [KindleWin]::CaptureWindow($hwnd, $script:useScreen)
    try {
        if (-not $script:useScreen -and [KindleWin]::MostlyBlack($bmp, 0.92)) {
            Write-Host "PrintWindow looks black; switching to CopyFromScreen"
            $script:useScreen = $true
            $bmp.Dispose()
            $bmp = [KindleWin]::CaptureWindow($hwnd, $true)
        }
        $cropped = [KindleWin]::Crop($bmp, $cropVals[0], $cropVals[1], $cropVals[2], $cropVals[3])
    } finally {
        $bmp.Dispose()
    }
    $cropped.Save($peekPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $cropped.Dispose()
    return (Get-FileHash -Algorithm SHA256 -Path $peekPath).Hash
}

function Get-StableKindleHash {
    $h1 = Get-KindleFrameHash
    $tries = 0
    while ($tries -lt 8) {
        Start-Sleep -Milliseconds $RenderWaitMs
        $h2 = Get-KindleFrameHash
        if ($h2 -eq $h1) {
            return $h1
        }
        $h1 = $h2
        $tries++
    }
    return $h1
}

function Invoke-KindleAdvance([string]$method) {
    [KindleWin]::ShowWindow($hwnd, 9) | Out-Null
    [KindleWin]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 80
    $side = 0.90
    if (-not $nextOnRight) {
        $side = 0.10
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
        "focus" { [KindleWin]::ClickAt($hwnd, 0.50, 0.55) }
        "arrow-key" {
            [KindleWin]::ClickAt($hwnd, 0.50, 0.55)
            Start-Sleep -Milliseconds 80
            [KindleWin]::TapKey($vkArrow)
            [System.Windows.Forms.SendKeys]::SendWait($Keys)
        }
        "arrow-post" { [KindleWin]::PostKey($hwnd, $vkPostArrow) }
        "page-key" {
            [KindleWin]::ClickAt($hwnd, 0.50, 0.55)
            Start-Sleep -Milliseconds 80
            [KindleWin]::TapKey($vkPage)
        }
        "page-post" { [KindleWin]::PostKey($hwnd, $vkPostPage) }
        "space" { [KindleWin]::TapKey([byte]0x20) }
        "line" {
            [KindleWin]::TapKey($vkVert)
            [KindleWin]::TapKey($vkVert)
        }
        "click-side" { [KindleWin]::ClickAt($hwnd, $side, 0.50) }
        "click-low" { [KindleWin]::ClickAt($hwnd, $side, 0.66) }
        "click-high" { [KindleWin]::ClickAt($hwnd, $side, 0.38) }
        "wheel" { [KindleWin]::WheelAt($hwnd, 0.50, 0.55, $wheel) }
    }
}

$methods = @("focus", "arrow-key", "click-side", "page-key", "wheel", "click-low", "arrow-post", "page-post", "line", "space", "click-high")
if ($TurnMethod -eq "Key") {
    $methods = @("focus", "arrow-key", "page-key", "arrow-post", "page-post", "line", "space")
}
if ($TurnMethod -eq "Click") {
    $methods = @("focus", "click-side", "click-low", "click-high", "wheel")
}

$hash = Get-StableKindleHash
$page = 1
$path = Join-Path $OutDir ("{0:D4}.png" -f $page)
Copy-Item -Force $peekPath $path
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
        $nextHash = Get-StableKindleHash
        if ($nextHash -ne $hash) {
            $hash = $nextHash
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
        if ($stalls -ge $StopOnDuplicate) {
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

Remove-Item -Force -ErrorAction SilentlyContinue $peekPath
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
