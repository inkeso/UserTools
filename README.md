Some simple tools for everyday-stuff.  
Some ar Gtk-based, some are for terminal.

### `colorpicker.py`

Just the Gtk3 colorpicker (but preset to the color in clipboard). Picked color will be written to stdout and clipboard (and primary). Needs xclip.


### `colorterminal.py`

Show ANSI-Colors in terminal. 

```
usage: colorterminal.py [ 16 | 256 | rgb | all ]

default is 16
```

### `pyruler.py`

Screenruler with basic measurement-capabilities


### `schild.py`

Display text as a nice banner in terminal.

```
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


### `webkit.py`

Just a window with a WebView (for your WebApp needs)

```
usage: webkit.py [-h] [-n] [-t TITLE] [-g GEOMETRY] [-i ICON] [-j JAVASCRIPT] [URL]

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
                        Start some javascript after loading
```
