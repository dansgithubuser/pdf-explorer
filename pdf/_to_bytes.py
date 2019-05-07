'''
Objects are documented in section 7.3 of ISO 32000-1:2008.
'''

from ._objects import Name, Ref, Stream

import re
import string

class Custom:
    def __init__(self, object, padding=0):
        self.object = object
        self.padding = padding

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

def transform_custom(x):
    return to_bytes(x.object) + b' ' * x.padding

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
        Custom: transform_custom,
    }[object.__class__](object)
    if type(result) == str: result = result.encode('utf-8')
    return result
