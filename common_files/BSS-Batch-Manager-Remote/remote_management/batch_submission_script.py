import argparse
import fnmatch
import getpass
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zipfile import BadZipFile, ZipFile
import traceback

EXEC_NAME: str = "bond_switch_simulator.exe"
CWD: Path = Path(__file__).parent.resolve()
JOB_SCRIPT_TEMPLATE_PATH: Path = CWD.joinpath("job_submission_template.sh")
EXEC_PATH: Path = CWD.joinpath(EXEC_NAME)
TIMEOUT: int = 30 * 24 * 60 * 60  # Approximately 1 month
USERNAME: str = getpass.getuser()
MAX_PARALLEL_JOBS: int = 500


def initialise_log(log_path: Path) -> None:
    """
    Sets up the logging for the script.
    The log file is stored in the same directory as the script.
    """
    log_path.open('w').close()  # Clear the log
    logging.basicConfig(filename=log_path,
                        format="[%(asctime)s] [%(levelname)s]: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        level=logging.INFO)


def command_lines(command_array: str) -> list[str]:
    """
    Executes a command on the remote server and returns the output as a list of lines

    Args:
        command_array: The command to be executed
    Returns:
        A list of the lines of the output
    """
    lines = subprocess.run(command_array, stdout=subprocess.PIPE, shell=True).stdout.decode("utf-8").split("\n")[:-1]
    return lines


def create_job_script(template_file_path: Path,
                      save_path: Path,
                      exec_name: str,
                      job_desc: str = "qsub_log") -> None:
    """
    Creates a job submission script from a template file with the correct paths, job description and executable name

    Args:
        template_file_path: The path to the template file
        save_path: The path to save the new job submission script
        exec_name: The name of the executable to be run
        job_desc: The description of the job
    """
    JOB_DESC_LINE = 7
    JOB_PATH_LINE = 9
    EXEC_LINE = 15

    with template_file_path.open("r") as template_file:
        template_lines = template_file.readlines()

    template_lines[JOB_DESC_LINE - 1] = f"#$ -N {job_desc}\n"
    template_lines[JOB_PATH_LINE - 1] = f'job_dir="{save_path.parent}"\n'
    template_lines[EXEC_LINE - 1] = f"./{exec_name}\n"

    with save_path.open("w+") as new_template_file:
        new_template_file.writelines(template_lines)


def import_qstat(username: str) -> list[tuple[int, str, str, datetime]]:
    """
    Gets the job id, job name and start time of all jobs in qstat for a given username

    Args:
        username: The username to search for in qstat
    Returns:
        A list of tuples containing the job id, job name and start time
    """
    # qstat has a lot of information, but we only need the job id, job name and start time
    # Every job listed in qstat has a job-ID line in this format:
    #     0        1         2      3      4          5            6
    # [job-ID] [priority] [name] [user] [state] [submit-date] [submit-time] ... and others
    # The next line is indented like so:         Full jobname: [job-name]
    # To extract this information, we take every line that starts with a digit (job-id) or starts with "Full jobname"
    lines = (line for line in command_lines(f"qstat -u {username} -r") if line[0].isdigit() or line.strip().startswith("Full jobname"))
    jobs = []
    for i, line in enumerate(lines):
        if i % 2 == 0:
            # The job-ID line
            job_data = line.split()
            job_id = int(job_data[0])
            start_date = datetime.strptime(job_data[5], "%m/%d/%Y").date()
            start_time = datetime.strptime(job_data[6], "%H:%M:%S").time()
            job_status = job_data[4]
            continue
        # The job-name line
        job_name = line.split()[2]
        start = datetime.combine(start_date, start_time, tzinfo=timezone.utc)
        jobs.append((job_id, job_name, job_status, start))
    return jobs


def prepare_job(job_path: Path, job_script_template_path: Path, exec_path: Path, batch_desc: str) -> None:
    """
    Copy over initial_network and initial_lammps_files directories and the executable to the job's input_files directory
    and create a job submission script

    Args:
        run_path: The path to the batch of jobs
        batch_desc: The description of the batch
        exec_name: The name of the executable to be run
    """
    input_files_path = job_path.joinpath("input_files")
    shutil.copytree(job_path.parent.joinpath("initial_network"), input_files_path.joinpath("bss_network"))
    shutil.copytree(job_path.parent.joinpath("initial_lammps_files"), input_files_path.joinpath("lammps_files"))
    shutil.copy(exec_path, job_path.joinpath(exec_path.name))
    job_path.joinpath("output_files").mkdir()
    create_job_script(job_script_template_path,
                      job_path.joinpath("job_submission_script.sh"),
                      exec_path.name,
                      f"{batch_desc}_{job_path.name}")


def safe_remove(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except FileNotFoundError:
        pass


def safe_move(source: Path, destination: Path) -> None:
    try:
        shutil.move(source, destination)
    except FileNotFoundError:
        pass


def clean_job(job_path: Path, qsub_output: Path) -> None:
    """
    Cleans up the job directory by removing the input_files directory and the executable
    Works for partially or already cleaned jobs

    Args:
        job_path: The path to the job directory
        qsub_output: The path to the qsub log file
    """
    safe_move(job_path.joinpath("input_files", "bss_parameters.txt"), job_path.joinpath("bss_parameters.txt"))
    safe_move(qsub_output, job_path.joinpath("qsub.log"))

    safe_remove(job_path.joinpath("input_files"))
    safe_remove(job_path.joinpath(EXEC_NAME))
    safe_remove(job_path.joinpath("job_submission_script.sh"))
    safe_remove(job_path.joinpath("output_files", "lammps.log"))  # This tends to be a very large file


def clean_finished_jobs(run_path: Path, batch_desc: str) -> None:
    """
    Identifies and cleans up finished jobs in the run directory

    Args:
        run_path: The path to the batch of jobs
        batch_desc: The description of the batch
    """
    for job_path in run_path.iterdir():
        if job_path.is_file() or job_path.name == "initial_network" or job_path.name == "initial_lammps_files":
            continue
        try:
            qsub_output_path = next(file for file in job_path.iterdir() if fnmatch.fnmatch(file.name, f"{batch_desc}_{job_path.name}.o*"))
        except StopIteration:
            # If qsub log is not found, the job is still running
            continue
        clean_job(job_path, qsub_output_path)
    errored_jobs = {job[1]: job[0] for job in import_qstat(USERNAME) if job[2] == "Eqw"}
    for errored_job, id in errored_jobs.values():
        logging.warn(f"Job failed: {errored_job}")
        command_lines(f"qdel {id}")


def submit_batch(username: str, run_path: Path) -> None:
    """
    Submits each batch with a maximum of MAX_PARALLEL_JOBS jobs in parallel
    Cleans up any finished batches

    Args:
        username: The username of the user who submitted the jobs
        run_path: The path to the batch of jobs
    """
    logging.info("Submitting jobs...")
    cleaning_interval = 5
    counter = 1
    batch_desc = run_path.name
    for job_path in Path.iterdir(run_path):
        if job_path.is_file() or job_path.name == "initial_network" or job_path.name == "initial_lammps_files":
            continue
        # Wait until there are < MAX_PARALLEL_JOBS jobs in parallel
        while len(command_lines(f'qstat | grep "{username}"')) >= MAX_PARALLEL_JOBS:
            time.sleep(5)
        prepare_job(job_path, JOB_SCRIPT_TEMPLATE_PATH, EXEC_PATH, batch_desc)
        logging.info(f"qsub -j y -o {job_path.resolve()} {job_path.joinpath('job_submission_script.sh').resolve()}")
        command_lines(f"qsub -j y -o {job_path.resolve()} {job_path.joinpath('job_submission_script.sh').resolve()}")
        if counter % cleaning_interval == 0:
            clean_finished_jobs(run_path, batch_desc)
        counter += 1

    logging.info("Waiting for completion...")
    start_time = time.time()
    while len(command_lines(f'qstat | grep "{username}"')) > 0:
        if time.time() - start_time > TIMEOUT:
            logging.error("Timeout reached, exiting")
            break
        if counter % cleaning_interval == 0:
            clean_finished_jobs(run_path, batch_desc)
        counter += 1
        time.sleep(5)
    clean_finished_jobs(run_path, batch_desc)


def write_log_to_zip(zip_path: Path, log_path: Path, arcname: Optional[str] = None) -> None:
    """
    Writes the log file to the zip file and removes the original

    Args:
        zip_path: The path to the zip file
        log_path: The path to the log file
    """
    if arcname is None:
        arcname = log_path.name
    with ZipFile(zip_path, "a") as return_zip:
        return_zip.write(log_path, arcname=arcname)
    try:
        log_path.unlink()
    except FileNotFoundError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit jobs without overloading host")
    parser.add_argument("-p", type=str, help="Path to run folder", metavar="path", required=True)
    args = parser.parse_args()
    run_path: Path = Path(args.p).resolve()
    log_path = run_path.parent.joinpath(f"{run_path.name}_batch_submission_script.log")
    initialise_log(log_path)
    logging.info("Starting batch submission script")

    if not os.access(run_path.parent, os.W_OK):
        logging.error(f"You don't have permission to write to {run_path.parent}")
        sys.exit(1)

    try:
        # Unzip the batch zip sent over from remote host, and delete it
        zip_path: Path = next(file for file in run_path.iterdir() if file.suffix == '.zip')
        logging.info(f"Unzipping batch zip {zip_path}")
        with ZipFile(zip_path, 'r') as batch_zip:
            batch_zip.extractall(run_path)
        zip_path.unlink()
        # Submit the batch using qsub (maximum of 200 jobs at a time)
        submit_batch(USERNAME, run_path)
    except StopIteration:
        logging.error(f"No zip file found in {run_path}")
        sys.exit(1)
    except BadZipFile:
        logging.error(f"Bad zip file {zip_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occured: {e}")
        logging.error(traceback.format_exc())
        sys.exit(1)
    finally:
        try:
            logging.info(f"Zipping up run folder {run_path}")
            shutil.make_archive(run_path, 'zip', run_path)
        except Exception as e:
            logging.error(f"An error occurred while creating the return zip: {e}")
        finally:
            logging.info("Complete!")
            logging.shutdown()
            write_log_to_zip(run_path.with_suffix(".zip"), log_path, "batch_submission_script.log")
            shutil.rmtree(run_path)
            run_path.parent.joinpath(f"{run_path.name}_completion_flag").touch()


if __name__ == "__main__":
    main()
