import paramiko
import os
import argparse
from zipfile import ZipFile
from time import sleep

def createSSHClient(hostname, port, username, password = None):
    client= paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, port, username, password)
    return client

def ssh_login_silent(host, username = True, password = None):
    try:
        ssh = createSSHClient(hostname = host, port = 22, username = username)
        return ssh
    except (paramiko.AuthenticationException, paramiko.SSHException):
        return False

def command_lines(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    lines = stdout.read().decode("ascii").split("\n")[:-1]
    return lines

def mkdir_p(sftp, remote_path):
    if remote_path == "/":
        sftp.chdir("/")
        return
    if remote_path == "":
        return
    try:
        sftp.chdir(remote_path)
    except IOError:
        dirname = os.path.dirname(remote_path)
        basename = os.path.basename(remote_path)
        mkdir_p(sftp, dirname)
        sftp.mkdir(basename)
        sftp.chdir(basename)
        return True
    
def sftp_exists(sftp, path):
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False

def initialise(ssh, brm_dir):
    sftp = ssh.open_sftp()
    if not sftp_exists(sftp, brm_dir):
        mkdir_p(sftp, os.path.join(brm_dir))
        sftp.put(os.path.join(os.getcwd(), "common_files", "Batch-Manager-Remote.zip"), os.path.join(brm_dir, "Batch-Manager-Remote.zip"))
        sftp.close()
        stdin, stdout, stderr = ssh.exec_command(f"unzip {os.path.join(brm_dir, 'Batch-Manager-Remote.zip')} -d {brm_dir};"\
                                                 f"rm {os.path.join(brm_dir, 'Batch-Manager-Remote.zip')}")
        stdout.read()
parser = argparse.ArgumentParser(description = "Submit jobs without overloading Coulson")
parser.add_argument("-n", type = str, help = "Batch name", metavar = "zip_path", required = True)
parser.add_argument("-x", type = int, help = "Number of runs of batch", metavar = "num_runs", required = True)
parser.add_argument("-y", type = str, help = "Type of batch", metavar = "batch_type", required = True, choices = ["netmc", "triangle_raft"])
parser.add_argument("-p", type = str, help = "Local batch zip path", metavar = "local_batch_path", required = True)
parser.add_argument("-o", type = str, help = "Local ouput folder", metavar = "output_path", required = True)
parser.add_argument("-u", type = str, help = "Coulson Username", metavar = "username", required = True)
parser.add_argument("-c", type = str, help = "check_file_exists.sh path", metavar = "cfe_path", default = True)
args = parser.parse_args()

batch_name = args.n
num_runs = args.x
batch_type = args.y
local_batch_path = args.p
output_path = args.o
coulson_username = args.u
cfe_path = args.c

save_path = os.path.join(output_path, batch_type, batch_name, f"{batch_name}_run_{num_runs + 1}.zip")

ssh = ssh_login_silent("coulson.chem.ox.ac.uk", coulson_username)
sftp = ssh.open_sftp()
coulson_home = command_lines(ssh, "readlink -f ~/")[0]  
initialise(ssh, os.path.join(coulson_home, "Batch-Manager-Remote"))


coulson_run_path = os.path.join(coulson_home, "Batch-Manager-Remote", f"{batch_type}",f"{batch_name}", f"{batch_name}_run_{num_runs + 1}")
zip_path = f"{coulson_run_path}.zip"
mkdir_p(sftp, coulson_run_path)
sftp.put(local_batch_path, os.path.join(coulson_run_path, f"{batch_name}.zip"))
ssh.exec_command(f"python3 {os.path.join(coulson_home, 'Batch-Manager-Remote', 'remote_management', 'batch_submission_script.py')} "\
                 f"-p {coulson_run_path} -t {batch_type}")

if cfe_path:
    cfe_path = os.path.join(coulson_home, "Batch-Manager-Remote", "remote_management", "check_file_exists.sh")
while True:
    if command_lines(ssh, f"bash {cfe_path} {zip_path}")[0] == "True":
        break
    sleep(5)
try:
    os.makedirs(os.path.dirname(save_path))
except OSError:
    pass
sftp.get(zip_path, save_path)
sftp.remove(zip_path)
sftp.rmdir(os.path.dirname(zip_path))
ssh.close()
with ZipFile(save_path, "r") as run_zip:
    run_zip.extractall(os.path.join(os.path.dirname(save_path), f'run_{num_runs + 1}'))
os.remove(save_path)