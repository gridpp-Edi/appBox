#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import fcntl
import json
import logging
import os
import pprint
import pty
import pwd
import select
import signal
import struct
import sys
import termios
import threading
import time
import tty
import subprocess

appLogger = logging.getLogger('appBox')
logging.basicConfig(level=logging.INFO, format='%(message)s')

def getUN():
    return pwd.getpwuid(os.getuid())[0]


class SettingsManager():

    settings = None

    def get_default_bind_mounts():

        bind_mount_paths = ['/cvmfs','/scratch', '/localdisk', '/Data', '/mnt', '/exports']

        found_paths = []

        for subpath in bind_mount_paths:
            if not os.path.exists(subpath):
                appLogger.warning('PATH: {} not found so won\'t attempt to mount into contaier.'.format(subpath))
                continue

            found_paths.append(subpath)

        return found_paths


    def get_settings():

        if SettingsManager.settings:       
            return SettingsManager.settings

        _settings = {
             'apptainer_cmd': SettingsManager.get_singularity_cmd(),
             'bind_mount_paths': SettingsManager.get_default_bind_mounts(),
             'default_fuse_lib_preload': SettingsManager.get_cvmfs_fuse(),
             'default_image_wrk_path': SettingsManager.get_default_scratch(),
             'default_img': 'docker://centos:centos7',
             'default_mappings': {
                                   'CO6':      'docker://centos:centos6',
                                   'CO7':      'docker://centos:centos7',
                                   'SL7':      'docker://centos:centos7',
                                   'EL7':      'docker://centos:centos7',
                                   'CO8':      'docker://almalinux:8',
                                   'EL8':      'docker://almalinux:8',
                                   'Alma8':    'docker://almalinux:8',
                                   'EL9':      'docker://almalinux:9',
                                   'Alma9':    'docker://almalinux:9',
                                   'Rocky8':   'docker://rockylinux:8',
                                   'Rocky9':   'docker://rockylinux:9',
                                   'Ubuntu':   'docker://ubuntu:22.04',
                                   'Ubuntu22': 'docker://ubuntu:22.04',
                                   'Ubuntu20': 'docker://ubuntu:20.04',
                                   'TF216':    'docker://tensorflow/tensorflow:2.16.1-gpu-jupyter',
                                   'TF215':    'docker://tensorflow/tensorflow:2.15.0-gpu-jupyter',
                                   'TF214':    'docker://tensorflow/tensorflow:2.14.0-gpu-jupyter',
                                   'PyTorch22CUDA12': 'docker://pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime',
                                   'PyTorch22CUDA11': 'docker://pytorch/pytorch:2.2.2-cuda11.8-cudnn8-runtime',
                                   'PyTorch21CUDA12': 'docker://pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime',
                                   'PyTorch21CUDA11': 'docker://pytorch/pytorch:2.2.2-cuda11.8-cudnn8-runtime',
                                 },
             'default_sandbox_path': os.path.join(SettingsManager.get_default_scratch(), 'appBox'),
             'exec_as_root_by_default': False,
             'interactive_command': ['/bin/bash', '-i'],
             'timeout': 0.05,
            }

        SettingsManager.settings = _settings

        return SettingsManager.settings

    def get_default_scratch():
        if os.path.exists('/scratch'):
            default_scratch_path = os.path.join('/scratch', 'appBox_'+str(getUN()))
        else:
            default_scratch_path = os.path.join('/tmp', 'appBox_'+str(getUN()))
        return default_scratch_path

    def get_cvmfs_fuse():

        if os.path.exists('/usr/lib/libcvmfs_fuse.so'):
            return 'export LD_PRELOAD="/usr/lib/libcvmfs_fuse.so"'
        elif os.path.exists('/usr/lib64/libcvmfs_fuse.so'):
            return 'export LD_PRELOAD="/usr/lib64/libcvmfs_fuse.so"'
        else:
            return ''

    def get_singularity_cmd(s_path=None, cmd=None):

        if not s_path:
            path = '/cvmfs/atlas.cern.ch/repo/containers/sw/apptainer/x86_64-el8/current/bin/'
        if not cmd:
            cmd = 'apptainer'

        return os.path.join(path, cmd)

    def load_settings(settings_path):
        pass

    def save_settings(settings_path):
        pass

    cmd_env = {}

    def get_bind_paths():

        path_str = ''
        for subpath in SettingsManager.get_settings()['bind_mount_paths']:
            path_str+=subpath+':'+subpath+','

        return path_str

    def get_app_env():

        CMD_ENV = SettingsManager.cmd_env

        if len(CMD_ENV.keys())==0:

            CMD_ENV['SCRATCH_ROOT']=SettingsManager.get_settings()['default_image_wrk_path']
            CMD_ENV['APPTAINER_BIND']=SettingsManager.get_bind_paths()
            for app_env in ['', 'APPTAINERENV_', 'APPTAINERENV_APPTAINERENV_']:
                for wrk_folder in [('TMPDIR', 'TMP'), ('CACHEDIR', 'CACHE'), ('PULLFOLDER', 'PULL')]:
                    CMD_ENV[app_env + 'APPTAINER_' + wrk_folder[0]]=os.path.join(CMD_ENV['SCRATCH_ROOT'],wrk_folder[1])
                CMD_ENV[app_env + 'BIND']=SettingsManager.get_bind_paths()

        return CMD_ENV

    def get_app_scriptEnv():

        script_env = ''
        app_env = SettingsManager.get_app_env()

        for k,v in app_env.items():
            script_env+='export {}="{}"\n'.format(k,v)

        return script_env

    def get_app_pythonEnv():

        return SettingsManager.get_app_env()

    def get_this_image(img_str):

        img_map = SettingsManager.get_settings()['default_mappings']

        return img_map.get(img_str, img_str)

class NormalSubShell():
    def __init__(self, quiet):

        self.p = None        
        self.quiet = quiet
        self._should_stop = False
        self.running = False

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
        self.p = subprocess.Popen(SettingsManager.get_settings()['interactive_command'],
                      preexec_fn=os.setsid,
                      stdin=self.stdout_s,
                      stdout=self.stdout_s,
                      stderr=self.stdout_s,
                      universal_newlines=True)

        for s in [self.stdout_s,]:
            os.close(s)

    def run_queue(self, queued_cmds, ignore_history=True):

        self._wrangle_tty()
        self._launch_shell()

        readable = [self.stdout_m, ]

        full_cmd = ''

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

        if ignore_history:
            full_cmd = 'set +o history; unset HISTFILE; ' + full_cmd

        full_cmd += ' ; exit $? \n'

        os.write(self.stdout_m, full_cmd.encode())

        while True:

            self.running = True
            should_continue = self._shell_fwd_bck(readable)

            if not should_continue:
                break

        self._cleanup()


    def _shell_fwd_bck(self, readable):

        if self.p and self.p.poll() is None:
            
            r, w, e = select.select(readable, [], [], SettingsManager.get_settings()['timeout'])

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
        threading.Thread.__init__(self)
        NormalSubShell.__init__(self, False)

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
            self.running = False
            self._cleanup()


class RunCommand():

    def runCommand(thisCmd):

        if type(thisCmd) is list:
            _cmd = ' '.merge(thisCmd)
        else:
            _cmd = thisCmd

        _cmd = _cmd + " ; exit $?"
        full_cmd = ['bash', '-c', "{}".format(_cmd)]

        try:
            result = subprocess.run(full_cmd, stdout = subprocess.PIPE,
                                              stderr = subprocess.DEVNULL)

            stdout = result.stdout.decode()
            returncode = result.returncode
        except:
            stdout = ''
            returncode = -99

        return stdout, returncode


class SandboxInstaller():

    def build_launch_script(install_path, as_root):

        activate_script = '#!/bin/bash\n'

        for subpath in SettingsManager.get_settings()['bind_mount_paths']:
            local_path= './'+subpath
            activate_script += 'mkdir -p '+os.path.join(install_path, subpath) + '\n'

        apptainer_shell_cmd  = '\n'

        apptainer_shell_cmd += SettingsManager.get_app_scriptEnv()

        apptainer_shell_cmd += '\n'
        apptainer_shell_cmd += 'unset LD_PRELOAD\n'
        apptainer_shell_cmd += 'export APPTAINERENV_PS1=$PS1\n'

        if as_root:
            apptainer_shell_cmd += SettingsManager.get_settings()['apptainer_cmd'] + ' exec -w -f '+install_path+' /bin/bash \n'
        else:
            apptainer_shell_cmd += SettingsManager.get_settings()['apptainer_cmd'] + ' exec -w '+install_path+' /bin/bash \n'

        activate_script += apptainer_shell_cmd

        return activate_script

    def build_activate_scripts(install_path):

        bin_dir = os.path.join(install_path, 'bin')

        def _build_script(as_root=False):

            if as_root:
                script_name = 'activate-asroot'
            else:
                script_name = 'activate'
            activate_script_path = os.path.join(bin_dir, script_name)


            if not os.path.exists(activate_script_path):

                if not os.path.exists(bin_dir):
                    os.makedirs(bin_dir)
                with open(activate_script_path, 'w') as _file:
                    _file.write(SandboxInstaller.build_launch_script(install_path, as_root))

        _build_script(as_root=False)
        _build_script(as_root=True)

    def build_singularity_env(root=None):

        if not root:
            root = os.path.dirname(SettingsManager.get_settings()['default_sandbox_path'])

        if not os.path.exists(root):
            os.makedirs(root)

        image_wrk_path = SettingsManager.get_settings()['default_image_wrk_path']

        for i in ['TMP','CACHE','PULL']:
            wrk_path = os.path.join(image_wrk_path, i)
            if not os.path.exists(wrk_path):
                os.makedirs(wrk_path)

    def checkImgStorage(install_image):

        #docker inspect -f "{{ .Size }}" 

        install_image_ver = install_image.split(':')[-1]
        install_image_name = install_image.split(':')[-2][2:]

        try:
            img_url = "https://hub.docker.com/v2/repositories/{}/tags/{}".format(install_image_name, install_image_ver)
            appLogger.debug('Checking URL: {}'.format(img_url))
            image_size, rc = RunCommand.runCommand("curl -s {} | jq '.full_size'".format(img_url))
            if rc != 0:
                img_url = "https://hub.docker.com/v2/repositories/library/{}/tags/{}".format(install_image_name, install_image_ver)
                appLogger.debug('Checking URL: {}'.format(img_url))
                image_size, rc = RunCommand.runCommand("curl -s {} | jq '.full_size'".format(img_url))

            image_size = int(image_size.strip())
        except:
            image_size = -1

        appLogger.debug('Image size: {} bytes'.format(image_size))

        total_free_space = 0

        for i in ['TMP','CACHE','PULL']:

            subpath = os.path.join(SettingsManager.get_app_env()['SCRATCH_ROOT'], i)

            partition_data = os.statvfs(subpath)
            free_space = partition_data.f_bavail * partition_data.f_frsize

            appLogger.debug('Looking at Path: {}'.format(subpath))
            appLogger.debug('Found Free Space: {} bytes'.format(free_space))

            total_free_space = total_free_space + free_space

        if image_size>0 and total_free_space<(image_size*3):

            appLogger.error('Insufficient Space to extract image: {}'.format(install_image))
            raise Exception('Not Enough space to downlaod and extract image')
        
        appLogger.debug('Space < 3 * ImageSize')

        return (image_size, total_free_space)


    def checkPathCapacity(install_path, image_size):

        partition_data = os.statvfs(install_path)

        free_space = partition_data.f_bavail * partition_data.f_frsize

        appLogger.debug('Free Space found: {} bytes'.format(free_space))
        appLogger.debug('Free Space needed: {} bytes'.format(image_size))

        if free_space < (image_size + 10*1024*1024):

            appLogger.error('Not enough space to install.')
            raise Exception('Not enough space at: "{}" to extract image for "installation".'.format(install_path))


    def pullImage(install_image, debug):

        image_size, total_free_space = SandboxInstaller.checkImgStorage(install_image)

        appLogger.info('Pulling Image: "{}"'.format(install_image))

        shell = NormalSubShell(quiet=not debug)

        apptainer = SettingsManager.get_settings()['apptainer_cmd']

        cmd_queue = [SettingsManager.get_app_scriptEnv(), ]
        cmd_queue += [SettingsManager.get_settings()['default_fuse_lib_preload'], ]
        cmd_queue += [apptainer + ' pull "'+install_image+'"', ]
        cmd_queue += ['unset LD_PRELOAD', ]

        shell.run_queue(cmd_queue)

        del shell

        return image_size


    def buildSandbox(install_path, install_image, image_size, debug):

        SandboxInstaller.checkPathCapacity(install_path, image_size)

        appLogger.info('Building Sandbox at: "{}"'.format(install_path))

        shell = NormalSubShell(quiet=not debug)

        apptainer = SettingsManager.get_settings()['apptainer_cmd']

        cmd_queue  = [SettingsManager.get_app_scriptEnv(), ]
        cmd_queue += [SettingsManager.get_settings()['default_fuse_lib_preload'], ]
        cmd_queue += [apptainer + ' build --force --fix-perms --sandbox --fakeroot "'+install_path+'"  "'+install_image+'"', ]
        cmd_queue += ['unset LD_PRELOAD', ]

        shell.run_queue(cmd_queue)

        del shell

    def fixupSandbox(install_path):

        appLogger.info('Fixing Sandbox: "{}"'.format(install_path))

        for _folder in SettingsManager.get_settings()['bind_mount_paths']:

            _folder = './'+_folder

            bind_folder = os.path.join(install_path, _folder)

            if not os.path.exists(bind_folder):
                os.makedirs(bind_folder)

        app_conf_path = os.path.join(install_path, './etc/apt/apt.conf.d/')

        if os.path.exists(app_conf_path):

            fix_apt  = 'APT::Sandbox::User "root";\nAPT::Sandbox::Verify "0";\n'
            fix_apt += 'APT::Sandbox::Verify::IDs "0";\nAPT::Sandbox::Verify::Groups "0";\n'
            fix_apt += 'APT::Sandbox::Verify::Regain "0";'

            with open(os.path.join(app_conf_path, 'sandbox-disable')) as _file:
                _file.write(fix_apt)


        SandboxInstaller.build_activate_scripts(install_path)


class appBoxManager():

    def create_new_appenv(install_path, install_image, debug):

        if os.path.exists(install_path):
            appLogger.info('Found Container at "{}", skipping.'.format(install_path))
            return

        appLogger.info('appBox Apptainer Sandbox Installer')

        # Needed for CACHE/TMP folders
        SandboxInstaller.build_singularity_env(install_path)

        image_size = SandboxInstaller.pullImage(install_image, debug)

        SandboxInstaller.buildSandbox(install_path, install_image, image_size, debug)

        SandboxInstaller.fixupSandbox(install_path)

        appLogger.info('Installed')

    def build_env_script():

        return SettingsManager.get_app_scriptEnv()

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


    def getArgsParser():

        class BlankLinesHelpFormatter(argparse.HelpFormatter):
            def _split_lines(self, text, width):
                return super()._split_lines(text, width) + ['']

        parser = argparse.ArgumentParser(
                        prog='appBox', formatter_class=BlankLinesHelpFormatter,
                        description='This is a short tool to allow you to install a custom image like a "virtualenv".')

        default_root = SettingsManager.get_settings()['default_sandbox_path']

        parser.add_argument('-rc', '--run-command',
                            help='Run a given command inside a sandbox.')

        parser.add_argument('-rp', '--run-path',
                            help='Path to look for an installed image (extracted sandbox) to use as a run-environment.')

        parser.add_argument('-rcr', '--run-command-root',
                            help='Run a given command AS ROOT inside a sandbox.')

        parser.add_argument('-ri', '--run-interactive',
                            type=str, default=default_root,
                            help='Launch a sandbox shell from this location.')

        parser.add_argument('-rir', '--run-interactive-root',
                            type=str, default=default_root,
                            help='Launch a sandbox shell AS ROOT from this location.')

        default_image = SettingsManager.get_settings()['default_img']

        parser.add_argument('-ii', '--install-image',
                            default=default_image,
                            help='Image to install, or short-hand of image from "{} -li"'.format(sys.argv[0]))

        parser.add_argument('-ip', '--install-path',
                            default=default_root,
                            help='Install path, path to "install" an image to on disk. (The path that an image extracted to on disk)')

        parser.add_argument('-ra', '--run-after', action='store_true',
                            help='Should we drop into the new sandbox after installing.')

        parser.add_argument('-rar', '--run-after-root', action='store_true',
                            help='Should we drop into the new sandbox AS ROOT after installing.')

        parser.add_argument('-li', '--list-images', action='store_true',
                            help='List suggested images to "install".')

        parser.add_argument('-q', '--quiet', action='store_true',
                            help='Quiet')

        parser.add_argument('-d', '--debug', action='store_true',
                            help='Debugging on.')

        return parser


if __name__ == '__main__':

    parser = appBoxManager.getArgsParser()

    parsed_args = parser.parse_args(sys.argv[1:])

    if parsed_args.list_images:
        pprint.pprint(SettingsManager.get_settings()['default_mappings'])
        sys.exit(0)

    if not parsed_args.quiet:
        appBoxManager.header()

    if parsed_args.debug:
        appLogger.info('Debugging Enabled, Jolan tru.')
        logging.basicConfig(level=logging.DEBUG, format='%(message)s')

    if False:
        appBoxManager.start_interactive()

    else:

        this_image = SettingsManager.get_this_image(parsed_args.install_image)

        this_path = os.path.abspath(parsed_args.install_path)

        appBoxManager.create_new_appenv(this_path, this_image, parsed_args.debug)

        if parsed_args.run_after:
            _user_cmd = 'source '+os.path.join(parsed_args.install_path, 'bin/activate\n')
            appBoxManager.start_interactive(_user_cmd)
        elif parsed_args.run_after_root:
            _root_cmd = 'source '+os.path.join(parsed_args.install_path, 'bin/activate-asroot\n')
            appBoxManager.start_interactive(_root_cmd)

    sys.exit(0)

