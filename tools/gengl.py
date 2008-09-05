#!/usr/bin/env python

'''Generate files in pyglet.gl and pyglet/GLU
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

import marshal
import optparse
import os.path
import urllib2
import sys
import textwrap

from wraptypes.wrap import CtypesWrapper

script_dir = os.path.abspath(os.path.dirname(__file__))

GLEXT_ABI_H = 'http://oss.sgi.com/projects/ogl-sample/ABI/glext.h'
GLEXT_NV_H = 'http://developer.download.nvidia.com/opengl/includes/glext.h'
GLXEXT_ABI_H = 'http://oss.sgi.com/projects/ogl-sample/ABI/glxext.h'
GLXEXT_NV_H = 'http://developer.download.nvidia.com/opengl/includes/glxext.h'
WGLEXT_ABI_H = 'http://oss.sgi.com/projects/ogl-sample/ABI/wglext.h'
WGLEXT_NV_H = 'http://developer.download.nvidia.com/opengl/includes/wglext.h'

AGL_H = '/System/Library/Frameworks/AGL.framework/Headers/agl.h'
GL_H = '/usr/include/GL/gl.h'
GLU_H = '/usr/include/GL/glu.h'
GLX_H = '/usr/include/GL/glx.h'
WGL_H = os.path.join(script_dir, 'wgl.h')

CACHE_FILE = os.path.join(script_dir, '.gengl.cache')
_cache = {}

def load_cache():
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            _cache = marshal.load(open(CACHE_FILE, 'rb')) or {}
        except:
            pass
    _cache = {}

def save_cache():
    try:
        marshal.dump(_cache, open(CACHE_FILE, 'wb'))
    except:
        pass

def read_url(url):
    if url in _cache:
        return _cache[url]
    if os.path.exists(url):
        data = open(url).read()
    else:
        data = urllib2.urlopen(url).read()
    _cache[url] = data
    save_cache()
    return data

class GLWrapper(CtypesWrapper):
    requires = None
    requires_prefix = None

    def __init__(self, header):
        self.header = header
        super(GLWrapper, self).__init__()

    def print_preamble(self):
        import time
        print >> self.file, textwrap.dedent("""
             # This content is generated by %(script)s.
             # Wrapper for %(header)s
        """ % {
            'header': self.header,
            'date': time.ctime(),
            'script': __file__,
        }).lstrip()

    def handle_ctypes_function(self, name, restype, argtypes, filename, lineno):
        if self.does_emit(name, filename):
            self.emit_type(restype)
            for a in argtypes:
                self.emit_type(a)

            self.all_names.append(name)
            print >> self.file, '# %s:%d' % (filename, lineno)
            print >> self.file, '%s = _link_function(%r, %s, [%s], %r)' % \
              (name, name, str(restype), 
               ', '.join([str(a) for a in argtypes]), self.requires)
            print >> self.file

    def handle_ifndef(self, name, filename, lineno):
        if self.requires_prefix and \
           name[:len(self.requires_prefix)] == self.requires_prefix:
            self.requires = name[len(self.requires_prefix):]
            print >> self.file, '# %s (%s:%d)'  % \
                (self.requires, filename, lineno)

def progress(msg):
    print >> sys.stderr, msg

marker_begin = '# BEGIN GENERATED CONTENT (do not edit below this line)\n'
marker_end = '# END GENERATED CONTENT (do not edit above this line)\n'

class ModuleWrapper(object):
    def __init__(self, header, filename,
                 prologue='', requires_prefix=None, system_header=None,
                 link_modules=()):
        self.header = header
        self.filename = filename
        self.prologue = prologue
        self.requires_prefix = requires_prefix
        self.system_header = system_header
        self.link_modules = link_modules

    def wrap(self, dir):
        progress('Updating %s...' % self.filename)
        source = read_url(self.header) 
        filename = os.path.join(dir, self.filename)

        prologue = []
        epilogue = []
        state = 'prologue'
        try:
            for line in open(filename):
                if state == 'prologue':
                    prologue.append(line)
                    if line == marker_begin:
                        state = 'generated'
                elif state == 'generated':
                    if line == marker_end:
                        state = 'epilogue'
                        epilogue.append(line)
                elif state == 'epilogue':
                    epilogue.append(line)
        except IOError:
            prologue = [marker_begin]
            epilogue = [marker_end]
            state = 'epilogue'
        if state != 'epilogue':
            raise Exception('File exists, but generated markers are corrupt '
                            'or missing')

        outfile = open(filename, 'w')
        print >> outfile, ''.join(prologue)
        wrapper = GLWrapper(self.header)
        if self.system_header:
            wrapper.preprocessor_parser.system_headers[self.system_header] = \
                source
        header_name = self.system_header or self.header
        wrapper.begin_output(outfile, 
                             library=None,
                             link_modules=self.link_modules,
                             emit_filenames=(header_name,))
        wrapper.requires_prefix = self.requires_prefix
        source = self.prologue + source
        wrapper.wrap(header_name, source)
        wrapper.end_output()
        print >> outfile, ''.join(epilogue)

modules = {
    'gl':  
        ModuleWrapper(GL_H, 'gl.py'),
    'glu': 
        ModuleWrapper(GLU_H, 'glu.py'),
    'glext_arb': 
        ModuleWrapper(GLEXT_ABI_H, 'glext_arb.py', 
            requires_prefix='GL_', system_header='GL/glext.h',
            prologue='#define GL_GLEXT_PROTOTYPES\n#include <GL/gl.h>\n'),
    'glext_nv': 
        ModuleWrapper(GLEXT_NV_H, 'glext_nv.py',
            requires_prefix='GL_', system_header='GL/glext.h',
            prologue='#define GL_GLEXT_PROTOTYPES\n#include <GL/gl.h>\n'),
    'glx': 
        ModuleWrapper(GLX_H, 'glx.py', 
            requires_prefix='GLX_',
            link_modules=('pyglet.libs.x11.xlib',)),
    'glxext_arb': 
        ModuleWrapper(GLXEXT_ABI_H, 'glxext_arb.py', requires_prefix='GLX_',
            system_header='GL/glxext.h',
            prologue='#define GLX_GLXEXT_PROTOTYPES\n#include <GL/glx.h>\n',
            link_modules=('pyglet.libs.x11.xlib',)),
    'glxext_nv': 
        ModuleWrapper(GLXEXT_NV_H, 'glxext_nv.py', requires_prefix='GLX_',
            system_header='GL/glxext.h',
            prologue='#define GLX_GLXEXT_PROTOTYPES\n#include <GL/glx.h>\n',
            link_modules=('pyglet.libs.x11.xlib',)),
    'agl':
        ModuleWrapper(AGL_H, 'agl.py'),
    'wgl':
        ModuleWrapper(WGL_H, 'wgl.py'),
    'wglext_arb':
        ModuleWrapper(WGLEXT_ABI_H, 'wglext_arb.py', requires_prefix='WGL_',
            prologue='#define WGL_WGLEXT_PROTOTYPES\n'\
                     '#include "%s"\n' % WGL_H.encode('string_escape')),
    'wglext_nv':
        ModuleWrapper(WGLEXT_NV_H, 'wglext_nv.py', requires_prefix='WGL_',
            prologue='#define WGL_WGLEXT_PROTOTYPES\n'\
                     '#include "%s"\n' % WGL_H.encode('string_escape')),
}


if __name__ == '__main__':
    op = optparse.OptionParser()
    op.add_option('-D', '--dir', dest='dir',
                  help='output directory')
    op.add_option('-r', '--refresh-cache', dest='refresh_cache',
                  help='clear cache first', action='store_true')
    options, args = op.parse_args()

    if not options.refresh_cache:
        load_cache()
    else:
        save_cache()

    if not args:
        print >> sys.stderr, 'Specify module(s) to generate:'
        print >> sys.stderr, '  %s' % ' '.join(modules.keys())

    if not options.dir:
        options.dir = os.path.join(script_dir, os.path.pardir, 'pyglet', 'gl')
    if not os.path.exists(options.dir):
        os.makedirs(options.dir)

    for arg in args:
        if arg not in modules:
            print >> sys.stderr, "Don't know how to make '%s'" % arg
            continue

        modules[arg].wrap(options.dir)

