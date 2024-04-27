import click
from click import echo
from openai_chat.chat import Chat
import os
import re
import openai
from datetime import datetime
from glob import glob
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from colorama import Fore, Style
import colorama
import textwrap


DATE_FMT = "%I.%M.%S %p %A %b %d %Y"
PATH_NAME = ".openai_chat_history"

path = os.path.join(os.path.expanduser("~"), PATH_NAME)


@click.command()
@click.argument("action", type=click.Choice(["chat", "new", "history"]), default="chat")
@click.option(
    "--delete",
    "-d",
    help="Delete a previous chat. Pass integer to delete nth most recent chat.",
    default=None,
)
@click.option(
    "--jump",
    "-j",
    help="Jump to a previous chat. Pass integer to jump to nth most recent chat.",
    default=None,
)
def main(*args, **kwargs):
    colorama.init(autoreset=True)
    return run(*args, **kwargs)


def run(action, delete, jump):
    if action == "history":
        return display_history()
    if delete:
        return delete_chat(delete)
    key = get_key()
    if not key:
        return
    openai.api_key = key

    if not os.path.exists(path):
        os.mkdir(path)

    curr_chat_file = datetime.now().strftime(DATE_FMT) + ".json"
    curr_chat_file = os.path.join(path, curr_chat_file)
    last_chat_file = None
    opening_subtitle = None

    if action == "new":
        chat = Chat()
    else:
        last_chat_file = get_chat_by_index(jump)
        if not last_chat_file:
            return print("No previous chat sessions found")
        chat = Chat(last_chat_file)
        chat.display_history()
        opening_subtitle = f"   (Resumed from {prettify_date(get_fname(last_chat_file))})"

    key_bindings = KeyBindings()
    done = False

    @key_bindings.add(Keys.ControlK)
    def _(event):
        event.current_buffer.validate_and_handle()

    @key_bindings.add(Keys.ControlS)
    def _(event):
        nonlocal done
        done = True
        event.current_buffer.validate_and_handle()

    session = PromptSession(key_bindings=key_bindings)

    while True:
        chat.display_sep("user", opening_subtitle)
        opening_subtitle = None
        try:
            user_input = session.prompt("", multiline=True).strip()
        except KeyboardInterrupt:
            print("Saving and quitting")
            return chat.save(curr_chat_file, last_chat_file)

        if user_input.lower() in ["q", ""]:
            print("Saving and quitting")
            return

        if done:
            echo("Saving...")
        else:
            echo("Chatting...")
        chat.log_user(user_input)
        chat.save(curr_chat_file, last_chat_file)
        if done:
            return
        response = chat.send()
        chat.log_assistant(response)
        chat.save(curr_chat_file)
        echo("\033[F\033[K")
        chat.display_sep("assistant")
        echo(block(response))


def validate_date(s) -> bool:
    try:
        datetime.strptime(s, DATE_FMT)
        return True
    except ValueError:
        return False


def get_fname(path) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def prettify_date(s) -> str:
    s = s.replace(".", ":")
    # s = re.sub(r"(\d\d:\d\d):\d\d", r"\1", s)
    s = re.sub(r" \d\d\d\d$", "", s)
    s = re.sub(r" AM ", "am ", s)
    s = re.sub(r" PM ", "pm ", s)
    s = re.sub(r"^0", "", s)
    return s


def delete_chat(index=None) -> None:
    record = get_chat_by_index(index, strict=True)
    if not record:
        return print(f"No chat found at index {index}")
    if input(f"Delete '{get_fname(record)}'? (y/n): ").lower() == "y":
        os.remove(record)
        print("Deleted.")


def get_chat_by_index(find_index=None, strict=False) -> str | None:
    history = sorted_chat_history()
    if not history:
        return None

    if find_index is None:
        find_index = 0

    index = int(find_index)

    too_small = index + len(history) < 0
    too_large = index >= len(history)

    if strict and (too_small or too_large):
        return None

    if too_small:
        print("Index out of bounds. Defaulting to most recent chat.")
        return history[0]
    if too_large:
        print("Index out of bounds. Defaulting to earliest chat.")
        return history[-1]

    return history[index]


def sorted_chat_history() -> list[str]:
    """
    Newest first.
    """
    # Filtered the files by the desired format
    json_files = [
        f for f in glob(os.path.join(path, "*.json")) if validate_date(get_fname(f))
    ]
    if not json_files:
        return []

    return list(
        reversed(
            sorted(
                json_files,
                key=lambda f: datetime.strptime(get_fname(f), DATE_FMT),
            )
        )
    )


def display_history(page: int = 0) -> None:
    history = sorted_chat_history()
    if not history:
        return print("No previous chat sessions found")

    ichunks = list(enumerate(chunk_list_indexed(history, 3), start=1))
    num_chunks = len(ichunks)

    for page, ichats in ichunks:
        if page == 1:
            print(f"\nPress enter to view more, or 'q' to quit")
            print("=" * 50)
        for i, fname in ichats:
            print(f"({i})  {prettify_date(get_fname(fname))}")
        print("-" * 37 + f" Pg. {page}/{num_chunks} ----")
        if page < num_chunks:
            char = click.getchar()
            try:
                int(char)
                return run(action="chat", delete=None, jump=int(char))
            except ValueError:
                if char.lower() == "q":
                    break


def get_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        bash_file = os.path.join(os.path.expanduser("~"), ".bashrc")
        print(
            "Please set the OPENAI_API_KEY environment variable.\n"
            "You can get an API key from https://beta.openai.com/account/api-keys.\n"
            "You can set the environment variable by running the following command\n"
            "in your terminal:\n"
            "   export OPENAI_API_KEY='XXXXXX'\n"
            "This will only set it temporarily. To set it permanently, add the command above\n"
            "to the end of your shell's startup script (e.g. ~/.bashrc or ~/.zshrc)."
            "To see which kind of shell you are using, run the following command:\n"
            "   echo $SHELL\n"
            f"For example, if you're using bash, look for the file, '{bash_file}'.\n"
            "If it doesn't exist, create it. Then add the above 'export ...' command\n"
            "to the file."
        )
        return None
    return key


def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def chunk_list_indexed(lst, n):
    for i in range(0, len(lst), n):
        yield [(j + i, x) for j, x in enumerate(lst[i : i + n])]


def block(text, width=100):
    wrapped_lines = []
    for line in text.splitlines():
        wrapped_line = textwrap.fill(line, width=width, break_long_words=False, break_on_hyphens=False)
        wrapped_lines.append(wrapped_line)
    return '\n'.join(wrapped_lines)


def dedent_wrap(s, prefix_mask='InfeasibleEdgeConstraint: ') -> str:
    s = prefix_mask + ' '.join(s.split())
    wraps = textwrap.wrap(textwrap.dedent(s.strip()), width=80)
    wraps[0] = wraps[0].replace(prefix_mask, '')
    return '\n'.join(wraps)
