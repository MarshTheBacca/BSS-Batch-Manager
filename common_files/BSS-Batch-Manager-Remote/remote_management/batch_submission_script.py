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

EXEC_NAME: str = "bond_switch_simulator.exe"
CWD: Path = Path(__file__).parent.resolve()
JOB_SCRIPT_TEMPLATE_PATH: Path = CWD.joinpath("job_submission_template.sh")
EXEC_PATH: Path = CWD.joinpath(EXEC_NAME)
TIMEOUT = 5 * 30 * 24 * 60 * 60  # Approximately 5 months
USERNAME: str = getpass.getuser()


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


def find_char_indexes(string: str, target_char: str, invert: bool = False) -> list[int]:
    """
    Finds the indexes of all occurrences of the target character in the string
    Args:
        string: The string to be searched
        target_char: The character to be found
        invert: Whether or not to invert the search
    Returns:
        A list of the indexes of the target character in the string
    """
    return [i for i, char in enumerate(string) if (char == target_char) is not invert]


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


def import_qstat(username: str) -> list[tuple[str, str, datetime]]:
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
            job_id = job_data[0]
            start_date = datetime.strptime(job_data[5], "%m/%d/%Y").date()
            start_time = datetime.strptime(job_data[6], "%H:%M:%S").time()
        else:
            # The job-name line
            job_name = line.split()[2]
            start = datetime.combine(start_date, start_time, tzinfo=timezone.utc)
            jobs.append((job_id, job_name, start))
    return jobs


def get_files(path: Path) -> list[Path]:
    """
    Gets all the paths inside a path that are files recursively

    Args:
        path: The path to search for files in
    Returns:
        A list of all the paths that are files inside the given path
    """
    return [file for file in Path(path).rglob('*') if file.is_file()]


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


def clean_job(job_path: Path) -> None:
    """
    Cleans up the job directory by removing the input_files directory and the executable

    Args:
        job_path: The path to the job directory
    """
    logging.info(f"Cleaning job: {job_path}")
    batch_desc = job_path.parent.name
    shutil.rmtree(job_path.joinpath("input_files", "lammps_files"))
    shutil.move(job_path.joinpath("input_files", "bss_parameters.txt"), job_path.joinpath("bss_parameters.txt"))
    shutil.rmtree(job_path.joinpath("input_files"))
    job_path.joinpath(EXEC_NAME).unlink()
    job_path.joinpath("job_submission_script.sh").unlink()
    job_path.joinpath("output_files", "lammps.log").unlink()
    try:
        qsub_output = next(file for file in job_path.iterdir() if fnmatch.fnmatch(file.name, f"{batch_desc}_{job_path.name}.o*"))
        shutil.move(qsub_output, job_path.joinpath("qsub.log"))
    except StopIteration:
        logging.warning(f"qsub log not found for job {job_path.name}")


def submit_batch(username: str, run_path: Path) -> None:
    """
    Submits each batch with a maximum of 200 in parallel

    Args:
        username: The username of the user who submitted the jobs
        run_path: The path to the batch of jobs
    """
    batch_desc = run_path.name
    splice_length = len(batch_desc) + 1
    logging.info("Submitting jobs...")
    logging.info(f"Batch description: {batch_desc}")
    for job_path in Path.iterdir(run_path):
        if job_path.is_file() or job_path.name == "initial_network" or job_path.name == "initial_lammps_files":
            continue
        initial_running_jobs = set(running_job[1] for running_job in import_qstat(username) if running_job[1].startswith(batch_desc))
        prepare_job(job_path, JOB_SCRIPT_TEMPLATE_PATH, EXEC_PATH, batch_desc)
        # Wait until there are <201 jobs in parallel
        while len(command_lines(f'qstat | grep "{username}"')) > 200:
            time.sleep(5)

        # Once there are <201 jobs in parallel, clean finished jobs and submit the next job
        final_running_jobs = set(running_job[1] for running_job in import_qstat(username) if running_job[1].startswith(batch_desc))
        jobs_finished = initial_running_jobs - final_running_jobs
        for finished_job in jobs_finished:
            clean_job(run_path.joinpath(finished_job[splice_length:]))
        command_lines(f"qsub -j y -o {job_path.resolve()} {job_path.joinpath('job_submission_script.sh').resolve()}")


def wait_for_completion(username: str, run_path: Path) -> None:
    """
    Waits for all jobs in a batch to finish, or until a timeout is reached

    Args:
        username: The username of the user who submitted the jobs
        batch_desc: The description of the batch
    """
    start_time = time.time()
    batch_desc = run_path.name
    splice_length = len(batch_desc) + 1

    # Now wait until there are no jobs in qstat with the batch description, cleaning up any finished jobs
    while True:
        if time.time() - start_time > TIMEOUT:
            logging.error("Timeout reached, exiting")
            break
        initial_running_jobs = set(job[1] for job in import_qstat(username) if job[1].startswith(batch_desc))
        if not initial_running_jobs:
            break
        time.sleep(5)
        final_running_jobs = set(job[1] for job in import_qstat(username) if job[1].startswith(batch_desc))
        jobs_finished = initial_running_jobs - final_running_jobs
        for finished_job in jobs_finished:
            clean_job(run_path.joinpath(finished_job[splice_length:]))


def write_dir_to_zip(zip_file: ZipFile, path: Path, arcname: str = "", exclude_files: Optional[set] = None) -> None:
    """
    Writes a directory to a zip file

    Args:
        zip_file: The zip file to write to
        path: The path to the directory to write
        arcname: The name of the directory in the zip file
        exclude_files: A set of files to exclude from the zip
    """
    if exclude_files is None:
        exclude_files = {}
    for path in path.iterdir():
        if path.is_file() and path.name not in exclude_files:
            zip_file.write(path, arcname=str(Path(arcname) / path.name))
        elif path.is_dir():
            write_dir_to_zip(zip_file, path, arcname=str(Path(arcname) / path.name))


def write_log_to_zip(zip_path: Path, log_path: Path) -> None:
    """
    Writes the log file to the zip file (needs to be done at the end to contain all messages)

    Args:
        zip_path: The path to the zip file
        log_path: The path to the log file
    """
    with ZipFile(zip_path, "a") as return_zip:
        return_zip.write(log_path, arcname=log_path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit jobs without overloading host")
    parser.add_argument("-p", type=str, help="Path to run folder", metavar="path", required=True)
    args = parser.parse_args()
    run_path: Path = Path(args.p).resolve()
    log_path = run_path.joinpath("batch_submission_script.log")
    initialise_log(log_path)
    logging.info("Starting batch submission script")

    if not os.access(run_path.parent, os.W_OK):
        logging.error(f"You don't have permission to write to {run_path.parent}")
        sys.exit(1)

    try:
        # Unzip the batch zip sent over from remote host, and delete it
        zip_path: Path = next(file for file in Path(run_path).iterdir() if file.suffix == '.zip')
        logging.info(f"Unzipping batch zip {zip_path}")
        with ZipFile(zip_path, 'r') as batch_zip:
            batch_zip.extractall(run_path)
        zip_path.unlink()
        # Submit the batch using qsub (maximum of 200 jobs at a time)
        logging.info("Submitting batch")
        submit_batch(USERNAME, run_path)
        # Wait for the batch to finish
        logging.info("Waiting for completion")
        wait_for_completion(USERNAME, run_path)
    except StopIteration:
        logging.error(f"No zip file found in {run_path}")
        sys.exit(1)
    except BadZipFile:
        logging.error(f"Bad zip file {zip_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occured: {e}")
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
            write_log_to_zip(run_path.with_suffix('.zip'), log_path)
            shutil.rmtree(run_path)
            run_path.parent.joinpath(f"{run_path.name}_completion_flag").touch()


if __name__ == "__main__":
    main()
