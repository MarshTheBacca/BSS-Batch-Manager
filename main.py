import shutil
import traceback
from copy import deepcopy
from itertools import product
from pathlib import Path

from matplotlib import pyplot as plt

from utils import (BatchData, BatchOutputData, BSSInputData, BSSType,
                   generate_job_name, get_batch_name, get_options,
                   get_valid_int, select_network, select_potential)

NUMBER_ORDERS = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
                 9: "ninth", 10: "tenth"}

CWD = Path(__file__).parent


def create_bss_input_parameters(template_data: BSSInputData,
                                vary_arrays: list[list[BSSType]],
                                var_indexes: list[int],
                                batches_path: Path,
                                network_path: Path,
                                potential_path: Path) -> None:
    meshgrid = list(product(*vary_arrays))
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


def analyse_batch(output_files_path: Path) -> None:
    network = select_network(output_files_path, "Select a network to analyse")
    if network is None:
        return
    runs = sorted([run for run in network.iterdir() if run.is_dir()], key=lambda x: int(x.name[4:]))
    print(f"Reading from {runs[-1].name} ...")
    batch_output_data = BatchOutputData.from_files(runs[-1])
    batch_output_data.create_images(None, seed_skip=True)
    # batch_output_data.plot_radial_distribution(batch_output_data.jobs)
    # plt.show()
    # plt.clf()


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
                                   "3) Edit the batch template\n4) Submit batch to host\n5) Analyse a batch\n6) Exit\n", 1, 6)
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
                analyse_batch(output_path)
            elif option == 6:
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
