#!/usr/bin/env python3

import os
import shutil
import yaml
import configparser

class Builder:

    def __init__( self ):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        manifest = self._load_yaml('projects.yaml')
        self.projects = manifest['projects']
        self.zip = self.config.get('build', 'zip')
        self.system = self.config.get('build', 'sys')

        self.tools_path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__))))
        self.root_path = os.path.abspath(os.path.join(self.tools_path, os.pardir))

        self.output_path = os.path.join(self.root_path, 'build')
        self.source_path = os.path.join(self.root_path, 'projects')

        # travel path one up
        os.chdir(self.root_path)

        for proj in self.projects:
            print('Project : ' + proj['name'])
            print('')
            # Clone the project
            result = self._git_project(proj)
            if not result:
                continue
            # Build the project
            result = self._build_project(proj)
            if not result:
                continue
            print("Successfully processed project {name}".format(name=proj['name']))
            print('')

    def _load_yaml( self, file_name):
        with open(file_name, 'r') as manifest_file:
            try:
                result = yaml.load(manifest_file, Loader=yaml.FullLoader)
            except yaml.YAMLError as e:
                print("ERROR: Failed to load YAML manifest {}: {{".format(file_name, e))
                return None
        return result

    def _git_project( self, project ):
        # Extract our name and type
        project_name = project['name']
        project_type = project['type']
        project_git = project['git']
        project_url = project['url']
        project_tag = project['tag']
        dtype = os.path.join(self.source_path, project_type)
        dname = os.path.join(self.source_path, project_type, project_name)
        if not os.path.isdir(dname):
            project_git = 'clone'
        if project_git == 'clone':
            if os.path.isdir(dname):
                self._delete_dirs(dname)
            if not os.path.isdir(dtype):
                os.makedirs(dtype)
            os.chdir(dtype)
            result = self._clone_git(project_name, project_url)
            if project_tag != 'none':
                os.chdir(dname)
                result = self._checkout_git(project_name, project_tag)
        elif project_git == 'clean':
            os.chdir(dname)
            self._clean_git(project_name)
        else:
            os.chdir(dname)
            self._clean_git(project_name, reset=False)
        return result

    def _build_project( self, project ):
        # Extract our name and type
        project_name = project['name']
        project_type = project['type']
        result = False
        dname = os.path.join(self.output_path, project_type, project_name)
        self._delete_dirs(dname)
        # Build the project
        print("Building project '{name}'".format(name=project_name))
        if project['type'] == 'plugins':
            result = self._build_plugin(project)
        elif project['type'] == 'server':
            result = self._build_server(project)
        elif project['type'] == 'utils':
            result = self._build_plugin(project)
        else:
            print("ERROR: Invalid project type.")
            print('')
        return result

    def _build_server( self, project ):
        # Extract our name and type
        project_name = project['name']
        project_type = project['type']
        result = True
        try:
            if project_name == 'jellyfin-web':
                self._web_build(project_type, project_name)
            else:
                self._dotnet_build(project_type, project_name)
        except Exception as e:
            print("ERROR: Failed build project {name}: {err}".format(name=project_name, err=e))
            print('')
            return False
        return result

    def _build_plugin( self, project ):
        # Extract our name and type
        project_name = project['name']
        project_type = project['type']
        result = True
        try:
            self._dotnet_build(project_type, project_name, '', False)
        except Exception as e:
            print("ERROR: Failed build project {name}: {err}".format(name=project_name, err=e))
            print('')
            return False
        return result

    def _clone_git( self, pname, purl ):
        print("Cloning project '{name}'".format(name=pname))
        gitname = 'https://{url}'.format(url=purl)
        if not os.path.isdir(pname):
            try:
                os.system('git clone ' + gitname)
            except Exception as e:
                print("ERROR: Failed to clone project {name}: {err}".format(name=pname, err=e))
                print('')
                return False
        else:
            print("Project is already cloned.")
        print('')
        return True

    def _checkout_git( self, pname, pvers ):
        print("Checkout project '{name}' to version '{version}'".format(name=pname, version=pvers))
        try:
            os.system('git checkout tags/{} -b branch_{}'.format(pvers, pvers))
        except Exception as e:
            print("ERROR: Failed to checkout project {name}: {err}".format(name=pname, err=e))
            print('')
            return False
        print('')
        return True

    def _clean_git( self, pname, reset=True):
        print("Clean project '{name}'".format(name=pname))
        try:
            os.system('git clean -fx')
            if reset:
                os.system('git reset --hard HEAD')
        except Exception as e:
            print("ERROR: Failed to clean project {name}: {err}".format(name=pname, err=e))
            print('')
            return False
        print('')
        return True
        pass

    def _zip_project( self, ptype ):
        pass

    def _get_plugin_name_dir( self, pname ):
        return pname.split('-')[2].capitalize()

    def _web_build( self, ptype, pname ):
        dsource = os.path.join(self.source_path, ptype, pname)
        os.chdir(dsource)
        print("Install yarn for '{name}'".format(name=pname))
        print('')
        os.system('yarn install')

    def _dotnet_build( self, ptype, pname, proot='Jellyfin.Server', server=True):
        dsource = os.path.join(self.source_path, ptype, pname)
        os.chdir(dsource)
        nname = pname
        #Pre Build
        if server:
            print("Copy '{name}'".format(name=pname + '-web'))
            print('')
            src_web = os.path.join(self.source_path, ptype, pname + '-web', 'dist')
            dst_web = os.path.join(self.source_path, ptype, pname, 'MediaBrowser.WebDashboard', pname + '-web')
            self._copy_files(src_web,dst_web)
            print("Build '{name}'".format(name=pname))
            print('')
            cmd = 'dotnet {action} --configuration {type} {root}'.format(action = 'build', type='Release', root=proot)
            os.system(cmd)
        else:
            if os.path.exists('build.yaml'):
                build = self._load_yaml('build.yaml')
                nname = build['nicename']
            else:
                nname = self._get_plugin_name_dir(pname)
        #Build
        print("Publish '{name}'".format(name=pname))
        print('')
        doutput = os.path.join(self.output_path, ptype, nname)
        if len(doutput.split(' '))>1:
            doutput = '"' + doutput + '"'
        cmd = 'dotnet {action} --configuration {type} {root} --output {output}'.format(action = 'publish', type='Release', root=proot, output=doutput)
        os.system(cmd)
        #Clean Build
        if server:
            self._clean_runtimes(self.system)
        else:
            bfiles = []
            bfiles.append('Jellyfin.Plugin.{name}.dll'.format(name = self._get_plugin_name_dir(pname)))
            if os.path.exists('build.yaml'):
                build = self._load_yaml('build.yaml')
                bfiles = build['artifacts']
                for fn in os.listdir(os.path.join(self.output_path, ptype, nname)):
                    if fn not in bfiles:
                        os.remove(os.path.join(self.output_path, ptype, nname, fn))

    def _clean_runtimes( self, par ):
        druntime = os.path.join(self.output_path, 'server', 'jellyfin', 'runtimes')
        for fn in os.listdir(druntime):
            if (not fn.startswith( par )):
                self._delete_dirs(os.path.join(druntime, fn))

    def _copy_files( self, src, dst ):
        if os.path.exists(src):
            shutil.copytree(os.path.abspath(src), os.path.abspath(dst))

    def _delete_dirs( self, dir ):
        if os.path.isdir(dir):
            os.system('rm -rf ' + dir)

if ( __name__ == '__main__' ):
    # start
    Builder()