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
# Author(s)     Stuart Herbert
#               Renat Lumpau   <rl03@gentoo.org>
#               Gunnar Wrobel  <wrobel@gentoo.org>
#
# ========================================================================
''' A class that returns the file type for a given path.'''

# ========================================================================
# Dependencies
# ------------------------------------------------------------------------

import re

from WebappConfig.debug     import OUT

# ========================================================================
# Handler for File Types
# ------------------------------------------------------------------------

class FileType:
    '''
    A helper class to determine file and directory types.

    The file type is determined based on two initial lists:

    - a list of all files and directories owned by the config user
    - a list of all files and directories owned by the server user
    '''

    def __init__(self,
                 config_owned,
                 server_owned,
                 server_owned_r,
                 virtual_files = 'virtual',
                 default_dirs  = 'default-owned'):
        '''
        Populates the cache with the file types as provided by the
        ebuild.
        '''

        self.__cache = {}

        # Validity of entries are checked by the command line parser
        self.__virtual_files = virtual_files
        self.__default_dirs  = default_dirs

        # populate cache
        for i in config_owned:

            OUT.debug('Adding config-owned file', 8)

            self.__cache[self.__fix(i)] = 'config-owned'

        for i in server_owned:

            if self.__fix(i) in list(self.__cache.keys()):

                OUT.debug('Adding config-server-owned file', 8)

                self.__cache[self.__fix(i)] = 'config-server-owned'

            else:

                OUT.debug('Adding server-owned file', 8)

                self.__cache[self.__fix(i)] = 'server-owned'

        for i in server_owned_r:

            if self.__fix(i) in self.__cache.keys():

                OUT.die('{} is a the same time recursively server-owned and {}: This case is not supported.'.format(self.__fix(i), self.__cache[self.__fix(i)]))

            else :

                OUT.debug('Adding recursively server-owned file', 8)

                self.__cache[self.__fix(i).strip()] = 'server-owned-dir'


    def filetype(self, filename, parent_type = ''):
        '''
        Inputs:

          filename      - the file that we need a decision about

          parent_type  - the type of the parent directory

        returns one of these:

          server-owned         - file needs to be owned by the webserver user
                                 (and needs to be a local copy)
          config-owned         - file needs to be owned by the config user
                                 (and needs to be a local copy)
          config-server-owned  - Both the previous cases at the same time
          virtual              - we do not need a local copy of the file

        NOTE:
          Use get_dirtype(directory) for directories

        NOTE:
          the user can use --virtual-files on the command-line to change
          what type virtual files are really reported as
        '''

        # remove any whitespace and trailing /
        filename = self.__fix(filename)

        # look for config-protected files in the cache
        if filename in list(self.__cache.keys()):
            # Check if parent type is recursive
            if parent_type == 'server-owned-dir':
                new_type = self.__cache[filename]
                if new_type == 'config-owned':
                    return 'config-server-owned'
                if new_type == 'server-owned':
                    OUT.warn('Configuration error: {} is marked server-owned twice'.format(filename))
                return 'server-owned'
            return self.__cache[filename]

        # Check if parent type is recursive
        if parent_type == 'server-owned-dir':
            return 'server-owned'
        # unspecified file (and thus virtual)
        return self.__virtual_files

    def dirtype(self, directory, parent_type = ''):
        '''
        Inputs:

          directory     - the directory that we need a decision about

          parent_type  - the type of the parent directory

        returns one of these:

          server-owned         - dir needs to be owned by the webserver user
          config-owned         - dir needs to be owned by the config user
          config-server-owned  - Both the previous cases at the same time
          server-owned-dir     - Directory that contains file/dirs to be owned
                                 by the webserver user
          default-owned        - we need a local copy, owned by root

        NOTE:
          Use get_filetype(filename) for files

        NOTE:
          the user can use --default-dirs on the command-line to change
          what type default directories are really reported as
        '''

        # remove any whitespace and trailing /
        directory = self.__fix(directory)

        # check the cache
        if directory in list(self.__cache.keys()):
            # Check if parent type is recursive
            if parent_type == 'server-owned-dir':
                new_type = self.__cache[directory]
                if new_type == 'config-owned':
                    OUT.die('This version does not support config dirs')
                if new_type == server-owned:
                    OUT.warn('Configuration error: {} is marked server-owned two times'.format(filename))
                return 'server-owned-dir'
            return self.__cache[directory]

        # Check if parent type is recursive
        if parent_type == 'server-owned-dir':
            return 'server-owned-dir'
        # unspecified directories are default-owned
        return self.__default_dirs

    def __fix(self, filename):
        ''' Removes trailing slash and whitespace from a path '''
        filename = filename.strip()
        while filename[-1] == '/':
            filename = filename[:-1]

        # Fix double slashes
        filename = re.compile('/+').sub('/', filename) 

        return filename
