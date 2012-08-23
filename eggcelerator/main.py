import os
import sys
import socket
import subprocess
import logging

from path import path
from pkg_resources import parse_requirements, Distribution, WorkingSet, get_build_platform
from setuptools.command.easy_install import PackageIndex, unpack_archive

log = logging.getLogger(__name__)

class Eggcelerator(object):

    def __init__(
        self, requirement=None, remote_package_index=None,
        local_cache=None, build_cache=None):
        self._requirement = requirement
        self._local_cache = path(local_cache).expand()
        self._build_cache = path(build_cache).expand()
        self._pi_remote = PackageIndex(remote_package_index)
        self._pi_local = PackageIndex(self._local_cache)

    def run_all(self):
        if not self._local_cache.exists():
            self._local_cache.makedirs()
        if not self._build_cache.exists():
            self._build_cache.makedirs()

        with open(self._requirement) as fp:
            requirements = list(parse_requirements(fp))

        log.debug('Generate a set of distributions to satisfy all reqs and their dependencies')
        dists = self.get_distributions(requirements)
        requirements = [ dist.as_requirement() for dist in dists ]

        log.info('Ensure packages are cached locally')
        for req in requirements:
            self.ensure_local_req(req)
        log.debug('done.')

        log.info('Ensure packages have binary eggs locally')
        for req in requirements:
            bdist = self.ensure_bdist(req)
            self.install_bdist(bdist)
        log.debug('done.')

        log.info('Cleanup build directories')
        self._build_cache.rmtree()

    def get_distributions(self, requirements):
        ws = WorkingSet()
        def find_dist(req):
            self._pi_local.find_packages(req)
            for dist in self._pi_local[req.key]:
                if dist in req: return dist
            self._pi_remote.find_packages(req)
            for dist in self._pi_remote[req.key]:
                if dist in req: return dist
        return ws.resolve(requirements, installer=find_dist)

    def ensure_local_req(self, req):
        log.debug('ensure local: %s', req)
        self._pi_local.find_packages(req)
        for dist in self._pi_local[req.key]:
            if dist in req:
                log.debug('Found %s to satisfy %s', dist.location, req)
                break
        else:
            self.download_req(req)

    def ensure_bdist(self, req):
        log.debug('ensure bdist: %s', req)
        self._pi_local.find_packages(req)
        dists = [ dist for dist in self._pi_local[req.key]
                  if dist in req ]
        bdists = [ dist for dist in dists
                   if dist.location.endswith('.egg')
                   and dist.platform in (None, get_build_platform()) ]
        assert dists, 'No distributions found for %s' % req
        if bdists:
            log.debug('Found bdist: %s', bdists[0].location)
        if not bdists:
            bdists = self.compile_bdist(dists[0])
            log.debug('Compiled bdist: %s', bdists[0].location)
        return bdists[0]

    def install_bdist(self, bdist):
        log.debug('easy_install -i %s %s', self._local_cache, bdist.location)
        subprocess.check_output(['easy_install', '-i', self._local_cache, bdist.location])

    def download_req(self, req):
        log.debug('Download %s', req)
        try:
            self._pi_remote.find_packages(req)
        except socket.timeout:
            log.warning(
                'Socket timeout looking up %s, may have missing packages', req)
        for dist in self._pi_remote[req.key]:
            if dist.as_requirement() == req:
                dest = self._local_cache / req.project_name
                if not dest.exists():
                    dest.mkdir()
                self._pi_remote.download(req, dest)
                break
        else:
            assert False, "Requirement not found: %s" % req

    def compile_bdist(self, dist):
        build_dir = self._build_cache / dist.project_name + '-' + dist.version
        if build_dir.exists():
            build_dir.rmtree()
            
        unpack_archive(dist.location, self._build_cache)
        dest_dir = self._local_cache / dist.project_name
        result = []
        self._build_an_egg(build_dir)
        fns = (build_dir / 'dist').listdir()
        assert len(fns) == 1, (
            "Don't know what to do with multiple files in the dist dir")
        pathname, ext = path(fns[0]).splitext()
        dest_fn = dest_dir / (fns[0]).basename()
        path(fns[0]).copy(dest_fn)
        result.append(dist.clone(
                location=dest_fn,
                platform=get_build_platform()))
        return result

    def _build_an_egg(self, build_dir):
        with build_dir:
            try:
                subprocess.check_output(
                    [sys.executable, 'setup.py', 'bdist_egg'])
            except subprocess.CalledProcessError:
                # Monkey-patch the setup.py to include setuptools instead of distutils
                path('setup.py').copy('setup-eggcelerator-inner.py')
                path('setup.py').write_text(
                    "import distutils.core\n"
                    "import setuptools\n"
                    "distutils.core.setup = setuptools.setup\n"
                    "execfile('setup-eggcelerator-inner.py')")
                subprocess.check_output(
                    [sys.executable, 'setup.py', 'bdist_egg'])
