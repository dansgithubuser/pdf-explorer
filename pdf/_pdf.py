from ._parser import Parser
from ._objects import Ref

import pprint

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
        self.header = [parser.parse(r'%([^\n\r]*)')]
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
                object_0, object_n = [int(i) for i in parser.parse(r'[^\n\r]*').split()]
                for i in range(object_n):
                    ref, free = parser.parse('(\d+ \d+) ([fn])')
                    self.xref[object_0 + i] = {
                        'ref': Ref(ref),
                        'free': free == 'f',
                    }
            # trailer
            parser.parse('trailer')
            dictionary = parser.parse_object()
            parser.parse('startxref')
            startxref = int(parser.parse('\d+'))
            self.trailer.append({
                'dictionary': dictionary,
                'startxref': startxref,
            })
            parser.parse(r'%%EOF\s*')
        # return so we can use something like named constructor idiom
        return self

    def root(self):
        return self.trailer[-1]['dictionary']['Root']

    def object(self, *args):
        return self.objects[Ref(*args)]
