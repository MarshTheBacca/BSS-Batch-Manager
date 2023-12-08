import os
from stat import S_ISREG

from .ssh_utils import command_lines

def linux_path_converter(path):
    problematic_chars = ("^", "(", ")")
    return_path = ""
    for char in path:
        if char in problematic_chars:
            return_path += "\\"+char
        else:
            return_path += char
    return return_path

def mkdir_p(sftp, remote_path):
    #Change to this path, recursively making new folders if needed.
    #Returns True if any folders were created.
    
    if remote_path == "/":
        # absolute path so change directory to root
        sftp.chdir("/")
        return
    if remote_path == "":
        # top-level relative directory must exist
        return
    try:
        sftp.chdir(remote_path) # sub-directory exists
    except IOError:
        dirname, basename = os.path.split(remote_path.rstrip("/"))
        mkdir_p(sftp, dirname) # make parent directories
        sftp.mkdir(basename) # sub-directory missing, so created it
        sftp.chdir(basename)
        return True
    
def import_files(sftp, remote_path, local_path):
    files = []
    for element in sftp.listdir_attr(remote_path):
        mode = element.st_mode
        if S_ISREG(mode):
            files.append(element.filename)
    for file in files:
        local_file_path = os.path.join(local_path,file)
        remote_file_path = os.path.join(remote_path,file)
        sftp.get(remote_file_path, local_file_path)
        
def put_dir(sftp, source, target):
    ''' Uploads the contents of the source directory to the target path. The
        target directory needs to exists. All subdirectories in source are 
        created under target.
    '''
    for item in os.listdir(source):
        if os.path.isfile(os.path.join(source, item)):
            sftp.put(os.path.join(source, item), '%s/%s' % (target, item))
        else:
            sftp.mkdir('%s/%s' % (target, item), ignore_existing=True)
            sftp.put_dir(os.path.join(source, item), '%s/%s' % (target, item))
            
def crop_paths(paths):
    del_path=os.path.commonpath(paths)
    return_array=(os.path.relpath(path,del_path) for path in paths)
    return return_array

def fast_scandir(dirname):
    subfolders = [f.path for f in os.scandir(dirname) if f.is_dir()]
    for dirname in subfolders:
        subfolders.extend(fast_scandir(dirname))
    return subfolders

def remote_fast_scandir(ssh, path_pattern):
    lines = command_lines(ssh, f"find ~+ . -type d -path {path_pattern}")
    remote_paths = [path for path in lines if path[0] != "."]
    return remote_paths

def initialise(cwd):
    required_dirs = (os.path.join(cwd, "output_files", "netmc"), os.path.join(cwd, "output_files", "triangle_raft"),
                            os.path.join(cwd, "batches", "netmc"), os.path.join(cwd, "batches", "triangle_raft"))
    required_files = ((os.path.join(cwd, "batch_history.txt")),)
    for directory in required_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)
    for file in required_files:
        if not os.path.exists(file):
            open(file, "a").close()
            
        