import subprocess
import multiprocessing


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


def clean_name(string: str, conversions: dict[str, str] = {"(": "", ")": "", "^": "pow", " ": "_"}) -> str:
    """
    Converts all occurrences of characters in the conversions dictionary to their corresponding value in the string
    Args:
        string: The string to be cleaned
        conversions: The dictionary of characters to be converted
    Returns:
        The cleaned string
    """
    return "".join(conversions.get(char, char) for char in string)


def background_process(command_array: tuple[str, ...] | list[str], silent: bool = True) -> None:
    """
    Starts a background process with the given command array that does not terminate when the parent process does
    Args:
        command_array: The command array to be run
        silent: Whether or not to suppress output from the process
    """
    process = multiprocessing.Process(target=child_process, args=[command_array, silent])
    process.daemon = True
    process.start()


def child_process(command_array: tuple[str, ...] | list[str], silent: bool = True) -> None:
    """
    Processes the command array in a new session
    Args:
        command_array: The command array to be run
        silent: Whether or not to suppress output from the process
    """
    if silent:
        subprocess.Popen(command_array, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(command_array, start_new_session=True)
