#!/usr/bin/env python3
"""Copy the validated MF297D host-TX tuning into an existing build tree."""
from pathlib import Path
import argparse, shutil, subprocess

def enable(tree):
    integration=Path(__file__).resolve().parents[1]
    source=integration/'overlay/files'
    ttl_package=integration/'overlay/package/luci-app-ttl'
    if not (ttl_package/'Makefile').is_file():
        raise SystemExit('Missing bundled luci-app-ttl sources. Update the complete MF297D checkout with git pull --ff-only, then retry. No build files were changed.')
    for rel in ('usr/sbin/mf297d-host-tx','etc/init.d/mf297d-host-tx','etc/uci-defaults/95-mf297d-host-tx','etc/uci-defaults/99-mf297d-luci-themes','etc/config/mf297d_tuning','etc/config/mf297d-ttl'):
        dest=tree/'files'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        if rel.startswith('etc/config/') and dest.exists():
            continue
        shutil.copyfile(source/rel,dest)
        dest.chmod(0o600 if rel.startswith('etc/config/') else 0o755)
        if not rel.startswith('etc/config/'):
            subprocess.run(['sh','-n',str(dest)],check=True)
    dest=tree/'files/etc/sysupgrade.conf'
    existing=dest.read_bytes().replace(b'\r\n',b'\n') if dest.exists() else b''
    lines=existing.splitlines()
    for line in (source/'etc/sysupgrade.conf').read_bytes().splitlines():
        if line not in lines:lines.append(line)
    dest.write_bytes(b'\n'.join(lines)+b'\n')
    package=tree/'package/mf297d-host-tso'
    shutil.copytree(integration/'packages/mf297d-host-tso',package,dirs_exist_ok=True)
    shutil.copyfile(integration/'src/host_tso.c',package/'src/host_tso.c')
    shutil.copytree(ttl_package,tree/'package/luci-app-ttl',dirs_exist_ok=True)
    config=tree/'.config'
    if config.exists():
        lines=config.read_text().splitlines()
        for name in ('kmod-mf297d-host-tso','luci-app-ttl'):
            lines=[s for s in lines if s not in ('# CONFIG_PACKAGE_'+name+' is not set','CONFIG_PACKAGE_'+name+'=m','CONFIG_PACKAGE_'+name+'=y')]
            lines.append('CONFIG_PACKAGE_'+name+'=y')
        config.write_bytes(('\n'.join(lines)+'\n').encode())
        subprocess.run(['make','defconfig'],cwd=tree,check=True)
    print('MF297D IPv4 host TX checksum tuning installed; existing tuning settings preserved.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);a=p.parse_args();enable(a.tree.resolve())
