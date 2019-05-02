import os
import re

from ._objects import Name, Ref, Stream

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

def transform_array(x, parser, _depth):
    result = []
    while not parser.parse(']', allow_nonmatch=True, _depth=_depth):
        result.append(parser.parse_object(_depth=_depth + 1))
    return result

def transform_dictionary_or_stream(x, parser, _depth):
    result = {}
    while not parser.parse('>>', allow_nonmatch=True, _depth=_depth):
        entry = Name(parser.parse(pattern_name, _depth=_depth)[0])
        result[entry.value] = parser.parse_object(_depth=_depth + 1)
    if parser.parse('stream', allow_nonmatch=True, skip_space=False, _depth=_depth):
        l = result['Length']
        e = parser.content.find(b'endstream', parser.i + l) - 1
        result = Stream(result, parser.content[e - l:e])
        parser._advance(e)
        parser.parse(r'\s*endstream', _depth=_depth)
    return result

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

    def skip(self, pattern=r'\s*', _depth=0):
        self.parse(pattern, allow_nonmatch=True, skip_space=False, skip_comment=False, _depth=_depth)

    def parse(self, pattern, allow_nonmatch=False, skip_space=True, binary=False, skip_comment=True, _depth=0):
        m = self.check(pattern)
        if not m or not len(m.group()):
            if allow_nonmatch: return
            raise Exception("parse failed on line {}, index {}; expected {}, got {}".format(
                self.line, self.i, repr(pattern), repr(self.check('(.*?)(\n|\r|$)').group(1))
            ))
        self._advance(self.i + len(m.group()), _depth=_depth)
        if skip_comment:
            self.skip(_depth=_depth)
            if not self.check('%%EOF'):
                self.skip('%[^\r\n]*', _depth=_depth)
        if skip_space:
            self.skip(_depth=_depth)
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
        for pattern, transform, kwargs in [
            (pattern_name, lambda x: Name(x[0]), {}),
            ('\d+ \d+ R', Ref, {}),
            (r'[+-]?(?:\d*)?\.?\d*', transform_number, {}),
            (pattern_string_literal, lambda x: transform_string_literal(x[0]), {'binary': True}),
            (r'<<', lambda x: transform_dictionary_or_stream(x, self, _depth), {}),
            (r'\[', lambda x: transform_array(x, self, _depth), {}),
            ('<(.*?)>', lambda x: transform_string_hexadecimal(x[0]), {}),
            ('true', lambda x: True, {}),
            ('false', lambda x: False, {}),
            ('null', lambda x: None, {}),
        ]:
            obj = self.parse(pattern, allow_nonmatch=True, **kwargs, _depth=_depth)
            if obj is not None: return transform(obj)
        raise Exception('unknown object at line {}, index {}'.format(self.line, self.i))
