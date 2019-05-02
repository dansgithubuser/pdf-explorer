from ._parser import Parser
from ._objects import Name, Ref, Stream

import copy
import pprint
import re
import string

def transform_typical(x):
    return repr(x)

def transform_ref(x):
    return '{} R'.format(x)

def transform_string(x):
    if any(i not in string.printable for i in x):
        x = ''.join('{:02X}'.format(ord(i)) for i in x)
        return '<{}>'.format(x)
    else:
        x = re.sub(r'([()\\])', r'\\\1', x)
        return '({})'.format(x)

def transform_dictionary(x):
    result = b'<<'
    for k, v in x.items():
        result += transform_typical(Name(k)).encode('utf-8') + b' ' + to_bytes(v) + b' '
    result += b'>>'
    return result

def transform_stream(x):
    result = transform_dictionary(x.dictionary)
    result += b'\nstream\n'
    result += x.stream
    result += b'\nendstream'
    return result

def transform_array(x):
    result = b'['
    for i in x:
        result += to_bytes(i) + b' '
    result += b']'
    return result

def transform_bool(x):
    return {True: 'true', False: 'false'}[x]

def transform_null(x):
    return 'null'

def to_bytes(object):
    result = {
        Name: transform_typical,
        Ref: transform_ref,
        int: transform_typical,
        float: transform_typical,
        str: transform_string,
        dict: transform_dictionary,
        Stream: transform_stream,
        list: transform_array,
        bool: transform_bool,
        None: transform_null,
    }[object.__class__](object)
    if type(result) == str: result = result.encode('utf-8')
    return result

class Xref:
    def __init__(self, offset, generation_number, keyword):
        assert keyword in 'nf'
        self.offset = offset
        self.generation_number = generation_number
        self.keyword = keyword

    def __repr__(self):
        return '{:010} {:05} {}'.format(
            self.offset,
            self.generation_number,
            self.keyword,
        )

class Trailer:
    def __init__(self, dictionary, startxref):
        self.dictionary = dictionary
        self.startxref = startxref

    def __repr__(self):
        return '{} startxref {}'.format(self.dictionary, self.startxref)

class Pdf:
    def __init__(self):
        self.header = []
        self.objects = {}
        self.xref = {}
        self.trailer = []

    def __repr__(self):
        return (
            '===== header =====\n'
            '{}\n'
            '\n'
            '===== objects =====\n'
            '{}\n'
            '\n'
            '===== xref =====\n'
            '{}\n'
            '\n'
            '===== trailer =====\n'
            '{}'
        ).format(self.header, pprint.pformat(self.objects), pprint.pformat(self.xref), pprint.pformat(self.trailer))

    def __getitem__(self, key):
        return self.objects(key)

    def load(self, file_name):
        with open(file_name, 'rb') as f: parser = Parser(f.read())
        # header
        self.header = parser.parse(r'%([^\n\r]*)')
        x = parser.parse(r'%([^\n\r]*)', allow_nonmatch=True, binary=True)
        if x: self.header.append(x[0])
        while parser.i < len(parser.content):
            # body
            while not parser.check('xref|startxref'):
                ref = Ref(parser.parse(r'\d+ \d+ obj'))
                self.objects[ref] = parser.parse_object()
                parser.parse('endobj')
            # XFA
            if parser.check('startxref'):
                raise Exception("sorry, this isn't actually a PDF, it looks to be XFA")
            # cross-reference table
            parser.parse('xref')
            while not parser.check('trailer'):
                object_number_i, objects = [int(i) for i in parser.parse(r'[^\n\r]*').split()]
                for i in range(objects):
                    offset, generation_number, keyword = parser.parse('(\d+) (\d+) ([fn])')
                    if object_number_i + i == 0: continue
                    self.xref[object_number_i + i] = Xref(int(offset), int(generation_number), keyword)
            # trailer
            parser.parse('trailer')
            dictionary = parser.parse_object()
            parser.parse('startxref')
            startxref = int(parser.parse('\d+'))
            self.trailer.append(Trailer(dictionary, startxref))
            parser.parse(r'%%EOF\s*')
        # return so we can use something like named constructor idiom
        return self

    def save(self, file_name):
        def fb(format, *args): return format.format(*args).encode('utf-8')
        with open(file_name, 'wb') as file:
            # header
            for i in self.header:
                file.write(b'%')
                if type(i) == str: i = i.encode('utf-8')
                file.write(i)
                file.write(b'\n')
            # body
            object_offsets = {}
            for k, v in self.objects.items():
                object_offsets[k] = file.tell()
                file.write(fb('{}', k))
                file.write(b' obj ')
                file.write(to_bytes(v))
                file.write(b' endobj\n')
            # cross-reference table
            startxref = file.tell()
            file.write(b'xref\n')
            file.write(b'0 1\n')
            file.write(fb('{}\n', Xref(0, 65535, 'f')))
            for k, v in sorted(self.xref.items()):
                file.write(fb('{} 1\n', k))
                xref = copy.copy(v)
                xref.offset = object_offsets[Ref(k, v.generation_number)]
                file.write(fb('{}\n', xref))
            # trailer
            file.write(b'trailer\n')
            dictionary = {
                k: v
                for k, v in self.trailer[-1].dictionary.items()
                if k != Name('Prev')
            }
            file.write(to_bytes(dictionary))
            file.write(fb('startxref {}\n', startxref))
            file.write(b'%%EOF\n')

    def root(self):
        return self.trailer[-1].dictionary['Root']

    def object(self, *args):
        return self.objects[Ref(*args)]
