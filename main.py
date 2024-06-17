import itertools
import shutil
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Optional, Generator

from matplotlib import pyplot as plt

from utils import (BatchData, BatchOutputData, BSSInputData, BSSType,
                   generate_job_name, get_batch_name, get_options,
                   get_valid_int, receive_batches,
                   select_network, select_potential, ResultsData)

NUMBER_ORDERS = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
                 9: "ninth", 10: "tenth"}

CWD = Path(__file__).parent


def create_bss_input_parameters(template_data: BSSInputData,
                                vary_arrays: list[list[BSSType]],
                                var_indexes: list[int],
                                batches_path: Path,
                                network_path: Path,
                                potential_path: Path) -> None:
    meshgrid = list(itertools.product(*vary_arrays))
    print(f"You selected network: {network_path.name}")
    batch_name = get_batch_name(batches_path)
    if batch_name is None:
        return
    temp_data: BSSInputData = deepcopy(template_data)
    changing_vars = [temp_data.table_relevant_variables[i] for i in var_indexes]
    for array in meshgrid:
        job_name = generate_job_name(changing_vars, array)
        input_files_path = batches_path.joinpath(batch_name, "jobs", job_name, "input_files")
        input_files_path.mkdir(parents=True)
        temp_data.export(input_files_path.joinpath("bss_parameters.txt"))
    batch_path = batches_path.joinpath(batch_name)
    shutil.copytree(network_path, batch_path.joinpath("initial_network"))
    batch_path.joinpath("initial_lammps_files").mkdir()
    shutil.move(batch_path.joinpath("initial_network", "lammps_network.txt"),
                batch_path.joinpath("initial_lammps_files", "lammps_network.txt"))
    shutil.copy(potential_path, batch_path.joinpath("initial_lammps_files", "lammps_potential.txt"))
    shutil.copy(Path(__file__).parent.joinpath("common_files", "lammps_script.txt"),
                batch_path.joinpath("initial_lammps_files", "lammps_script.txt"))
    shutil.make_archive(batches_path.joinpath(batch_name), "zip", batches_path.joinpath(batch_name))
    shutil.rmtree(batches_path.joinpath(batch_name))


def choose_vars(template_data: BSSInputData) -> tuple[list[list[BSSType]], list[int]] | tuple[None, None]:
    num_vars = get_valid_int("How many variables would you like to vary? (10 to exit)\n", 1, 10)
    if num_vars == 10:
        return None, None
    exit_num = len(template_data.table_relevant_variables) + 1
    selected_var_indexes = []
    vary_arrays = []
    while len(selected_var_indexes) < num_vars:
        template_data.table_print(relevant_only=True)
        option = get_valid_int(f"Enter the {NUMBER_ORDERS[len(selected_var_indexes) + 1]} variable ({exit_num} to exit)\n", 1, exit_num)
        if option == exit_num:
            return None, None
        if option - 1 in selected_var_indexes:
            print("You have already selected this variable")
            continue
        selected_var_indexes.append(option - 1)
        print(f"You have selected {template_data.table_relevant_variables[option - 1].name}")
        vary_array = template_data.table_relevant_variables[option - 1].get_vary_array()
        if vary_array is None:
            return None, None
        vary_arrays.append(vary_array)
    return vary_arrays, selected_var_indexes


def create_batch(template_data: BSSInputData, batches_path: Path, networks_path: Path, potential_paths: Path) -> None:
    network_path = select_network(networks_path, "Select a network to use for the batch")
    if network_path is None:
        return
    potential_path = select_potential(potential_paths, "Select a potential to use for the batch")
    if potential_path is None:
        return
    vary_arrays, selected_var_indexes = choose_vars(template_data)
    if vary_arrays is None:
        return
    create_bss_input_parameters(template_data, vary_arrays, selected_var_indexes, batches_path, network_path, potential_path)


def analyse_network(output_files_path: Path, secondary_path: Optional[Path] = None) -> None:
    network = select_network(output_files_path, "Select a network to analyse", secondary_path)
    if network is None:
        return
    runs = sorted([run for run in network.iterdir() if run.is_dir()], key=lambda x: int(x.name[4:]))
    print(f"Reading from {runs[-1].name} ...")
    batch_output_data = BatchOutputData.from_files(runs[-1])
    # batch_output_data.plot_ring_size_distribution(refresh=False)
    batch_output_data.plot_energy_vs_temperatures()
    plt.show()
    plt.clf()


def get_pore_size(batch: Path) -> int | None:
    try:
        return int(batch.name.split("_")[3])
    except ValueError:
        return None


def get_network_tuple(paths: set[Path]) -> list[tuple[Path, int]]:
    network_tuple = []
    for path in paths:
        for batch in path.iterdir():
            if batch.is_dir() and (pore_size := get_pore_size(batch)) is not None:
                for job in batch.joinpath("run_1", "jobs").iterdir():
                    network_tuple.append((job, pore_size))
    return network_tuple


def get_job_paths(output_paths: set[Path]) -> Generator[Path, None, None]:
    for output_path in output_paths:
        for batch_path in output_path.iterdir():
            jobs_path = batch_path.joinpath("run_1", "jobs")
            if jobs_path.exists() and jobs_path.is_dir():
                yield from jobs_path.iterdir()


def analyse_batch(paths: set[Path]) -> None:
    option = get_valid_int("Choose from one of the following presets\n1) Energy Vs Pore size\n2) Generate master data\n3) Exit\n", 1, 3)
    if option == 1:
        network_tuple = get_network_tuple(paths)
    elif option == 2:
        results_data = ResultsData.gen_from_paths(list(get_job_paths(paths)), Path(__file__).parent.joinpath("thesis_results", "master_data.csv"))
    elif option == 3:
        return


def main() -> None:
    try:
        options = get_options(CWD.joinpath("config.csv"))
        hostname = options["hostname"]
        if hostname is None:
            print("Please give a hostname to submit batches to in the config.csv file")
            return
        username = options["username"]
    except RuntimeError as e:
        print(e)
        return
    except KeyError:
        print("Could not load username and hostname config options (did you delete config lines?)")
        return
    print(f"Loaded username: {username} for connecting to: {hostname}")
    try:
        secondary_output_path = options["secondary_output_path"]
        if secondary_output_path is not None:
            secondary_output_path = Path(secondary_output_path)
            secondary_output_path.mkdir(exist_ok=True)
            # check if user has write permissions to this directory:
            secondary_output_path.joinpath("test_file").touch()
            secondary_output_path.joinpath("test_file").unlink()
            print("Secondary output path set to: ", secondary_output_path)
    except KeyError:
        print("Could not load secondary output path config option (did you delete config lines?)")
        secondary_output_path = None
    except PermissionError:
        print(f"User does not have write permissions to {secondary_output_path}")
        secondary_output_path = None
    except FileNotFoundError:
        print(f"Secondary output path does not exist: {secondary_output_path}")
        secondary_output_path = None
    try:
        common_files_path = CWD.joinpath("common_files")
        common_files_path.joinpath("batch_log.csv").touch(exist_ok=True)
        batches_path = CWD.joinpath("batches")
        batches_path.mkdir(exist_ok=True)
        output_path = CWD.joinpath("output_files")
        output_path.mkdir(exist_ok=True)
        networks_path = CWD.joinpath("networks")
        networks_path.mkdir(exist_ok=True)
        potentials_path = CWD.joinpath("potentials")
        potentials_path.mkdir(exist_ok=True)
        template_data = BSSInputData.from_file(common_files_path.joinpath("bss_parameters.txt"))
        batch_data = BatchData.from_files(common_files_path.joinpath("batch_log.csv"), batches_path)
        while True:
            option = get_valid_int("What would you like to do?\n1) Create a batch\n2) Delete a batch\n"
                                   "3) Edit the batch template\n4) Submit batch to host\n5) Receive Batches\n6) Analyse a batch\n7) Exit\n", 1, 7)
            if option == 1:
                create_batch(template_data, batches_path, networks_path, potentials_path)
                batch_data.refresh(batches_path)
            elif option == 2:
                batch_data.delete_batch()
            elif option == 3:
                template_data.edit_value_interactive()
                template_data.export(common_files_path.joinpath("bss_parameters.txt"))
            elif option == 4:
                batch_data.submit_batch(output_path, CWD.joinpath("utils", "batch_submit.py"), username, hostname)
            elif option == 5:
                receive_batches(username, hostname, output_path, secondary_output_path)
            elif option == 6:
                analyse_batch({output_path, secondary_output_path})
            elif option == 7:
                break
    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except PermissionError as e:
        print(f"Permission error: {e}")
    except Exception as e:
        print(f"An unexpected error occured: {e}")
        print("Traceback: ")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()
