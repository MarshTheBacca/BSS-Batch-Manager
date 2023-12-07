import os
import paramiko
import maskpass

from .validation_utils import valid_str


def command_print(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    out_lines = stdout.read().decode("ascii").split("\n")[:-1]
    for line in out_lines:
        print(line)
    error_lines = stderr.read().decode("ascii").split("\n")[:-1]
    for line in error_lines:
        print(line)

def command_lines(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    lines = stdout.read().decode("ascii").split("\n")[:-1]
    return lines

def createSSHClient(hostname, port, username, password = None):
    client= paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, port, username, password)
    return client

def sftp_put(sftp, local_path, remote_path):
    try:
        sftp.put(local_path, remote_path)
    except IOError:
        sftp_put(os.path.dirname(remote_path))
        sftp.mkdir(os.path.basename(remote_path))

def ssh_login(username = True, password = None):
    try:
        ssh = createSSHClient(hostname = "coulson.chem.ox.ac.uk", port = 22, username = username, password = password)
    except (paramiko.AuthenticationException, paramiko.SSHException):
        while True:
            username = valid_str("Enter your username\n", length_range = (2, 20), char_types = "ASCII", exit_string = "e")
            if not username:
                return False, None, None
            try:
                ssh = createSSHClient(hostname = "coulson.chem.ox.ac.uk", port = 22, username = username, password = password)
                return ssh, username, None
            except (paramiko.AuthenticationException, paramiko.SSHException):
                pass
            password = maskpass.advpass(prompt = "Please enter your password for Coulson\n", mask = "*")
            try:
                ssh=createSSHClient(hostname = "coulson.chem.ox.ac.uk", port = 22, username = username, password = password)
                break
            except paramiko.AuthenticationException:
                print("Incorrect username or password.")
    return ssh, username, password

def ssh_login_silent(host, username = True, password = None):
    try:
        ssh = createSSHClient(hostname = host, port = 22, username = username)
        return ssh
    except (paramiko.AuthenticationException, paramiko.SSHException):
        return False
