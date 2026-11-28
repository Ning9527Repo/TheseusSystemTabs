#!/usr/bin/env python3
"""Run extracted production ObjC metadata/action/hook code with native Foundation stand-ins."""
from pathlib import Path
import os, subprocess, sys, tempfile, hashlib, json, re
ROOT=Path(__file__).resolve().parents[1]

def main():
    native=(ROOT/'Sources/WeChatHost.m').read_text()
    bridge=(ROOT/'Sources/WeChatBridge.swift').read_text()
    header=(ROOT/'Sources/WeChatHost.h').read_text().replace('#import <UIKit/UIKit.h>','')
    source=native[native.index('@implementation NGWeChatTabEntry'):]
    a=source.index('BOOL NGIsWeChatProcess(void) {'); b=source.index('static BOOL NGWCIsClass(',a)
    source=source[:a]+'BOOL NGIsWeChatProcess(void) { return YES; }\n\n'+source[b:]
    template=(ROOT/'tests/WeChatHostStandins.m').read_text()
    data=template.replace('// BODY_INSERTED_HERE',header+'\n'+source)
    assert '// BODY_INSERTED_HERE' not in data
    assert '*original' in source and 'if (*original) return YES;' in source
    assert 'models.count != 4' in source and 'NGWCOwner(bar, modern)' in source
    assert 'NGSystemTabIsCapturing() && [NGWeChatTabsBridge usesOverlay:bar]' in source
    assert 'bar.layer.mask = originalMask' in bridge
    assert 'if !glass.ngHostIsInteracting && !activationPending' in bridge
    assert 'NGWeChatActivateTab(bar, index)' in bridge
    assert 'states.removeObject(forKey: bar)' in bridge
    assert 'updating.contains(bar)' in bridge
    assert '0.2.31' in (ROOT/'tools/build.py').read_text()
    with tempfile.TemporaryDirectory(prefix='wechat-adapter-') as d:
        p=Path(d)/'main.m';p.write_text(data)
        if '--emit' in sys.argv:
            Path(sys.argv[sys.argv.index('--emit')+1]).write_text(data)
        else:
            out=Path(d)/'wechat-test'
            subprocess.run(['xcrun','clang','-fobjc-arc','-fblocks','-Wall','-Wextra','-Werror',
                '-I',str(ROOT/'tests'),str(p),'-framework','Foundation','-framework','CoreGraphics','-o',str(out)],check=True)
            subprocess.run([str(out)],check=True)
    print(json.dumps({'wechat_adapter_source_checks':True,'actual_production_host_extracted':True}))

if __name__=='__main__':main()
