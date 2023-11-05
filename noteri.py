from textual.app import App, ComposeResult
from textual.widgets import Markdown, TextArea, Markdown, DirectoryTree, Markdown, Label, Input, Switch, Button, Footer, MarkdownViewer
from textual.widgets.text_area import LanguageDoesNotExist
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.validation import Length
from textual.events import Event
from textual import on
from textual import work
from textual.binding import Binding
from textual import events
import pyperclip 

from functools import partial
from pathlib import Path
from textual.command import Hit, Hits, Provider
import os
import argparse
from tree_sitter_languages import get_language
import shutil

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

    def _read_files_helper(self, path, depth = 0):
        file_list = []    
        if depth == 5:
            return []
        
        l = list(Path(path).glob("*"))

        for p in l:
            if p.name[0] == "." or p.name[0] == "venv":
                continue
            if p.is_dir():
                for item in self._read_files_helper(p, depth=depth+1):
                    file_list.append(item)
            elif p.is_file():
                file_list.append(p)
        return file_list


    def read_files(self) -> list[Path]:
        return self._read_files_helper(Path(self.app.directory))
        #return list(Path(self.app.directory).glob("*.*"))

    async def startup(self) -> None:  
        """Called once when the command palette is opened, prior to searching."""
        worker = self.app.run_worker(self.read_files, thread=True)
        self.file_paths = await worker.wait()

    async def search(self, query: str) -> Hits:  
        """Search for files."""
        matcher = self.matcher(query)
        app = self.app
        assert isinstance(app, Noteri)

        commands = {
            "Open": app.open_file,
            "Link File": app.create_link, 
        }

        # Open File
        for command, action in commands.items():
            for path in self.file_paths:
                full_command = f"{command} {str(path)}"
                score = matcher.match(full_command)

                # Open File
                if score > 0:
                    yield Hit(
                        score,
                        matcher.highlight(full_command),  
                        partial(action, path),
                        #help="Open this file in the viewer",
                    )
                

        # Define a map of commands and their respective actions
        commands = {
            "New File": partial(app.action_new),
            "Save As": partial(app.action_save_as),
            "Save": partial(app.action_save),
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
            "Create Link": partial(app.action_create_link),
            "Copy Link": partial(app.action_copy_link),
            "Block Quote": partial(app.action_block_quote),
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
    
class FileSelectionPopup(ModalScreen):
    BINDINGS = [ ("escape", "pop_screen") ]

    def __init__(self, title, callback, message="") -> None:
        super().__init__()
        self.callback = callback
        self.title = title
        self.message = message

        self.selected_file = None

    def compose(self) -> ComposeResult:
        yield DirectoryTree()
        yield Label()
        yield Button("Create Link", "#create")

    @on (DirectoryTree.FileSelected)
    def file_selected(self, message:DirectoryTree.FileSelected):
        self.selected_file = Path(message.path)

    @on(Button.Pressed, "#Create")
    def yes(self, event:Button.Pressed):
        self.app.post_message(Noteri.FileSystemCallback(self.callback, self.selected_file))
        self.app.pop_screen()
    
class ExtendedTextArea(TextArea):
    """A subclass of TextArea with parenthesis-closing functionality."""

    def _insert_bookend_pair(self, bookend_start: str, bookend_end: str) -> None:
        self.selected_text
        if self.selected_text == "":
            self.insert(bookend_start + bookend_end)
            self.move_cursor_relative(columns=-1)
        else:
            selection = self.selection
            text = bookend_start + self.selection + bookend_end
            self.insert(text)
            self.selection = (selection.start, selection.end + len(bookend_end + bookend_start))
        
    def _whitespace(self, spaces: int) -> None:
        
        if spaces < 0:
            spaces = abs(spaces)
            if self.selected_text == "":
                start_location = self.get_cursor_line_start_location()
                text = self.get_text_range(start_location, self.cursor_location)
                # remove leading whitespace from text up to spaces number if whitepsace exists
                if text.startswith(" " * spaces):
                    text = text[spaces:]
                    self.replace(text, start_location, self.cursor_location)
                elif text.startswith("\t"):
                    text = text[1:]
                    self.replace(text, start_location, self.cursor_location)
            else:
                selection = self.selection
                lines = self.selected_text.split("\n")
                new_lines = []
                for line in lines:
                    if line.startswith(" " * spaces):
                        new_lines.append(line[spaces:])
                    else:
                        new_lines.append(line)
                text = "\n".join(new_lines)
                self.insert(text)
                self.selection = (selection.start, selection.end - spaces)
            return

        if self.selected_text == "":
            self.insert(" " * spaces)
        else:
            selection = self.selection
            lines = self.selected_text.split("\n")
            new_lines = []
            for line in lines:
                new_lines.append(" " * spaces + line)
            text = "\n".join(new_lines)
            self.insert(text)


    def _on_key(self, event: events.Key) -> None:

        self.notify(str(event.aliases))
        if event.character == "(":
            self._insert_bookend_pair("(", ")")
            event.prevent_default() 
        elif event.character == "[":
            self._insert_bookend_pair("[", "]")
            event.prevent_default()
        elif event.character == "{":
            self._insert_bookend_pair("{", "}")
            event.prevent_default()
        elif event.character == "'":
            self._insert_bookend_pair("'", "'")
            event.prevent_default()
        elif event.character == '"':
            self._insert_bookend_pair('"', '"')
            event.prevent_default()
        elif event.character == "`":
            self._insert_bookend_pair("`", "`")
            event.prevent_default()
        elif event.character == "<":
            self._insert_bookend_pair("<", ">")
            event.prevent_default()

        elif event.aliases == {"shift+tab"}:
            self.notify(str("SHIFT TAB"))

            self._whitespace(-4)
            event.prevent_default()
             
        elif event.character == "\t":
            self._whitespace(4)
            event.prevent_default()



class Noteri(App):
    CSS_PATH = "noteri.tcss"
    COMMANDS = App.COMMANDS | {FileCommands} | {WidgetCommands}
    BINDINGS = [
        Binding("ctrl+n", "new", "New File"),
        Binding("ctrl+s", "save", "Save File"),
        Binding("shift+ctrl+s", "save_as", "Save As"),
        Binding("ctrl+r", "rename", "Rename File"),
        Binding("ctrl+d", "delete", "Delete File"),
        Binding("ctrl+shift+x", "cut", "Cut Text", priority=True),
        Binding("ctrl+shift+c", "copy", "Copy Text", priority=True),
        Binding("ctrl+shift+v", "paste", "Paste Text", priority=True),
        Binding("ctrl+f", "find", "Find Text"),
        Binding("ctrl+t", "table", "Create Table"),
        Binding("ctrl+shift+t", "bullet_list", "Create Bullet List"),
        Binding("ctrl+shift+n", "numbered_list", "Create Numbered List"),
        Binding("ctrl+shift+b", "block_quote", "Create Block Quote"),
        Binding("ctrl+shift+k", "create_link", "Create Link"),
        Binding("ctrl+shift+l", "copy_link", "Copy Link"),
        Binding("ctrl+shift+h", "horizontal_rule", "Create Horizontal Rule"),
        Binding("ctrl+b", "bold", "Bold Text"),
        Binding("ctrl+i", "italic", "Italic Text"),
        Binding("ctrl+1", "heading", "Heading 1"),
        Binding("ctrl+2", "heading", "Heading 2"),
        Binding("ctrl+3", "heading", "Heading 3"),
        Binding("ctrl+4", "heading", "Heading 4"),
        Binding("ctrl+5", "heading", "Heading 5"),
        Binding("ctrl+6", "heading", "Heading 6"),
        Binding("ctrl+y", "redo", "Redo"),
        Binding("ctrl+z", "undo", "Undo"),

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

        self.directory = "./"
        self.filename = None
        self.languages = []
        self.clipboard = ""
        self.unsaved_changes = False
        self.action_stack = []
        self.selected_directory = self.directory
        self.backlinks = []
        self.history_index = 0
        self.history = []
        self.history_disabled = False
        self.history_counter = 0

        path = Path(path)
        if path.is_file():
            self.filename = path

            #TODO: Path too

        elif path.is_dir():
            self.directory = path
            self.selected_directory = path
        


    def compose(self) -> ComposeResult:
        self.ta = ExtendedTextArea()
        for scm_file in Path(SCM_PATH).glob("*.scm"):
            self.app.ta.register_language(get_language(scm_file.stem), scm_file.read_text())
        
        #Find  Binding("ctrl+x", "delete_line", "delete line", show=False) in self.ta.BINDINGS, and remove it
        self.app.ta.BINDINGS = [b for b in self.ta.BINDINGS if b.key != "ctrl+x"]
        self.app.ta.action_delete_line = self.action_cut
        self.app.ta.delete_word_right = self.action_find
        with Vertical():
            with Horizontal():
                yield DirectoryTree(self.directory)
                yield self.ta
                with Vertical(id="md"):
                    yield Markdown("", id="title")
                    with ScrollableContainer():
                        yield Markdown(id="markdown")
                        yield Markdown(id="backlinks")

        yield Label(id="footer")

    def on_mount(self):
        self.ta.focus()
        self.query_one("#markdown", expect_type=Markdown).display = False
        self.open_file(self.filename)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).watch_path()
        self.print_footer()
        pass

    @work(thread=True, exclusive=True)
    def print_footer(self):
        unsaved_char = ""
        if self.unsaved_changes:
            unsaved_char = "*"

        filename = self.filename
        if self.filename is None:
            filename = "New File"
        
        language = self.ta.language
            
        if language is None:
            language = "Plain Text"

        selected_text = self.ta.selected_text
        #calculate selection width
        cursor_width = ""
        if len(selected_text) > 0:
            cursor_width = f" : {len(selected_text)}"

        cursor_location = self.ta.cursor_location
        self.query_one("#footer", expect_type=Label).update( 
        f"{self.selected_directory} {unsaved_char}{filename} | {language} | {str(cursor_location)}{cursor_width}"
        )

    @on(TextArea.SelectionChanged)
    def cursor_moved(self, event:TextArea.SelectionChanged) -> None:
        self.print_footer()

    def update_markdown(self, text):

        #create a timer to update the markdown in case of rapid typing
        self.query_one("#markdown", expect_type=Markdown).update(text)

    @on(TextArea.Changed)

    def text_area_changed(self, event:TextArea.Changed) -> None:
        self.history_counter += 1
        self.unsaved_changes = True
        self.update_markdown(event.text_area.text)
        self.print_footer()

        if self.history_counter > 5:
            self.add_history()

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
        if message.href.startswith("http"):
            self.notify(f"Opening external link {message.href}")
            os.system(f"open {message.href}")
            return
        
        file_suffixs = [
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".gif",
            ".bmp",
            ".svg",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".zip",
            ".tar",
            ".gz",
            ".tgz",
            ".rar",
            ".7z",
            ".mp3",
            ".mp4",
            ".wav",
            ".ogg",
            ".flac",
            ".avi",
            ".mov",
            ".wmv",
            ".mkv",
            ".webm",
            ".m4a",
            ".m4v",
            ".flv",
            ".mpeg",
            ".mpg",
            ".mpe",
            ".mp2",
            ".mpv",
            ".m2v",
            ".m4v",
            ".3gp",
            ".3g2",
            ".mxf",
            ".roq",
        ]

        for suffix in file_suffixs:
            if message.href.endswith(suffix):
                self.notify(f"Opening external file {self.filename.parent}/{message.href}")
                os.system(f"open {self.filename.parent}/{message.href}")
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

        #TODO: Sort

        for item in self.backlinks:
            backlink_text += f"- [{item.name}]({str(item)})\n"

        if backlink_text != "":
            bl.display = True
            bl.styles.height = "auto"
        else:
            bl.display = False
            bl.styles.height = "0"

        backlink_text = "###\n### Backlinks\n" + backlink_text
        bl.update(backlink_text)

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
        

        try:
            with open(path) as f:
                text = f.read()
                self.ta.load_text(text)
                self.filename = path
                self.selected_directory = path.parent

        except FileNotFoundError as e:
            self.notify(f"File not found: {path}", severity="error", title="FileNotFoundError")
            return
        except UnicodeDecodeError as e:
            #self.notify(f"File is not a text file: {path}", severity="error", title="UnicodeDecodeError")
            os.system(f"open {path}")
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
                self.ta.language = file_extensions[path.suffix]
            except LanguageDoesNotExist:
                self.notify(f"Issue loading {file_extensions[path.suffix]} language.", title="Language Error", severity="error")
                self.ta.language = None
            except NameError:
                self.notify(f"Issue loading {file_extensions[path.suffix]} language.", title="Language Error", severity="error")
                self.ta.language = None
        else:
            self.ta.language = None

        md = self.query_one("#markdown", expect_type=Markdown)
        title = self.query_one("#title", expect_type=Markdown)
        backlinks = self.query_one("#backlinks", expect_type=Markdown)

        if path.suffix == ".md":
            md.display = True
            title.display = True
            backlinks.display = True
            md.update(text)
            title.update("## " + str(self.filename.parts[-1])[:-3])
            self.update_backlinks()

        else:
            title.display = False
            md.display = False
            backlinks.display = False

        self.history.clear()
        self.history_index = 0
        self.add_history()
        
        self.configure_widths()

        self.unsaved_changes = False
        
    def toggle_widget_display(self, id):
        widget = self.query_one(id)

        if widget.display:
            widget.display = False
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
        backlinks = self.query_one("#backlinks")

        ta = self.ta

        if markdown.display and self.ta.display:
            md.styles.width = "50%"
            self.ta.styles.width = "50%"
        elif markdown.display:
            md.styles.width = "100%"
            self.ta.styles.width = "0"
        elif self.ta.display:
            md.styles.width = "0"
            self.ta.styles.width = "100%"
        else:
            md.styles.width = "0"
            self.ta.styles.width = "0"

        # TODO: Cooler way of doing this
        md.display = markdown.display
        title.display = markdown.display
        backlinks.display = markdown.display


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
            f.write(self.ta.text)
        self.notify(f"Saved {filename}", title="Saved")
        self.filename = filename
        self.query_one("DirectoryTree", expect_type=DirectoryTree).watch_path()
        self.unsaved_changes = False
        self.print_footer()

    def delete_file(self):
        dt = self.query_one("DirectoryTree", expect_type=DirectoryTree)
        if dt.cursor_node.daself.ta.path.is_dir():
            shutil.rmtree(dt.cursor_node.daself.ta.path)
        else:
            os.remove(dt.cursor_node.daself.ta.path)
        self.notify(f"Deleted {dt.cursor_node.daself.ta.path}", title="Deleted")
        dt.watch_path()

    def new_directory(self, directory_name):
        os.mkdir(directory_name)
        self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
        self.notify(f"Created {directory_name}", title="Created")

    def rename_file(self, new_filename):
        path = self.query_one("DirectoryTree", expect_type=DirectoryTree).cursor_node.daself.ta.path
        if new_filename == path:
            return
        file_path = Path(new_filename)

        if path.is_dir():
            # move directory
            os.rename(str(path), new_filename)
            self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
        elif path.is_file():
            tmp = self.filename
            self.save_file(new_filename)
            os.remove(tmp)
            self.query_one("DirectoryTree", expect_type=DirectoryTree).reload()
        return
        
    def create_table(self, rows, columns, header):
        self.add_history()
        
        self.history_counter
        insert_text = ""
        if header:
            insert_text += f"|   {'|   '.join([''] * columns)}|\n"
            insert_text += f"|{'|'.join(['---'] * columns)}|\n"

        for i in range(rows):
            row_text = f"|   {'|   '.join([''] * columns)}|\n"
            insert_text += row_text

        self.ta.replace(insert_text, self.ta.selection.start, self.ta.selection.end)

    def cleanup_table(self):
        
        md_table = self.ta.selected_text

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

    
        self.ta.replace(clean_table, self.ta.selection.start, self.ta.selection.end)

    def unsaved_changes_callback(self, value):
        if value:
            self.save_file()
        self.unsaved_changes = False
        self.action_stack.pop()()

    def delete_file_callback(self, value):
        if value:
            self.delete_file()

    def action_new(self):
        self.push_screen(InputPopup(self.new_file, title="New File", validators=[Length(minimum=1)], default = str(self.selected_directory) + "/"))

    def action_new_directory(self):
        self.push_screen(InputPopup(self.new_directory, title="New Directory", validators=[Length(minimum=1)], default = str(self.selected_directory) + "/"))


    def action_save(self):
        self.save_file()
    
    def action_save_as(self):
        self.push_screen(InputPopup(self.save_file, title="Save As", validators=[Length(minimum=1)]))

    def action_rename(self):
        path = self.query_one("DirectoryTree", expect_type=DirectoryTree).cursor_node.daself.ta.path
        self.push_screen(InputPopup(self.rename_file, title="Rename", validators=[Length(minimum=1)], default=str(path)))
    
    def action_delete(self):
        dt = self.query_one("DirectoryTree", expect_type=DirectoryTree)
        self.push_screen(YesNoPopup(f"Delete {dt.cursor_node.daself.ta.path}", self.delete_file_callback))
    
    def action_copy(self):
        
        self.clipboard = self.ta.selected_text
        pyperclip.copy(self.clipboard)
        self.notify(f"{self.clipboard}", title="Copied")

    def action_cut(self):
        self.action_copy()
        
        self.ta.delete(self.ta.selection.start, self.ta.selection.end)
        
    def action_paste(self):
        
        self.ta.replace(pyperclip.paste(), self.ta.selection.start, self.ta.selection.end)

    def action_table(self):
        
        if self.ta.selected_text != "":
            self.cleanup_table()
            return
        self.push_screen(MarkdownTablePopup(self.create_table, validators=[Length(minimum=1)]))

    def action_bullet_list(self):
        
        # in area selected, add a bullet to each line if it doesn't already exist
        lines = self.ta.selected_text.split('\n')
        refactored_lines = []
        for line in lines:
            # Check if the line already starts with a bullet
            if not line.startswith('- '):
                line = f"- {line}"
            refactored_lines.append(line)
        
        self.ta.replace('\n'.join(refactored_lines), self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)

    
    def action_numbered_list(self):
        
        # In area selected, add "1. " to each line if not already numbered and not whitespace
        lines = self.ta.selected_text.split('\n')
        refactored_lines = []
        for line in lines:
            # Check if the line is not just whitespace and doesn't already start with a number followed by a dot and a space
            if line.strip() and not line.lstrip().startswith(tuple(f"{i}." for i in range(1, 10))):
                line = f"1. {line}"

        self.ta.replace('\n'.join(refactored_lines), self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)

    def action_block_quote(self):
        
        refactored_lines = []
        # If there is a selection, wrap it in a code block
        for line in self.ta.selected_text.split('\n'):
            if not line.startswith('>'):
                line = f"> {line}"
            refactored_lines.append(line)
        self.ta.replace('\n'.join(refactored_lines), self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)

    def action_code_block(self):
        

        # If there is a selection, wrap it in a code block
        if self.ta.selected_text != "":
            self.ta.replace(f"```\n{self.ta.selected_text}\n```", self.ta.selection.start, self.ta.selection.end)
            return

    def action_create_link(self):
        self.create_link()

    def action_bold(self):
        
        self.ta.replace(f"**{self.ta.selected_text}**", self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)

    def action_italic(self):
        
        self.ta.replace(f"*{self.ta.selected_text}*", self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)

    def action_horizontal_rule(self):
        
        self.ta.replace(f"---", self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)
    
    def action_heading(self, level):
        
        self.ta.replace(f"{'#' * level} {self.ta.selected_text}", self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)

    def action_find(self):
        self.app.push_screen(InputPopup(self.find_text, title="Find", validators=[Length(minimum=1)]))
        pass

    def find_text(self, search_text):
        
        cursor_location = self.ta.cursor_location

        # calculate the string index from a row collumn on newlines.
        
        text = self.ta.text
        split_lines = text.split("\n")

        #calculate lenths of each line and stop before greater than selection row
        col = -1
        tmp_find_col = -1
        split_lines[0] = split_lines[0][cursor_location[1]:]
        for line in split_lines[cursor_location[0]:]:
            tmp_find_col = line.find(search_text)
            self.notify(f"Line: {line} {tmp_find_col}")
            if tmp_find_col != -1:
                col = tmp_find_col
            break

        if col == -1:
            self.notify(f"Could not find text {search_text}. Selection {cursor_location}. ", title="Find", severity="warning")
            return

        else:
            self.ta.selection = (cursor_location[0], col, cursor_location[0], col + len(search_text))

    def action_copy_link(self):
        
        #put link into clipboard
        text = f"[{self.filename.name}]({self.filename})"
        pyperclip.copy(self.ta.selected_text)

    def add_history(self):
        if self.history_disabled:
            return

        ta = self.query_one("TextArea", TextArea)
        if self.history_index < len(self.history) - 1:
            self.history[self.history_index] = { "text": self.ta.text, 
                                                 "cursor_location": self.ta.cursor_location}
            #remove forward history
            self.history = self.history[:self.history_index + 1]
            #self.notify("Remove forward history")
        else:
            self.history.append({ "text": self.ta.text, 
                                  "cursor_location": self.ta.cursor_location})
        self.history_index += 1
        self.history_counter = 0
        #self.notify(f"add history. {self.history_index} {len(self.history)}")

        # make self.history only latest 10
        if len(self.history) > 10:
            self.history = self.history[-10:]
            self.history_index = 9

    def action_undo(self):
        
        self.notify(f"Index: {self.history_index} Len History: {len(self.history)}")

        if self.history_index > 0:
            self.history_index -= 1
            self.history_disabled = True
            self.add_history()
            self.ta.load_text(self.history[self.history_index]["text"])
            self.ta.cursor_location = self.history[self.history_index]["cursor_location"]
            self.history_counter = -1
            self.notify(f"{self.history_index} {len(self.history)}")
        
        self.history_disabled = False

        if self.history_index == 0:
            self.add_history()

    def action_redo(self):
        

        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.history_disabled = True
            self.ta.load_text(self.history[self.history_index]["text"])
            self.ta.cursor_location = self.history[self.history_index]["cursor_location"]
            self.history_counter = -1
        self.history_disabled = False

    def create_link(self, link:str=None, message=None, relative=True):
        

        if link == None:
            #TODO: Fuzzy match existing files
            if self.ta.selected_text.startswith('htt') or self.ta.selected_text.startswith("#"):
                link = self.ta.selected_text
            elif  self.ta.selected_text.endswith(".md"):
                link = self.ta.selected_text
            else:
                link = ""

        if str(link).endswith(".md") and relative:
            link_path = Path(link)
            
            try:
                self.notify(f"{self.selected_directory}\n{link_path}")
                link = link_path.relative_to(self.selected_directory)
            except ValueError as e:
                self.notify(f"Could not find relative path for {link_path}, using abs")
                link = self.ta.selected_text

        if message == None and str(link).endswith(".md"):
            message = str(Path(link).name)[:-3]

        if message == None:
            if self.ta.selected_text == "":
                message = ""
            else:
                message = self.ta.selected_text

        self.ta.replace(f"[{message}]({link})", self.ta.selection.start, self.ta.selection.end, maintain_selection_offset=False)        

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
