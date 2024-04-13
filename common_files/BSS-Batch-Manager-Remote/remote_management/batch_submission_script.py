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
    # The next line is intended like so:         Full jobname: [job-name]
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


def prepare_batch(run_path: Path, batch_desc: str, exec_name: str) -> None:
    """
    For each job, copy over initial_network and initial_lammps_files directories and the executable to the job's input_files directory
    and create a job submission script for each job

    Args:
        run_path: The path to the batch of jobs
        batch_desc: The description of the batch
        exec_name: The name of the executable to be run

    Exits:
        If there are no jobs found in the batch
    """
    if not any(job.is_dir() and job.name != "initial_network" and job.name != "initial_lammps_files" for job in Path.iterdir(run_path)):
        logging.error(f"No jobs found in batch: {run_path}")
        sys.exit(1)
    cwd = Path(__file__).parent.resolve()
    job_script_template_path = cwd.joinpath("job_submission_template.sh")
    exec_path = cwd.joinpath(exec_name)
    for job in Path.iterdir(run_path):
        if job.is_file() or job.name == "initial_network" or job.name == "initial_lammps_files":
            continue
        input_files_path = job.joinpath("input_files")
        shutil.copytree(run_path.joinpath("initial_network"), input_files_path.joinpath("bss_network"))
        shutil.copytree(run_path.joinpath("initial_lammps_files"), input_files_path.joinpath("lammps_files"))
        shutil.copy(exec_path, job.joinpath(exec_path.name))
        job_script_output_path = job.joinpath("job_submission_script.sh")
        create_job_script(job_script_template_path,
                          job_script_output_path,
                          exec_path.name, batch_desc)


def submit_batch(username: str, run_path: Path, exec_name: str, batch_desc: str) -> None:
    """
    Submits each batch with a maximum of 200 in parallel

    Args:
        username: The username of the user who submitted the jobs
        exec_name: The name of the executable to be run
        run_path: The path to the batch of jobs
        batch_desc: The description of the batch
    """
    logging.info("Preparing batch...")
    prepare_batch(run_path, batch_desc, exec_name)
    logging.info("Submitting jobs...")
    for job in Path.iterdir(run_path):
        if job.is_file() or job.name == "initial_network" or job.name == "initial_lammps_files":
            continue
        # Wait until there are <201 jobs in parallel
        while len(command_lines(f'qstat | grep "{username}"')) > 200:
            time.sleep(5)
        # Once there are <201 jobs in parallel, submit the job and start the next iteration.
        command_lines(f"qsub -j y -o {job.resolve()} {job.joinpath('job_submission_script.sh').resolve()}")


def wait_for_completion(username: str, batch_desc: str) -> None:
    """
    Waits for all jobs in a batch to finish, or until a timeout is reached (5 months)

    Args:
        username: The username of the user who submitted the jobs
        batch_desc: The description of the batch
    """
    # 5 months is approximately 5*30*24*60*60 = 10,800,000 seconds
    timeout = 5 * 30 * 24 * 60 * 60
    start_time = time.time()

    # Now wait until there are no jobs in qstat with our batch_desc defined above, checking every 5 seconds
    while True:
        if time.time() - start_time > timeout:
            logging.error("Timeout reached, exiting")
            break
        job_names: list[str] = [job[1] for job in import_qstat(username)]
        if batch_desc not in job_names:
            break
        time.sleep(5)


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


def create_zip(run_path: Path, batch_desc: str) -> None:
    """
    Creates a zip file of the initial network and lammps files,
    the output files of each job and the qsub log but not lammps.log

    Args:
        run_path: The path to the run folder
    """
    with ZipFile(run_path.with_suffix('.zip'), "x") as return_zip:
        write_dir_to_zip(return_zip, run_path.joinpath("initial_network"), arcname="initial_network")
        write_dir_to_zip(return_zip, run_path.joinpath("initial_lammps_files"), arcname="initial_lammps_files")
        for job in run_path.iterdir():
            if job.is_dir() and job.name != "initial_network" and job.name != "initial_lammps_files":
                write_dir_to_zip(return_zip, job.joinpath("output_files"), arcname=job.name, exclude_files={"lammps.log"})
                return_zip.write(job.joinpath("input_files", "bss_parameters.txt"), arcname=f"{job.name}/bss_parameters.txt")
                try:
                    qsub_output = next(file for file in job.iterdir() if fnmatch.fnmatch(file.name, f"{batch_desc}.o*"))
                    return_zip.write(qsub_output, arcname=f"{job.name}/qsub.log")
                except StopIteration:
                    logging.warning(f"qsub log not found for job {job.name}")


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

    batch_desc: str = run_path.name
    username: str = getpass.getuser()

    try:
        # Unzip the batch zip sent over from remote host, and delete it
        zip_path: Path = next(file for file in Path(run_path).iterdir() if file.suffix == '.zip')
        logging.info(f"Unzipping batch zip {zip_path}")
        with ZipFile(zip_path, 'r') as batch_zip:
            batch_zip.extractall(run_path)
        zip_path.unlink()
        # Submit the batch using qsub (maximum of 200 jobs at a time)
        logging.info("Submitting batch")
        submit_batch(username, run_path, EXEC_NAME, batch_desc)
        # Wait for the batch to finish
        logging.info("Waiting for completion")
        wait_for_completion(username, batch_desc)
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
            create_zip(run_path, batch_desc)
        except Exception as e:
            logging.error(f"An error occurred while creating the return zip: {e}")
        finally:
            logging.info("Complete!")
            logging.shutdown()
            write_log_to_zip(run_path.with_suffix('.zip'), log_path)
            shutil.rmtree(run_path)


if __name__ == "__main__":
    main()
