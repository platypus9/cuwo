from createdef import (FormattedOutput, comment_remover, parse_header,
                       struct_dict, get_mask_condition)
import os

CUR_DIR = os.path.dirname(__file__)
MASK_H = os.path.join(CUR_DIR, 'masked_read.h')
DEST_PXD = os.path.join(CUR_DIR, '..', 'cuwo', 'tgen_wrap.pxd')
DEST_PYX = os.path.join(CUR_DIR, '..', 'cuwo', 'tgen_wrap.pyx')
DEST_DEF = os.path.join(CUR_DIR, '..', 'terraingen', 'tgen2', 'src',
                        'tgendef.h')
SRC = os.path.join(CUR_DIR, 'tgen.h')

CYTHON_TYPES = {
    'int8': 'int8_t',
    'uint8': 'uint8_t',
    'int16': 'int16_t',
    'uint16': 'uint16_t',
    'int32': 'int32_t',
    'uint32': 'uint32_t',
    'int64': 'int64_t',
    'uint64': 'uint64_t'
}

VEC_TYPES = {
    'vec3': ('float', 'dtype_float32'),
    'ivec3': ('int32_t', 'dtype_int32'),
    'qvec3': ('int64_t', 'dtype_int64')
}

PYX_DEFS = '''
from cython cimport view
from libc.string cimport memset, memcpy, memcmp
from cuwo.vector import Vector3
from cuwo.common import filter_bytes
from cuwo import strings
from cuwo.bytes cimport ByteReader, ByteWriter
from cpython.mem cimport PyMem_Malloc, PyMem_Realloc, PyMem_Free
from cpython.ref cimport PyTypeObject, Py_INCREF
import numpy as np

cdef extern from "numpy/arrayobject.h":
    object PyArray_NewFromDescr(PyTypeObject * subtype, np.dtype descr,
                                int nd, np.npy_intp* dims,
                                np.npy_intp* strides, void* data, int flags,
                                object obj)

cdef np.dtype dtype_float32 = np.dtype(np.float32) 
cdef np.dtype dtype_int32 = np.dtype(np.int32)
cdef np.dtype dtype_int64 = np.dtype(np.int64)
cdef np.npy_intp vec3_dim = 3

np.import_array()

cdef class MemoryHolder:
    def __dealloc__(self):
        PyMem_Free(self.data)
'''

DEFS = '''
cimport numpy as np
import numpy as np
from cython.view cimport array as carray
from libc.stdint cimport (uintptr_t, uint32_t, uint8_t, uint64_t, int64_t,
                          int32_t, int8_t, int16_t, uint16_t)
from cpython.mem cimport PyMem_Malloc

ctypedef float vec3[3];
ctypedef int64_t qvec3[3];
ctypedef int32_t ivec3[3];

cdef class MemoryHolder:
    cdef void * data

    cdef inline void * alloc(self, uint32_t size):
        self.data = PyMem_Malloc(size)
        return self.data
'''

H_DEFS = '''
#include <stdint.h>

typedef float vec3[3];
typedef int64_t qvec3[3];
typedef int32_t ivec3[3];
'''

def get_wrapper(typ, dim=None, ptr=False):
    pass

def get_new(klass):
    return f'{klass}.__new__({klass})'

def main():
    pxd = FormattedOutput('tgen wrap')
    pyx = FormattedOutput('tgen wrap')

    pyx.putln(PYX_DEFS)

    pyx.putln()
    pyx.putln()
    tgendef = FormattedOutput(None)
    pxd.putln(DEFS)
    tgendef.putln('// Definitions (autogenerated)')
    tgendef.putln(H_DEFS)
    # pyx.putln(DEFS)
    for name in ('input.h', 'tgen.h'):
        with open(os.path.join(CUR_DIR, name), 'rU') as fp:
            text = comment_remover(fp.read())
        parse_header(text)

    array_gens = {}
    vec_gens = {}
    for s_name, s in struct_dict.items():
        if s.defs:
            for d in s.defs:
                name, val = d
                pyx.putln('%s = %s' % (name, val))
                if not name.endswith('_BIT'):
                    continue
                val = 1 << eval(val)
                name = '%s_FLAG' % name.replace('_BIT', '')
                pyx.putln('%s = %s' % (name, hex(val)))
            pyx.putln()
            pyx.putln()

        tgendef.putln(f'struct {s_name} // size {s.get_size()}')
        tgendef.putln(f'{{')
        tgendef.indent()

        pyx.putln(f'cdef class Wrap{s_name}:')
        pyx.indent()

        pyx.putln(f'def get_addr(self):')
        pyx.indent()
        pyx.putln(f'return <uintptr_t>self.data')
        pyx.dedent()

        pyx.putln(f'def __bytes__(self):')
        pyx.indent()
        pyx.putln(f'cdef bytes ret = (<char*>(self.data))'
                   '[:sizeof(self.data[0])]')
        pyx.putln('return ret')
        pyx.dedent()

        pyx.putln(f'def read(self, ByteReader reader):')
        pyx.indent()
        pyx.putln(f'reader.read_c(self.data, sizeof({s_name}))')
        pyx.dedent()

        pyx.putln(f'def write(self, ByteWriter writer):')
        pyx.indent()
        val = 'self.data[0]'
        pyx.putln(f'writer.write_c(self.data, sizeof({s_name}))')
        pyx.dedent()

        pyx.putln(f'def cast(self, object klass):')
        pyx.indent()
        pyx.putln(f'cdef Wrap{s_name} c = {get_new("klass")}')
        pyx.putln(f'c.holder = self.holder')
        pyx.putln(f'c._init_ptr(self.data)')
        pyx.putln(f'return c')
        pyx.dedent()

        pyx.putln(f'def copy(self):')
        pyx.indent()
        wrap_name = main_wrap_name = f'Wrap{s_name}'
        pyx.putln(f'cdef {wrap_name} inst = {get_new(wrap_name)}')
        pyx.putln(f'inst.alloc()')
        pyx.putln(f'memcpy(inst.data, self.data, sizeof({s_name}))')
        pyx.putln(f'return inst')
        pyx.dedent()

        pyx.putln(f'def __init__(self):')
        pyx.indent()
        pyx.putln(f'self.alloc()')
        pyx.putln()
        pyx.dedent()

        for copy in (True, False):
            if copy:
                postfix = '_copy'
            else:
                postfix = '_reset'
            pyx.putln(f'def make_standalone{postfix}(self):')
            pyx.indent()
            pyx.putln('if self.holder is not None:')
            pyx.indent()
            if not copy:
                pyx.putln(f'memset(self.data, 0, sizeof({s_name}))')
            pyx.putln('return')
            pyx.dedent()
            pyx.putln(f'cdef {s_name} * old_data = self.data')
            pyx.putln(f'self.realloc()')
            if copy:
                pyx.putln(f'memcpy(self.data, old_data, sizeof({s_name}))')
            else:
                pyx.putln(f'memset(self.data, 0, sizeof({s_name}))')
            pyx.dedent()

        pyx.putln(f'cdef void realloc(self):')
        pyx.indent()
        pyx.putln(f'self.holder = {get_new("MemoryHolder")}')
        pyx.putln(f'cdef void * buf = self.holder.alloc(sizeof({s_name}))')
        pyx.putln(f'self._set_ptr(<{s_name}*>buf)')
        pyx.dedent()

        pyx.putln(f'cdef void alloc(self):')
        pyx.indent()
        pyx.putln(f'self.holder = {get_new("MemoryHolder")}')
        pyx.putln(f'cdef void * buf = self.holder.alloc(sizeof({s_name}))')
        pyx.putln(f'self._init_ptr(<{s_name}*>buf)')
        pyx.dedent()

        pxd.putln(f'cdef struct {s_name}:')
        pxd.indent()

        reset_f = FormattedOutput(None)
        reset_f.putln(f'def reset(self):')
        reset_f.indent()
        reset_f.putln(f'memset(self.data, 0, sizeof(self.data[0]))')

        python_obj_pxd = FormattedOutput(None)
        python_obj_init = FormattedOutput(None)
        python_obj_reset = FormattedOutput(None)

        done_attr = set()

        for attr_i, attr in enumerate(s.attrs):
            # pxd
            attr_typ = CYTHON_TYPES.get(attr.typ, attr.typ)
            attr_s = attr_typ
            if attr.ptr:
                attr_s = 'uint32_t'
            name = attr.name
            if name == 'pad':
                name += str(attr_i)
            attr_s += f' {name}'
            if attr.dim is not None:
                attr_s += f'[{attr.dim}]'
            pxd.putln(attr_s)
            tgendef.putln(attr_s + ';')

            if attr.name in done_attr:
                continue

            is_vec = False
            prop_name = name
            if (attr.name.endswith('_start') and
                    s.attrs[attr_i+1].name.endswith('_end') and 
                    s.attrs[attr_i+2].name.endswith('_capacity')):
                is_vec = True
                vec_type = attr.typ
                if not attr.ptr:
                    vec_type = 'uint8'
                if is_vec:
                    prop_name = prop_name.replace('_start', '')
                    name2 = s.attrs[attr_i+1].name
                    name3 = s.attrs[attr_i+2].name
                    done_attr.add(name2)
                    done_attr.add(name3)

            # pyx
            if attr.name == 'pad':
                continue

            pyx.putln(f'@property')
            value = f'self.data[0].{name}'
            pyx.putln(f'def {prop_name}(self):')
            pyx.indent()

            if attr.default:
                reset_f.putln(f'{value} = {attr.default}')

            setter = FormattedOutput(None)
            setter.putln(f'@{prop_name}.setter')
            setter.putln(f'def {prop_name}(self, value):')
            setter.indent()
            if attr.name == 'name':
                pyx.putln(f'cdef int i = 0')
                pyx.putln(f'while i < 16:')
                pyx.indent()
                pyx.putln(f'if {value}[i] == 0: break')
                pyx.putln('i += 1')
                pyx.dedent()
                pyx.putln(f'return filter_bytes({value}[:i])')

                setter.putln(f'cdef str v = value')
                setter.putln(f"cdef bytes vv = "
                             f"v.encode('ascii', 'ignore')[:16]")
                setter.putln(f'cdef const char * c = vv')
                setter.putln(f'cdef size_t size = len(vv)')
                setter.putln(f'cdef int i')
                setter.putln(f'for i in range(16):')
                setter.indent()
                setter.putln(f'if i >= size:')
                setter.indent()
                setter.putln(f'{value}[i] = 0')
                setter.dedent()
                setter.putln('else:')
                setter.indent()
                setter.putln(f'{value}[i] = c[i]')
                setter.dedent()
                setter.dedent()

            elif is_vec:
                vec_name = vec_type.replace(' ', '').replace('*', 'Ptr')
                wrap_name = f'Wrap{vec_name}Vec'
                vec_gens[vec_type] = wrap_name

                setter.putln(f'raise NotImplementedError()')

                python_obj_pxd.putln(f'cdef {wrap_name} _{prop_name}')

                pyx.putln(f'if self._{prop_name} is not None:')
                pyx.indent()
                pyx.putln(f'return self._{prop_name}')
                pyx.dedent()

                pyx.putln(f'self._{prop_name} = {get_new(wrap_name)}')
                pyx.putln(f'self._{prop_name}.holder = self.holder')
                pyx.putln(f'self._{prop_name}._init_ptr(&{value})')
                pyx.putln(f'return self._{prop_name}')

                python_obj_reset.putln(f'if self._{prop_name} is not None:')
                python_obj_reset.indent()
                python_obj_reset.putln(f'self._{prop_name}.holder = '
                                        'self.holder')
                python_obj_reset.putln(f'self._{prop_name}._set_ptr(&{value})')
                python_obj_reset.dedent()
            elif attr.typ in VEC_TYPES and not attr.ptr:
                typt, typ = VEC_TYPES[attr.typ]

                python_obj_pxd.putln(f'cdef np.ndarray '
                                     f'_{prop_name}')

                pyx.putln(f'if self._{prop_name} is not None:')
                pyx.indent()
                pyx.putln(f'return self._{prop_name}')
                pyx.dedent()

                pyx.putln(f'Py_INCREF({typ})')
                pyx.putln(f'cdef {typt} * {prop_name}ptr = &{value}[0]')
                pyx.putln(f'self._{prop_name} = '
                    f'PyArray_NewFromDescr(<PyTypeObject *>Vector3, '
                    f'{typ}, 1, '
                    f'&vec3_dim, NULL, <void*>{prop_name}ptr, np.NPY_DEFAULT, '
                    f'<object>NULL);')
                pyx.putln(f'np.set_array_base(self._{prop_name}, self.holder)')
                pyx.putln(f'return self._{prop_name}')

                python_obj_reset.putln(f'if self._{prop_name} is not None:')
                python_obj_reset.indent()
                python_obj_reset.putln(f'np.set_array_base(self._{prop_name}, '
                                       f'self.holder)')
                python_obj_reset.putln(f'self._{prop_name}.data = '
                                       f'<char*>&{value}')
                python_obj_reset.dedent()
                setter.putln(f'{value} = <{typt}[3]>value')
            elif not attr.is_local() and not attr.ptr:
                ret_type = CYTHON_TYPES.get(attr.typ, attr.typ)
                ret_type_p = ret_type
                ret_type_c = ret_type
                if attr.dim is not None:
                    ret_type_p += f'[:{attr.dim}]'
                    ret_type_c += f'[:{attr.dim}]'
                    python_obj_pxd.putln(f'cdef carray _{prop_name}')

                    pyx.putln(f'if self._{prop_name} is not None:')
                    pyx.indent()
                    pyx.putln(f'return self._{prop_name}')
                    pyx.dedent()

                    pyx.putln(f'self._{prop_name} = '
                              f'<{ret_type_c}>(&{value}[0])')
                    pyx.putln(f'return self._{prop_name}')

                    python_obj_reset.putln(f'if self._{prop_name} is not None:')
                    python_obj_reset.indent()
                    python_obj_reset.putln(f'self._{prop_name}.data = '
                                           f'<char*>(&{value}[0])')
                    python_obj_reset.dedent()
                    setter.putln(f'raise NotImplementedError()')
                else:
                    pyx.putln(f'return {value}')
                    setter.putln(f'{value} = value')
            elif attr.ptr or attr.dim is not None:
                if attr.ptr:
                    pyx.putln(f'if {value} == 0:')
                    pyx.indent()
                    pyx.putln('return None')
                    pyx.dedent()
                    value = f'(<{attr_typ}*>{value})'

                typ = attr.typ
                value = f'&{value}[0]'
                k = (typ, attr.dim)
                if k in array_gens:
                    wrap_name = array_gens[k]
                else:
                    wrap_name = f'WrapArray{len(array_gens)}'
                    array_gens[k] = wrap_name

                python_obj_pxd.putln(f'cdef {wrap_name} _{prop_name}')
                pyx.putln(f'if self._{prop_name} is not None:')
                pyx.indent()
                pyx.putln(f'return self._{prop_name}')
                pyx.dedent()

                pyx.putln(f'self._{prop_name} = {get_new(wrap_name)}')
                pyx.putln(f'self._{prop_name}.holder = self.holder')
                pyx.putln(f'self._{prop_name}._init_ptr({value})')
                pyx.putln(f'return self._{prop_name}')

                python_obj_reset.putln(f'if self._{prop_name} is not None:')
                python_obj_reset.indent()
                python_obj_reset.putln(f'self._{prop_name}.holder = '
                                        'self.holder')
                python_obj_reset.putln(f'self._{prop_name}._set_ptr({value})')
                python_obj_reset.dedent()
                # if attr.ptr:
                #     setter.putln(f'cdef {wrap_name} v = value')
                #     setter.putln(f'{value} = v.array')
                # else:
                setter.putln(f'raise NotImplementedError()')
            elif attr.is_local():
                wrap_name = f'Wrap{attr.typ}'

                pyx.putln(f'if self._{prop_name} is not None:')
                pyx.indent()
                pyx.putln(f'return self._{prop_name}')
                pyx.dedent()

                python_obj_pxd.putln(f'cdef {wrap_name} _{prop_name}')
                pyx.putln(f'self._{prop_name} = {get_new(wrap_name)}')
                pyx.putln(f'self._{prop_name}.holder = self.holder')
                pyx.putln(f'self._{prop_name}._init_ptr(&{value})')
                pyx.putln(f'return self._{prop_name}')

                python_obj_reset.putln(f'if self._{prop_name} is not None:')
                python_obj_reset.indent()
                python_obj_reset.putln(f'self._{prop_name}.holder = '
                                        'self.holder')
                python_obj_reset.putln(f'self._{prop_name}._set_ptr(&{value})')
                python_obj_reset.dedent()
                setter.putln(f'cdef {wrap_name} v = value')
                setter.putln(f'{value} = v.data[0]')
            else:
                raise NotImplementedError()
            pyx.dedent()

            pyx.putcode(setter)

        # end of struct
        pxd.dedent()
        pxd.putln('')

        # write cdef class
        pxd.putln(f'cdef class Wrap{s_name}:')
        pxd.indent()
        pxd.putln(f'cdef void alloc(self)')
        pxd.putln(f'cdef void realloc(self)')
        pxd.putln(f'cdef void _init_ptr(self, {s_name} * ptr)')
        pxd.putln(f'cdef void _set_ptr(self, {s_name} * ptr)')
        pxd.putln(f'cdef {s_name} * data')
        pxd.putln(f'cdef MemoryHolder holder')
        pxd.putcode(python_obj_pxd)
        pxd.dedent()

        pyx.putcode(reset_f)

        pyx.putln(f'cdef void _init_ptr(self, {s_name} * ptr):')
        pyx.indent()
        pyx.putln('self.data = ptr')
        pyx.putcode(python_obj_init)
        pyx.dedent()

        pyx.putln(f'cdef void _set_ptr(self, {s_name} * ptr):')
        pyx.indent()
        pyx.putln('self.data = ptr')
        pyx.putcode(python_obj_reset)
        pyx.dedent()

        pyx.putln(f'def set_ptr(self, {main_wrap_name} v):')
        pyx.indent()
        pyx.putln(f'self.holder = v.holder')
        pyx.putln(f'self._set_ptr(v.data)')
        pyx.dedent()

        if s_name == 'EntityData':
            # setters
            bits = {}

            for d in s.defs:
                orig_name, value = d
                if not orig_name.endswith('_BIT'):
                    continue
                value = int(value)
                name = orig_name[:-4].lower()
                bits[value] = name

            for index in sorted(bits):
                name = bits[index]

        elif s_name == 'AppearanceData':
            for attr in s.attrs:
                if attr.name.endswith('_model'):
                    name = attr.name.split('_')[0]

                    pyx.putln()

                    pyx.putln('def get_%s(self):' % name)
                    pyx.indent()
                    pyx.putln('return strings.MODEL_NAMES[self.data[0].%s]'
                              % attr.name)
                    pyx.dedent()

                    pyx.putln()

                    pyx.putln('def set_%s(self, name):' % name)
                    pyx.indent()
                    pyx.putln('self.data[0].%s = strings.MODEL_IDS[name]'
                              % attr.name)
                    pyx.dedent()

        pyx.dedent()

        tgendef.dedent()
        tgendef.putln('};')

        tgendef.putln(f'static_assert(sizeof({s_name}) == {s.get_size()},')
        tgendef.putln(f'              "Invalid size for {s_name}");')

    for (typ, max_index), name in array_gens.items():
        pyx.putln(f'cdef class {name}:')
        pyx.indent()

        c_typ = CYTHON_TYPES.get(typ, typ)
        is_basic = c_typ in CYTHON_TYPES.values()
        use_arr = not is_basic and max_index is not None
        wrap_name = f'Wrap{typ}'
        pxd.putln(f'cdef class {name}:')
        pxd.indent()
        pxd.putln(f'cdef MemoryHolder holder')
        if use_arr:
            for i in range(max_index):
                pxd.putln(f'cdef {wrap_name} _data{i}')
        else:
            pxd.putln(f'cdef {c_typ} * data')
        pxd.putln(f'cdef void _init_ptr(self, {c_typ} * ptr)')
        pxd.putln(f'cdef void _set_ptr(self, {c_typ} * ptr)')
        pxd.dedent()

        init = FormattedOutput(None)
        reset = FormattedOutput(None)

        pyx.putln(f'def __getitem__(self, uint32_t index):')
        pyx.indent()
        if max_index is not None:
            pyx.putln(f'if index >= {max_index}: raise IndexError()')
        if c_typ in CYTHON_TYPES.values():
            pyx.putln('return self.data[index]')
        elif use_arr:
            for i in range(max_index):
                init.putln(f'self._data{i} = {get_new(wrap_name)}')
                init.putln(f'self._data{i}.holder = self.holder')
                init.putln(f'self._data{i}._init_ptr(&ptr[{i}])')
                reset.putln(f'self._data{i}._set_ptr(&ptr[{i}])')
                pyx.putln(f'if index == {i}: return self._data{i}')
        else:
            pyx.putln(f'cdef {wrap_name} ret = {get_new(wrap_name)}')
            pyx.putln(f'ret.holder = self.holder')
            pyx.putln(f'ret._init_ptr(&self.data[index])')
            pyx.putln(f'return ret')
        pyx.dedent()

        pyx.putln(f'cdef void _init_ptr(self, {c_typ} * ptr):')
        pyx.indent()
        if not use_arr:
            pyx.putln(f'self.data = ptr')
        pyx.putcode(init)
        pyx.dedent()

        pyx.putln(f'cdef void _set_ptr(self, {c_typ} * ptr):')
        pyx.indent()
        if not use_arr:
            pyx.putln(f'self.data = ptr')
        pyx.putcode(reset)
        pyx.dedent()


        if max_index is not None:
            pyx.putln(f'def __len__(self):')
            pyx.indent()
            pyx.putln(f'return {max_index}')
            pyx.dedent()

        pyx.dedent()


    for typ, name in vec_gens.items():
        final_type = typ.replace(' ', '').replace('*', '')
        is_ptr = False
        if typ.endswith('*'):
            is_ptr = True
        pyx.putln(f'cdef class {name}:')
        pyx.indent()

        c_typ = CYTHON_TYPES.get(final_type, final_type)
        pxd.putln(f'cdef class {name}:')
        pxd.indent()
        pxd.putln(f'cdef uint32_t * data')
        pxd.putln(f'cdef MemoryHolder holder')
        pxd.putln(f'cdef void _init_ptr(self, uint32_t * ptr)')
        pxd.putln(f'cdef void _set_ptr(self, uint32_t * ptr)')
        pxd.dedent()

        pyx.putln(f'cdef void _init_ptr(self, uint32_t * ptr):')
        pyx.indent()
        pyx.putln('self.data = ptr')
        pyx.dedent()

        pyx.putln(f'cdef void _set_ptr(self, uint32_t * ptr):')
        pyx.indent()
        pyx.putln('self.data = ptr')
        pyx.dedent()

        pyx.putln('def get_data(self): return (self.data[0], '
                                              'self.data[1], '
                                              'self.data[2])')

        pyx.putln('def clear(self):')
        pyx.indent()
        pyx.putln(f'self.data[1] = self.data[0]')
        pyx.dedent()

        pyx.putln(f'def __getitem__(self, uint32_t index):')
        pyx.indent()

        def get_data(i):
            ret = f'self.data[{i}]'
            if is_ptr:
                ret = f'(<uint32_t*>{ret})[0]'
            return ret

        if is_ptr:
            size_type = 'uint32_t'
        else:
            size_type = c_typ

        pyx.putln(f'cdef char * val = <char*>self.data[0]')
        pyx.putln(f'cdef char * end = <char*>self.data[1]')
        pyx.putln(f'val += sizeof({size_type}) * index')
        pyx.putln(f'if val >= end: raise IndexError()')
        if is_ptr:
            pyx.putln(f'cdef {c_typ} * res = <{c_typ}*>(<uint32_t*>val)[0]')
        else:
            pyx.putln(f'cdef {c_typ} * res = <{c_typ}*>val')
        if c_typ in CYTHON_TYPES.values():
            pyx.putln('return res[0]')
        else:
            wrap_name = f'Wrap{final_type}'
            pyx.putln(f'cdef {wrap_name} ret = {get_new(wrap_name)}')
            pyx.putln(f'ret.holder = self.holder')
            pyx.putln(f'ret._init_ptr(&res[0])')
            pyx.putln(f'return ret')
        pyx.dedent()
        pyx.putln(f'def __len__(self):')
        pyx.indent()
        pyx.putln(f'cdef char * val = <char*>self.data[0]')
        pyx.putln(f'cdef char * end = <char*>self.data[1]')
        pyx.putln(f'return <uint32_t>(end - val) / sizeof({size_type})')
        pyx.dedent()

        pyx.dedent()

    # mask data
    mask_data = []
    mask_input = open(MASK_H, 'rb').read().decode('utf-8')
    mask_input = mask_input.splitlines()
    entity_struct = struct_dict['EntityData']
    for bit_index, line in enumerate(mask_input):
        start = line.find('read_') + 5
        end = line.find('_masked', start)
        size = int(line[start:end])
        attr_start = line.find('->')
        if attr_start == -1:
            attr = 'x'
        else:
            attr_end = line.find(');')
            attr = line[attr_start+2:attr_end]
        offset = 0
        for struct_attr in entity_struct.attrs:
            name, typ, dim, spec = struct_attr.get()
            if name == attr:
                break
            offset += 1
        else:
            print(attr)
            raise NotImplementedError()
        mask_data.append((offset, size))

    for index in sorted(bits):
        name = bits[index]
        func_name = 'is_%s_set' % name
        pyx.putln('cpdef inline bint %s(uint64_t mask):' % func_name)
        pyx.indent()
        pyx.putln('return %s' % get_mask_condition(index))
        pyx.dedent()
        pyx.putln()
        pyx.putln()

    # read masked data
    pyx.putln('cpdef uint64_t read_masked_data(WrapEntityData entity, '
              'ByteReader reader):')
    pyx.indent()
    pyx.putln('cdef bytes temp')
    pyx.putln('cdef char * tempc')
    pyx.putln('cdef uint64_t mask = reader.read_uint64()')

    for bit_index, v in enumerate(mask_data):
        offset, size = v
        pyx.putln('if %s:' % get_mask_condition(bit_index))
        pyx.indent()

        while size > 0:
            attr = entity_struct.attrs[offset]
            name, typ, dim, spec = attr.get()
            attr_size = attr.get_size()
            val = f'entity.data[0].{name}'
            pyx.putln(f'reader.read_c(&{val}, sizeof({val}))')

            size -= attr_size
            offset += 1
        if size != 0:
            raise NotImplementedError()
        pyx.dedent()
    pyx.putln()
    pyx.putln('return mask')
    pyx.dedent()
    pyx.putln()
    pyx.putln()

    # get masked size
    pyx.putln('cpdef unsigned int get_masked_size(uint64_t mask):')
    pyx.indent()
    pyx.putln('cdef unsigned int size = 0')
    for bit_index, v in enumerate(mask_data):
        offset, size = v
        pyx.putln('if %s:' % get_mask_condition(bit_index))
        pyx.indent()
        pyx.putln('size += %s' % size)
        pyx.dedent()
    pyx.putln('return size')
    pyx.dedent()
    pyx.putln()
    pyx.putln()

    # write masked data
    pyx.putln('cpdef write_masked_data(WrapEntityData entity, '
              'ByteWriter writer, '
              'uint64_t mask):')
    pyx.indent()
    pyx.putln('writer.write_uint64(mask)')
    pyx.putln('cdef bytes view')
    for bit_index, v in enumerate(mask_data):
        pyx.putln('if %s:' % get_mask_condition(bit_index))
        pyx.indent()
        offset, size = v

        while size > 0:
            attr = entity_struct.attrs[offset]
            name, typ, dim, spec = attr.get()
            attr_size = attr.get_size()
            val = f'entity.data[0].{name}'
            pyx.putln(f'writer.write_c(&{val}, sizeof({val}))')
            size -= attr_size
            offset += 1
        pyx.dedent()
    pyx.dedent()

    # get mask description
    pyx.putln('def get_mask_desc(uint64_t mask):')
    pyx.indent()
    pyx.putln('cdef dict ret = {}')
    for index in sorted(bits):
        name = bits[index]
        pyx.putln('if %s:' % get_mask_condition(index))
        pyx.indent()
        pyx.putln(f'ret[{index}] = "{name}"')
        pyx.dedent()
    pyx.putln('return ret')
    pyx.dedent()

    # get mask bits
    pyx.putln('cpdef uint64_t get_mask(WrapEntityData old_ent, '
                                      'WrapEntityData new_ent):')
    pyx.indent()
    pyx.putln('cdef uint64_t mask = 0')
    for bit_index, v in enumerate(mask_data):
        offset, size = v

        while size > 0:
            attr = entity_struct.attrs[offset]
            name, typ, dim, spec = attr.get()
            attr_size = attr.get_size()

            old_val = f'old_ent.data[0].{name}'
            new_val = f'new_ent.data[0].{name}'
            cond = f'memcmp(&{old_val}, &{new_val}, sizeof({old_val})) != 0'
            pyx.putln(f'mask |= <uint64_t>({cond}) << {bit_index}')

            size -= attr_size
            offset += 1
        if size != 0:
            raise NotImplementedError()
    pyx.putln('return mask')
    pyx.dedent()

    with open(DEST_PXD, 'wb') as fp:
        fp.write(pxd.get())

    with open(DEST_PYX, 'wb') as fp:
        fp.write(pyx.get())

    with open(DEST_DEF, 'wb') as fp:
        fp.write(tgendef.get())

if __name__ == '__main__':
    main()