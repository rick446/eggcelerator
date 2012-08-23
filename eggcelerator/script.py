import os
import sys
import socket
import subprocess
import logging
from ConfigParser import ConfigParser

from path import path
from pkg_resources import parse_requirements, Distribution, WorkingSet, get_build_platform
from setuptools.command.easy_install import PackageIndex, unpack_archive

LOCAL_CACHE='/home/vagrant/packages'

PI_LOCAL = PackageIndex(LOCAL_CACHE)
PI_PYPI = PackageIndex()

TMPDIR='/home/vagrant/build'

def main():
    requirements = []
    with open('requirements.txt') as fp:
        for line in fp:
            for req in parse_requirements(line):
                requirements.append(req)
    print 'Verify all requirements are downloaded locally'
    for req in requirements:
        ensure_cached_locally(req)
        ensure_compiled_as_bdist(req)
    print 'Done verifying local cache'

    # ws = build_working_set(requirements)

    print 'Verify all requirements are compiled to egg'
    for req in requirements:
        ensure_compiled_as_bdist(req)
    print 'Done verifying egg compilation'

def ensure_cached_locally(req):
    print req, '...',
    PI_LOCAL.find_packages(req)
    for dist in PI_LOCAL[req.key]:
        if dist.as_requirement() == req:
            print 'found.'
            break
    else:
        print 'not found.'
        download_req_to_local_cache(req)

def build_working_set(reqs):
    ws = WorkingSet()
    for req in reqs:
        PI_LOCAL.find_packages(req)
        dists = PI_LOCAL[req.key]
        for dist in dists:
            ws.add(dist)
    import pdb; pdb.set_trace()
    return ws

def ensure_compiled_as_bdist(req):
    print req, '...',
    PI_LOCAL.find_packages(req)
    dists = [ dist for dist in PI_LOCAL[req.key]
              if dist.as_requirement() == req ]
    bdists = [ dist for dist in dists
               if dist_is_binary(dist) ]
    assert dists, 'No distributions found for %s' % req
    if bdists:
        print 'found bdist: %s.' % bdists[0]
    if not bdists:
        bdists = compile_bdist(dists[0])
        print 'compiled bdist: %s.' % bdists[0]

def dist_is_binary(dist):
    return dist.py_version is not None

def compile_bdist(dist):
    build_dir = path(TMPDIR) / dist.project_name + '-' + dist.version
    if build_dir.exists():
        build_dir.rmtree()
    unpack_archive(dist.location, TMPDIR)
    dest_dir = path(LOCAL_CACHE) / dist.key
    result = []
    with build_dir:
        try:
            subprocess.check_output(
                [sys.executable, 'setup.py', 'bdist_egg'])
        except subprocess.CalledProcessError:
            really_i_want_an_egg()
        fns = (build_dir / 'dist').listdir()
        if len(fns) != 1:
            import pdb; pdb.set_trace()
        assert len(fns) == 1, (
            "Don't know what to do with multiple files in dist dir")
        pathname, ext = path(fns[0]).splitext()
        dest_fn = dest_dir / fns[0].basename()
        path(fns[0]).copy(dest_fn)
        result.append(dist.clone(
                location=dest_fn,
                platform=get_build_platform()))
    build_dir.rmtree()
    return result

def really_i_want_an_egg():
    '''Monkey-patch the setup.py to force use of setuptools'''
    path('setup.py').copy('setup-egg-inner.py')
    with open('setup.py', 'wb') as fp:
        fp.write('''
import distutils.core
import setuptools
distutils.core.setup = setuptools.setup
execfile('setup-egg-inner.py')
''')
    subprocess.check_output(
        [sys.executable, 'setup.py', 'bdist_egg'])

def download_req_to_local_cache(req):
    try:
        PI_PYPI.find_packages(req)
    except socket.timeout:
        print 'Socket timeout, may have missed some stuff'
        print PI_PYPI[req.key]
    for dist in PI_PYPI[req.key]:
        if dist.as_requirement() == req:
            dest = path(LOCAL_CACHE) / req.key
            if not dest.exists():
                dest.mkdir()
            PI_PYPI.download(req, dest)
            break
    else:
        assert False, "Requirement not found: %s" % req
        

if __name__ == '__main__':
    main()
