import paramiko
from pathlib import Path

COULSON_HOSTNAME = "coulson.chem.ox.ac.uk"


class LogInException(Exception):
    pass


def command_print(ssh: paramiko.SSHClient, command: list) -> None:
    """
    Prints the output of a command run on a remote server

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
    """
    Gets the output of a command run on a remote server as a list of lines

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


def create_ssh_client(username: str, hostname: str = COULSON_HOSTNAME, port: int = 22) -> paramiko.SSHClient:
    """
    Creates an SSH client by loading the system host keys and setting the missing host key policy to AutoAddPolicy

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


def ssh_login_silent(username: str, hostname: str = COULSON_HOSTNAME) -> paramiko.SSHClient:
    """
    Logs into a remote server using SSH on port 22

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
    """
    Checks if a file or directory exists on the remote server

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
    """
    Makes a directory and all parent directories on the remote server and changes to that directory

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
        land_directory(sftp, dirname)
        try:
            sftp.mkdir(basename)
            sftp.chdir(basename)
        except IOError:
            raise IOError(f"Could not make remote directory {remote_path}, check permissions")
