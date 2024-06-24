#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, tty, termios, argparse

def getch(): # get single keypress
    """wait single keypress"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    def rdch(n=1): return sys.stdin.read(n)
    try:
        tty.setraw(fd)
        ch = rdch()
        if ch == '\x1b':
            nby = rdch()
            if nby == '[':
                nby = rdch()
                if nby in 'ABCD': ch = {'A': "Up", 'B': "Down", 'C': "Right", 'D': "Left"}[nby]
            else:
                ch = ch+nby
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

O = sys.stderr

def _render1(options, prefix, active):
    # render buttons
    bwidth = max(len(x[0]) for x in options)
    displ = prefix
    for i, (ostr, ocol) in enumerate(options):
        face = f"\x1b[4{ocol};97;1m" if i == active else f"\x1b[0;3{ocol}m"
        displ += f"{face} {ostr:^{bwidth}} \x1b[m "
    O.write(displ)
    O.flush()


def _render3(options, prefix, active):
    # render buttons
    bwidth = max(len(x[0]) for x in options)
    displ = [" "*len(prefix), prefix, " "*len(prefix)]
    for i, (ostr, ocol) in enumerate(options):
        face = f"\x1b[4{ocol};97;1m" if i == active else "\x1b[m"
        displ[0] += f"\x1b[0;9{ocol}m ▁{'▁'*bwidth}▁ \x1b[m "
        displ[1] += f"\x1b[0;9{ocol}m▕{face} {ostr:^{bwidth}} \x1b[0;3{ocol}m▏\x1b[m "
        displ[2] += f"\x1b[0;3{ocol}m ▔{'▔'*bwidth}▔ \x1b[m "
    O.write("\n".join(displ)+"\x1b[A")
    O.flush()


def getanswer(options=(("Yes", 2), ("No", 1)), prefix="", default=0, border=True):
    active = default
    result = None
    while result is None:
        (_render3 if border else _render1)(options, prefix, active)
        match k := getch():
            case '\x03' | '\x1b\x1b': 
                result = -1, ""
            case 'Up' | 'Left':
                active = (active - 1) % len(options)
            case 'Dn' | 'Right' | '\t':
                active = (active + 1) % len(options)
            case '\r' | '\n' | ' ':
                result = active, options[active][0]
            #case _: O.write(" unkown key: "+repr(k))
        if border: O.write("\x1b[A")
        O.write("\r")
        O.flush()
    O.write("\n")
    if border: O.write("\n\n")
    O.flush()
    return result
    


if __name__ == '__main__':
    class RawDefFormatter(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter): pass
    parser = argparse.ArgumentParser(
        prog='YesNo', 

        description='''\
Show a selection (output to stderr), set exitcode to selected item index
or 255 in case of Ctrl-C or EscEsc. Optionally output selection to stdout.

Use Arrowkeys or Tab to change selection.
Space or Return to confirm.
Esc-Esc or Ctrl+C to abort.

Options are displayed as buttons next to each other. buttons will be all the 
same size, depending on the longest one. If there are more buttons than 
horizontal space available in the terminal, output will be garbled.
For larger lists, consider using something like fzf, smenu or dialog instead.
''',

        epilog='''
examples:
  yesno "Clear Screen?" && clear
 
  RES=$(yesno "Was darf's sein?" -o "Tor 1" "Tor 2" "Tor 3" -c 0 0 0 -s)
  echo "Selection: $? »$RES«"
        ''',

        formatter_class=RawDefFormatter
    )
    parser.add_argument("prefix",          type=str, nargs="?",  default="",            help="Print question bevor choice")
    parser.add_argument("-n", "--noborder", action="store_true", default=False,         help="No border around buttons, (1 line instead of 3)")
    parser.add_argument("-o", "--options", type=str, nargs="*",  default=("Yes", "No"), help="Options to choose from")
    parser.add_argument("-c", "--colors",  type=str, nargs="*",  default=(2,1),         help="Colors for each option (0-7)")
    parser.add_argument("-d", "--default", type=int,             default=0,             help="Index of preselected item")
    parser.add_argument("-i", "--index",   action="store_true",  default=False,         help="print selected item index to stdout")
    parser.add_argument("-s", "--string",  action="store_true",  default=False,         help="print selected item string to stdout")
    args = parser.parse_args()
    
    sys.tracebacklimit = 0
    for i, c in enumerate(args.colors): assert 0 <= int(c) < 8, f"Color #{i} out of range: {c}"
    del sys.tracebacklimit

    while len(args.colors) < len(args.options): # recycle last color
        args.colors += args.colors[-1],

        
    a_idx, a_str = getanswer(
        tuple(zip(args.options, args.colors)),
        args.prefix,
        args.default,
        not args.noborder
    )

    outstr = []
    if args.index: oustr.append(str(a_idx))
    if args.string: oustr.append(str(a_str))
    if outstr: sys.stdout(" ".join(outstr))

    sys.exit(255 if a_idx < 0 else a_idx)
