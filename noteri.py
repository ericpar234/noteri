from textual.app import App, ComposeResult
from textual.widgets import Markdown, TextArea, Markdown, DirectoryTree, Markdown, Label, Input, Switch, Button, Footer, MarkdownViewer
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.validation import Length
from textual.events import Event
from textual import on
from textual import work
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
        self.widgets = ["DirectoryTree", "#markdown", "TextArea", "#footer"]

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

        # Define a map of commands and their respective actions
        commands = {
            "New File": partial(app.action_new),
            "Save As": partial(app.push_screen, InputPopup(app.save_file, title="Save As", validators=[Length(minimum=1)])),
            "Save": partial(app.save_file),
            "Rename": partial(app.action_rename),
            "Delete": partial(app.action_delete),
            "Find": partial(app.action_find),
            "New Directory": partial(app.action_new_directory),
            "Cut": partial(app.action_cut),
            "Copy": partial(app.action_copy),
            "Paste": partial(app.action_paste),
            "Table": partial(app.action_table),
            "Bullet List": partial(app.action_bullet_list),
            "Numbered List": partial(app.action_numbered_list),
            "Code Block": partial(app.action_code_block),
            "Bold": partial(app.action_bold),
            "Italic": partial(app.action_italic),
            "Horizontal Rule": partial(app.action_horizontal_rule),
            "Heading 1": partial(app.action_heading, 1),
            "Heading 2": partial(app.action_heading, 2),
            "Heading 3": partial(app.action_heading, 3),
            "Heading 4": partial(app.action_heading, 4),
            "Heading 5": partial(app.action_heading, 5),
            "Heading 6": partial(app.action_heading, 6),
        }

        # Loop through the commands map
        for command, action in commands.items():
            score = matcher.match(command)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command),
                    action
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

class YesNoPopup(ModalScreen):

    BINDINGS = [ ("escape", "pop_screen") ]

    def __init__(self, title, callback, message="") -> None:
        super().__init__()
        self.callback = callback
        self.title = title
        self.message = message

    def compose(self) -> ComposeResult:
        yield Label(self.title)
        yield Label(self.message)
        yield Button("Yes", id="yes")
        yield Button("No", id="no", variant="error")

    @on(Button.Pressed, "#yes")
    def yes(self, event:Button.Pressed):
        self.app.post_message(Noteri.FileSystemCallback(self.callback, (True,)))
        self.app.pop_screen()
    
    @on(Button.Pressed, "#no")
    def no(self, event:Button.Pressed):
        self.app.post_message(Noteri.FileSystemCallback(self.callback, (False,)))
        self.app.pop_screen()
    
        

class Noteri(App):
    CSS_PATH = "noteri.tcss"
    COMMANDS = App.COMMANDS | {FileCommands} | {WidgetCommands}
    directory = "./"
    filename = None
    languages = []
    clipboard = ""
    unsaved_changes = False
    action_stack = []
    selected_directory = directory
    backlinks = []

    BINDINGS = [
        Binding("ctrl+n", "new", "New File"),
        Binding("ctrl+s", "save", "Save File"),
        Binding("shift+ctrl+s", "save_as", "Save As"),
        Binding("ctrl+r", "rename", "Rename File"),
        Binding("ctrl+d", "delete", "Delete File"),
        Binding("ctrl+shift+x", "cut", "Cut Text", priority=True),
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
            self.selected_directory = path
        

    def compose(self) -> ComposeResult:
        ta = TextArea()
        for scm_file in Path(SCM_PATH).glob("*.scm"):
            ta.register_language(get_language(scm_file.stem), scm_file.read_text())
        
        #Find  Binding("ctrl+x", "delete_line", "delete line", show=False) in ta.BINDINGS, and remove it
        ta.BINDINGS = [b for b in ta.BINDINGS if b.key != "ctrl+x"]

        with Vertical():
            with Horizontal():
                yield DirectoryTree(self.directory)
                yield ta
                with Vertical(id="md"):
                    yield Label("", id="title")
                    with ScrollableContainer():
                        yield Markdown(id="markdown")
                        yield Markdown(id="backlinks")

        yield Label(id="footer")

    def on_mount(self):
        self.query_one("TextArea", expect_type=TextArea).focus()
        self.query_one("#markdown", expect_type=Markdown).display = False
        self.open_file(self.filename)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).watch_path()
        self.print_footer()
        pass

    @work(thread=True, exclusive=False)
    def print_footer(self):
        unsaved_char = ""
        if self.unsaved_changes:
            unsaved_char = "*"

        filename = self.filename
        if self.filename is None:
            filename = "New File"
        
        language = self.query_one("TextArea", expect_type=TextArea).language
            
        if language is None:
            language = "Plain Text"

        selected_text = self.query_one("TextArea", expect_type=TextArea).selected_text
        #calculate selection width
        cursor_width = ""
        if len(selected_text) > 0:
            cursor_width = f" : {len(selected_text)}"

        cursor_location = self.query_one("TextArea", expect_type=TextArea).cursor_location
        self.query_one("#footer", expect_type=Label).update( 
        f"{unsaved_char}{filename} | {language} | {str(cursor_location)}{cursor_width}"
        )

    @on(TextArea.SelectionChanged)
    def cursor_moved(self, event:TextArea.SelectionChanged) -> None:
        self.print_footer()

    @on(TextArea.Changed)
    def text_area_changed(self, event:TextArea.Changed) -> None:
        self.unsaved_changes = True
        self.query_one("#markdown", expect_type=Markdown).update(event.text_area.text)
        self.print_footer()

    @on(DirectoryTree.FileSelected)
    def file_selected(self, event:DirectoryTree.FileSelected):
        self.open_file(event.path)
        self.unsaved_changes = False

    @on(DirectoryTree.DirectorySelected)
    def directory_selected(self, event:DirectoryTree.DirectorySelected):
        self.selected_directory = (event.path)

    @on(Markdown.LinkClicked)
    def linked_clicked(self, message:Markdown.LinkClicked ):
        self.toggle_class("DirectoryTree")
        #read first character of path
        if message.href[0] == "#":
            self.query_one("#markdown", expect_type=Markdown).goto_anchor(message.href[1:])
            return
        
        #get subdirectory of filepath
        #path = Path(self.filename).parent / message.href
        if message.markdown.id == "backlinks":
            path = Path(message.href)
        else:
            path = Path(self.filename).parent / message.href

        self.open_file(path)

    def _update_backlinks_helper(self, path:Path):
        glob = list(Path(path).glob("./*"))

        for item in glob:
            if item.name[0] == ".":
                continue

            if item.is_dir():
                self._update_backlinks_helper(item)
            elif item.name.endswith(".md"):
                with open(item, "r") as f:
                    text = f.read()
                    if text.find( self.filename.name + ")") != -1:
                        self.backlinks.append(item)

    def update_backlinks(self):
        self.backlinks.clear()
        bl = self.query_one("#backlinks", expect_type=Markdown)
        self._update_backlinks_helper(self.directory)

        backlink_text = ""
        for item in self.backlinks:
            backlink_text += f"- [{item.name}]({str(item)})\n"
        
        if backlink_text != "":
            backlink_text = "###\n### Backlinks\n" + backlink_text
            bl.update(backlink_text)
            bl.display = True
        else:
            bl.display = False

    def open_file(self, path: Path) -> None:

        if path == None:
            return
        if path.is_dir():
            return

        if self.unsaved_changes:
            self.action_stack.insert(0, partial(self.open_file, path))
            self.push_screen(YesNoPopup("Unsaved Changes",  self.unsaved_changes_callback, message=f"Save Changes to {self.filename} ?"))
            return

        path = Path(path)
        
        ta = self.query_one("TextArea", expect_type=TextArea)

        try:
            with open(path) as f:
                text = f.read()
                ta.load_text(text)
                self.filename = path
                self.selected_directory = path.parent

        except FileNotFoundError as e:
            self.notify(f"File not found: {path}", severity="error", title="FileNotFoundError")
            return
        except UnicodeDecodeError as e:
            self.notify(f"File is not a text file: {path}", severity="error", title="UnicodeDecodeError")
            return
         
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
            try:
                ta.language = file_extensions[path.suffix]
            except NameError:
                self.notify(f"Issue loading {file_extensions[path.suffix]} language.", title="Language Error", severity="error")
                ta.language = None
        else:
            ta.language = None

        md = self.query_one("#markdown", expect_type=Markdown)
        title = self.query_one("#title", expect_type=Label)

        if path.suffix == ".md":
            md.display = True
            title.display = True
            md.update(text)
            title.update(self.filename.parts[-1])
            self.update_backlinks()

        else:
            title.display = False
            md.display = False

        

        self.configure_widths()

        self.unsaved_changes = False
        
    def toggle_widget_display(self, id):
        widget = self.query_one(id)

        if widget.display:
            widget.display = False
            return
        else:
            widget.display = True

        self.configure_widths()

    def configure_widths(self):

        # if both enabled set width to 50%
        # if one enabled set to 100% and 0%
        # if both disabled set to 0%

        markdown = self.query_one("#markdown")
        md = self.query_one("#md")
        title = self.query_one("#title")
        ta = self.query_one("TextArea")

        if markdown.display and ta.display:
            markdown.styles.width = "50%"
            ta.styles.width = "50%"
        elif markdown.display:
            markdown.styles.width = "100%"
            ta.styles.width = "0"
        elif ta.display:
            markdown.styles.width = "0"
            ta.styles.width = "100%"
        else:
            markdown.styles.width = "0"
            ta.styles.width = "0"
        
        title.width = markdown.styles.width

        md.display = markdown.display        

    def new_file(self, file_name):
        with open(file_name, "w") as f:
            f.write("")
        self.query_one("DirectoryTree", expect_type=DirectoryTree).watch_path()
        self.open_file(Path(file_name))
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
        self.query_one("DirectoryTree", expect_type=DirectoryTree).watch_path()
        self.unsaved_changes = False
        self.print_footer()

    def delete_file(self, filename):
        os.remove(filename)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).watch_path()
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
        header_cols = lines[0].split('|')[1:-1]
        matrix = [line.split('|')[1:-1] for line in lines[2:]]
        matrix = [[cell.strip() for cell in row] for row in matrix if any(cell.strip() for cell in row)]
        matrix.insert(0, [col.strip() for col in header_cols])  # Include headers in the matrix for width calculation
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

        rebuilt_table = ['| ' + ' | '.join(center_cell(cell, width) for cell, width in zip(row, col_widths)) + ' |' for row in matrix[1:]]  # Exclude header row
        rebuilt_header = '| ' + ' | '.join(center_cell(cell, width) for cell, width in zip(matrix[0], col_widths)) + ' |'
        rebuilt_separator = '|-' + '-|-'.join('-' * width for width in col_widths) + '-|'
        clean_table = '\n'.join([rebuilt_header, rebuilt_separator] + rebuilt_table)

    
        ta.replace(clean_table, ta.selection.start, ta.selection.end)

    def unsaved_changes_callback(self, value):
        if value:
            self.save_file()
        self.unsaved_changes = False
        self.action_stack.pop()()


    def action_new(self):
        self.push_screen(InputPopup(self.new_file, title="New File", validators=[Length(minimum=1)], default = str(self.selected_directory) + "/"))

    def action_new_directory(self):
        self.push_screen(InputPopup(self.new_directory, title="New Directory", validators=[Length(minimum=1)], default = str(self.selected_directory) + "/"))


    def action_save(self):
        self.save_file()
    
    def action_save_as(self):
        self.push_screen(InputPopup(self.save_file, title="Save As", validators=[Length(minimum=1)]))

    def action_rename(self):
        self.push_screen(InputPopup(self.rename_file, title="Rename", validators=[Length(minimum=1)], default=str(self.filename)))
    
    def action_delete(self):
        self.delete_file(self.filename)
    
    def action_copy(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        self.clipboard = ta.selected_text
        pyperclip.copy(self.clipboard)
        self.notify(f"{self.clipboard}", title="Copied")

    def action_cut(self):
        self.action_copy()
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.delete(ta.selection.start, ta.selection.end)
        
    def action_paste(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.replace(pyperclip.paste(), ta.selection.start, ta.selection.end)

    def action_table(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        if ta.selected_text != "":
            self.cleanup_table()
            return
        self.push_screen(MarkdownTablePopup(self.create_table, validators=[Length(minimum=1)]))

    def action_bullet_list(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        # in area selected, add a bullet to each line if it doesn't already exist
        lines = ta.selected_text.split('\n')
        refactored_lines = []
        for line in lines:
            # Check if the line already starts with a bullet
            if not line.startswith('- '):
                line = f"- {line}"
            refactored_lines.append(line)
        
        ta.replace('\n'.join(refactored_lines), ta.selection.start, ta.selection.end, maintain_selection_offset=False)

    
    def action_numbered_list(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        # In area selected, add "1. " to each line if not already numbered and not whitespace
        lines = ta.selected_text.split('\n')
        refactored_lines = []
        for line in lines:
            # Check if the line is not just whitespace and doesn't already start with a number followed by a dot and a space
            if line.strip() and not line.lstrip().startswith(tuple(f"{i}." for i in range(1, 10))):
                line = f"1. {line}"
            refactored_lines.append(line)

        ta.replace('\n'.join(refactored_lines), ta.selection.start, ta.selection.end, maintain_selection_offset=False)

    def action_code_block(self):
        ta = self.query_one("TextArea", expect_type=TextArea)

        # If there is a selection, wrap it in a code block
        if ta.selected_text != "":
            ta.replace(f"```\n{ta.selected_text}\n```", ta.selection.start, ta.selection.end)
            return
        
    def action_create_link(self, link, message):
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.replace(f"[{message}]({link})", ta.selection.start, ta.selection.end, maintain_selection_offset=False)

    def action_bold(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.replace(f"**{ta.selected_text}**", ta.selection.start, ta.selection.end, maintain_selection_offset=False)

    def action_italic(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.replace(f"*{ta.selected_text}*", ta.selection.start, ta.selection.end, maintain_selection_offset=False)

    def action_horizontal_rule(self):
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.replace(f"---", ta.selection.start, ta.selection.end, maintain_selection_offset=False)
    
    def action_heading(self, level):
        ta = self.query_one("TextArea", expect_type=TextArea)
        ta.replace(f"{'#' * level} {ta.selected_text}", ta.selection.start, ta.selection.end, maintain_selection_offset=False)

    def action_find(self):
        pass

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
