#!/usr/bin/python -O
#
# /usr/sbin/webapp-config
#       Python script for managing the deployment of web-based
#       applications
#
#       Originally written for the Gentoo Linux distribution
#
# Copyright (c) 1999-2007 Authors
#       Released under v2 of the GNU GPL
#
# ========================================================================

# ========================================================================
# Dependencies
# ------------------------------------------------------------------------

import os, os.path, re, shutil, subprocess, tempfile

from WebappConfig.debug     import OUT

# ========================================================================
# Constants
# ------------------------------------------------------------------------

MAKE_CONF_FILE = ['/etc/make.conf', '/etc/portage/make.conf']

# ========================================================================
# SELinux handler
# ------------------------------------------------------------------------

class SELinux:

    def __init__(self, package_name, vhost_hostname, policy_types = ()):
        self.package_name = package_name
        self.vhost_hostname = vhost_hostname
        self.policy_name = '{}_{}'.format(package_name, vhost_hostname)
        self.policy_types = policy_types
        if not self.policy_types:
            for filename in MAKE_CONF_FILE:
                try:
                    with open(filename) as file:
                        for line in file.readlines():
                            if line.startswith('POLICY_TYPES='):
                                self.policy_types = line[len('POLICY_TYPES='):-1].strip(' "').split()
                                break
                        if self.policy_types is not None:
                            break
                except IOError:
                    pass
            if not self.policy_types:
                 OUT.die('No SELinux policy was found, abording')

    def remove_module(self):
        OUT.info('Removing SELinux modules')
        for policy in self.policy_types:
            if subprocess.call(['semodule', '-s', policy, '-r', self.policy_name]):
                OUT.warn('Unable to remove {} SELinux module for {} @ {}'.format(policy, self.package_name, self.vhost_hostname))

    def create_module(self, package_version, vhost_root, server_files, server_dirs):
        temp_dir = tempfile.mkdtemp()
        OUT.info('Creating SELinux modules')
        cleaned_version = re.match(r'(?P<version>[0-9]*\.[0-9]*(?:\.[0-9]*)?)', package_version).group('version')
        for policy in self.policy_types:
            base_dir = os.path.join(temp_dir, policy)
            os.mkdir(base_dir)
            with open(os.path.join(base_dir, '{}.te'.format(self.policy_name)), 'w') as te_file:
                te_file.write('policy_module({},{})\n'.format(self.policy_name, cleaned_version))
                te_file.write('require {\n')
                te_file.write('  type httpd_sys_rw_content_t;\n')
                te_file.write('}')
            with open(os.path.join(base_dir, '{}.fc'.format(self.policy_name)), 'w') as fc_file:
                for files in server_files:
                    fc_file.write('{} gen_context(system_u:object_r:httpd_sys_rw_content_t,s0)\n'.format(SELinux.filename_re_escape(os.path.join(vhost_root, files.rstrip('\n')))))
                for dirs in server_dirs:
                    fc_file.write('{}(/.*)? gen_context(system_u:object_r:httpd_sys_rw_content_t,s0)\n'.format(SELinux.filename_re_escape(os.path.join(vhost_root, dirs.rstrip('\n')))))
            if subprocess.call(['make', '-s', '-C', base_dir, '-f', os.path.join('/usr/share/selinux', policy, 'include/Makefile'), '{}.pp'.format(self.policy_name)]):
                if not os.path.isfile(os.path.join('/usr/share/selinux', policy, 'include/Makefile')):
                    OUT.die('Policy {} is not supported, please fix your configuration'.format(policy))
                OUT.die('Unable to create {} SELinux module for {} @ {}'.format(policy, self.package_name, self.vhost_hostname))
        OUT.info('Installing SELinux modules')
        try:
            for policy in self.policy_types:
                if subprocess.call(['semodule', '-s', policy, '-i', os.path.join(temp_dir, policy, '{}.pp'.format(self.policy_name))]):
                    OUT.die('Unable to install {} SELinux module for {} @ {}'.format(policy, self.package_name, self.vhost_hostname))
        except IOError:
            OUT.die('"semodule" was not found, please check you SELinux installation')
        shutil.rmtree(temp_dir)

    @staticmethod
    def filename_re_escape(string):
        return re.sub('\.', '\.', string)
