Some simple tools for everyday-stuff.  
Some ar Gtk-based, some are for terminal.

Everything is independed of another, feel free to cherrypick. Also everything 
is tiny so be shure to check the sourccode for customizations.


### `colorpicker.py`

Just the Gtk3 colorpicker (but preset to the color in clipboard). Picked color 
will be written to stdout and clipboard (and primary). Needs xclip.


### `colorterminal.py`

Show ANSI-Colors in terminal. 

```text
usage: colorterminal.py [ 16 | 256 | rgb | all ]

default is 16
```


### jsonview.py

A simple GUI JSON-Viewer (Gtk). Accepts files and stdin.


### preview

A shellscript wrapping fzf and some other tools for very convenient navigation 
in various filelists.

Eg. `fd -i 'filename' | preview` or `locate -i 'filename' | preview`


### pms.py

Search for packages with pacman.

Show results in an interactive list, allowing for installation.

Other output options are available (JSON, CSV).


### `pyruler.py`

Screenruler with basic measurement-capabilities


### `schild.py`

Display text as a nice banner in terminal.

```text
usage: schild.py [-h] [-b {single,double,thick,underline,narrow,ascii,slashes,slashstar,octothorpe,none}]
                 [-c {cyan,green,red,cyan256,oran256,blue256,grey256,none}] [-d] [-l] [-o]

Pipe some text into this program to make a fancy sign.

optional arguments:
  -h, --help            show this help message and exit
  -b {single,double,thick,underline,narrow,ascii,slashes,slashstar,octothorpe,none}, --border {single,double,thick,underline,narrow,ascii,slashes,slashstar,octothorpe,none}
                        Use a different border
  -c {cyan,green,red,cyan256,oran256,blue256,grey256,none}, --color {cyan,green,red,cyan256,oran256,blue256,grey256,none}
                        Use a different color
  -d, --demo            Show all borders and colors
  -l, --left            Align left (do not center)
  -o, --outer           large sign: border as wide as the screen

```

### `ttfview.py`

Preview all font-files in current directory (or directory given as parameter)


### watch.sh

Needs _zsh_ and _expect_.

Interactive alternative to shell builtin »watch« with a nicer interface, allowing for instant interval changes.
It also handles complex commands a bit better. e.g.:
```sh
./watch.sh 'ls -l | tac'
```

```text
Usage:
 usage [options] command

Options:
  -b           beep if command has a non-zero exit
  -e           exit if command has a non-zero exit
  -n <secs>    seconds to wait between updates
  -h           display this help and exit
```

### `webkit.py`

Just a window with a WebView (for your WebApp needs)

```text
usage: webkit.py [-h] [-n] [-t TITLE] [-g GEOMETRY] [-i ICON] [-j JAVASCRIPT] [-c CSS] [URL]

positional arguments:
  URL                   URL

optional arguments:
  -h, --help            show this help message and exit
  -n, --no-escape       Do not Exit on Escape
  -t TITLE, --title TITLE
                        Window title. Defaults to URL.
  -g GEOMETRY, --geometry GEOMETRY
                        Window geometry. <Width>x<Height>[+<x+y|center>]
  -i ICON, --icon ICON  Set icon from imagefile
  -j JAVASCRIPT, --javascript JAVASCRIPT
                        Start some javascript after loading. May be a long string containing JS or a filename.
  -c CSS, --css CSS     Apply user-css. May be a long string containing CSS or a filename.

```
"-" as a filename for `-j` for `-c` won't work. (But each file is read only 
once, so you can use named pipes or fifos) Files are autodetected first, so if 
you start e.g.:
```sh
./webkit.py -j 'document.querySelectorAll(".footer").forEach(x=>x.style.display="none")' 'https://www.wikipedia.org'
```
and happen to have a file called `document.querySelectorAll(".footer").forEach(x=>x.style.display="none")`
in the current directory, the file is loaded (otherwise the JS will be execute as expected).

This also means that missing files are ignored silently (interpreted as JS/CSS 
which will probably fail).

Here is the same result for `-c` (just for the sake of this example):
```sh
./webkit.py -c '.footer{display:none}' 'https://www.wikipedia.org'
```

Use CSS to customize pages whenever you can. Custom JS tends to slow down 
startup/loading and is also applied only once on initial loading, not for any 
subsequent page-loads (clicking on a link or something).
Custom CSS is applied to every page.


### x3.sh

A simple shellscript for starting X11 without _startx_ and _xinit_, based on https://github.com/Earnestly/sx
Launches `$HOME/.xinitrc` or any given script (given as 1. parameter).



