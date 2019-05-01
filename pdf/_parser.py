import os
import re

from ._objects import Name, Ref, Stream

class Parser:
    def __init__(self, content):
        self.line = 1
        self.content = content
        self.i = 0

    def _advance(self, i, _depth=0):
        advanced = self.content[self.i:i]
        self.line += advanced.count(b'\n')
        self.i = i
        if os.environ.get('DEBUG'): print('{}advanced to {}: {}'.format('\t' * _depth, self.i, advanced))

    def check(self, pattern):
        m = re.match(pattern.encode(), self.content[self.i:])
        return m

    def parse(self, pattern, allow_nonmatch=False, skip_space=True, binary=False, _depth=0):
        m = self.check(pattern)
        if not m or not len(m.group()):
            if allow_nonmatch: return
            raise Exception("parse failed on line {}, index {}; expected {}, got {}".format(
                self.line, self.i, repr(pattern), repr(self.check('(.*?)(\n|\r|$)').group(1))
            ))
        self._advance(self.i + len(m.group()), _depth=_depth)
        if skip_space: self.parse('\s*', allow_nonmatch=True, skip_space=False, _depth=_depth)
        if binary:
            decode = lambda x: x
        else:
            decode = lambda x: x.decode()
        if m.groups():
            result = [decode(i) for i in m.groups()]
        else:
            result = decode(m.group())
        return result

    def parse_object(self, _depth=0):
        def transform_number(x):
            try: return int(x)
            except Exception: pass
            return float(x)
        not_raw_paren = (
            r'(?:'
                r'[^\\()]|\\.'
            r')*'
        )
        pattern_string_literal = (
            r'\(('
                + not_raw_paren +
                r'(?:'  # allow balanced raw parens
                    r'\('
                    + not_raw_paren +
                    '\)'
                r')*'
                + not_raw_paren +
            r')\)'
        )
        def transform_string_literal(x):
            if x[0:2] == b'\xfe\xff':
                x = x.decode('utf-16')
            else:
                try: x = x.decode()
                except: return x
            for k, v in {
                r'\n': '\n',
                r'\r': '\r',
                r'\t': '\t',
                r'\b': '\b',
                r'\f': '\f',
                r'\(': '(',
                r'\)': ')',
                r'\\': '\\',
            }.items(): x = x.replace(k, v)
            r = re.compile(r'\\([0-8]{1,3})')
            x = r.sub(lambda m: chr(int(m.group(1), 8)), x)
            return x
        def transform_string_hexadecimal(x):
            result = ''
            for i in range(0, len(x), 2):
                o = int(x[i], 16) * 16
                if i + 1 < len(x): o += int(x[i + 1], 16)
                result += chr(o)
            return result
        name_sentinel = '(?=' + '|'.join([
            r'\s',
            # according to ISO, seems name end should be indicated by space, but in practice we see other shenanigans
            '/',
            r'\(',
            r'\[', r'\]',
            '<', '>',
        ]) + ')'
        pattern_name = '/(.*?)' + name_sentinel
        def transform_array(x):
            result = []
            while not self.parse(']', allow_nonmatch=True, _depth=_depth):
                result.append(self.parse_object(_depth=_depth + 1))
            return result
        def transform_dictionary_or_stream(x):
            result = {}
            while not self.parse('>>', allow_nonmatch=True, _depth=_depth):
                entry = Name(self.parse(pattern_name, _depth=_depth)[0])
                result[entry.value] = self.parse_object(_depth=_depth + 1)
            if self.parse('stream', allow_nonmatch=True, skip_space=False, _depth=_depth):
                l = result['Length']
                e = self.content.find(b'endstream', self.i + l) - 1
                result = Stream(result, self.content[e - l:e])
                self._advance(e)
                self.parse(r'\s*endstream', _depth=_depth)
            return result
        for pattern, transform, kwargs in [
            (pattern_name, lambda x: Name(x[0]), {}),
            ('\d+ \d+ R', Ref, {}),
            (r'[+-]?\d?\.?\d*', transform_number, {}),
            (pattern_string_literal, lambda x: transform_string_literal(x[0]), {'binary': True}),
            (r'<<', transform_dictionary_or_stream, {}),
            (r'\[', transform_array, {}),
            ('<(.*?)>', lambda x: transform_string_hexadecimal(x[0]), {}),
            ('true', lambda x: True, {}),
            ('false', lambda x: False, {}),
        ]:
            obj = self.parse(pattern, allow_nonmatch=True, **kwargs, _depth=_depth)
            if obj is not None: return transform(obj)
        raise Exception('unknown object at line {}, index {}'.format(self.line, self.i))
