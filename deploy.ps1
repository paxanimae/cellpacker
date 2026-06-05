$dest = "$env:APPDATA\FreeCAD\Macro"

Write-Host "Deploying to $dest"

Copy-Item -Path "macros\BatteryPackLayoutTool_v3.FCMacro" `
          -Destination "$dest\BatteryPackLayoutTool_v3.FCMacro" -Force

Copy-Item -Path "cellpacker" `
          -Destination "$dest\cellpacker" -Recurse -Force

Write-Host "Done."
