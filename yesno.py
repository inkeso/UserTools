#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, sys, tty, termios, argparse

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


def getcursorposition():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    settings = termios.tcgetattr(fd)
    settings[3] = settings[3] & ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(fd, termios.TCSAFLUSH, settings)
    res = None
    try:
        rd = ""
        sys.stderr.write("\x1b[6n")
        sys.stderr.flush()
        while not (rd := rd + sys.stdin.read(1)).endswith('R'): True
        res = re.match(r".*\[(?P<y>\d*);(?P<x>\d*)R", rd)
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)
    if res: return int(res.group("x")), int(res.group("y"))
    return -1, -1


O = sys.stderr
class Confirm:
    BorderChars = [ " ▁ " ,
                    "▕ ▏" ,
                    " ▔ " ]

    def __init__(self, options=(("Yes", 2), ("No", 1)), prefix="", default=0, border=True):
        self.__active = None
        self.options = options
        self.bwidth = max(len(x[0]) for x in self.options)
        self.prefix = prefix + " "
        self.active = default
        self.highlight = "93;1"
        self.border = border

        # cursor positioning incl. fallback
        lines = 1 + 2*border
        cr = getcursorposition()[1]
        if cr > 0:  # absolute positioning needs "prescrolling"
            O.write("\n"*lines)
            ce = getcursorposition()[1]
            if cr > ce-lines: cr = ce-lines
            self.startrow = f"\x1b[{cr}H"
            self.endrow = f"\x1b[{ce}H"
        else:       # cursor position could not be determined: use relative positioning
            self.startrow = "\r" if not border else f"\x1b[A\r"
            self.endrow = "\n"*(1 + border)
            if border: O.write("\n")

        # try to auto-assign hotkeys
        self.hotkeys = {}
        for i, (o, _) in enumerate(self.options):
            for c in re.sub("[^a-z0-9]", "", o.lower()):
                if c not in self.hotkeys:
                    self.hotkeys[c] = i
                    break
        self.syektoh = dict(reversed(j) for j in self.hotkeys.items())
        self.result = None


    @property
    def active(self): return self.__active

    @active.setter
    def active(self, v):
        self.__active = v % len(self.options)


    def render(self, final=False):
        B = Confirm.BorderChars if self.border else [""]*3
        displ = [" "*len(self.prefix), self.prefix, " "*len(self.prefix)]
        for i, (ostr, ocol) in enumerate(self.options):
            drk = f"\x1b[0;3{ocol}m"
            brg = f"\x1b[0;9{ocol}m"
            face = "\x1b[m" if self.border else f"\x1b[0;3{ocol}m"
            if i == self.active:
                face = f"\x1b[4{ocol};{self.highlight}m"
                if final: drk, brg = brg, drk
            buttonlabl = f" {ostr:^{self.bwidth}} "
            if i in self.syektoh:
                c = self.syektoh[i]
                buttonlabl = re.sub(c, "\x1b[4m\\g<0>\x1b[24m", buttonlabl, 1, re.I)
            displ[0] += f"{brg}{B[0][0:2]}{B[0][1:2]*self.bwidth}{B[0][1:3]}\x1b[m "
            displ[1] += f"{brg}{B[1][0:1]}{face}{buttonlabl}{drk}{B[1][2:3]}\x1b[m "
            displ[2] += f"{drk}{B[2][0:2]}{B[2][1:2]*self.bwidth}{B[2][1:3]}\x1b[m "
        O.write(self.startrow)
        O.write("\n".join(displ)+"\x1b[A" if self.border else displ[1])
        if final: O.write(self.endrow)
        O.flush()


    def getanswer(self):
        while self.result is None:
            self.render()
            match k := getch():
                case '\x03' | '\x1b\x1b':
                    O.write("Cancelled")
                    self.result = -1, ""
                case 'Up' | 'Left':
                    self.active -= 1
                case 'Dn' | 'Right' | '\t':
                    self.active += 1
                case '\r' | '\n' | ' ':
                    self.result = self.active, self.options[self.active][0]
                case _:
                    if k in self.hotkeys:
                        i = self.hotkeys[k]
                        self.result = i, self.options[i][0]
                        self.active = i
                    else:
                        O.write("  unkown key "+repr(k))
            O.write("\x1b[K")
        self.render(True)
        return self.result


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
Other hotkeys will be assigned automatically.

Options are displayed as buttons next to each other. buttons will be all the
same size, depending on the longest one. If there are more buttons than
horizontal space available in the terminal, output will be garbled.
For larger lists, consider using something like fzf, smenu or dialog instead.
''',

        epilog='''
examples:
  # Simple confirmation:
  yesno "Clear Screen?" && clear

  # Multiple selection:
  RES=$(yesno "Was darf's sein?" -o "Tor 1" "Tor 2" "Tor 3" -c 0 0 0 -s)
  echo "Selection: $? »$RES«"

  # Center selection by using spaces as prefix:
  ./yesno.py "$(printf "%$((($(tput cols) - 15) / 2))s")"
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

    yesno = Confirm(
        tuple(zip(args.options, args.colors)),
        args.prefix,
        args.default,
        not args.noborder
    )
    a_idx, a_str = yesno.getanswer()

    outstr = []
    if args.index: outstr.append(str(a_idx))
    if args.string: outstr.append(str(a_str))
    if outstr: sys.stdout.write(" ".join(outstr))

    sys.exit(255 if a_idx < 0 else a_idx)
