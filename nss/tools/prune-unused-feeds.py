"""Exclude unrelated optional feed packages whose Kconfig forms cycles.

Only removes package/feeds symlinks in this new lab tree; feed source stays intact.
"""
from pathlib import Path
import json, subprocess, sys
W=Path(sys.argv[1]).resolve()
assert (W/'include/toplevel.mk').is_file(), 'Expected an OpenWrt source directory'
(W/'mf297d/logs').mkdir(parents=True,exist_ok=True)
names={'fwknop','luci-app-fwknopd','squeezelite','luci-app-nss'}
removed=[]
for p in (W/'package/feeds').glob('*/*'):
    if not p.is_symlink():continue
    if not (p.parent.name=='video' and p.name in ('qt5base','qt6base')) and p.name not in names:continue
    target=p.resolve()
    if not target.is_relative_to(W/'feeds'):raise ValueError('Unexpected symlink target')
    removed.append(str(p.relative_to(W)));p.unlink()
(W/'mf297d/excluded-optional-packages.json').write_text(json.dumps(removed,indent=2)+'\n')
result=subprocess.run(['make','defconfig'],cwd=W,text=True,capture_output=True,check=True)
log=result.stdout+result.stderr
(W/'mf297d/logs/defconfig-minimal.log').write_text(log)
if 'recursive dependency detected' in log or 'error:' in log:raise ValueError(log[-6000:])
print('Excluded unselected video/SPA/music/legacy NSS GUI package symlinks:',len(removed))
print('MF297D defconfig clean: no Kconfig dependency errors.')
