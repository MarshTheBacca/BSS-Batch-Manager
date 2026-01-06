import shutil
import stat
from pathlib import Path

import paramiko


class LogInException(Exception):
    pass


MIN_FREE_SPACE = 10 * 1024 * 1024 * 1024  # 10 GB


def command_print(ssh: paramiko.SSHClient, command: list) -> None:
    """Prints the output of a command run on a remote server.

    Args:
        ssh (paramiko.SSHClient): The SSH client
        command (list): The command to run
    Raises:
        paramiko.SSHException: If the command fails to run
    """
    try:
        _, stdout, stderr = ssh.exec_command(command)
    except paramiko.SSHException:
        raise paramiko.SSHException(f"Error running command: {command}")
    out_lines = stdout.read().decode("ascii").split("\n")[:-1]
    for line in out_lines:
        print(line)
    error_lines = stderr.read().decode("ascii").split("\n")[:-1]
    for line in error_lines:
        print(line)


def command_lines(ssh: paramiko.SSHClient, command: str) -> list[str]:
    """Gets the output of a command run on a remote server as a list of lines.

    Args:
        ssh (paramiko.SSHClient): The SSH client
        command (str): The command to run
    Returns:
        list[str]: The output of the command as a list of lines
    Raises:
        paramiko.SSHException: If the command fails to run
    """
    try:
        _, stdout, _ = ssh.exec_command(command)
    except paramiko.SSHException:
        raise paramiko.SSHException(f"Error running command: {command}")
    lines = stdout.read().decode("ascii").split("\n")[:-1]
    return lines


def create_ssh_client(username: str, hostname: str, port: int = 22) -> paramiko.SSHClient:
    """Creates an SSH client.

    Loads the system host keys and setting the missing host key policy to AutoAddPolicy.

    Args:
        username (str): The username to login with
        port (int): The port to connect to
        hostname (str): The hostname to connect to
    Returns:
        paramiko.SSHClient: The SSH client
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=hostname, port=port, username=username)
    return client


def ssh_login_silent(username: str, hostname: str) -> paramiko.SSHClient:
    """Logs into a remote server using SSH on port 22.

    Args:
        username (str): The username to login with
        hostname (str): The hostname to connect to (default is COULSON_HOSTNAME)

    Returns:
        paramiko.SSHClient: The SSH client
    Raises:
        LogInException: If the login fails
    """
    try:
        return create_ssh_client(username, hostname)
    except (paramiko.AuthenticationException, paramiko.SSHException):
        raise LogInException(f"Failed to login to {hostname} as {username} on port 22")


def sftp_exists(sftp: paramiko.SFTPClient, path: Path) -> bool:
    """Checks if a file or directory exists on the remote server.

    Args:
        sftp: An open sftp connection
        path: The path to the file or directory
    Returns:
        bool: True if the file or directory exists, False if it does not
    """
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def land_directory(sftp: paramiko.SFTPClient, remote_path: Path) -> None:
    """Makes a directory and all parent directories on the remote server.

    Also changes to that directory

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
    except OSError:
        dirname = remote_path.parent
        basename = remote_path.name
        land_directory(sftp, dirname)
        try:
            sftp.mkdir(basename)
            sftp.chdir(basename)
        except OSError:
            raise OSError(f"Could not make remote directory {remote_path}, check permissions")


def receive_batches(username: str, hostname: str, output_path: Path, secondary_output_path: Path | None = None) -> None:
    """Receives batches from the host, deleting batch files and empty batch folders along the way.

    Args:
        username (str): username to log in to host
        hostname (str): the server's hostname
        output_path (Path): the path to download and extract batches to
        secondary_output_path (Path, optional): the secondary path to download and extract batches to
    """
    ssh = ssh_login_silent(username, hostname)
    sftp = ssh.open_sftp()
    bmr_path = Path(command_lines(ssh, "readlink -f ~/")[0]).joinpath("BSS-Batch-Manager-Remote")
    none_found = True
    for name in sftp.listdir(bmr_path.as_posix()):
        if name == "remote_management":
            continue
        full_path = bmr_path.joinpath(name)
        if not stat.S_ISDIR(sftp.stat(full_path.as_posix()).st_mode):
            continue
        sub_files = sftp.listdir(full_path.as_posix())
        if not sub_files:
            sftp.rmdir(full_path.as_posix())
            continue
        for sub_file in sub_files:
            if not sub_file.endswith("completion_flag"):
                continue
            print(f"Identified completion_flag file: {sub_file}")
            none_found = False
            try:
                run_number = int(sub_file.split("_")[-3])
            except TypeError:
                print(f"TypeError while extracting integer from {sub_file}")
                return
            batch_name = "_".join(sub_file.split("_")[:-4])
            zip_path = full_path.joinpath(f"{batch_name}_run_{run_number}.zip")

            # Check available disk space
            _total, _used, free = shutil.disk_usage(output_path)
            if free < MIN_FREE_SPACE and secondary_output_path is not None:
                print("Switching to secondary output path due to low disk space")
                save_path = secondary_output_path.joinpath(batch_name, f"{batch_name}_run_{run_number}.zip")
            else:
                save_path = output_path.joinpath(batch_name, f"{batch_name}_run_{run_number}.zip")
            save_path.parent.mkdir(parents=True, exist_ok=True)
            print("Downloading batch...")
            sftp.get(zip_path.as_posix(), save_path.as_posix())
            print("Deleting zip and completion_flag files")
            sftp.remove(zip_path.as_posix())
            sftp.remove(full_path.joinpath(sub_file).as_posix())
            extract_path = save_path.parent.joinpath(f"run_{run_number}")
            extract_path.mkdir(parents=True, exist_ok=True)
            print("Extracting batch...")
            shutil.unpack_archive(filename=save_path, extract_dir=extract_path)
            save_path.unlink()
    if none_found:
        print("No batches to receive\n")
