"""Interpolation works on geometry, never blends artwork or resurrects actors."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Interpolation(unittest.TestCase):
    def test_subframes_identity_cuts_and_long_lists(self):
        source = r'''
#include "sh2_markvi.h"
#include <cassert>
int main() {
    using namespace sh2_markvi;
    const sprite a{128, 0, 1, 128, 1024, 0xff5000, 0x1234, 0x800, 0};
    sprite b=a; b.x=160; b.y=144; b.zoom=2048;
    for (unsigned n=1;n<=4;++n) {
        auto r=interpolate({a},{b},n,4);
        assert(r.size()==1 && r[0].x==128+n*8 && r[0].y==128+n*4 && r[0].zoom==1024+n*256);
        assert(r[0].attr==b.attr);
    }
    // Reordering and VRAM cache relocation do not change piece identity.
    sprite c=b; c.owner+=0x4c; c.x=190;
    b.attr=17;
    auto r=interpolate({a},{c,b},1,2);
    assert(r[0].x==190 && r[1].x==144 && r[1].attr==17);
    assert(interpolate({a},{},1,2).empty());
    assert(interpolate({}, {b}, 1,2)[0].x==160);
    // Object slot reuse with another handler, pose/LOD changes, palette/flip
    // changes and screen-coordinate wraps must snap, not leave ghost sprites.
    for (unsigned mode=0;mode<6;++mode) {
        sprite d=b;
        if(mode==0)++d.routine;
        if(mode==1)++d.descriptor;
        if(mode==2)++d.part;
        if(mode==3)d.attr^=0x800;
        if(mode==4)d.x=510;
        if(mode==5)d.size=0x100;
        assert(interpolate({a},{d},1,2)[0].x==d.x);
    }
    std::vector<sprite> old, now;
    for(unsigned i=0;i<1200;++i) {
        auto x=a,y=b; x.owner=y.owner=0xff0000+i*2;
        old.push_back(x);now.push_back(y);
    }
    r=interpolate(old,now,1,2);
    assert(r.size()==1200);
    for(auto &x:r)assert(x.x==144);
    assert(interpolate({a},{b},100,4)[0].x==160); // no extrapolation
    assert(interpolate({a},{b},1,0)[0].x==160);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'probe.cpp';p.write_text(source);binary=Path(tmp)/'probe'
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+[
                '-std=c++17','-Wall','-Wextra','-Werror','-I',str(ROOT/'src/markv'),str(p),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

if __name__=='__main__': unittest.main()
