import sys
mods = [k for k in sys.modules if k == "cellpacker" or k.startswith("cellpacker.")]
for m in mods:
    del sys.modules[m]
print(f"Cleared {len(mods)} cellpacker module(s): {mods}")
