import argparse
import logging
import time
from pathlib import Path
from zipfile import ZipFile

import paramiko

from ssh_utils import (command_lines, land_directory, sftp_exists,
                       ssh_login_silent, LogInException)


def initialise(ssh, bmr_dir: Path) -> None:
    """
    Checks if LAMMPSNetMC-Batch-Manager-Remote exists on the remote server.
    If it does not, it copies over the LAMMPSNetMC-Batch-Manager-Remote and unzips it
    """
    sftp: paramiko.SFTPClient = ssh.open_sftp()
    if not sftp_exists(sftp, bmr_dir.as_posix()):
        logging.info("LAMMPSNetMC-Batch-Manager-Remote did not exist. Copying over...")
        land_directory(sftp, bmr_dir)
        local_copy_of_remote_zip_path = Path(__file__).parent.parent.joinpath("common_files", "LAMMPSNetMC-Batch-Manager-Remote.zip")
        logging.info(f"Copying {local_copy_of_remote_zip_path} to {bmr_dir}")
        try:
            sftp.put(local_copy_of_remote_zip_path.as_posix(), bmr_dir.joinpath("LAMMPSNetMC-Batch-Manager-Remote.zip").as_posix())
        except FileNotFoundError:
            sftp.rmdir(bmr_dir.as_posix())
            raise FileNotFoundError(f"Could not find LAMMPSNetMC-Batch-Manager-Remote.zip at {local_copy_of_remote_zip_path}")
        sftp.close()
        _, stdout, _ = ssh.exec_command(f"unzip {bmr_dir.joinpath('LAMMPSNetMC-Batch-Manager-Remote.zip')} -d {bmr_dir.as_posix()};"
                                        f"rm {bmr_dir.joinpath('LAMMPSNetMC-Batch-Manager-Remote.zip')}")
        stdout.read()
        logging.info("Copy successful")
        return
    logging.info("LAMMPSNetMC-Batch-Manager-Remote already exists")


def main() -> None:
    log_path = Path(__file__).parent.joinpath("batch_submit.log")
    # Clear the log
    log_path.open('w').close()

    logging.basicConfig(filename=log_path,
                        format="[%(asctime)s] [%(levelname)s]: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        level=logging.INFO)
    logging.info("Batch submit started")
    logging.info("Parsing arguments")
    parser = argparse.ArgumentParser(description="Submit jobs without overloading Coulson")
    parser.add_argument("-n", type=str, help="Batch name", metavar="zip_path", required=True)
    parser.add_argument("-x", type=int, help="Number of runs of batch", metavar="num_runs", required=True)
    parser.add_argument("-p", type=str, help="Local batch zip path", metavar="local_batch_path", required=True)
    parser.add_argument("-o", type=str, help="Local ouput folder", metavar="output_path", required=True)
    parser.add_argument("-u", type=str, help="Coulson Username", metavar="username", required=True)
    args = parser.parse_args()
    batch_name = args.n
    num_runs = args.x
    local_batch_path = Path(args.p)
    output_path = Path(args.o)
    coulson_username = args.u
    save_path = output_path.joinpath(batch_name, f"{batch_name}_run_{num_runs + 1}.zip")

    logging.info("Connecting to Coulson")
    try:
        ssh = ssh_login_silent(coulson_username, "coulson.chem.ox.ac.uk")
        sftp = ssh.open_sftp()
    except (LogInException, paramiko.SSHException) as e:
        logging.error(e)
        return
    logging.info("Connection Successful")

    coulson_home_path = Path(command_lines(ssh, "readlink -f ~/")[0])
    logging.info("Checking for LAMMPSNetMC-Batch-Manager-Remote in home directory")
    try:
        initialise(ssh, coulson_home_path.joinpath("LAMMPSNetMC-Batch-Manager-Remote"))
    except FileNotFoundError as e:
        logging.error(e)
        return

    coulson_run_path = coulson_home_path.joinpath("LAMMPSNetMC-Batch-Manager-Remote", batch_name, f"{batch_name}_run_{num_runs + 1}")
    zip_path = Path(f"{coulson_run_path}.zip").as_posix()
    logging.info("Transferring batch zip to Coulson")
    land_directory(sftp, coulson_run_path)
    sftp.put(local_batch_path, coulson_run_path.joinpath(f"{batch_name}.zip").as_posix())
    logging.info("Executing remote python script")
    ssh.exec_command(f"python3 {coulson_home_path.joinpath('LAMMPSNetMC-Batch-Manager-Remote', 'remote_management', 'batch_submission_script.py').as_posix()} "
                     f"-p {coulson_run_path.as_posix()}")
    cfe_path = coulson_home_path.joinpath("LAMMPSNetMC-Batch-Manager-Remote", "remote_management", "check_file_exists.sh").as_posix()
    logging.info(f"Checking for output zip at\n{zip_path}")
    while True:
        if command_lines(ssh, f"bash {cfe_path} {zip_path}")[0] == "True":
            logging.info("Zip found")
            break
        logging.info("Zip not found")
        time.sleep(5)
    logging.info("Transfering output zip to local drive")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    sftp.get(zip_path, save_path)
    logging.info("Removing batch on Coulson")
    sftp.remove(zip_path)
    sftp.rmdir(Path(zip_path).parent.as_posix())
    ssh.close()
    logging.info("Extracting and deleting local zip")
    with ZipFile(save_path, "r") as run_zip:
        run_zip.extractall(save_path.parent.joinpath(f'run_{num_runs + 1}'))
    save_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
