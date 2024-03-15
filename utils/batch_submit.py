import paramiko
import argparse
from zipfile import ZipFile
from time import sleep
from pathlib import Path
from typing import Optional


def create_ssh_client(hostname: str, port: str, username: str) -> paramiko.SSHClient:
    """
    Creates an ssh client object and connects to the remote server

    Args:
        hostname: The hostname of the remote server
        port: The port of the remote server
        username: The username to login with
    Returns:
        An ssh object
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=hostname, port=port, username=username)
    return client


def ssh_login_silent(hostname_arg: str, username: Optional[str] = None) -> paramiko.SSHClient:
    """
    Attempts to login to a remote server using the given hostname and username
    If the login is successful, returns the ssh object

    Args:
        hostname_arg: The hostname of the remote server
        username: The username to login with
    Raises:
        paramiko.AuthenticationException: If the login is unsuccessful
    Returns:
        An ssh object if the login is successful
    """
    try:
        ssh = create_ssh_client(hostname=hostname_arg, port="22", username=username)
        return ssh
    except (paramiko.AuthenticationException, paramiko.SSHException):
        raise paramiko.AuthenticationException(f"Could not login to {hostname_arg} with username {username}")


def command_lines(ssh, command: str) -> list[str]:
    """
    Executes a command on the remote server

    Args:
        ssh: An open ssh connection
        command: The command to be executed
    Returns:
        A list of the lines of the output
    """
    _, stdout, _ = ssh.exec_command(command)
    lines = stdout.read().decode("ascii").split("\n")[:-1]
    return lines


def mkdir_p(sftp: paramiko.SFTPClient, remote_path: Path) -> None:
    """
    Makes a directory and all parent directories on the remote server

    Args:
        sftp: An open sftp connection
        remote_path: The path to the directory to be made
    Raises:
        IOError: If the directory could not be made
    Returns:
        None
    """
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
        try:
            sftp.mkdir(basename)
            sftp.chdir(basename)
        except IOError:
            raise IOError(f"Could not make remote directory {remote_path}, check permissions")


def sftp_exists(sftp, path: Path) -> bool:
    """
    Checks if a file or directory exists on the remote server
    returns True if it does, False if it does not
    """
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def initialise(ssh, brm_dir: Path) -> None:
    """
    Checks if Batch-Manager-Remote exists on the remote server.
    If it does not, it copies over the Batch-Manager-Remote and unzips it
    """
    sftp = ssh.open_sftp()
    if not sftp_exists(sftp, brm_dir.as_posix()):
        print("Batch-Manager-Remote did not exist. Copying over...")
        mkdir_p(sftp, brm_dir)
        sftp.put(Path.cwd().joinpath("common_files", "Batch-Manager-Remote.zip"), brm_dir.joinpath("Batch-Manager-Remote.zip").as_posix())
        sftp.close()
        _, stdout, _ = ssh.exec_command(f"unzip {brm_dir.joinpath('Batch-Manager-Remote.zip')} -d {brm_dir};"
                                        f"rm {brm_dir.joinpath('Batch-Manager-Remote.zip')}")
        stdout.read()
        print("Copy successful")
        return
    print("Batch-Manager-Remote already exists")


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

print("Args parsed")
save_path = output_path.joinpath(batch_type, batch_name, f"{batch_name}_run_{num_runs + 1}.zip")
print("Connecting to Coulson")
ssh = ssh_login_silent("coulson.chem.ox.ac.uk", coulson_username)
sftp = ssh.open_sftp()
print("Connection Successful")
coulson_home_path = Path(command_lines(ssh, "readlink -f ~/")[0])
print("Checking for Batch-Manager-Remote in home directory")
initialise(ssh, coulson_home_path.joinpath("Batch-Manager-Remote"))

coulson_run_path = coulson_home_path.joinpath("Batch-Manager-Remote", f"{batch_type}", f"{batch_name}",
                                              f"{batch_name}_run_{num_runs + 1}")
zip_path = Path(f"{coulson_run_path}.zip").as_posix()
print("Transferring batch zip to Coulson")
mkdir_p(sftp, coulson_run_path)
sftp.put(local_batch_path, coulson_run_path.joinpath(f"{batch_name}.zip").as_posix())
print("Executing remote python script")
ssh.exec_command(f"python3 {coulson_home_path.joinpath('Batch-Manager-Remote', 'remote_management', 'batch_submission_script.py').as_posix()} "
                 f"-p {coulson_run_path.as_posix()} -t {batch_type}")
cfe_path = coulson_home_path.joinpath("Batch-Manager-Remote", "remote_management", "check_file_exists.sh").as_posix()
print(f"Checking for output zip at\n{zip_path}")
while True:
    if command_lines(ssh, f"bash {cfe_path} {zip_path}")[0] == "True":
        print("Zip found")
        break
    print("Zip not found")
    sleep(5)
print("Transfering output zip to local drive")
save_path.parent.mkdir(parents=True, exist_ok=True)
sftp.get(zip_path, save_path)
print("Removing batch on Coulson")
sftp.remove(zip_path)
sftp.rmdir(Path(zip_path).parent.as_posix())
ssh.close()
print("Extracting local zip")
with ZipFile(save_path, "r") as run_zip:
    run_zip.extractall(save_path.parent.joinpath(f'run_{num_runs + 1}'))
save_path.unlink(missing_ok=True)
