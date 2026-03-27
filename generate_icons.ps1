Add-Type -AssemblyName System.Drawing

$preferredSource = Join-Path $PSScriptRoot "..\assets\logos\apk_icon.png"
$fallbackSource = Join-Path $PSScriptRoot "public\logos\aura.png"
$source = if (Test-Path $preferredSource) { $preferredSource } else { $fallbackSource }
$resBase = Join-Path $PSScriptRoot "android\app\src\main\res"
$img = [System.Drawing.Image]::FromFile($source)
Write-Host "Source: $($img.Width)x$($img.Height)"

function Resize-Image($srcImg, $width, $height, $outFile) {
    $bmp = New-Object System.Drawing.Bitmap($width, $height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $g.DrawImage($srcImg, 0, 0, $width, $height)
    $g.Dispose()
    $bmp.Save($outFile, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

function Create-Foreground($srcImg, $fgSize, $outFile) {
    $bmp = New-Object System.Drawing.Bitmap($fgSize, $fgSize)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $g.Clear([System.Drawing.Color]::Transparent)
    $padding = [math]::Round($fgSize * 0.22)
    $innerSize = $fgSize - (2 * $padding)
    $g.DrawImage($srcImg, $padding, $padding, $innerSize, $innerSize)
    $g.Dispose()
    $bmp.Save($outFile, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

$densities = @(
    @{ name="mipmap-mdpi";    icon=48;  fg=108 },
    @{ name="mipmap-hdpi";    icon=72;  fg=162 },
    @{ name="mipmap-xhdpi";   icon=96;  fg=216 },
    @{ name="mipmap-xxhdpi";  icon=144; fg=324 },
    @{ name="mipmap-xxxhdpi"; icon=192; fg=432 }
)

foreach ($d in $densities) {
    $dir = Join-Path $resBase $d.name
    $s = $d.icon
    $fg = $d.fg
    
    Resize-Image $img $s $s (Join-Path $dir "ic_launcher.png")
    Resize-Image $img $s $s (Join-Path $dir "ic_launcher_round.png")
    Create-Foreground $img $fg (Join-Path $dir "ic_launcher_foreground.png")
    
    Write-Host "OK: $($d.name) - icon:${s}x${s}, fg:${fg}x${fg}"
}

$img.Dispose()
Write-Host "All Aura icons generated!"
