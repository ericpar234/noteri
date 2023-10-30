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
from tree_sitter_languages import get_language

# python_language = get_language("python")
# python_highlight_query = (Path(__file__).parent / "python_highlights.scm").read_text()

python_language = get_language("python")
python_highlight_query = (Path(__file__).parent / "venv/lib/python3.11/site-packages/textual/tree-sitter/highlights/python.scm").read_text()
markdown_language = get_language("markdown")
markdown_highlight_query = (Path(__file__).parent / "venv/lib/python3.11/site-packages/textual/tree-sitter/highlights/markdown.scm").read_text()


#TODO: File Exists new file check
#TODO: 

class WidgetCommands(Provider):

    async def startup(self) -> None:  
        self.widgets = ["DirectoryTree", "#md", "Markdown", "TextArea"]

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
                    #help="Open this file in the viewer",
                )

        # New File
        new_file_command = f"New File"
        score = matcher.match(new_file_command)
        if score > 0:
            #get last section of string split on space
            yield Hit(
                score,
                matcher.highlight(new_file_command),  
                partial(self.app.action_new)
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

        # Save File
        save_file_command = f"Save"
        score = matcher.match(save_file_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(save_file_command),  
                partial(app.save_file),
            )

        # Rename
        rename_command = f"Rename"
        score = matcher.match(rename_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(rename_command),  
                partial(app.action_rename),
            )
        
        # Delete
        delete_command = f"Delete"
        score = matcher.match(delete_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(delete_command),  
                partial(app.action_delete),
            )

        # New Directory
        new_directory_command = f"New Directory"
        score = matcher.match(new_directory_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(new_directory_command),  
                partial(app.action_new_directory),
            )

class InputPopup(ModalScreen):
    BINDINGS = [ ("escape", "pop_screen") ]

    def __init__(self, callback, title="Input", validators=None, default=""):
        super().__init__()
        self.callback = callback
        self.title = title
        self.validators = validators
        self.default  = default

    def compose(self) -> ComposeResult:
        yield Label(self.title)
        yield Input(validators=self.validators, value=self.default)
    
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

    BINDINGS = [
        ("ctrl+n", "new", "New File"),
        ("ctrl+s", "save", "Save File"),
        ("shift+ctrl+s", "save_as", "Save As"),
        ("ctrl+r", "rename", "Rename File"),
        ("ctrl+d", "delete", "Delete File"),
    ]

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
        ta = TextArea()
        ta.register_language(python_language, python_highlight_query)
        ta.register_language(markdown_language, markdown_highlight_query)

        with Horizontal():
            yield DirectoryTree(self.directory)
            yield ta
            with ScrollableContainer(id="md"):
                yield Markdown()
            self.notify(f"IS DIR {self.directory}")

    def on_mount(self):
        self.query_one("TextArea", expect_type=TextArea).focus()
        self.query_one("Markdown", expect_type=Markdown).display = False
        self.open_file(self.filename)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
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
        
        path = Path(path)
        
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
        
        
        file_extensions = {
            ".sh": "bash",
            ".css": "css",
            ".html": "html",
            ".json": "json",
            ".md": "markdown",
            ".py": "python",
            ".regex": "regex",
            ".sql": "sql",
            ".toml": "toml",
            ".yaml": "yaml",
        }

        if path.suffix in file_extensions:
            ta.language = file_extensions[path.suffix]
            self.notify(f"Loaded {file_extensions[path.suffix]}", title="Loaded")
        self.configure_widths()

    def toggle_widget_display(self, id):
        widget = self.query_one(id)

        if widget.display:
            widget.display = False
            return
        else:
            widget.display = True

        self.configure_widths()

    def configure_widths(self):
        ids = ["#md", "TextArea"]

        # if both enabled set width to 50%
        # if one enabled set to 100% and 0%
        # if both disabled set to 0%
        
        if self.query_one("#md").display and self.query_one("TextArea").display:
            self.query_one("#md").styles.width = "50%"
            self.query_one("TextArea").styles.width = "50%"
        elif self.query_one("#md").display:
            self.query_one("#md").styles.width = "100%"
            self.query_one("TextArea").styles.width = "0"
        elif self.query_one("TextArea").display:
            self.query_one("#md").styles.width = "0"
            self.query_one("TextArea").styles.width = "100%"
        else:
            self.query_one("#md").styles.width = "0"
            self.query_one("TextArea").styles.width = "0"

    def new_file(self, file_name):
        with open(file_name, "w") as f:
            f.write("")
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
        self.open_file(file_name)
        self.notify(f"Created {file_name}", title="Created")
    
    def save_file(self, new_filename=None):
        if self.filename is None and new_filename is None:
            self.action_save_as()
            return
                
        filename = self.filename if new_filename is None else new_filename

        with open(filename, "w") as f:
            f.write(self.query_one("TextArea", expect_type=TextArea).text)  
        self.notify(f"Saved {filename}", title="Saved")
        self.filename = filename
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()

    def delete_file(self, filename):
        os.remove(filename)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
        self.notify(f"Deleted {filename}", title="Deleted")

    def new_directory(self, directory_name):
        os.mkdir(directory_name)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
        self.notify(f"Created {directory_name}", title="Created")

    def rename_file(self, new_filename):
        if new_filename == self.filename:
            return
        
        tmp = self.filename
        self.save_file(new_filename)
        os.remove(tmp)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
    
    def action_new(self):
        self.push_screen(InputPopup(self.new_file, title="New File", validators=[Length(minimum=1)]))

    def action_save(self):
        self.save_file()
    
    def action_save_as(self):
        self.push_screen(InputPopup(self.save_file, title="Save As", validators=[Length(minimum=1)]))

    def action_rename(self):
        self.push_screen(InputPopup(self.rename_file, title="Rename", validators=[Length(minimum=1)], default=str(self.filename)))
    
    def action_delete(self):
        self.delete_file(self.filename)
    
    def action_new_directory(self):
        self.push_screen(InputPopup(self.new_directory, title="New Directory", validators=[Length(minimum=1)]))

    @on(FileSystemCallback)
    def callback_message(self, message:FileSystemCallback):
        message.callback(message.input)
        

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", default="./", nargs='?', help="Path to file or directory to open")
    args = parser.parse_args()

    app = Noteri(args.path)
    app.run()

if __name__ == "__main__":
    main()
