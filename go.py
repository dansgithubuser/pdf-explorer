import pdf

import argparse
import glob
import os
import shutil
import subprocess
import webbrowser

DIR = os.path.dirname(__file__)

parser = argparse.ArgumentParser()
parser.add_argument('--browser', '-b', action='store_true')
parser.add_argument('--server', '-s', action='store_true')
parser.add_argument('--test', '-t', action='store_true')
args = parser.parse_args()

if args.browser:
    webbrowser.open_new_tab(os.path.join(DIR, 'index.html'))

if args.server:
    subprocess.check_call(['python', '-u', 'py-rpc-host', 'pdf'])

if args.test:
    def compare(a, b):
        with open(a, 'rb') as f: a = f.read()
        with open(b, 'rb') as f: b = f.read()
        return a == b
    for i in glob.glob(os.path.join('reference-pdfs', '*i.pdf')):
        print(i)
        truncated = i[:-5]
        test_file_name = truncated+'t.pdf'
        pdf.Pdf().load(i).save(test_file_name)
        if not compare(truncated+'o.pdf', test_file_name):
            print('warning: output changed')
        pdf.Pdf().load(test_file_name).save(test_file_name)
        if not compare(truncated+'o.pdf', test_file_name):
            print('error: not idempotent')
        os.remove(test_file_name)
