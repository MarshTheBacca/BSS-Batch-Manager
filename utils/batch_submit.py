import paramiko
import argparse
from zipfile import ZipFile
from time import sleep
from pathlib import Path


def createSSHClient(hostname: str, port: str, username: str, password=None) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, port, username, password)
    return client


def ssh_login_silent(host: str, username=None, password=None):
    try:
        ssh = createSSHClient(hostname=host, port=22, username=username)
        return ssh
    except (paramiko.AuthenticationException, paramiko.SSHException):
        return False


def command_lines(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    lines = stdout.read().decode("ascii").split("\n")[:-1]
    return lines


def mkdir_p(sftp: paramiko.SFTPClient, remote_path: Path):
    if remote_path == "/":
        sftp.chdir("/")
        return
    if remote_path == "":
        return
    try:
        sftp.chdir(remote_path.as_posix())
    except IOError:
        dirname = remote_path.parent
        basename = remote_path.name
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
    if not sftp_exists(sftp, brm_dir.as_posix()):
        mkdir_p(sftp, brm_dir)
        sftp.put(Path.cwd().joinpath("common_files", "Batch-Manager-Remote.zip"), brm_dir.joinpath("Batch-Manager-Remote.zip").as_posix())
        sftp.close()
        stdin, stdout, stderr = ssh.exec_command(f"unzip {brm_dir.joinpath('Batch-Manager-Remote.zip')} -d {brm_dir};"
                                                 f"rm {brm_dir.joinpath('Batch-Manager-Remote.zip')}")
        stdout.read()


parser = argparse.ArgumentParser(description="Submit jobs without overloading Coulson")
parser.add_argument("-n", type=str, help="Batch name", metavar="zip_path", required=True)
parser.add_argument("-x", type=int, help="Number of runs of batch", metavar="num_runs", required=True)
parser.add_argument("-y", type=str, help="Type of batch", metavar="batch_type", required=True, choices=["netmc", "triangle_raft"])
parser.add_argument("-p", type=str, help="Local batch zip path", metavar="local_batch_path", required=True)
parser.add_argument("-o", type=str, help="Local ouput folder", metavar="output_path", required=True)
parser.add_argument("-u", type=str, help="Coulson Username", metavar="username", required=True)
args = parser.parse_args()

batch_name = args.n
num_runs = args.x
batch_type = args.y
local_batch_path = Path(args.p)
output_path = Path(args.o)
coulson_username = args.u

save_path = output_path.joinpath(batch_type, batch_name, f"{batch_name}_run_{num_runs + 1}.zip")

ssh = ssh_login_silent("coulson.chem.ox.ac.uk", coulson_username)
sftp = ssh.open_sftp()
coulson_home_path = Path(command_lines(ssh, "readlink -f ~/")[0])
initialise(ssh, coulson_home_path.joinpath("Batch-Manager-Remote"))

coulson_run_path = coulson_home_path.joinpath("Batch-Manager-Remote", f"{batch_type}", f"{batch_name}",
                                              f"{batch_name}_run_{num_runs + 1}")
zip_path = f"{coulson_run_path}.zip"
mkdir_p(sftp, coulson_run_path)
sftp.put(local_batch_path, Path(coulson_run_path).joinpath(f"{batch_name}.zip").as_posix())
ssh.exec_command(f"python3 {coulson_home_path.joinpath('Batch-Manager-Remote', 'remote_management', 'batch_submission_script.py')} "
                 f"-p {coulson_run_path} -t {batch_type}")
cfe_path = coulson_home_path.joinpath("Batch-Manager-Remote", "remote_management", "check_file_exists.sh").as_posix()
while True:
    if command_lines(ssh, f"bash {cfe_path} {zip_path}")[0] == "True":
        break
    sleep(5)

save_path.parent.mkdir(parents=True, exist_ok=True)
sftp.get(zip_path, save_path)
sftp.remove(zip_path)
sftp.rmdir(Path(zip_path).parent.as_posix())
ssh.close()
with ZipFile(save_path, "r") as run_zip:
    run_zip.extractall(save_path.parent.joinpath(f'run_{num_runs + 1}'))
save_path.unlink(missing_ok=True)
