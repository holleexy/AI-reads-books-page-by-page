#Requires -Version 5.1
#Requires -STA
# Optional ASCII WinForms chooser. The default path is KindleCapture.bat (cmd CHOICE).
# Keep this file ASCII-only. Windows PowerShell 5.1 misparses UTF-8 Japanese without BOM.

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
