#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import plistlib
import shutil
import struct
import subprocess
import tarfile

from stage import ROOT, VENDOR, stage

PKG = 'com.ning.27tabbar'
VERSION = '0.2.27'
MIN_IOS = '16.0'
NAME = 'TheseusSystemTabs'
BUNDLE = NAME + 'Resources.bundle'
DYNAMIC = 'Library/MobileSubstrate/DynamicLibraries'
SDK_TOOL = ['xcrun', '--sdk', 'iphoneos']


def run(*args, capture=False):
    cmd = list(map(str, args))
    print('+', ' '.join(cmd), flush=True)
    result = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def parent_directories(entries):
    directories = {''}
    for name in entries:
        parts = name.split('/')
        if any(part in ('', '.', '..') for part in parts):
            raise ValueError('Invalid archive path: ' + name)
        directories.update('/'.join(parts[:index]) for index in range(1, len(parts)))
    if directories.intersection(entries):
        raise ValueError('Archive file used as a parent directory')
    return sorted(directories, key=lambda name: (name.count('/') + bool(name), name))


def verify_tar_layout(members, expected):
    seen, files = set(), set()
    for entry in members:
        assert entry.name == '.' or entry.name.startswith('./')
        name = '' if entry.name == '.' else entry.name[2:].rstrip('/')
        assert (entry.uid, entry.gid) == (0, 0)
        if entry.isdir():
            assert name not in seen and entry.mode == 0o755
            if name:
                assert name.rpartition('/')[0] in seen, name
            seen.add(name)
        else:
            assert entry.isfile() and name in expected and name not in files
            assert name.rpartition('/')[0] in seen, name
            files.add(name)
    assert seen == set(parent_directories(expected))
    assert files == set(expected)


def tar_gz(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for directory in parent_directories(entries):
            info = tarfile.TarInfo('./' + directory if directory else '.')
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.mtime = 0
            info.uname = info.gname = 'root'
            tar.addfile(info)
        for name, (data, mode) in sorted(entries.items()):
            info = tarfile.TarInfo('./' + name)
            info.size = len(data)
            info.mode = mode
            info.mtime = 0
            info.uname = info.gname = 'root'
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(output.getvalue(), compresslevel=9, mtime=0)


def ar_pack(entries):
    output = bytearray(b'!<arch>\n')
    for name, data in entries:
        header = f'{name + "/":16s}{0:<12d}{0:<6d}{0:<6d}{0o100644:<8o}{len(data):<10d}`\n'.encode('ascii')
        assert len(header) == 60
        output.extend(header)
        output.extend(data)
        if len(data) & 1:
            output.extend(b'\n')
    return bytes(output)


def make_deb(dylib, metal, arch):
    roothide = arch == 'arm64e'
    package_arch = 'iphoneos-' + arch
    base = ('' if roothide else 'var/jb/') + DYNAMIC
    info = {'CFBundleIdentifier': PKG + '.resources', 'CFBundleName': NAME + 'Resources',
            'CFBundlePackageType': 'BNDL', 'CFBundleVersion': VERSION, 'MinimumOSVersion': MIN_IOS}
    filter_plist = plistlib.dumps({'Filter': {'Bundles': ['com.apple.UIKit']}})
    payload = {base+'/'+NAME+'.dylib': (dylib, 0o755), base+'/'+NAME+'.plist': (filter_plist, 0o644),
               base+'/'+BUNDLE+'/default.metallib': (metal, 0o644),
               base+'/'+BUNDLE+'/Info.plist': (plistlib.dumps(info), 0o644)}
    for notice in ('LICENSE', 'NOTICE'):
        payload[base+'/'+BUNDLE+'/'+notice] = ((VENDOR/notice).read_bytes(), 0o644)
    size = (sum(len(data) for data, _ in payload.values()) + 1023) // 1024
    control = (f'Package: {PKG}\nName: 27TabBar\nVersion: {VERSION}\nArchitecture: {package_arch}\n'
               f'Depends: firmware (>= {MIN_IOS}), mobilesubstrate\nSection: Tweaks\n'
               'Conflicts: com.ning.theseussystemtabs\nReplaces: com.ning.theseussystemtabs\n'
               f'Maintainer: Ning\nAuthor: Ning\nInstalled-Size: {size}\n'
               'Description: 为标准 UIKit 标签栏接入 Theseus 浮动玻璃与拖动透镜。\n').encode()
    return ar_pack([('debian-binary', b'2.0\n'), ('control.tar.gz', tar_gz({'control': (control, 0o644)})),
                    ('data.tar.gz', tar_gz(payload))]), payload


def signed_macho(data, arch, install_name):
    magic, cpu, subtype, kind, count, size, _, _ = struct.unpack_from('<8I', data)
    assert magic == 0xFEEDFACF and cpu == 0x0100000C and kind == 6
    assert subtype == (0x80000002 if arch == 'arm64e' else 0), hex(subtype)
    p, seen = 32, set()
    for _ in range(count):
        cmd, length = struct.unpack_from('<2I', data, p)
        assert 8 <= length <= 32 + size - p
        if cmd == 0x32:
            assert struct.unpack_from('<2I', data, p + 8) == (2, 16 << 16)
            seen.add('ios16')
        if cmd == 0xD:
            offset = struct.unpack_from('<I', data, p + 8)[0]
            assert data[p+offset:p+length].split(b'\0', 1)[0].decode() == install_name
            seen.add('id')
        if cmd == 0x1D:
            offset, n = struct.unpack_from('<2I', data, p+8)
            assert offset + n <= len(data) and data[offset:offset+4] == b'\xfa\xde\x0c\xc0'
            seen.add('sign')
        p += length
    assert p == 32 + size and seen == {'ios16', 'id', 'sign'}, seen
    assert b'NGSystemTabsBridge' in data and b'TheseusTabBar' in data


def verify_deb(path, expected, arch, install_name, directory):
    path = Path(path)
    b = path.read_bytes()
    assert b.startswith(b'!<arch>\n')
    pos, members = 8, {}
    while pos < len(b):
        h = b[pos:pos+60]
        assert len(h) == 60 and h[-2:] == b'`\n'
        name = h[:16].decode().strip().removesuffix('/')
        n = int(h[48:58])
        assert name not in members and pos+60+n <= len(b)
        members[name] = b[pos+60:pos+60+n]
        pos += 60+n+(n&1)
    assert pos == len(b) and list(members) == ['debian-binary','control.tar.gz','data.tar.gz']
    assert members['debian-binary'] == b'2.0\n'
    with tarfile.open(fileobj=io.BytesIO(members['control.tar.gz']), mode='r:gz') as tar:
        verify_tar_layout(tar.getmembers(), {'control'})
        assert f'Architecture: iphoneos-{arch}\n'.encode() in tar.extractfile('./control').read()
    with tarfile.open(fileobj=io.BytesIO(members['data.tar.gz']), mode='r:gz') as tar:
        verify_tar_layout(tar.getmembers(), expected)
        for entry in tar:
            if entry.isdir():
                continue
            content, mode = expected[entry.name[2:]]
            assert tar.extractfile(entry).read() == content and entry.mode == mode
            if entry.name.endswith('.dylib'):
                signed_macho(content, arch, install_name)
                verified = directory/'verified.dylib'
                verified.write_bytes(content)
                run('codesign','--verify','--strict','--verbose=2',verified)
            if entry.name.endswith('.metallib'):
                assert len(content) > 8192 and content.startswith(b'MTLB')
    return {'package': path.name, 'architecture': 'iphoneos-'+arch, 'size': len(b),
            'sha256': hashlib.sha256(b).hexdigest(), 'minimum_ios': MIN_IOS, 'code_signature': 'strict'}


def build(arch, sdk):
    out = ROOT/'build'/arch
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    staged = out/'swift'
    stage(staged)
    target = f'{arch}-apple-ios{MIN_IOS}'
    prefix = '@loader_path/.jbroot/' if arch == 'arm64e' else '/var/jb/'
    install_name = prefix + DYNAMIC + '/' + NAME + '.dylib'
    host, dylib = out/'Host.o', out/(NAME+'.dylib')
    run(*SDK_TOOL, 'clang', '-target', target, '-isysroot', sdk, '-O2', '-fobjc-arc', '-fblocks',
        '-Wall', '-Wextra', '-Werror', '-c', ROOT/'Sources/Host.m', '-o', host)
    frameworks = [arg for n in ('UIKit','Foundation','Metal','MetalKit','QuartzCore','IOSurface','Accelerate','CoreGraphics') for arg in ('-framework',n)]
    run(*SDK_TOOL, 'swiftc', '-target', target, '-sdk', sdk, '-swift-version', '5', '-parse-as-library',
        '-O', '-whole-module-optimization', '-emit-library', '-module-name', NAME,
        '-module-cache-path', out/'ModuleCache', '-import-objc-header', ROOT/'Sources/Host.h',
        *sorted(staged.glob('*.swift')), *sorted((ROOT/'Sources').glob('*.swift')), host, *frameworks,
        '-Xlinker', '-install_name', '-Xlinker', install_name, '-o', dylib)
    shader = VENDOR/'Sources/Theseus/Shaders/TheseusShaders.metal'
    air, metal = out/'Theseus.air', out/'default.metallib'
    run(*SDK_TOOL, 'metal', '-target', f'air64-apple-ios{MIN_IOS}', '-isysroot', sdk,
        '-std=ios-metal2.4', '-O2', '-c', shader, '-o', air)
    run(*SDK_TOOL, 'metallib', air, '-o', metal)
    run('codesign','--force','--sign','-','--timestamp=none',dylib)
    packed, expected = make_deb(dylib.read_bytes(), metal.read_bytes(), arch)
    name = f'{PKG}_{VERSION}_iphoneos-{arch}.deb'
    temp = out/name
    temp.write_bytes(packed)
    receipt = verify_deb(temp, expected, arch, install_name, out)
    shutil.copyfile(temp, ROOT/'dist'/name)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--targets', choices=('roothide','rootless','both'), default='roothide')
    opt = parser.parse_args()
    if platform.system() != 'Darwin':
        raise SystemExit('Native build requires macOS with Xcode and the iPhoneOS Metal toolchain.')
    sdk = run(*SDK_TOOL,'--show-sdk-path',capture=True)
    (ROOT/'dist').mkdir(exist_ok=True)
    variants = {'roothide':['arm64e'], 'rootless':['arm64'], 'both':['arm64','arm64e']}[opt.targets]
    result = [build(arch, sdk) for arch in variants]
    (ROOT/'dist/verification.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
