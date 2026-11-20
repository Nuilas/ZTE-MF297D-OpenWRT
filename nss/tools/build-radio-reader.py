from pathlib import Path
import hashlib,json,os,re,shutil,subprocess,tarfile
import argparse
p=argparse.ArgumentParser();p.add_argument('--tree',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();W=a.tree.resolve();D=a.out.resolve();D.mkdir(parents=True,exist_ok=True);T=W/'mf297d/public-tools';T.mkdir(parents=True,exist_ok=True)
cc=W/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-gcc';prefix=str(cc).removesuffix('gcc')
env=dict(os.environ,PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',CC=str(cc),AR=prefix+'ar',RANLIB=prefix+'ranlib',STAGING_DIR=str(W/'staging_dir/target-aarch64_cortex-a53_musl'))
xz=T/'xz-5.8.4';log=(T/'build.log').open('wb')
if not xz.exists():
    with tarfile.open(W/'dl/xz-5.8.4.tar.bz2') as tar:tar.extractall(T,filter='data')
    subprocess.run(['./configure','--host=aarch64-openwrt-linux-musl','--prefix='+str(T/'prefix'),'--disable-shared','--enable-static','--disable-xz','--disable-xzdec','--disable-lzmadec','--disable-lzmainfo','--disable-doc','--disable-scripts','--disable-nls'],cwd=xz,env=env,check=True,stdout=log,stderr=subprocess.STDOUT)
subprocess.run(['make','-j8'],cwd=xz,env=env,check=True,stdout=log,stderr=subprocess.STDOUT)
subprocess.run(['make','install'],cwd=xz,env=env,check=True,stdout=log,stderr=subprocess.STDOUT)
src=T/'squashfs-tools'
if not src.exists():shutil.copytree(W/'build_dir/host/squashfs4-4.7.5/squashfs-tools',src,ignore=shutil.ignore_patterns('*.o','mksquashfs','unsquashfs','sqfscat','sqfstar','*.d'))
args=['make','-j8','CONFIG=1','CC='+str(cc),'GZIP_SUPPORT=0','LZO_SUPPORT=0','LZ4_SUPPORT=0','ZSTD_SUPPORT=0','XZ_SUPPORT=1','LZMA_XZ_SUPPORT=1','XZ_EXTENDED_OPTIONS=1','XATTR_SUPPORT=0','COMP_DEFAULT=xz','EXTRA_CFLAGS=-I'+str(T/'prefix/include'),'EXTRA_LDFLAGS=-static -L'+str(T/'prefix/lib'),'unsquashfs']
subprocess.run(args,cwd=src,env=env,check=True,stdout=log,stderr=subprocess.STDOUT);log.close()
shutil.copyfile(src/'unsquashfs',D/'unsquashfs-aarch64')
data=(D/'unsquashfs-aarch64').read_bytes();assert data[:4]==b'\x7fELF' and int.from_bytes(data[18:20],'little')==183
sources={n:hashlib.sha256((W/'dl'/n).read_bytes()).hexdigest() for n in ['xz-5.8.4.tar.bz2','squashfs4-4.7.5.tar.zst']}
(D/'reader-build.json').write_text(json.dumps({'sources':sources,'squashfs_commit':'708c59ae80853b0845017c33b42e56061cc546cd','binary_sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)},indent=2))
print('Static ARM64 SquashFS reader built:',len(data),'bytes.')
