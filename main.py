import shutil
from copy import deepcopy
from datetime import datetime
from itertools import product
from pathlib import Path

from tabulate import tabulate

from utils import (BatchData, BSSInputData, BSSType, generate_job_name,
                   get_options, get_valid_int, get_valid_str)

NUMBER_ORDERS = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
                 9: "ninth", 10: "tenth"}


class UserCancelledError(Exception):
    pass


class MissingFilesError(Exception):
    pass


def select_path(path: Path, prompt: str, is_file: bool) -> Path:
    """
    Select a path to load from the given directory
    Args:
        path: directory to search for paths
        is_file: if True, search for files, else search for directories
    Returns:
        the path of the file/directory to load
    Raises:
        UserCancelledError: if the user cancels the selection
        MissingFilesError: if no files/directories are found in the given directory
    """
    path_array = []
    paths = []
    sorted_paths = sorted(Path.iterdir(path), key=lambda p: p.stat().st_ctime, reverse=True)
    for i, path in enumerate(sorted_paths):
        if (path.is_file() if is_file else path.is_dir()):
            name = path.name
            creation_date = datetime.fromtimestamp(path.stat().st_ctime).strftime('%d/%m/%Y %H:%M:%S')
            path_array.append((i + 1, name, creation_date))
            paths.append(path)
    if not path_array:
        raise MissingFilesError(f"No {'files' if is_file else 'directories'} found in {path}")
    exit_num: int = len(path_array) + 1
    print(tabulate(path_array, headers=["Number", "Name", "Creation Date"], tablefmt="fancy_grid"))
    prompt += f" ({exit_num} to exit):\n"
    option: int = get_valid_int(prompt, 1, exit_num)
    if option == exit_num:
        raise UserCancelledError("User cancelled when selecting a path")
    return paths[option - 1]


def select_network(networks_path: Path, prompt: str) -> Path | None:
    return select_path(networks_path, prompt, is_file=False)


def select_potential(potentials_path: Path, prompt: str) -> Path | None:
    return select_path(potentials_path, prompt, is_file=True)


def get_batch_name(batches_path: Path) -> str:
    """
    Ask the user for a name for the batch

    Args:
        batches_path: the path to the batches directory
    Returns:
        the name of the batch
    Raises:
        UserCancelledError: if the user cancels entering a batch name
    """
    while True:
        batch_name = get_valid_str("Enter a name for the batch ('c' to cancel)\n", forbidden_chars=[" ", "/", r"\\"],
                                   lower=1, upper=20)
        if batch_name == "c":
            raise UserCancelledError("User cancelled when entering a batch name")
        if batches_path.joinpath(f"{batch_name}.zip").exists():
            print("A batch with that name already exists, please try again")
            continue
        try:
            batches_path.joinpath(batch_name).mkdir()
            return batch_name
        except FileExistsError:
            print("A batch with that name already exists, please try again")


def create_bss_input_parameters(template_data: BSSInputData,
                                vary_arrays: list[list[BSSType]],
                                var_indexes: list[int],
                                batches_path: Path,
                                network_path: Path,
                                potential_path: Path) -> None:
    meshgrid = list(product(*vary_arrays))
    batch_name = get_batch_name(batches_path)
    temp_data: BSSInputData = deepcopy(template_data)
    changing_vars = [temp_data.table_relevant_variables[i] for i in var_indexes]
    for array in meshgrid:
        job_name = generate_job_name(changing_vars, array)
        input_files_path = batches_path.joinpath(batch_name, job_name, "input_files")
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


def choose_vars(template_data: BSSInputData) -> tuple[list[list[BSSType]], list[int]]:
    num_vars = get_valid_int("How many variables would you like to vary? (10 to exit)\n", 1, 10)
    if num_vars == 10:
        raise UserCancelledError("User cancelled at number of variables")
    exit_num = len(template_data.table_relevant_variables) + 1
    selected_var_indexes = []
    vary_arrays = []
    while len(selected_var_indexes) < num_vars:
        template_data.table_print(relevant_only=True)
        option = get_valid_int(f"Enter the {NUMBER_ORDERS[len(selected_var_indexes) + 1]} variable ({exit_num} to exit)\n", 1, exit_num)
        if option == exit_num:
            raise UserCancelledError("User cancelled when deciding which variables to vary")
        if option - 1 in selected_var_indexes:
            print("You have already selected this variable")
            continue
        selected_var_indexes.append(option - 1)
        print(f"You have selected {template_data.table_relevant_variables[option - 1].name}")
        vary_array = template_data.table_relevant_variables[option - 1].get_vary_array()
        if vary_array is None:
            raise UserCancelledError("User cancelled when choosing a method of variation")
        vary_arrays.append(vary_array)
    return vary_arrays, selected_var_indexes


def create_batch(template_data: BSSInputData, batches_path: Path, networks_path: Path, potential_paths: Path) -> None:
    try:
        network_path = select_network(networks_path, "Select a network to use for the batch")
        potential_path = select_potential(potential_paths, "Select a potential to use for the batch")
        vary_arrays, selected_var_indexes = choose_vars(template_data)
        create_bss_input_parameters(template_data, vary_arrays, selected_var_indexes, batches_path, network_path, potential_path)
    except UserCancelledError:
        return
    except MissingFilesError as e:
        print(e)
        return


def main() -> None:
    cwd = Path(__file__).parent
    options = get_options(cwd.joinpath("config.csv"))
    username = options["username"]
    common_files_path = cwd.joinpath("common_files")
    common_files_path.joinpath("batch_log.csv").touch(exist_ok=True)
    batches_path = cwd.joinpath("batches")
    batches_path.mkdir(exist_ok=True)
    output_path = cwd.joinpath("output_files")
    output_path.mkdir(exist_ok=True)
    networks_path = cwd.joinpath("networks")
    networks_path.mkdir(exist_ok=True)
    potentials_path = cwd.joinpath("potentials")
    potentials_path.mkdir(exist_ok=True)
    template_data = BSSInputData.from_file(common_files_path.joinpath("bss_parameters.txt"))
    batch_data = BatchData.from_files(common_files_path.joinpath("batch_log.csv"), batches_path)
    while True:
        option = get_valid_int("What would you like to do?\n1) Create a batch\n2) Delete a batch\n"
                               "3) Edit the batch template\n4) Submit batch to Coulson\n5) Exit\n", 1, 5)
        if option == 1:
            create_batch(template_data, batches_path, networks_path, potentials_path)
            batch_data.refresh(batches_path)
        elif option == 2:
            batch_data.delete_batch()
        elif option == 3:
            template_data.edit_value_interactive()
            template_data.export(common_files_path.joinpath("bss_parameters.txt"))
        elif option == 4:
            batch_data.submit_batch(output_path, cwd.joinpath("utils", "batch_submit.py"), username)
        elif option == 5:
            break


if __name__ == "__main__":
    main()
