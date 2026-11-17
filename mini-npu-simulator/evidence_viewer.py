"""Run the real console program and display untouched captured output for screenshots.

This optional evidence helper uses only the Python standard library (including Tk).
It is not required to run main.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tkinter as tk
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent
CROSS = '0 1 0\n1 1 1\n0 1 0\n'
X = '1 0 1\n0 1 0\n1 0 1\n'
CASES = {
    'mode1': (['main.py', '--repeats', '1000'], '1\n'+CROSS+X+X),
    'mode2': (['main.py', '--mode', '2', '--repeats', '1000'], None),
    'invalid': (['main.py', '--mode', '2', '--data', 'fixtures/invalid.json', '--repeats', '1000'], None),
    'retry': (['main.py', '--repeats', '1000'], '1\n1 2\na b c\n'+CROSS+X+X),
    'tests': (['-m', 'unittest', '-v'], None),
}


def execute(name):
    args, stdin = CASES[name]
    started = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
    proc = subprocess.run([sys.executable]+args, input=stdin, cwd=str(ROOT),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8',
                          env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    record = {'scenario': name, 'started_kst': started,
              'command': [sys.executable]+args, 'cwd': str(ROOT),
              'python': platform.python_version(), 'platform': platform.platform(),
              'stdin': stdin, 'exit_code': proc.returncode,
              'main_sha256': hashlib.sha256((ROOT/'main.py').read_bytes()).hexdigest(),
              'data_sha256': hashlib.sha256((ROOT/'data.json').read_bytes()).hexdigest()}
    evidence = ROOT/'evidence'
    evidence.mkdir(exist_ok=True)
    (evidence/(name+'.txt')).write_text(proc.stdout, encoding='utf-8')
    (evidence/(name+'.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return record, proc.stdout


def show(name, record, output):
    window = tk.Tk()
    window.title('Mini NPU Evidence - '+name)
    window.geometry('1450x930+20+20')
    window.configure(bg='#101827')
    header = '실제 Python 실행 증빙 | {} | 종료 코드 {}'.format(name, record['exit_code'])
    tk.Label(window, text=header, bg='#101827', fg='#ffffff', font=('Malgun Gothic', 16, 'bold'), anchor='w').pack(fill='x', padx=16, pady=(12,6))
    meta = '{} KST | Python {}\n명령: python {}\nmain.py SHA256: {}'.format(record['started_kst'], record['python'], ' '.join(CASES[name][0]), record['main_sha256'])
    tk.Label(window, text=meta, bg='#101827', fg='#b8c9e2', font=('Malgun Gothic', 10), anchor='w', justify='left').pack(fill='x', padx=16)
    tk.Label(window, text='main.py를 subprocess로 실제 실행한 stdout/stderr 원문입니다. 입력은 파이프로 전달했으며 터미널 창 캡처는 아닙니다.', bg='#101827', fg='#77d8b5', font=('Malgun Gothic',10), anchor='w').pack(fill='x', padx=16, pady=6)
    body=tk.Frame(window, bg='#101827')
    body.pack(fill='both',expand=True,padx=16,pady=(0,14))
    if record['stdin'] is not None:
        left=tk.Text(body,width=18,bg='#182337',fg='#d7e4f9',font=('Malgun Gothic',11),wrap='none')
        left.pack(side='left',fill='y',padx=(0,12))
        left.insert('1.0','실제 전달한 stdin\n\n'+record['stdin'])
        left.configure(state='disabled')
    text=tk.Text(body,bg='#f6f8fb',fg='#111827',font=('Malgun Gothic',11),wrap='none',padx=12,pady=10)
    scrollbar=tk.Scrollbar(body,command=text.yview)
    scrollbar.pack(side='right',fill='y')
    text.pack(fill='both',expand=True)
    text.configure(yscrollcommand=scrollbar.set)
    text.insert('1.0',output)
    text.configure(state='disabled')
    window.mainloop()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario',choices=list(CASES)+['all'])
    parser.add_argument('--no-gui',action='store_true')
    options=parser.parse_args()
    for name in CASES if options.scenario=='all' else [options.scenario]:
        record, output=execute(name)
        if not options.no_gui:
            show(name,record,output)
        else:
            print('{}: exit {}'.format(name,record['exit_code']))
