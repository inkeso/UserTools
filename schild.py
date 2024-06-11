#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re, sys, argparse

# define styles & colors
borderstyles = {
    'single'    : { 'top' : "┌─┐", 'lr' : "│ │", 'btm' : "└─┘" },
    'double'    : { 'top' : "╔═╗", 'lr' : "║ ║", 'btm' : "╚═╝" },
    'thick'     : { 'top' : "▛▀▜", 'lr' : "▌ ▐", 'btm' : "▙▄▟" },
    'thickin'   : { 'top' : "▗▄▖", 'lr' : "▐ ▌", 'btm' : "▝▀▘" },
    'underline' : { 'top' : "   ", 'lr' : "   ", 'btm' : " ─ " },
    'strike'    : { 'top' : "   ", 'lr' : "»─«", 'btm' : "   " },
    'narrow'    : { 'top' : " ▁ ", 'lr' : "▕ ▏", 'btm' : " ▔ " },
    'brailin'   : { 'top' : "⢀⠤⡀", 'lr' : "⢸ ⡇", 'btm' : "⠈⠒⠁" },
    'brailout'  : { 'top' : "⡎⠉⢱", 'lr' : "⡇ ⢸", 'btm' : "⢇⣀⡸" },
    'braille'   : { 'top' : "⣾⠛⣷", 'lr' : "⣿ ⣿", 'btm' : "⢿⣤⡿" },
    'ascii'     : { 'top' : ",-.", 'lr' : "| |", 'btm' : "`-´" },
    'slashes'   : { 'top' : ("//", "=" ,"//"), 'lr' : ("//", " ", "//"), 'btm' : ("//", "=" ,"//") },
    'slashstar' : { 'top' : ("/*", "*" ,"**"), 'lr' : ("**", " ", "**"), 'btm' : ("**", "*" ,"*/") },
    'octothorpe': { 'top' : ("##", "#" ,"##"), 'lr' : ("##", " ", "##"), 'btm' : ("##", "#" ,"##") },
    'none'      : { 'top' : "   ", 'lr'  : "   ", 'btm' : "   " }
}

bordercolors = {
    'cyan'  : { # default. every 'theme' must have those 4:
        'bc1' : "\033[1;36m", # ANSI-Escapecode to set border-color (upper-right)
        'bc2' : "\033[1;36m", # ANSI-Escapecode to set border-color (lower-left)
        'fc'  : "\033[0;93m", # ANSI-Escapecode to set text-color (can have own background-color)
        'bg'  : ""            # ANSI-Escapecode to set background-color (for border)
    },
    'green'   : { 'bc1' : "\033[1;32m",    'bc2' : "\033[1;32m",     'fc' : "\033[0;97m",              'bg' : ""},
    'red'     : { 'bc1' : "\033[1;31m",    'bc2' : "\033[1;31m",     'fc' : "\033[0;97m",              'bg' : ""},
    'cyan256' : { 'bc1' : "\033[38;5;51m", 'bc2' : "\033[38;5;38m",  'fc' : "\033[48;5;23;38;5;220m",  'bg' : "\033[48;5;234m"},
    'oran256' : { 'bc1' : "\033[38;5;124m",'bc2' : "\033[38;5;88m",  'fc' : "\033[0;38;5;214m",        'bg' : "\033[48;5;236m"},
    'blue256' : { 'bc1' : "\033[38;5;18m", 'bc2' : "\033[38;5;27m",  'fc' : "\033[48;5;21;38;5;15m",   'bg' : ""},
    'grey256' : { 'bc1' : "\033[38;5;235m",'bc2' : "\033[38;5;237m", 'fc' : "\033[48;5;239;38;5;255m", 'bg' : ""},
    'none'    : { 'bc1' : "",              'bc2' : "",               'fc' : "",                        'bg': ""},
    # sondermodus: rgb :) wir machen das aber in code.
}


def demo():
    # demo
    d = ""
    if len(bordercolors) == len(borderstyles):
        for s,c in zip(borderstyles.keys(), bordercolors.keys()):
            d += schild("--border "+s+" --color "+c, s, c) + "\n"
    else:
        for s in borderstyles.keys(): d += schild("--border "+s, s, "none") + "\n"
        for s in bordercolors.keys(): d += schild("--color "+s, "thickin", s) + "\n"
    sys.stdout.write(d)


class objectify(object):
    def __init__(self, d):
        self.__dict__ = d

SGR = re.compile("\x1b\\[([0-9;]*?m|K)")
def wlen(s): return len(SGR.sub("", s))

def schild(txt, style, color, left=False, outer=False):
        
    frt = "".join(txt) #.strip()
    #frt = frt.decode("utf-8") # only needed for python 2
    # remove final linebreak
    if frt[-1:] == "\n": frt = frt [:-1]
    frt = frt.replace("\t", "    ").split('\n')
    frt_width = 0
    for line in frt: frt_width = max(wlen(line),frt_width)
    b = objectify(borderstyles[style])
    if color is None: 
        reset, clear = "", ""
        c = objectify(bordercolors["none"])
    else:
        reset, clear = "\033[0m", "\033[K"
        c = objectify(color)
    try:
        import curses
        curses.setupterm()
        tco = curses.tigetnum("cols")
    except:
        tco = 80 # or  $COLUMNS-env?
    
    borderwidth = 2 + len(b.lr[0]) + len(b.lr[2])
    
    if tco >= frt_width + borderwidth:
        pad = "" if left else (b.lr[1] if outer else " ") * ((tco - frt_width - borderwidth) // 2)
        if outer:
            top = c.bc1 + b.top[0] + (b.top[1]*(frt_width + 2 + 2*len(pad))) + b.top[2]
            bl =  c.bc2 + b.lr[0] + c.fc + pad + " "
            br =  " " + pad + reset + c.bg + c.bc1 + b.lr[2]
            btm = c.bc2 + b.btm[0] + (b.btm[1]*(frt_width + 2 + 2*len(pad))) + b.btm[2]
        else:
            top = pad + c.bc1 + b.top[0] + (b.top[1]*(frt_width+2)) + b.top[2] + pad
            bl =  pad + c.bc2 + b.lr[0] + c.fc + " "
            br =  " " + reset + c.bg + c.bc1 + b.lr[2] + pad
            btm = pad + c.bc2 + b.btm[0] + (b.btm[1]*(frt_width+2)) + b.btm[2] + pad
    else:
        pad, bl, br = "", c.fc, c.bc1
        top = " " * tco
        btm = " " * tco

    r = c.bg + top + clear + reset + "\n"
    for line in frt:
        line += " " * (min(tco,frt_width) - wlen(line))
        r += c.bg + bl + line + br + clear + reset + "\n"
    r += c.bg + btm + clear + reset + "\n"
    return(r)

def main():
    parser = argparse.ArgumentParser(description='Pipe some text into this program to make a fancy sign.')
    parser.add_argument('-b', '--border',  choices=borderstyles.keys(), default='single' , help='Use a different border')
    parser.add_argument('-c', '--color',   choices=bordercolors.keys(), default='cyan' , help='Use a different color preset')
    
    cc = parser.add_argument_group("custom colors", 
    "colors are gives as ANSI-colorcodes without Esc[ and m at the end."
    "\nDefault colors are: -bc1 1;36 -bc2 1;36 -fc 0;93"
    "\nYou may use a preset and override single color(s)"
    )
    cc.add_argument('-bc1','--bordercolor1', type=str, help='Custom color: Border top/right')
    cc.add_argument('-bc2','--bordercolor2', type=str, help='Custom color: Border bottom/left')
    cc.add_argument('-fc', '--forecolor',    type=str, help='Custom color: Text')
    cc.add_argument('-bg', '--background',   type=str, help='Custom color: Background')
    
    parser.add_argument('-d', '--demo',    action='store_true', help='Show all borders and colors')
    parser.add_argument('-l', '--left',    action='store_true', help='Align left (do not center)')
    parser.add_argument('-o', '--outer',   action='store_true', help='large sign: border as wide as the screen')
    args = parser.parse_args()
    if args.demo:
        demo()
        sys.exit(0)
    
    color = None
    if args.color != "none": color = bordercolors[args.color].copy()
    if args.bordercolor1 is not None: color['bc1'] = "\033["+args.bordercolor1+"m"
    if args.bordercolor2 is not None: color['bc2'] = "\033["+args.bordercolor2+"m"
    if args.forecolor    is not None: color['fc']  = "\033["+args.forecolor+"m"
    if args.background   is not None: color['bg']  = "\033["+args.background+"m"

    sys.stdout.write(schild(sys.stdin.readlines(), args.border, color, args.left, args.outer))

if __name__ == '__main__':
    main()
