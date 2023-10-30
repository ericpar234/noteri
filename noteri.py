from textual.app import App, ComposeResult
from textual.widgets import Markdown, TextArea, Markdown, DirectoryTree, Markdown, Label, Input
from textual.containers import Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.validation import Length
from textual.events import Event
from textual import on

from functools import partial
from pathlib import Path
from textual.command import Hit, Hits, Provider
import os
import argparse

class WidgetCommands(Provider):

    async def startup(self) -> None:  
        self.widgets = ["DirectoryTree", "Markdown", "TextArea"]

    async def search(self, query: str) -> Hits:  
        matcher = self.matcher(query)  
        app = self.app
        assert isinstance(app, Noteri)

        for widget in self.widgets:
            command = f"Toggle {str(widget)}"
            score = matcher.match(command)  
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command),  
                    partial(app.toggle_widget_display, widget),
                    help="Toggle this widget",
                )  

class FileCommands(Provider):
    def read_files(self) -> list[Path]:
        return list(Path(self.app.directory).glob("*.*"))

    async def startup(self) -> None:  
        """Called once when the command palette is opened, prior to searching."""
        worker = self.app.run_worker(self.read_files, thread=True)
        self.python_paths = await worker.wait()

    async def search(self, query: str) -> Hits:  
        """Search for Python files."""
        matcher = self.matcher(query)
        app = self.app
        assert isinstance(app, Noteri)

        for path in self.python_paths:
            command = f"Open {str(path)}"
            score = matcher.match(command)

            # Open File
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command),  
                    partial(app.open_file, path),
                    help="Open this file in the viewer",
                )

        # New File
        new_file_command = f"New File"
        score = matcher.match(new_file_command)
        if score > 0:
            #get last section of string split on space
            file_name = query.split(" ")[-1]
            yield Hit(
                score,
                matcher.highlight(new_file_command),  
                partial(app.new_file, file_name)
            )

        # Save File
        save_file_command = f"Save"
        score = matcher.match(save_file_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(save_file_command),  
                partial(app.save_file),
            )

        # Save As
        save_as_command = f"Save As"
        score = matcher.match(save_as_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(save_as_command),  
                partial(app.push_screen, InputPopup(app.save_file, title="Save As", validators=[Length(minimum=1)])),
            )

        # Rename
        rename_command = f"Rename"
        score = matcher.match(rename_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(rename_command),  
                partial(app.push_screen, InputPopup(app.rename_file, title="Rename", validators=[Length(minimum=1)])),
            )
        
        # Remove
        remove_command = f"Remove"
        score = matcher.match(remove_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(remove_command),  
                partial(app.remove_file, app.filename),
            )

class InputPopup(ModalScreen):

    def __init__(self, callback, title="Input", validators=None):
        super().__init__()
        self.callback = callback
        self.title = title
        self.validators = validators

    def compose(self) -> ComposeResult:
        yield Label(self.title)
        yield Input(validators=self.validators)
    
    # def on_mount(self):
    #     self.query_one("Input", expect_type=Input).focus()

    @on(Input.Submitted)
    def submitted(self, event:Input.Submitted):
        self.app.post_message(Noteri.FileSystemCallback(self.callback, event.input.value))
        self.app.pop_screen()

class Noteri(App):
    CSS_PATH = "noteri.tcss"
    COMMANDS = App.COMMANDS | {FileCommands} | {WidgetCommands}
    directory = "./"
    filename = None

    class FileSystemCallback(Event):
        def __init__(self, callback, input):
            super().__init__()
            self.callback = callback
            self.input = input


    def __init__(self, path="./"):
        super().__init__()
        path = Path(path)
        if path.is_file():
            self.filename = path

            #TODO: Path too

        elif path.is_dir():
            self.directory = path
        

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield DirectoryTree("./")
            yield TextArea(language="markdown")
            with ScrollableContainer():
                yield Markdown()

    def on_mount(self):
        self.query_one("TextArea", expect_type=TextArea).focus()
        self.query_one("Markdown", expect_type=Markdown).display = False
        self.open_file(self.filename)
        pass

    @on(TextArea.Changed)
    def text_area_changed(self, event:TextArea.Changed) -> None:
        self.query_one("Markdown", expect_type=Markdown).update(event.text_area.text)

    @on(DirectoryTree.FileSelected)
    def file_selected(self, event:DirectoryTree.FileSelected):
        self.open_file(event.path)

    @on(Markdown.LinkClicked)
    def linked_clicked(self, message:Markdown.LinkClicked ):
        self.toggle_class("DirectoryTree")
        #read first character of path
        if message.href[0] == "#":
            self.query_one("Markdown", expect_type=Markdown).goto_anchor(message.href[1:])
            return
        self.open_file(message.href)

    def open_file(self, path: Path) -> None:

        if path == None:
            return
        
        ta = self.query_one("TextArea", expect_type=TextArea)

        try:
            with open(path) as f:
                text = f.read()
                ta.clear()
                ta.load_text(text)
                self.filename = path
        except FileNotFoundError as e:
            self.notify(f"File not found: {path}", severity="error", title="FileNotFoundError")
            return
        except UnicodeDecodeError as e:
            self.notify(f"File is not a text file: {path}", severity="error", title="UnicodeDecodeError")
            return

        if path.suffix == ".md":
            self.query_one("Markdown", expect_type=Markdown).display = True
        else:
            self.query_one("Markdown", expect_type=Markdown).display = False

    def toggle_widget_display(self, id):
        widget = self.query_one(id)

        if widget.display:
            #widget.styles.width = "0%"
            widget.display = False
            #widget.disabled = True
            widget.visible = False
            #widget.styles.width = "0"
            return
        else:
            widget.display = True
            #widget.disabled = False
            widget.visible = True
            #widget.styles.width = "1fr"

    def new_file(self, file_name):
        with open(file_name, "w") as f:
            f.write("")
        self.open_file(file_name)
        #python create file
    
    def save_file(self, new_filename=None):
        if self.filename is None and new_filename is None:
            return
        
        filename = self.filename if new_filename is None else new_filename

        with open(filename, "w") as f:
            f.write(self.query_one("TextArea", expect_type=TextArea).text)  
        self.notify(f"Saved {filename}", title="Saved")
        self.filename = filename
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()


    def remove_file(self, filename):
        os.remove(filename)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()

    def rename_file(self, new_filename):

        if new_filename == self.filename:
            return
        
        tmp = self.filename
        self.save_file(new_filename)
        os.remove(tmp)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
    
    @on(FileSystemCallback)
    def callback_message(self, message:FileSystemCallback):
        message.callback(message.input)
        

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", default="./", nargs='?', help="Path to file or directory to open")
    args = parser.parse_args()

    app = Noteri()
    app.run()

if __name__ == "__main__":
    main()
