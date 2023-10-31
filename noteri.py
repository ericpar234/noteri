from textual.app import App, ComposeResult
from textual.widgets import Markdown, TextArea, Markdown, DirectoryTree, Markdown, Label, Input, Switch
from textual.containers import Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.validation import Length
from textual.events import Event
from textual import on
from textual.binding import Binding

import pyperclip 

from functools import partial
from pathlib import Path
from textual.command import Hit, Hits, Provider
import os
import argparse
from tree_sitter_languages import get_language


SCM_PATH = "venv/lib/python3.11/site-packages/textual/tree-sitter/highlights/"

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

        # Cut
        cut_command = f"Cut"
        score = matcher.match(cut_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(cut_command),  
                partial(app.action_cut),
            )
        # Copy
        copy_command = f"Copy"
        score = matcher.match(copy_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(copy_command),  
                partial(app.action_copy),
            )
        # Paste
        paste_command = f"Paste"
        score = matcher.match(paste_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(paste_command),  
                partial(app.action_paste),
            )

        # Table
        table_command = f"Table"
        score = matcher.match(table_command)
        if score > 0:
            yield Hit(
                score,
                matcher.highlight(table_command),  
                partial(app.action_table),
            )

class MarkdownTablePopup(ModalScreen):
    BINDINGS = [ ("escape", "pop_screen") ]

    def __init__(self, callback, validators=None):
        super().__init__()
        self.callback = callback
        self.validators = validators

    def compose(self) -> ComposeResult:
        yield Label("Header")
        yield Switch(id="header")
        yield Label("Rows")
        yield Input(validators=self.validators, id="rows")
        yield Label("Columns")
        yield Input(validators=self.validators, id="columns")

    @on(Input.Submitted)
    def submitted(self, event:Input.Submitted):
        rows = int(self.query_one("#rows", expect_type=Input).value)
        columns = int(self.query_one("#columns", expect_type=Input).value)
        header = self.query_one("#header", expect_type=Switch).value
        self.app.post_message(Noteri.FileSystemCallback(self.callback, (rows, columns, header)))
        self.app.pop_screen()

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
        self.app.post_message(Noteri.FileSystemCallback(self.callback, (event.input.value,)))
        self.app.pop_screen()

class Noteri(App):
    CSS_PATH = "noteri.tcss"
    COMMANDS = App.COMMANDS | {FileCommands} | {WidgetCommands}
    directory = "./"
    filename = None
    languages = []
    clipboard = ""

    BINDINGS = [
        Binding("ctrl+n", "new", "New File"),
        Binding("ctrl+s", "save", "Save File"),
        Binding("shift+ctrl+s", "save_as", "Save As"),
        Binding("ctrl+r", "rename", "Rename File"),
        Binding("ctrl+d", "delete", "Delete File"),
        # Binding("ctrl+shift+x", "cut", "Cut Text", priority=True),
        # Binding("ctrl+shift+c", "copy", "Copy Text", priority=True),
        # Binding("ctrl+shift+v", "paste", "Paste Text", priority=True),
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
        for scm_file in Path(SCM_PATH).glob("*.scm"):
            ta.register_language(get_language(scm_file.stem), scm_file.read_text())
        
        #Find  Binding("ctrl+x", "delete_line", "delete line", show=False) in ta.BINDINGS, and remove it
        ta.BINDINGS = [b for b in ta.BINDINGS if b.key != "ctrl+x"]

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
        
        #get subdirectory of filepath
        path = Path(self.filename).parent / message.href
        self.open_file(path)

    def open_file(self, path: Path) -> None:

        if path == None:
            return
        if path.is_dir():
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
            ".tcss": "css",
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
        else:
            ta.language = None
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
    
    def create_table(self, rows, columns, header):
        ta = self.query_one("TextArea", expect_type=TextArea)
        if header:
            ta.insert(f"|   {'|   '.join([''] * columns)}|\n")
            ta.insert(f"|{'|'.join(['---'] * columns)}|\n")
        for i in range(rows):
            ta.insert(f"|   {'|   '.join([''] * columns)}|\n")


    def cleanup_table(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        md_table = ta.selected_text

        if md_table == "":
            return
        if md_table == None:
            return
        
        lines = md_table.strip().split('\n')
        matrix = [line.split('|')[1:-1] for line in lines[2:]]
        matrix = [[cell.strip() for cell in row] for row in matrix if any(cell.strip() for cell in row)]
        matrix_transposed = list(zip(*matrix))
        matrix_transposed = [col for col in matrix_transposed if any(cell for cell in col)]
        matrix = list(zip(*matrix_transposed))

        # Calculate column widths based on the widest content in each column
        col_widths = [max(len(cell) for cell in col) for col in matrix_transposed]

        # Centering content in each cell
        def center_cell(cell, width):
            padding_total = max(width - len(cell), 0)
            padding_left = padding_total // 2
            padding_right = padding_total - padding_left
            return ' ' * padding_left + cell + ' ' * padding_right

        rebuilt_table = ['| ' + ' | '.join(center_cell(cell, width) for cell, width in zip(row, col_widths)) + ' |' for row in matrix]
        header_cols = lines[0].split('|')[1:-1]
        valid_indices = [i for i, col in enumerate(matrix_transposed) if any(cell for cell in col)]
        rebuilt_header = '| ' + ' | '.join(center_cell(header_cols[i].strip(), col_widths[i]) for i in valid_indices) + ' |'
        rebuilt_separator = '|-' + '-|-'.join('-' * width for width in col_widths) + '-|'
        clean_table = '\n'.join([rebuilt_header, rebuilt_separator] + rebuilt_table)

    
        ta.replace(clean_table, ta.selection.start, ta.selection.end)



            

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

    def action_copy(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        self.clipboard = ta.selected_text
        pyperclip.copy(self.clipboard)
        self.notify(f"Copied {self.clipboard}", title="Copied")

    def action_cut(self):
        self.action_copy()
        ta = self.query_one("TextArea", expect_type=TextArea).delete(ta.selection.start, ta.selection.end)
        
    def action_paste(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.replace(pyperclip.paste(), ta.selection.start, ta.selection.end)

    def action_table(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        if ta.selected_text != "":
            self.cleanup_table()
            return
        self.push_screen(MarkdownTablePopup(self.create_table, validators=[Length(minimum=1)]))

    
    @on(FileSystemCallback)
    def callback_message(self, message:FileSystemCallback):
        message.callback(*message.input)
        

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", default="./", nargs='?', help="Path to file or directory to open")
    args = parser.parse_args()

    app = Noteri(args.path)
    app.run()

if __name__ == "__main__":
    main()
