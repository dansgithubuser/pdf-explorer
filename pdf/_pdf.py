'''
This file makes page and section references to ISO 32000-1:2008.

Overall file structure is documented in section 7.5.
'''

from ._parser import Parser
from ._objects import Name, Ref, Stream
from ._to_bytes import to_bytes, Custom

import copy
import pprint
import re
import uuid

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
        self.uniquifier = uuid.uuid4()
        self.templatify_forms_padding = 80
        self.templatify_forms_custom_padding = {}

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
                try:
                    self.objects[ref] = parser.parse_object()
                except:
                    print('exception while parsing object {}'.format(ref))
                    raise
                parser.parse('endobj')
            # cross-reference
            if parser.parse('startxref', allow_nonmatch=True):
                # stream p49 (7.5.8)
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
        # font
        fonts = self.descend('root', 'AcroForm', 'DR', 'Font')
        da = self.descend('root', 'AcroForm', 'DA')
        if da:
            font_name = re.search('/(.*?) .*?Tf', da).group(1)
            self.font = fonts[font_name]
        else:
            self.font = next(iter(fonts.values()))
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

    def descend(self, object, *keys, extract=None):
        def follow(x):
            if x == 'root':
                x = self.root()
            if x.__class__ == Ref:
                x = self.object(x)
            return x
        x = follow(object)
        for i in keys:
            if x.__class__ not in [dict, Stream] or i not in x: return
            x = follow(x[i])
        if extract == Name:
            if x.__class__ != Name: return
            x = x.value
        return x

    def templatify_text(self, ref, **kwargs):
        whitelist = kwargs.get('whitelist')
        da = kwargs.get('da')
        da = self.descend(ref, 'DA') or da
        if self._templatify_kids(ref, Pdf.templatify_text, whitelist, da): return
        form = self.object(ref)
        if self.remove_dv and 'DV' in form:
            del form['DV']
        form['V'] = Custom(self._template_value('t', ref), padding=self._templatify_padding(ref))
        self._templatify_appearance(ref, self._template_value('g', ref), da)

    def templatify_button(self, ref, **kwargs):
        whitelist = kwargs.get('whitelist')
        if self._templatify_kids(ref, Pdf.templatify_button, whitelist): return
        form = self.object(ref)
        value = self._template_value('b', ref)
        form['AS'] = Custom(Name(value), padding=self._templatify_padding(ref))
        form['V'] = Custom(Name(value), padding=self._templatify_padding(ref))

    def templatify_choice(self, ref, **kwargs):
        whitelist = kwargs.get('whitelist')
        form = self.object(ref)
        value = self._template_value('c', ref)
        form['V'] = Custom(value, padding=self._templatify_padding(ref))
        self._templatify_appearance(ref, value)

    def templatify_forms(self, whitelist=None, remove_dv=False):
        self.remove_dv = remove_dv
        for k, v in self.objects.items():
            if not self._white(k, whitelist): continue
            ft = self.descend(v, 'FT', extract=Name)
            if ft == 'Tx': #  p430 (12.7)
                self.templatify_text(k, whitelist=whitelist)
            elif ft == 'Btn':
                self.templatify_button(k, whitelist=whitelist)
            elif ft == 'Ch':
                self.templatify_choice(k, whitelist=whitelist)

    def _templatify_kids(self, ref, templatify, whitelist, da=None):
        form = self.object(ref)
        if 'Kids' in form:
            for kid in form['Kids']:
                if not self._white(kid, whitelist): continue
                templatify(self, kid, whitelist=whitelist, da=da)
            return True
        return False

    def _white(self, ref, whitelist):
        if not whitelist:
            return True
        if self.descend(ref, 'Kids'):
            return True
        if ref.object_number in whitelist:
            return True
        return False

    def _template_value(self, prefix, ref):
        return '{}{}-{}'.format(prefix, ref.object_number, self.uniquifier)

    def _templatify_appearance(self, ref, value, da=None):
        form = self.object(ref)
        if 'AP' not in form: return
        da = self.descend(form, 'DA') or da
        if da:
            font, font_size = re.search('/([^ ]+) ([^ ]+) Tf', da).groups()
        else:
            font, font_size = 'none', '0'
        rect = self.descend(form, 'Rect')
        tm_f = rect[3] - rect[1]  # p88
        for k, v in self.descend(form, 'AP').items():  # p80 (7.7.4)
            v = self.descend(v)
            if v.__class__ != Stream: continue
            if 'Filter' in v:
                del v['Filter']
            v['Resources'] = {
                'Font': {
                    font: self.font,
                }
            }
            v.stream = (
                '/Tx BMC\n'  # p435
                'q\n'
                'BT\n'
                f'{da}\n'
                f'1 0 0 1 0 {tm_f} Tm\n'  # p250
                f'{font_size} TL\n'
                'T*\n'
                f'({value})' + ' '*self._templatify_padding(ref) + 'Tj\n'  # p81 (7.8.2), p251 (9.4.3)
                'ET\n'
                'Q\n'
                'EMC\n'
            ).encode('utf-8')
            v['Length'] = len(v.stream)

    def _templatify_padding(self, ref):
        return self.templatify_forms_custom_padding.get(ref.object_number, self.templatify_forms_padding)
