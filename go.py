import os
import subprocess
import webbrowser

DIR = os.path.dirname(__file__)

webbrowser.open_new_tab(os.path.join(DIR, 'index.html'))
subprocess.check_call(['python', 'py-rpc-host', 'pdf.py'])
