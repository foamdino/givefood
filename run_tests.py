#!/usr/bin/env python
import importlib, os, sys
import nose

from givefood.boot import fix_path
fix_path(include_dev_libs_path=True)

def runtests():
    modnames = []
    dirs = set()
    for modname in sys.argv[1:]:
        modnames.append(modname)

        mod = importlib.import_module(modname)
        fname = mod.__file__
        dirs.add(os.path.dirname(fname))

    modnames = list(dirs) + modnames

    nose.run(argv=modnames)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "givefood.settings")

    runtests()
    
