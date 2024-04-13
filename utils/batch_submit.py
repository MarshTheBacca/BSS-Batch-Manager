import argparse
import errno
import logging
import sys
import time
from pathlib import Path
from zipfile import ZipFile
import shutil

import paramiko
from ssh_utils import (LogInException, command_lines, land_directory,
                       sftp_exists, ssh_login_silent)

TIMEOUT = 5 * 30 * 24 * 60 * 60  # 5 months is approximately 5*30*24*60*60 = 10,800,000 seconds


def initialise_log() -> None:
    """
    Sets up the logging for the script.
    The log file is stored in the same directory as the script.
    """
    log_path = Path(__file__).parent.joinpath("batch_submit.log")
    log_path.open('w').close()  # Clear the log
    logging.basicConfig(filename=log_path,
                        format="[%(asctime)s] [%(levelname)s]: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        level=logging.INFO)


def parse_arguments() -> argparse.Namespace:
    """
    Parses the arguments for the script

    Returns:
        argparse.Namespace: The parsed arguments
    Exits:
        If the arguments are not provided correctly
    """
    parser = argparse.ArgumentParser(description="Submit jobs without overloading host")
    parser.add_argument("-n", type=str, help="Batch name", metavar="zip_path", required=True)
    parser.add_argument("-x", type=int, help="Number of runs of batch", metavar="num_runs", required=True)
    parser.add_argument("-p", type=str, help="Local batch zip path", metavar="local_batch_path", required=True)
    parser.add_argument("-o", type=str, help="Local ouput folder", metavar="output_path", required=True)
    parser.add_argument("-u", type=str, help="Username", metavar="username", required=True)
    parser.add_argument("-z", type=str, help="Hostname", metavar="hostname", required=True)

    try:
        return parser.parse_args()
    except argparse.ArgumentError as e:
        logging.error(e)
        sys.exit(1)


def connect_to_host(username: str, hostname: str) -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    """
    Attempts to connect to host

    Args:
        username (str): The username to connect with
    Exits:
        If the connection fails
    """
    try:
        ssh = ssh_login_silent(username=username, hostname=hostname)
        sftp = ssh.open_sftp()
        return ssh, sftp
    except (LogInException, paramiko.SSHException) as e:
        logging.error(e)
        sys.exit(1)


def initialise_remote(ssh: paramiko.SSHClient, sftp: paramiko.SFTPClient, bmr_dir: Path) -> None:
    """
    Checks if BSS-Remote exists on the remote server.
    If it does not, it copies over BSS-Batch-Manager-Remote.zip and unzips it

    Args:
        ssh (paramiko.SSHClient): The ssh client for the server
        sftp (paramiko.SFTPClient): The sftp client for the server
        bmr_dir (Path): The directory of the BSS-Batch-Manager-Remote
    Exits:
        If the BSS-Batch-Manager-Remote.zip cannot be found locally
        If the user does not have permission to write to the remote directory
        If an error occurs while copying the local zip to the remote directory
    """
    if not sftp_exists(sftp, bmr_dir.as_posix()):
        logging.info("BSS-Batch-Manager-Remote did not exist. Copying over...")
        land_directory(sftp, bmr_dir)
        local_copy_of_remote_path = Path(__file__).parent.parent.joinpath("common_files", "BSS-Batch-Manager-Remote")
        local_zip_path = Path(shutil.make_archive(local_copy_of_remote_path, 'zip', local_copy_of_remote_path))
        logging.info(f"Copying {local_zip_path} to {bmr_dir}")
        try:
            sftp.put(local_zip_path.as_posix(), bmr_dir.joinpath("BSS-Batch-Manager-Remote.zip").as_posix())
        except FileNotFoundError:
            sftp.rmdir(bmr_dir.as_posix())
            logging.error(f"Could not find BSS-Batch-Manager-Remote.zip at {local_zip_path}")
            sys.exit(1)
        except IOError as e:
            if e.errno == errno.EACCES:
                logging.error(f"Permission denied: Cannot write to {bmr_dir}")
                sys.exit(1)
        except Exception as e:
            logging.error(f"An error occurred while copying local zip to remote directory: {e}")
            sys.exit(1)
        finally:
            local_zip_path.unlink(missing_ok=True)
        _, stdout, _ = ssh.exec_command(f"unzip {bmr_dir.joinpath('BSS-Batch-Manager-Remote.zip')} -d {bmr_dir.as_posix()};"
                                        f"rm {bmr_dir.joinpath('BSS-Batch-Manager-Remote.zip')}")
        stdout.read()
        logging.info("Copy successful")
        return
    logging.info("BSS-Batch-Manager-Remote already exists")


def wait_for_zip(ssh: paramiko.SFTPClient, zip_path: Path, cfe_path: Path, timeout: int = TIMEOUT, interval: int = 5) -> None:
    """
    Checks if a zip file exists on the remote server within a timeout period

    Args:
        ssh (paramiko.SFTPClient): The sftp client for the server
        zip_path (Path): The path to the zip file
        cfe_path (Path): The path to the check_file_exists.sh script
        timeout (int, optional): The timeout period in seconds. Defaults to TIMEOUT.
        interval (int, optional): The interval between checks in seconds. Defaults to 5.
    Exits:
        If the zip file is not found within the timeout period
    """
    start_time = time.time()
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            logging.error(f"Timed out while waiting for zip at {zip_path}")
            sys.exit(1)
        result = command_lines(ssh, f"bash {cfe_path} {zip_path}")
        if result and result[0] == "True":
            break
        logging.info(f"Zip check at {round(elapsed_time)} seconds: Failed")
        time.sleep(interval)


def main() -> None:
    initialise_log()
    logging.info("Batch submit started")
    logging.info("Parsing arguments")
    args = parse_arguments()
    batch_name = args.n
    num_runs = args.x
    local_batch_path = Path(args.p)
    output_path = Path(args.o)
    username = args.u
    hostname = args.z
    save_path = output_path.joinpath(batch_name, f"{batch_name}_run_{num_runs + 1}.zip")

    logging.info(f"Connecting to {hostname}")
    try:
        ssh, sftp = connect_to_host(username, hostname)
        try:
            logging.info("Connection Successful!")
            logging.info("Checking for BSS-Batch-Manager-Remote in home directory")
            coulson_home_path = Path(command_lines(ssh, "readlink -f ~/")[0])
            initialise_remote(ssh, sftp, coulson_home_path.joinpath("BSS-Batch-Manager-Remote"))

            logging.info("Transferring batch zip to server")
            coulson_run_path = coulson_home_path.joinpath("BSS-Batch-Manager-Remote", batch_name, f"{batch_name}_run_{num_runs + 1}")
            zip_path = Path(f"{coulson_run_path}.zip").as_posix()
            land_directory(sftp, coulson_run_path)
            sftp.put(local_batch_path, coulson_run_path.joinpath(f"{batch_name}.zip").as_posix())

            logging.info("Executing remote python script with command:")
            command = (f"python3 {coulson_home_path.joinpath('BSS-Batch-Manager-Remote', 'remote_management', 'batch_submission_script.py').as_posix()} "
                       f"-p {coulson_run_path.as_posix()}")
            logging.info(command)
            ssh.exec_command(command)

            logging.info(f"Checking for output zip at\n{zip_path}")
            cfe_path = coulson_home_path.joinpath("BSS-Batch-Manager-Remote", "remote_management", "check_file_exists.sh").as_posix()
            wait_for_zip(ssh, zip_path, cfe_path)
            logging.info("Zip found!")

            logging.info("Transfering output zip to local drive")
            save_path.parent.mkdir(parents=True, exist_ok=True)
            sftp.get(zip_path, save_path)

            logging.info("Removing batch on server")
            sftp.remove(zip_path)
            sftp.rmdir(Path(zip_path).parent.as_posix())
            ssh.close()

            logging.info("Extracting and deleting local zip")
            with ZipFile(save_path, "r") as run_zip:
                run_zip.extractall(save_path.parent.joinpath(f'run_{num_runs + 1}'))
            save_path.unlink(missing_ok=True)
        finally:
            ssh.close()
    except Exception as e:
        logging.error(f"An unexpected error occured: {e}")
        sys.exit(1)
    logging.info("Complete!")


if __name__ == "__main__":
    main()
