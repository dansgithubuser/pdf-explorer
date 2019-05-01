import argparse
import os
import subprocess
import webbrowser

DIR = os.path.dirname(__file__)

parser = argparse.ArgumentParser()
parser.add_argument('--browser', '-b', action='store_true')
args = parser.parse_args()

if args.browser: webbrowser.open_new_tab(os.path.join(DIR, 'index.html'))
subprocess.check_call(['python', '-u', 'py-rpc-host', 'pdf'])
