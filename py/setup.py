import os
import re
import atexit
import shutil
import zipfile
import tempfile
import subprocess
from setuptools import setup, find_packages
from distutils.command.sdist import sdist


_version_re = re.compile(r'^version\s*=\s*"(.*?)"\s*$(?m)')


DEBUG_BUILD = os.environ.get('SYMBOLIC_DEBUG') == '1'

with open('README', 'rb') as f:
    readme = f.read()


if os.path.isfile('../Cargo.toml'):
    with open('../Cargo.toml') as f:
        version = _version_re.search(f.read()).group(1)
else:
    with open('version.txt') as f:
        version = f.readline().strip()


def vendor_rust_deps():
    subprocess.Popen(['git', 'archive', '--worktree-attributes',
                      '-o', 'py/rustsrc.zip', 'HEAD'], cwd='..').wait()


def write_version():
    with open('version.txt', 'wb') as f:
        f.write('%s\n' % version)


class CustomSDist(sdist):
    def run(self):
        vendor_rust_deps()
        write_version()
        sdist.run(self)


def build_native(spec):
    cmd = ['cargo', 'build']
    if not DEBUG_BUILD:
        cmd.append('--release')
        target = 'release'
    else:
        target = 'debug'

    # Step 0: find rust sources
    if os.path.isfile('rustsrc.zip'):
        scratchpad = tempfile.mkdtemp()
        @atexit.register
        def delete_scratchpad():
            shutil.rmtree(scratchpad)
        zf = zipfile.ZipFile('rustsrc.zip')
        zf.extractall(scratchpad)
        rust_path = scratchpad + '/cabi'
    else:
        rust_path = '../cabi'
        scratchpad = None

    # Step 1: build the rust library
    build = spec.add_external_build(
        cmd=cmd,
        path=rust_path
    )

    spec.add_cffi_module(
        module_path='symbolic._lowlevel',
        dylib=lambda: build.find_dylib('symbolic', in_path='target/%s' % target),
        header_filename=lambda: build.find_header('symbolic.h', in_path='include'),
        rtld_flags=['NOW', 'NODELETE']
    )


setup(
    name='symbolic',
    version=version,
    packages=find_packages(),
    author='Sentry',
    license='MIT',
    author_email='hello@sentry.io',
    description='A python library for dealing with symbol files and more.',
    long_description=readme,
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'milksnake',
    ],
    setup_requires=[
        'milksnake',
    ],
    milksnake_tasks=[
        build_native,
    ],
    cmdclass={
        'sdist': CustomSDist,
    }
)
