#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import select
import termios
import tty
import pty
import fcntl
import struct
import threading
import time
import signal
from subprocess import Popen, TimeoutExpired

TIMEOUT=0.05

command = ['/bin/bash', '-i']

apptainer_cmd="/cvmfs/atlas.cern.ch/repo/containers/sw/apptainer/x86_64-el8/current/bin/apptainer"

install_root='/scratch/apptainer_'+str(os.getuid())+'/CO9'

mount_paths=['cvmfs','scratch','localdisk']

cmd_env = {}

def get_app_env():

    if len(cmd_env.keys())==0:

        cmd_env['SCRATCH_ROOT']=os.path.dirname(install_root)
        cmd_env['APPTAINER_BIND']=get_mount_paths()
        for app_env in ['', 'APPTAINERENV_', 'APPTAINERENV_APPTAINERENV_']:
            for wrk_folder in [('TMPDIR', 'TMP'), ('CACHEDIR', 'CACHE'), ('PULLFOLDER', 'PULL')]:
                cmd_env[app_env + 'APPTAINER_' + wrk_folder[0]]=os.path.join(cmd_env['SCRATCH_ROOT'],wrk_folder[1])
            cmd_env[app_env + 'BIND']=get_mount_paths()

    return cmd_env

def get_app_scriptEnv():

    script_env = ''
    app_env = get_app_env()

    for k,v in app_env.items():
        script_env+=' export {}="{}"\n'.format(k,v)

    return script_env

def get_app_pythonEnv():

    return get_app_env()


class NormalSubShell():
    def __init__(self, quiet):

        self.p = None        
        self.exit_cmd = ['exit'.encode(),]
        self.quiet = quiet

    def _wrangle_tty(self):

        # save original tty setting then set it to raw mode
        old_i_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        # open pseudo-terminal to interact with subprocess
        stdout_m_fd, stdout_s_fd = pty.openpty()

        size = os.get_terminal_size()
        winsize = struct.pack("HHHH", size[1], size[0], 0, 0)
        fcntl.ioctl(stdout_m_fd, termios.TIOCSWINSZ, winsize)

        #print('Opening PTY')

        self.old_i_tty = old_i_tty
        self.stdout_m, self.stdout_s = stdout_m_fd, stdout_s_fd

    def _launch_shell(self):

        # use os.setsid() make it run in a new process group, or bash job control will not be enabled
        self.p = Popen(command,
                      preexec_fn=os.setsid,
                      stdin=self.stdout_s,
                      stdout=self.stdout_s,
                      stderr=self.stdout_s,
                      universal_newlines=True)

        for s in [self.stdout_s,]:
            os.close(s)

    def run_queue(self, queued_cmds):

        self._wrangle_tty()
        self._launch_shell()

        readable = [self.stdout_m, ]

        full_cmd = ''

        i=0

        for cmd in queued_cmds:

            if type(cmd) is not str:
                _cmd = cmd.decode()
            else:
                _cmd = cmd

            if _cmd[-1] in ['\n',]:
                _cmd = _cmd[:-1]

            if len(full_cmd)!=0:
                full_cmd+= ' && '
            full_cmd += _cmd

        full_cmd = full_cmd.replace('\n', ' && ')

        full_cmd += ' ; exit $?\n'

        os.write(self.stdout_m, full_cmd.encode())

        while True:

            should_continue = self._shell_fwd_bck(readable)

            if not should_continue:
                break

        self._cleanup()


    def _shell_fwd_bck(self, readable):

        if self.p and self.p.poll() is None:
            
            r, w, e = select.select(readable, [], [], TIMEOUT)

            for _in in r:
                if _in is sys.stdin:
                    d = os.read(sys.stdin.fileno(), 10240)
                    if d.decode() in ['\x04',]:
                        self._should_stop = True
                        return False
                    os.write(self.stdout_m, d)
                elif _in is self.stdout_m:
                    try:
                        o = os.read(self.stdout_m, 10240)
                    except OSError as e:
                        return False
                    if o and not self.quiet:
                        os.write(sys.stdout.fileno(), o)
                else:
                    raise Exception('Help')
            return True
        else:

            return False
            
    def _cleanup(self):

        self.running = False

        # restore tty settings back
        termios.tcdrain(sys.stdin)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_i_tty)
        #sys.stdin.flush()
        os.close(self.stdout_m)
        self.p = None
        self.old_i_tty = None
        self.stdout_m = None
        self.stdout_s = None
        sys.stdout.flush()

class InteractiveShell(threading.Thread, NormalSubShell):
    def __init__(self):
        self.stdout = None
        self.stderr = None
        threading.Thread.__init__(self)
        NormalSubShell.__init__(self, False)

        self.p = None
        self._should_stop = False
        self.running = False
        
        self._wrangle_tty()
        self._launch_shell()

    def run(self):
        self.launch_interactive()

    def stop(self):
        self._should_stop = True

    def launch_interactive(self):

        if not self.p:
            self._wrangle_tty()
            self._launch_shell()
            self._should_stop = False

        try:

            readable = [sys.stdin, self.stdout_m]

            self.running = True

            while True:

                should_continue = self._shell_fwd_bck(readable)

                if not should_continue:
                    self.p.kill()
                    self.p.terminate()
                    break

                if self._should_stop:
                    os.write(self.stdin_m, str('exit').encode())
                    self.p.kill()
                    self.p.terminate()
                    break

        finally:
            self._cleanup()


def get_singularity_cmd(s_path=None, cmd=None):

    if not s_path:
        path = '/cvmfs/atlas.cern.ch/repo/containers/sw/apptainer/x86_64-el8/current/bin/'
    if not cmd:
        cmd = 'apptainer'

    return os.path.join(path, cmd)


def build_singularity_env(root=None):

    if not root:
        root = os.path.dirname(install_root)

    if not os.path.exists(root):
        os.makedirs(root)

    for i in ['TMP','CACHE','PULL']:
        wrk_path = os.path.join(root, i)
        if not os.path.exists(wrk_path):
            print(wrk_path)
            os.makedirs(wrk_path)

def build_activate_scripts():

    bin_dir = os.path.join(install_root, 'bin')

    activate_script_path = os.path.join(bin_dir, 'activate')

    if not os.path.exists(activate_script_path):

        if not os.path.exists(bin_dir):
            os.makedirs(bin_dir)

        with open(activate_script_path, 'w') as _file:

            _file.write(build_launch_script(install_root))

def get_cvmfs_fuse():

    if os.path.exists('/usr/lib/libcvmfs_fuse.so'):
        return 'export LD_PRELOAD="/usr/lib/libcvmfs_fuse.so"'
    elif os.path.exists('/usr/lib64/libcvmfs_fuse.so'):
        return 'export LD_PRELOAD="/usr/lib64/libcvmfs_fuse.so"'
    else:
        return 'export LD_PRELOAD=""'

def create_new_appenv(shell):

    if os.path.exists(install_root):
        return

    build_singularity_env()

    cmd_queue = [get_app_scriptEnv(), ]
    cmd_queue += [get_cvmfs_fuse(), ]
    cmd_queue += [apptainer_cmd + ' pull --force "docker://almalinux:9"', ]
    cmd_queue += [apptainer_cmd + ' build --force --fix-perms --sandbox --fakeroot "'+install_root+'"  "docker://almalinux:9"', ]
    cmd_queue += ['unset LD_PRELOAD', ]

    shell.run_queue(cmd_queue)

    for _folder in mount_paths:

        bind_folder = os.path.join(install_root, _folder)
    
        if not os.path.exists(bind_folder):
            os.makedirs(bind_folder)

    build_activate_scripts()

def get_mount_paths():

    path_str = ''
    for subpath in mount_paths:
        local_path = os.path.join('/'+subpath)
        path_str+=local_path+':'+local_path

    return path_str

def build_env_script():

    return get_app_scriptEnv()

def build_launch_script(root):

    activate_script = '#!/bin/bash\n'

    for subpath in mount_paths:
        activate_script += 'mkdir -p '+os.path.join(root, subpath) + '\n'

    apptainer_shell_cmd = '\n'
    apptainer_shell_cmd += 'unset LD_PRELOAD\n'
    apptainer_shell_cmd += 'export APPTAINERENV_PS1=$PS1\n'
    apptainer_shell_cmd += 'alias deavtivate=exit\n'
    apptainer_shell_cmd += apptainer_cmd + ' shell -f -w '+root+'\n'

    activate_script += apptainer_shell_cmd

    return activate_script

def header():

    print('                                                            ')
    print('░░      ░░░       ░░░       ░░░       ░░░░      ░░░  ░░░░  ░')
    print('▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒▒  ▒▒  ▒▒')
    print('▓  ▓▓▓▓  ▓▓       ▓▓▓       ▓▓▓       ▓▓▓  ▓▓▓▓  ▓▓▓▓    ▓▓▓')
    print('█        ██  ████████  ████████  ████  ██  ████  ███  ██  ██')
    print('█  ████  ██  ████████  ████████       ████      ███  ████  █')
    print('████████████████████████████████████████████████████████████')
    print('')

def start_interactive(custom_cmd=None):

    m=InteractiveShell()

    if custom_cmd:
        if type(custom_cmd) is str:
            _cmd = custom_cmd.encode()
        else:
            _cmd = custom_cmd
        os.write(m.stdout_m, _cmd)

    m.start()
    while m.p is not None and m.p.poll() is None:
        time.sleep(0.05)
    m.stop()
    m.join()
    os.write(sys.stdout.fileno(), '\n'.encode())

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
                    prog='appBox',
                    description='This is a short tool to allow you to install a custom image like a "virtualenv".')

    parser.add_argument('-p', '--path', '--prompt',
                        help='Where you want to "install the image", aka the path to the sandbox.')
    parser.add_argument('-i', '--image',
                        help='Image to install: e.g. "docker://almalinux:9"')
    parser.add_argument('-l', '--launch', '--run',
                        help='Launch a sandbox from this location.')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Quiet')

    parsed_args = parser.parse_args(sys.argv[1:])

    if not parsed_args.quiet:
        header()

    if True:

        start_interactive()

    else:

        n = NormalSubShell(quiet=True)
        create_new_appenv(n)
        del n

        _cmd = 'source '+os.path.join(install_root, 'bin/activate\n')
        start_interactive(_cmd)

    sys.exit(0)

