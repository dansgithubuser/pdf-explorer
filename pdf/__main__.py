import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pdf import Pdf

parser = argparse.ArgumentParser()
parser.add_argument('pdf')
parser.add_argument('--compare', '-c')
parser.add_argument('--save', '-s')
args = parser.parse_args()

pdf = Pdf().load(args.pdf)

if args.compare:
    other = Pdf().load(args.compare)
    for k, v in pdf.objects.items():
        if k not in other.objects:
            print('===== {} ===== missing from other'.format(k))
        if other.objects[k] != v:
            print((
                '===== {} =====\n'
                '{}\n'
                '\n'
                '===== other =====\n'
                '{}'
            ).format(k, v, other.objects[k]))
    for k in other.objects.keys():
        if k not in pdf.objects:
            print('===== {} ===== missing'.format(k))
if args.save:
    pdf.save(args.save)
