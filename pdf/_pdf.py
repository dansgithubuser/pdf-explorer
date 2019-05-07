from ._parser import Parser
from ._objects import Name, Ref, Stream
from ._to_bytes import to_bytes

import copy
import pprint

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
        self.header = parser.parse(r'%([^\n\r]*)', skip_comment=False)
        x = parser.parse(r'%([^\n\r]*)', allow_nonmatch=True, binary=True, skip_comment=False)
        if x: self.header.append(x[0])
        while parser.i < len(parser.content):
            # body
            while not parser.check('xref|startxref'):
                ref = Ref(parser.parse(r'\d+ \d+ obj'))
                self.objects[ref] = parser.parse_object()
                parser.parse('endobj')
            # cross-reference
            if parser.parse('startxref', allow_nonmatch=True):
                # stream
                startxref = int(parser.parse(r'\d+'))
                for k, v in self.objects.items():
                    if isinstance(v, Stream) and v.get('Type') == Name('XRef'):
                        xref = v
                        break
                i = 0
                object_number = 0
                while i < len(xref.decoded):
                    x = []
                    for j, v in enumerate(xref['W']):
                        if v == 0:
                            x.append([
                                1,
                                None,
                                0 if x and x[0] == 1 else None
                            ][j])
                        else:
                            x.append(int.from_bytes(xref.decoded[i:i+v], 'big'))
                            i += v
                    if x[0] == 0:
                        if object_number != 0:
                            self.xref[object_number] = Xref(x[1], x[2], 'f')
                    elif x[0] == 1:
                        self.xref[object_number] = Xref(x[1], x[2], 'n')
                    elif x[0] == 2:
                        raise Exception('unimplemented')
                    object_number += 1
                self.trailer.append(Trailer(
                    {
                        k: v
                        for k, v in xref.dictionary.items()
                        if k not in ['Type', 'Filter', 'DecodeParams', 'Length', 'W']
                    },
                    startxref,
                ))
            else:
                # table
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
            # end of file
            parser.parse('%%EOF\s*')
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
        if self.trailer:
            return self.trailer[-1].dictionary['Root']
        for k, v in self.objects.items():
            if type(v) == dict and v.get('Type') == Name('Catalog'):
                return k

    def object(self, *args):
        return self.objects[Ref(*args)]
