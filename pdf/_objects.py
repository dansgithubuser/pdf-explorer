'''
This file makes page and section references to ISO 32000-1:2008.

Objects are documented in section 7.3 of ISO 32000-1:2008.
'''

import re
import pprint
import zlib

class Name:
    escape_regex = re.compile('#([0-9a-fA-F]{2})')

    def __init__(self, literal):
        self.value = Name.escape_regex.sub(lambda m: chr(int(m.group(1), 16)), literal)

    def __eq__(self, other):
        if not isinstance(other, Name): return False
        return self.value == other.value

    def __repr__(self):
        return '/{}'.format(self.value)

    def to_json(self): return repr(self)

class Stream:
    def __init__(self, dictionary, stream):
        self.dictionary = dictionary
        self.stream = stream
        self.decoded = None
        if not self.dictionary.get('Filter'):
            self.decoded = self.stream
        elif self.dictionary['Filter'] == Name('FlateDecode'):  # p22 (7.4), p25 (7.4.4)
            self.decoded = zlib.decompress(self.stream)
            try: self.decoded.decode('utf-8')
            except: pass

    def __eq__(self, other):
        if not isinstance(other, Stream): return False
        return (self.dictionary, self.stream) == (other.dictionary, other.stream)

    def __repr__(self):
        return 'Stream({} {})'.format(pprint.pformat(self.dictionary), self.decoded or hash(self.stream))

    def __getitem__(self, key):
        return self.dictionary[key]

    def __setitem__(self, key, value):
        self.dictionary[key] = value

    def __delitem__(self, key):
        del self.dictionary[key]

    def __contains__(self, item):
        return item in self.dictionary

    def to_json(self):
        uniquifier = 'pdf_py_meta'
        assert uniquifier not in self.dictionary
        return dict(self.dictionary, **{
            uniquifier: {'type': 'stream', 'decoded': self.decoded},
        })

    def get(self, key):
        return self.dictionary.get(key)

class Ref:
    def __init__(self, *args):
        types = [type(i) for i in args]
        if types == [str]:
            self.object_number, self.generation_number = [int(i) for i in args[0].split()[:2]]
        elif types == [int]:
            self.object_number, self.generation_number = args[0], 0
        elif types == [Ref]:
            self.object_number, self.generation_number = args[0].object_number, args[0].generation_number
        elif types == [int, int]:
            self.object_number, self.generation_number = args
        else:
            raise Exception('invalid arguments {}'.format(args))

    def __eq__(self, other):
        if not isinstance(other, Ref): return False
        return (self.object_number, self.generation_number) == (other.object_number, other.generation_number)

    def __hash__(self):
        return hash((self.object_number, self.generation_number))

    def __repr__(self):
        return '{} {}'.format(self.object_number, self.generation_number)

    def to_json(self): return repr(self)
