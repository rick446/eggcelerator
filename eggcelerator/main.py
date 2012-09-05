import sys
import socket
import logging
from subprocess import Popen, CalledProcessError, PIPE, STDOUT

from path import path
from pkg_resources import parse_requirements, WorkingSet, get_build_platform
from setuptools.command.easy_install import PackageIndex, unpack_archive

log = logging.getLogger(__name__)

def check_call(cmd):
    proc = Popen(cmd, stderr=PIPE, stdin=PIPE)
    (dout, derr) = proc.communicate()
    if proc.returncode != 0:
        log.error('Error calling %s (rc=%d)', cmd, proc.returncode)
        log.error('Stdout follows:\n%s', dout)
        log.error('Stdout follows:\n%s', derr)
        raise CalledProcessError(proc.returncode, cmd)

class Eggcelerator(object):

    def __init__(
        self, requirement=None, remote_package_index=None,
        local_cache=None, build_cache=None,
        s3_cache=None, s3_config=None):
        if not s3_cache.endswith('/'): s3_cache += '/'

        self._requirement = requirement
        self._local_cache = path(local_cache).expand() + '/'
        self._build_cache = path(build_cache).expand()
        self._pi_remote = PackageIndex(remote_package_index)
        self._pi_local = PackageIndex(self._local_cache)
        self._s3_cache = s3_cache
        self._s3_config = path(s3_config).expand()

    def run_all(self):
        if not self._local_cache.exists():
            self._local_cache.makedirs()
        if not self._build_cache.exists():
            self._build_cache.makedirs()

        s3cmd = path(sys.prefix) / 'bin/s3cmd'

        if self._s3_cache:
            log.info('Initial sync with %s', self._s3_cache)
            cmd = [s3cmd, '-c', self._s3_config, 'sync',
                   self._s3_cache, self._local_cache ]
            log.debug('Command is %r', map(str, cmd))
            check_call(cmd)

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
            self.ensure_bdist(req)
            # bdist = self.ensure_bdist(req)
            # self.install_bdist(bdist)
        log.debug('done.')

        log.info('Cleanup build directories')
        self._build_cache.rmtree()

        if self._s3_cache:
            log.info('Final sync with %s', self._s3_cache)
            cmd = [s3cmd, '-c', self._s3_config, 'sync' ]
            cmd += self._local_cache.glob('*')
            cmd.append(self._s3_cache)
            log.debug('Command is %r', map(str, cmd))
            check_call(cmd)

    def get_distributions(self, requirements):
        ws = WorkingSet()
        remote_fetches = []
        def installer(req):
            dist = find_dist(req)
            if dist is None: return None
            self.install_dist(dist)
            return dist
        def find_dist(req):
            self._pi_local.find_packages(req)
            for dist in sorted(self._pi_local[req.key], key=lambda d: -d.precedence):
                if dist in req: return dist
            remote_fetches.append(req)
            self._pi_remote.find_packages(req)
            for dist in sorted(self._pi_remote[req.key], key=lambda d: -d.precedence):
                if dist in req: return dist
        result = ws.resolve(requirements, installer=installer)
        log.debug('Remote fetches:')
        for req in remote_fetches:
            log.debug('%s', req)
        return result

    def ensure_local_req(self, req):
        log.debug('ensure local: %s', req)
        self._pi_local.find_packages(req)
        for dist in sorted(self._pi_local[req.key], key=lambda d: -d.precedence):
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

    def install_dist(self, dist):
        log.info('Install %s', dist.location)
        cmd_local = [ sys.prefix + '/bin/easy_install',
                      '-i', self._local_cache, 
                      dist.location ]
        cmd_remote = [ sys.prefix + '/bin/easy_install',
                      dist.location ]
        log.debug('Command is %r', map(str, cmd_local))
        try:
            check_call(cmd_local)
        except CalledProcessError:
            log.exception('Error installing %s, retrying', dist.location)
            check_call(cmd_remote)

    def install_bdist(self, bdist):
        log.info('Install %s', bdist.location)
        cmd = [ sys.prefix + '/bin/easy_install',
                '-i', self._local_cache, bdist.location]
        log.debug('Command is %r', map(str, cmd))
        try:
            check_call(cmd)
        except CalledProcessError:
            log.exception('Error installing %s, retrying', bdist.location)
            check_call(cmd)

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
                check_call(
                    [sys.executable, 'setup.py', 'bdist_egg'])
            except CalledProcessError:
                # Monkey-patch the setup.py to include setuptools instead of distutils
                path('setup.py').copy('setup-eggcelerator-inner.py')
                path('setup.py').write_text(
                    "import distutils.core\n"
                    "import setuptools\n"
                    "distutils.core.setup = setuptools.setup\n"
                    "execfile('setup-eggcelerator-inner.py')")
                check_call(
                    [sys.executable, 'setup.py', 'bdist_egg'])

