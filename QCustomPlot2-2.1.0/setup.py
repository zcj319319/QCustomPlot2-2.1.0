#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import platform
import subprocess
import sys

import sipconfig

from distutils.core import DistutilsError
from distutils.ccompiler import CCompiler
from distutils.sysconfig import customize_compiler
from os.path import join, exists, abspath, dirname

from setuptools import setup, Extension

from sipdistutils import build_ext

from PyQt5.QtCore import PYQT_CONFIGURATION
from PyQt5.QtCore import QLibraryInfo

CPU_COUNT = os.cpu_count() if 'cpu_count' in dir(os) else 1 # number of parallel compilations

# monkey-patch for parallel compilation, see
# https://stackoverflow.com/questions/11013851/speeding-up-build-process-with-distutils
def parallelCCompile(self, sources, output_dir=None, macros=None, include_dirs=None, debug=0, extra_preargs=None, extra_postargs=None, depends=None):
    # those lines are copied from distutils.ccompiler.CCompiler directly
    macros, objects, extra_postargs, pp_opts, build = self._setup_compile(output_dir, macros, include_dirs, sources, depends, extra_postargs)
    cc_args = self._get_cc_args(pp_opts, debug, extra_preargs)
    # parallel code
    import multiprocessing.pool
    def _single_compile(obj):
        try: src, ext = build[obj]
        except KeyError: return
        self._compile(obj, src, ext, cc_args, extra_postargs, pp_opts)
    # convert to list, imap is evaluated on-demand
    list(multiprocessing.pool.ThreadPool(CPU_COUNT).imap(_single_compile,objects))
    return objects


WINDOWS_HOST = (platform.system() == 'Windows')
LINUX_HOST = (platform.system() == 'Linux')

# This is with Unix pathsep even on windows
QT_BINARIES = QLibraryInfo.location(QLibraryInfo.BinariesPath)
if WINDOWS_HOST:
    # Default to Qt's jom instead of MSVC nmake
    DEFAULT_MAKE = 'jom.exe'
    # Try to find qmake.exe in PATH
    pipe = subprocess.Popen('where qmake.exe', stdout=subprocess.PIPE)
    (stdout, stderr) = pipe.communicate()
    DEFAULT_QMAKE = str(stdout.strip(), 'utf8') if sys.version_info.major == 3 else str(stdout.strip())
    if DEFAULT_QMAKE == '':
        print('Unable to find qmake.exe. Please set the path manually using --qmake option.')
else:
    DEFAULT_MAKE = 'make'
    DEFAULT_QMAKE = '{}/{}'.format(QT_BINARIES, 'qmake')

DEFAULT_QT_INCLUDE = QLibraryInfo.location(QLibraryInfo.HeadersPath)
ROOT = abspath(dirname(__file__))
BUILD_DIR = os.getcwd()
BUILD_STATIC_DIR = join(ROOT, 'lib-static')

# Monkey-patch, see above
CCompiler.compile=parallelCCompile


with open(join(ROOT, 'README.md'), 'r') as fh:
    long_description = fh.read()


class MyBuilderExt(build_ext):
    user_options = build_ext.user_options[:]
    user_options += [
        ('qmake=', None, 'Path to qmake'),
        ('qt-include-dir=', None, 'Path to Qt headers'),
        ('qt-library-dir=', None, 'Path to Qt library dir (used at link time)'),
        ('make=', None, 'Path to make (either GNU make/nmake/jom)')
    ]

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.qmake = None
        self.qt_include_dir = None
        self.qt_library_dir = None
        self.make = None
        self.static_lib = None
        pyqt_sip_config = PYQT_CONFIGURATION['sip_flags']
        if self.sip_opts is None:
            self.sip_opts = pyqt_sip_config
        else:
            self.sip_opts += pyqt_sip_config

    def finalize_options(self):
        build_ext.finalize_options(self)
        if self.qmake is None:
            print('Setting qmake to \'%s\'' % DEFAULT_QMAKE)
            self.qmake = DEFAULT_QMAKE
        if self.make is None:
            print('Setting make to \'%s\'' % DEFAULT_MAKE)
            self.make = DEFAULT_MAKE
        if self.qt_include_dir is None:
            pipe = subprocess.Popen([self.qmake, '-query', 'QT_INSTALL_HEADERS'], stdout=subprocess.PIPE)
            (stdout, stderr) = pipe.communicate()
            self.qt_include_dir = str(stdout.strip(), 'utf8') if sys.version_info.major == 3 else str(stdout.strip())
            print('Setting Qt include dir to \'%s\'' % self.qt_include_dir)

        if self.qt_library_dir is None:
            pipe = subprocess.Popen([self.qmake, '-query', 'QT_INSTALL_LIBS'], stdout=subprocess.PIPE)
            (stdout, stderr) = pipe.communicate()
            self.qt_library_dir = str(stdout.strip(), 'utf8') if sys.version_info.major == 3 else str(stdout.strip())
            print('Setting Qt library dir to \'%s\'' % self.qt_library_dir)

        if not exists(self.qmake):
            raise DistutilsError('Could not determine valid qmake at %s' % self.qmake)

    def __build_qcustomplot_library(self):
        if WINDOWS_HOST:
            qcustomplot_static = join(BUILD_DIR, self.build_temp, 'release', 'qcustomplot.lib')
        else:
            qcustomplot_static = join(BUILD_DIR, self.build_temp, 'libqcustomplot.a')
        if exists(qcustomplot_static):
            return

        if sys.version_info.major == 3:
          os.makedirs(self.build_temp, exist_ok=True)
        else:
          os.makedirs(self.build_temp)
        os.chdir(self.build_temp)
        print('Make static qcustomplot library...')
        self.spawn([self.qmake, join(ROOT, 'QCustomPlot/src/qcp-staticlib.pro'), 'DESTDIR='])
        # AFAIK only nmake does not support -j option
        has_multiprocess = not(WINDOWS_HOST and 'nmake' in self.make)
        make_cmdline = [self.make]
        if has_multiprocess:
            make_cmdline.extend(['-j', str(CPU_COUNT)])
        self.spawn([self.make, '-j', str(CPU_COUNT)])

        os.chdir(BUILD_DIR)
        self.static_lib = qcustomplot_static
        # Possibly it's hack
        qcustomplot_ext = self.extensions[0]
        qcustomplot_ext.extra_objects = [qcustomplot_static]

    def build_extensions(self):
        customize_compiler(self.compiler)
        try:
            self.compiler.compiler_so.remove('-Wstrict-prototypes')
        except (AttributeError, ValueError):
            pass
        self.__build_qcustomplot_library()
        # Possibly it's hack
        qcustomplot_ext = self.extensions[0]
        qcustomplot_ext.include_dirs += [
            join(self.qt_include_dir, subdir)
            for subdir in ['.', 'QtCore', 'QtGui', 'QtWidgets', 'QtPrintSupport']
        ]
        qcustomplot_ext.library_dirs += [
            BUILD_DIR,
            self.build_temp,
            self.qt_library_dir
        ]

        qcustomplot_ext.libraries = [
            'Qt5Core',
            'Qt5Gui',
            'Qt5Widgets',
            'Qt5PrintSupport',
            'qcustomplot'
        ]

        if WINDOWS_HOST:
            qcustomplot_ext.library_dirs.append(join(self.build_temp, 'release'))
            qcustomplot_ext.libraries.append('Opengl32')

        build_ext.build_extensions(self)

    def _sip_sipfiles_dir(self):
        cfg = sipconfig.Configuration()
        return join(cfg.default_sip_dir, 'PyQt5')

setup(
    name='QCustomPlot2',
    version='2.1.0',
    description='QCustomPlot is a Qt widget for plotting and data visualization',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Dmitry Voronin, Giuseppe Corbelli, Christopher Gilbert, Sergey Salnikov',
    author_email='salsergey@gmail.com',
    url='https://osdn.net/users/salsergey/pf/QCustomPlot2-PyQt5',
    platforms=['Linux', 'Windows'],
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development :: User Interfaces'
    ],
    requires=[
        'sipconfig',
        'PyQt5'
    ],
    ext_modules=[
        Extension(
            'QCustomPlot2',
            [join(ROOT, 'sip/all.sip')],
            include_dirs=[ROOT, join(ROOT, 'sip')]
        ),
    ],
    cmdclass={'build_ext': MyBuilderExt}
)
