#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install MF297D sysupgrade hooks into this port's existing source tree."""
from pathlib import Path
import argparse,shutil,subprocess
P=Path(__file__).resolve().parents[2]

def patch_platform(text):
    old='\tzte,mf297d)\n\t\techo "MF297D RAM lab: custom NAND/ENV updater is not implemented." >&2\n\t\treturn 1\n\t\t;;'
    for function,new in [('platform_check_image','mf297d_check_image'),('platform_do_upgrade','mf297d_do_upgrade')]:
        start=text.index(function+'() {');before=text[:start];section=text[start:]
        if old in section:section=section.replace(old,'\tzte,mf297d)\n\t\t'+new+' "$1"\n\t\t;;',1)
        assert new+' "$1"' in section,'Unrecognised platform hook: '+function
        text=before+section
    marker='# MF297D fixed-layout sysupgrade support'
    if marker not in text:
        needle="RAMFS_COPY_DATA='/etc/fw_env.config /var/lock/fw_printenv.lock'"
        assert needle in text
        text=text.replace(needle,needle+'\n\n'+marker+'\n. /lib/upgrade/mf297d.sh\nRAMFS_COPY_BIN="$RAMFS_COPY_BIN /usr/libexec/mf297d-upgrade-guard sha256sum jsonfilter mktemp"')
    return text

def enable(tree):
    platform=tree/'target/linux/qualcommax/ipq50xx/base-files/lib/upgrade/platform.sh'
    platform.write_bytes(patch_platform(platform.read_text()).encode());subprocess.run(['sh','-n',str(platform)],check=True)
    dest=tree/'files/lib/upgrade/mf297d.sh';dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(P/'nss/overlay/files/lib/upgrade/mf297d.sh',dest);dest.chmod(0o644)
    version=tree/'files/etc/mf297d-sysupgrade-version';version.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(P/'nss/overlay/files/etc/mf297d-sysupgrade-version',version)
    subprocess.run(['sh','-n',str(dest)],check=True)
    print('MF297D sysupgrade source hooks installed. Runtime requires the one-time FIT boot migration.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);a=p.parse_args();enable(a.tree.resolve())
