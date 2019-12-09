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
''' This module provides the classes for actually adding or removing
files of a virtual install location.  '''

# ========================================================================
# Dependencies
# ------------------------------------------------------------------------

import sys, os, os.path, shutil, stat, re

from WebappConfig.debug    import OUT

# ========================================================================
# Helper functions
# ------------------------------------------------------------------------

def all(boolean):
    ''' Replacement for reduce() '''
    for i in boolean:
        if not i:
            return False
    return True

# ========================================================================
# Worker class
# ------------------------------------------------------------------------

class WebappRemove:
    '''
    This is the handler for removal of web applications from their virtual
    install locations.
    '''

    def __init__(self,
                 content,
                 verbose,
                 pretend):

        self.__content = content
        self.__v       = verbose
        self.__p       = pretend

    def remove_dirs(self):
        '''
        It is time to remove the dirs that we installed originally.
        '''

        OUT.debug('Trying to remove directories', 6)

        success = [self.remove(i) for i in self.__content.get_directories()]

        # Tell the caller if anything was left behind

        return all(success)

    def remove_files(self):
        '''
        It is time to remove the files that we installed originally.
        '''

        OUT.debug('Trying to remove files', 6)

        success = [self.remove(i) for i in self.__content.get_files()]

        # Tell the caller if anything was left behind

        return all(success)

    def remove(self, entry):
        '''
        Decide whether to delete something - and then go ahead and do so

        Just like portage, we only remove files that have not changed
        from when we installed them.  If the timestamp or checksum is
        different, we leave the file in place.

        Inputs

          entry    - file/dir/sym to remove
        '''

        OUT.debug('Trying to remove file', 6)

        # okay, deal with the file | directory | symlink

        removeable = self.__content.get_canremove(entry)

        if not removeable:

            # Remove directory or file.

            # Report if we are only pretending
            if self.__p:
                OUT.info('    pretending to remove: ' + entry)

            # try to remove the entry
            try:
                entry_type = self.__content.etype(entry)
                if self.__content.etype(entry) == 'dir':
                    # its a directory -> rmdir
                    if not self.__p:
                        os.rmdir(entry)
                else:
                    # its a file -> unlink
                    if not self.__p:
                        os.unlink(entry)
            except:
                # Report if there is a problem
                OUT.notice('!!!      '
                           + self.__content.epath(entry))
                return

            if self.__v and not self.__p:
                # Report successful deletion

                OUT.notice('<<< ' + entry_type + ' '
                           * (5 - len(entry_type))
                           + self.__content.epath(entry))

            self.__content.delete(entry)

            return True

        else:

            OUT.notice(removeable)

            return False


class WebappAdd:
    '''
    This is the class that handles the actual transfer of files from
    the web application source directory to the virtual install location.
    '''

    def __init__(self,
                 source,
                 destination,
                 permissions,
                 handler,
                 flags):

        self.__sourced   = source
        self.__destd     = destination
        self.__perm      = permissions
        self.__ws        = handler['source']
        self.__content   = handler['content']
        self.__remove    = handler['removal']
        self.__protect   = handler['protect']
        self.__link_type = flags['linktype']
        self.__relative  = flags['relative']
        self.__u         = flags['upgrade']
        self.__v         = flags['verbose']
        self.__p         = flags['pretend']

        self.config_protected_dirs = []

        os.umask(0)

    def mkdirs(self, directory = '', current_type = ''):
        '''
        Create a set of directories

        Inputs

        directory   - the directory within the source hierarchy
        '''

        sd = self.__sourced + '/' + directory
        real_dir = re.compile('/+').sub('/',
                self.__ws.appdir()
                + '/' + self.__sourced
                + '/' + directory)

        OUT.debug('Creating directories', 6)

        if not self.__ws.source_exists(sd):

            OUT.warn(self.__ws.package_name()
                     + ' does not install any files from '
                     + real_dir + '; skipping')
            return

        OUT.info('    Installing from ' + real_dir)

        for i in self.__ws.get_source_directories(sd):

            OUT.debug('Handling directory', 7)

            # create directory first
            next_type = self.mkdir(directory + '/' + i, current_type)

            # then recurse into the directory
            self.mkdirs(directory + '/' + i, next_type)

        for i in self.__ws.get_source_files(sd):

            OUT.debug('Handling file', 7)

            # handle the file
            self.mkfile(directory + '/' + i, current_type)


    def mkdir(self, directory, current_type):
        '''
        Create a directory with the correct ownership and permissions.

        directory   - name of the directory
        '''
        src_dir = self.__sourced + '/' + directory
        dst_dir = self.__destd + '/' + directory

        OUT.debug('Creating directory', 6)

        # some special cases
        #
        # these should be triggered only if we are trying to install
        # a webapp into a directory that already has files and dirs
        # inside it

        if os.path.exists(dst_dir) and not os.path.isdir(dst_dir):
            # something already exists with the same name
            #
            # in theory, this should automatically remove symlinked
            # directories

            OUT.warn('    ' + dst_dir + ' already exists, but is not a di'
                     'rectory - removing')
            if not self.__p:
                os.unlink(dst_dir)

        dirtype = self.__ws.dirtype(src_dir, current_type)

        OUT.debug('Checked directory type', 8)

        (user, group, perm) = self.__perm['dir'][dirtype]

        dsttype = 'dir'

        if not os.path.isdir(dst_dir):

            OUT.debug('Creating directory', 8)

            if not self.__p:
                os.makedirs(dst_dir, perm(0o755))

                os.chown(dst_dir,
                         user,
                         group)

        self.__content.add(dsttype,
                           dirtype,
                           self.__destd,
                           directory,
                           directory,
                           self.__relative)

        return dirtype

    def mkfile(self, filename, current_type):
        '''
        This is what we are all about.  No more games - lets take a file
        from the master image of the web-based app, and make it available
        inside the install directory.

        filename    - name of the file

        '''

        OUT.debug('Creating file', 6)

        dst_name  = self.__destd + '/' + filename
        file_type = self.__ws.filetype(self.__sourced + '/' + filename, current_type)

        OUT.debug('File type determined', 7)

        # are we overwriting an existing file?

        OUT.debug('Check for existing file', 7)

        if os.path.exists(dst_name):

            OUT.debug('File in the way!', 7)

            my_canremove = True

            # o-oh - we're going to be overwriting something that already
            # exists

            # If we are upgrading, check if the file can be removed
            if self.__u:
                my_canremove = self.__remove.remove(self.__destd, filename)
            # Config protected file definitely cannot be removed
            elif file_type[0:6] == 'config':
                my_canremove = False

            if not my_canremove:
                # not able to remove the file
                #           or
                # file is config-protected

                dst_name = self.__protect.get_protectedname(self.__destd,
                                                            filename)
                OUT.notice('^o^ hiding ' + filename)
                self.config_protected_dirs.append(self.__destd + '/' 
                                                  + os.path.dirname(filename))

                OUT.debug('Hiding config protected file', 7)

            else:

                # it's a file we do not know about - so get rid
                # of it anyway
                #
                # this behaviour here *is* by popular request
                # personally, I'm not comfortable with it -- Stuart

                if not self.__p:
                    if os.path.isdir(dst_name):
                        os.rmdir(dst_name)
                    else:
                        os.unlink(dst_name)
                else:
                    OUT.info('    would have removed "' +  dst_name + '" s'
                             'ince it is in the way for the current instal'
                             'l. It should not be present in that location'
                             '!')


        # if we get here, we can get on with the business of making
        # the file available

        (user, group, perm) = self.__perm['file'][file_type]
        my_contenttype = ''

        src_name = self.__ws.appdir() + '/' + self.__sourced + '/' + filename

        # Fix the paths
        src_name = re.compile('/+').sub('/', src_name)
        dst_name = re.compile('/+').sub('/', dst_name)

        OUT.debug('Creating File', 7)

        # this is our default file type
        #
        # we link in (soft and hard links are supported)
        # if we're allowed to
        #
        # some applications (/me points at PHP scripts)
        # won't run if symlinked in.
        # so we now support copying files in too
        #
        # default behaviour is to hard link (if we can), and
        # to copy if we cannot
        #
        # if the user wants symlinks, then the user has to
        # use the new '--soft' option

        if file_type == 'virtual' or os.path.islink(src_name):

            if self.__link_type == 'soft':
                try:

                    OUT.debug('Trying to softlink', 8)

                    if not self.__p:
                        if self.__v:
                            print("\n>>> SOFTLINKING FILE: ")
                            print(">>> Source: " + src_name +
                                  "\n>>> Destination: " + dst_name + "\n")
                        os.symlink(src_name, dst_name)

                    my_contenttype = 'sym'

                except Exception as e:

                    if self.__v:
                        OUT.warn('Failed to softlink (' + str(e) + ')')

            elif self.__link_type == 'copy':
                try:

                    OUT.debug('Trying to copy files directly', 8)

                    if not self.__p:
                        if self.__v:
                            print("\n>>> COPYING FILE: ")
                            print(">>> Source: " + src_name +
                                  "\n>>> Destination: " + dst_name + "\n")
                        shutil.copy(src_name, dst_name)

                    my_contenttype = 'file'

                except Exception as e:

                    if self.__v:
                        OUT.warn('Failed to copy (' + str(e) + ')')

            elif os.path.islink(src_name):
                try:

                    OUT.debug('Trying to copy symlink', 8)

                    if not self.__p:
                        if self.__v:
                            print("\n>>> SYMLINK COPY: ")
                            print(">>> Source: " + src_name +
                                  "\n>>> Destination: " + dst_name + "\n")
                        os.symlink(os.readlink(src_name), dst_name)

                    my_contenttype = 'sym'

                except Exception as e:

                    if self.__v:
                        OUT.warn('Failed copy symlink (' + str(e) + ')')

            else:
                try:

                    OUT.debug('Trying to hardlink', 8)

                    if not self.__p:
                        if self.__v:
                            print("\n>>> HARDLINKING FILE: ")
                            print(">>> Source: " + src_name +
                                  "\n>>> Destination: " + dst_name + "\n")
                        os.link(src_name, dst_name)

                    my_contenttype = 'file'

                except Exception as e:

                    if self.__v:
                        OUT.warn('Failed to hardlink (' + str(e) + ')')

        if not my_contenttype:

            if not self.__p:
                if self.__v:
                    print("\n>>> COPYING FILE: ")
                    print(">>> Source: " + src_name +
                          "\n>>> Destination: " + dst_name + "\n")
                shutil.copy(src_name, dst_name)
            my_contenttype = 'file'


        if not self.__p and not os.path.islink(src_name):

            old_perm =  os.stat(src_name)[stat.ST_MODE] & 511

            os.chown(dst_name,
                     user,
                     group)

            os.chmod(dst_name,
                     perm(old_perm))

        self.__content.add(my_contenttype,
                           file_type,
                           self.__destd,
                           filename,
                           dst_name,
                           self.__relative)

        return file_type
