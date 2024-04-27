import openai
import json
import os
from colorama import Fore, Style
import click
from click import echo
import textwrap

class Chat:
    message_history: list[dict[str, str]] = []
    saved: bool = False

    def __init__(self, filename=None):
        if filename:
            with open(filename, 'r') as f:
                self.message_history = json.load(f)

    def log(self, message: str, role: str):
        self.message_history.append({
            'role': role,
            'content': message,
        })
        return self

    def log_user(self, message: str):
        return self.log(message, 'user')

    def log_system(self, message: str):
        return self.log(message, 'system')

    def log_assistant(self, message: str):
        return self.log(message, 'assistant')

    def send(self) -> str:
        if not self.message_history:
            print("Must provide a message to start a chat")
            return ""

        res = openai.ChatCompletion.create(
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            messages=self.message_history,
        )
        return res['choices'][0]['message']['content']

    def save(self, filename, old_filename=None):
        if self.message_history:
            with open(filename, 'w') as f:
                json.dump(self.message_history, f, indent=2)
            if old_filename and os.path.exists(old_filename):
                os.remove(old_filename)

    def display_sep(self, role: str, subtitle=None, **kwargs):
        role = role.upper()
        mapping = dict(
            SYSTEM=Fore.LIGHTCYAN_EX,
            ASSISTANT=Fore.LIGHTMAGENTA_EX,
            USER = Fore.LIGHTGREEN_EX,
        )
        text = mapping[role] + role
        if subtitle:
            text += Style.RESET_ALL + " " + subtitle
        echo(text, **kwargs)

    def display_history(self):
        for message in self.message_history:
            self.display_sep(message['role'])
            echo(block(message['content']))
            echo("\n")


def block(text, width=100):
    wrapped_lines = []
    for line in text.splitlines():
        wrapped_line = textwrap.fill(line, width=width, break_long_words=False, break_on_hyphens=False)
        wrapped_lines.append(wrapped_line)
    return '\n'.join(wrapped_lines)
