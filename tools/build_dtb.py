"""Compile a public DT template, requiring this unit's Ethernet MACs."""
import argparse, re, subprocess
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', choices=['native','recovery','maintenance','maintenance-env'], required=True)
    p.add_argument('--lan-mac',required=True)
    p.add_argument('--wan-mac',required=True)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    def mac(value):
        if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',value): raise ValueError('Invalid MAC syntax')
        b=bytes.fromhex(value.replace(':',''))
        if b[0]&1 or b in (b'\0'*6,b'\xff'*6): raise ValueError('Invalid unicast MAC')
        return '['+' '.join(f'{x:02x}' for x in b)+']'
    if a.lan_mac.lower()==a.wan_mac.lower(): raise ValueError('MACs must differ')
    root=Path(__file__).resolve().parents[1]
    source=(root/'dts'/f'mf297d-{a.variant}.dts').read_text()
    source=source.replace('[02 00 00 00 00 01]',mac(a.lan_mac)).replace('[02 00 00 00 00 02]',mac(a.wan_mac))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(a.out),'-'],input=source.encode(),check=True)
if __name__=='__main__': main()
