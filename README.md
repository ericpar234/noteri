# Noteri
A text editor built using textual.

## Install

Install xclip on linux for copy and paste functionality

```bash
sudo apt-get install xclip
```

```
pip install -r requirements
```

## Features

### Markdown Viewer

View markdown documents. Will search for backlinks in path.

### Command Pallet

`cmd + /` to open command pallet

#### Application

`Toggle`: toggle on and off display of widgets


#### File Operations
`New`: Start a new document

`Open`: open a file by name

`Save`: Save the current editor

`Save As`: Input name to save file.

`Rename`: Change the name of the file.

#### Markdown Editor
`Link [FILE PATH]`: Link another file

`Table`: Create a table. With nothing selected, prompts user for row and column size. With selection, will format a table to look nice. Support for tab and return in table.

`Bullet`: Make a bulleted list out of selection

`Numbered List`: Make a numbered list out of selection.

`Table of Contents`: Table of contents from Headings in markdown document.


