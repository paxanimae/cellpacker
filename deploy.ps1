$dest = "$env:APPDATA\FreeCAD\Macro"

Write-Host "Deploying to $dest"

Copy-Item -Path "macros\BatteryPackLayoutTool_v3.FCMacro" `
          -Destination "$dest\BatteryPackLayoutTool_v3.FCMacro" -Force

# Remove first: Copy-Item -Recurse into an existing directory nests the
# source inside it instead of overwriting, leaving stale files behind.
if (Test-Path "$dest\cellpacker") {
    Remove-Item -Path "$dest\cellpacker" -Recurse -Force
}
Copy-Item -Path "cellpacker" -Destination "$dest" -Recurse -Force

Write-Host "Done."
