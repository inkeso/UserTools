#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import io
import sys
import json
import shlex
import curses
import argparse
import subprocess
import concurrent.futures
from collections import namedtuple


def wrap(s, w):
    """a simpler but 10x faster replacement for textwrap.wrap"""
    line_len, line_buf = 0, []
    for word in s.split():
        # If appending the word would cause overflow, flush the line.
        if line_len + len(line_buf) + len(word) > w and line_buf:
            yield ' '.join(line_buf)
            line_len, line_buf = 0, []
        # If just this word alone would overflow, break it by force.
        while len(word) > w:
            yield word[:w]
            word = word[w:]
        line_buf.append(word)
        line_len += len(word)
    if line_buf:
        yield ' '.join(line_buf)


def pacman(args):
    """thin wrapper for calling pacman and returning its output"""
    procrun = subprocess.run(["pacman"] + args,
        encoding="utf-8", 
        env= dict(os.environ, LC_ALL="C"),
        capture_output=True
    )
    if procrun.stderr:
        sys.stderr.write(procrun.stderr)
        sys.exit(200)
    return procrun.stdout.splitlines()


def sudopacman(args):
    """interactive pacman with sudo"""
    os.system(shlex.join(["sudo", "pacman"] + args))


# ANSI-CSI helper:
def csi(code=""): return f"\033[{code}m"
def fg(string="", code=None): return string if code is None else f"\033[38;5;{code}m{string}\033[39m"
def bg(string="", code=None): return string if code is None else f"\033[48;5;{code}m{string}\033[49m"
def hl(string="", code=1): return f"\033[{code}m{string}\033[2{code if code != 1 else 2}m"


def alen(astr):
    """calculate length of string, ignoring ANSI-colorcodes"""
    return len(re.sub("\033\\[.*?m", "", astr))


def columnize(lst, width=80):
    """
    display a list of strings in columns
    lst may be a list of strings or a list of tuples (str, fg-color) for formatting.
    (Or a mix of both)
    """
    # Anzahl möglicher Spalten berechnen bei max. Breite pro Spalte
    
    lst = [(x, None) if type(x) is str else x for x in lst] 
    
    cwidth = max(len(x[0]) for x in lst)
    ncols = min(len(lst), width // (cwidth + 2))
    res = []
    if ncols < 1:   # wordwrap needed... 
        for l in lst: 
            res += [fg(f"{w:{width}}", l[1]) for w in wrap(l[0], width)]
    else:
        # Zeilen berechnen.
        nrows = len(lst) // ncols + (len(lst) % ncols > 0)
        cols = []   # columns
        for i in range(ncols):
            thiscol = lst[(i * nrows):((i + 1) * nrows)]
            if not thiscol: continue
            cwis = max(len(e[0]) for e in thiscol)
            ccol = [fg(f"{e[0]:{cwis}}", e[1]) for e in thiscol]
            while len(ccol) < nrows: ccol.append(" " * cwis)
            cols.append(ccol)

        # display
        for r in range(nrows):
            #res += ["  ".join(cols[c][r] for c in range(ncols))]
            res += ["  ".join(c[r] for c in cols)]

    return res



# styles used for terminal output (ascii/ansi)
class Style:
    ext_str = "Foreign"     # string to show in db-column for external packages
    min_desc = 30           # minimal width of description-column
    
    # colors/formatting. 
    header  = "40;97;4;1"   # bold white underline on black background (full CSI-Sequence)
    zebra   = 233, 234      # alternating row background (256-color background)
    db      = 5             # foreground-colors for various columns/fields
    ext     = 1             # (256-color numbers)
    grps    = 3
    pkg     = 15
    ver     = 6
    ins     = 10
    old     = 9
    desc    = 7
    
    # hightlight match. Only use one of:
    # 1=bold  2=dim  3=italic  4=underline  5=blink  7=reverse  9=crossed
    highlight = 4

    # CSI-sequences used in interactive mode (LineSelect)
    cursor = "44"
    scrollbar = "38;5;118;48;5;57"   # scrollbar-color (complete CSI)
    selected = "1;42", "1;41"        # highlight selected item


class Pkg:
    Row = namedtuple("Row", "db pkg ver grps ins old desc")
    Col = namedtuple("Col", "db pkg ver grps desc")
    

    def __init__(self):
        # convenience
        self.env = dict(os.environ, LC_ALL="C")
        
        # will be populated by search()
        self.regex = None
        self.rows = None
        
        # will be populated by getting self.cols (eg. in to_ascii())
        self._cols = None


    @property
    def cols(self):
        """
        get max column-widths for output on terminal
        """
        if self._cols is None:
            db = max(len(r.db) for r in self.rows)
            pk = max(len(r.pkg) for r in self.rows)
            gr = max(max( (len(g) for g in gp.grps.split()) if gp.grps else (0,) ) for gp in self.rows)
            vr = max(max(len(r.ver), len(r.old) if r.old else 0) for r in self.rows)
            ds = max(len(r.desc) for r in self.rows)
            self._cols = Pkg.Col(db, pk, vr, gr, ds)
        return self._cols


    def _get_foreign(self):
        """
        search foreign packages, returns results.
        Do not use. Use search() instead.
        """
        rows = []
        cur = {}
        for l in pacman(["-Qmi"]):
            if l:       # collect info
                if ":" not in l: continue
                cur.update(((x.strip() for x in l.split(":", 1)),))
            elif cur:   # new entry is about to start
                if self.regex.search(f"{cur['Groups'].replace('None', '')} {cur['Name']} {cur['Description']}"):
                    grps = cur["Groups"] != "None" and cur["Groups"] or None
                    rows.append(Pkg.Row(Style.ext_str, cur["Name"], cur["Version"],
                        grps, "installed", None, cur["Description"]))
                cur = {}
        return rows


    def _get_sync(self):
        """
        search in repos, returns results.
        Do not use. Use search() instead.
        """
        # repack 2 consecutive lines in 
        pacsync = "\n".join(pacman(["-Ss", self.regex.pattern])).replace("\n    ", " »» ").splitlines()
        pattern = r"^([^ ]+?)/([^ ]+?) ([^ ]+?)(?: \((.+?)\))?(?: \[(installed)(?:\]|: ([^ ]+?)\]))? »» (.+)$"
        return [
            Pkg.Row(*re.match(pattern, entry).groups()) 
            for entry in pacsync if self.regex.search(entry)
        ]


    def search(self, search="."):
        """
        Perform a search in local and remot databases.
        The results are stored in self.rows. Use to_*() functions to retrieve.
        """
        self.regex = re.compile(search, re.IGNORECASE)
        self._cols = None
        with concurrent.futures.ThreadPoolExecutor() as executor:
            f1 = executor.submit(self._get_foreign)
            f2 = executor.submit(self._get_sync)
            self.rows = f1.result() + f2.result()
            self.rows.sort(key=lambda x: x.pkg)


    def to_json(self):
        """
        print a JSON-String with currently fetched rows.
        """
        json.dump([r._asdict() for r in self.rows], sys.stdout, indent=2)
        print()


    def to_csv(self, sep="\t"):
        """
        print items in each row separated by tab (or other separator)
        """
        sys.stdout.write(sep.join(Pkg.Row._fields)+"\n")
        
        for r in self.rows:
            print(sep.join(s if s else "" for s in r))

    
    def _highlight(self, l):
        """
        highlight search, ignoring first word (which is always empty 
        or an ANSI-escape-sequence)
        """
        for i in range(len(l)):
            p, s = l[i].split(" ",1)
            s = self.regex.sub(hl("\\g<0>", Style.highlight), s)
            l[i] = f"{p} {s}"

    
    def _formatize(self, width=80):
        """
        reformat rowlist to fit specified width, colorize etc.
        """
        if not self.rows: return []
        descwidth = width - sum(self.cols[:4]) - 9
        rem = set()     # remove these columns
        if descwidth < Style.min_desc or self.cols.grps == 0:
            rem.add("grps")
            descwidth += self.cols.grps + 2
        if descwidth < Style.min_desc:
            rem.add("db")
            descwidth += self.cols.db + 2
        if descwidth < Style.min_desc:
            rem.add("ver")
            descwidth += self.cols.ver + 2
        if descwidth < Style.min_desc:
            raise Exception(f"Terminal too small. Need at least {self.cols.pkg + Style.min_desc + 3} columns.")
            
        
        # expand versions to single-line if there's enough space
        splitver = True
        anyold = any(r.old for r in self.rows)
        if anyold and descwidth - self.cols.desc > self.cols.ver + 3:
            descwidth -= self.cols.ver + 3
            splitver = False
            
        
        # same with groups if there is still enough space.
        splitgrps = True
        grpswidth = max(len(r.grps) if r.grps else 0 for r in self.rows)
        if descwidth - self.cols.desc > grpswidth - self.cols.grps:
            descwidth -= grpswidth - self.cols.grps
            splitgrps = False
        else: 
            grpswidth = self.cols.grps
            
        # insert header
        ret = []
        if Style.header:
            header = []
            def mkhead(w, l): return [f"{csi(Style.header)} {w[:l]:{l}} {csi()}"]
            if "db" not in rem: header.append(mkhead('Repo', self.cols.db))
            if "grps" not in rem: header.append(mkhead('Group(s)', grpswidth))
            header.append(mkhead('Name', self.cols.pkg))
            if "ver" not in rem: header.append(mkhead('Version', self.cols.ver if splitver else self.cols.ver * 2 + 3))
            header.append([mkhead('Description', descwidth-1)[0]])
            ret = [header]

        for n, r in enumerate(self.rows):
            frow = []
            
            desc = list(wrap(r.desc, descwidth))
            grps = (r.grps.split() if splitgrps else [r.grps]) if r.grps else [""]
            rol = max(
                len(grps) if "grps" not in rem else 1,
                2 if r.old and splitver and "ver" not in rem else 1,
                len(desc)
            )
            
            # add column entries with all the same length (number of columns may vary)
            if "db" not in rem:
                db = [fg(f" {r.db:{self.cols.db}} ", Style.db if r.db != Style.ext_str else Style.ext)]
                frow.append(db + [" " * (self.cols.db + 2)] * (rol - 1))
            
            if "grps" not in rem:
                grs = [fg(f" {g:{grpswidth}} ", Style.grps) for g in grps]
                self._highlight(grs)
                frow.append(grs + [" " * (grpswidth + 2)] * (rol - len(grs)))
            
            pkg = [fg(f" {r.pkg:{self.cols.pkg}} ", Style.ins if r.ins else Style.pkg)]
            self._highlight(pkg)
            
            frow.append(pkg + [" " * (self.cols.pkg + 2)] * (rol - 1))

            if "ver" not in rem:
                ver = [fg(f" {r.ver:{self.cols.ver}} ", Style.ins if r.ins else Style.ver)]
                ver += [" " * (self.cols.ver + 2)] * (rol - 1)
                if r.old: 
                    if splitver:
                        ver[1] = fg(f" {r.old:{self.cols.ver}} ", Style.old) 
                    else:
                        ver[0] += "→" + fg(f" {r.old:{self.cols.ver}} ", Style.old)
                else:
                    if not splitver:
                        ver[0] += f"  {'':{self.cols.ver}} "
                
                frow.append(ver + [" " * (self.cols.ver + 2)] * (rol - len(ver)))
                
            while len(desc) < rol: desc += [""]
            des = [fg(f" {d:{descwidth}}", Style.desc) for d in desc]
            self._highlight(des)
            frow.append(des)
            ret.append(frow)
        return ret


    def to_ansi(self, width=80):
        """
        display rows as a nice table with specified width.
        if width is too small, group, database and version will be omitted 
        (in that order, until sufficient space for description is available)
        """
        try:
            for n, r in enumerate(self._formatize(width)):
                #rowtxt = "\n".join("".join(c[i] for c in r) for i in range(len(r[0])))
                #sys.stdout.write(bg(rowtxt, Style.zebra[n % 2])+"\n")

                rowtxt = "\n".join(bg("".join(c[i] for c in r), Style.zebra[n % 2]) for i in range(len(r[0])))
                sys.stdout.write(rowtxt + "\n")
        except Exception as e:
            sys.stderr.write(fg(e, 9)+"\n")


    def to_list(self, width=80):
        """
        same as above, but without the zebra-stripes and return a list 
        instead of printing to stdout
        """
        ret = []
        try:
            for n, r in enumerate(self._formatize(width)):
                ret.append(["".join(c[i] for c in r) for i in range(len(r[0]))])
        except Exception as e:
            ret.append([f"\n\n\x1b[91m{e}\x1b[m"])
        return ret

    
    @classmethod
    def info(cls, name, width=80):
        """
        show fancy package-info.
        Highlight installed packages.
        """
        if width < 40: return ["Width too small"]

        pacinfo = pacman(["-Sii", name])
        if not pacinfo: return [f"No such package »{name}«"]

        # header aus folgendem:
        hfields = ("Repository", "Name", "Version", "Description", "Groups")
        # Dies sind Paketlisten und werden anders formatiert:
        plists = ("Depends On", "Required By", "Optional For", "Replaces", "Conflicts With")

        installed = [x.split()[0] for x in pacman(["-Q"])]
        info = {}
        last = ""
        for l in pacinfo:
            if ":" in l and l[0] != " ":
                k, v = l.split(":", 1)
                last = k.strip()
            else:
                v = l
            v = v.strip()
            if v != "None":
                if last in info: info[last] += "\n" + v
                else:            info[last] = v
        
        # precalculate width: untere Infos zuerst ohne padding rendern
        fancyinfo = []
        CW = 17  # number of chars for left column
        for k, v in info.items():
            if k in hfields: continue
            txt = []
            for r in v.split("\n"):
                lw = [x for x in wrap(r, width - CW)]
                if k == "Optional Deps":
                    odh = lw[0].split(": ", 1)
                    if len(odh) == 2:
                        lw[0] = f"{fg(odh[0], Style.pkg if odh[0] not in installed else Style.ins)}: {odh[1]}"
                elif k in plists:   # colorize package-list
                    lw = columnize([(x, Style.pkg if x not in installed else Style.ins) for x in r.split()], width - CW)
                    
                txt += lw
            if not txt: continue
            txt[0] = fg(f"{k:{CW - 2}}", 14) + ": " + txt[0]
            if len(txt) > 1:
                for i in range(1, len(txt)):
                    txt[i] = f"{'':{CW}}" + txt[i]
            fancyinfo += txt
            # insert blank row in some cases
            if k in plists + ("Licenses", "Provides", "Optional Deps"):
                fancyinfo += [""]
        
        # reduce width if possible
        width = min(width, max(alen(x) for x in fancyinfo))
        
        result = [
            fg(info['Name'], Style.pkg if info['Name'] not in installed else Style.ins) + " " +
            fg(info['Version'], Style.ver) + " " +
            " " * (width - len(info['Name'] + info['Version'] + info['Repository']) - 2) +
            fg(info['Repository'], Style.db)
        ]
        if "Groups" in info:
            result += [" "*width]
            result += [fg(f"{info['Groups']:{width}}", Style.grps)]
    
        result += [" "*width]
        result += [f"{v:{width}}" for v in wrap(info['Description'], width)]
        result += [" "*width]
        
        # add fancyinfo with right padding
        result += [x + " " * (width - alen(x)) for x in fancyinfo]
        
        return result


class LineSelect():
    """
    Select a line interactively. We only use curses to some extend, since
    input is already ANSI-formated.
    """
    scroll_padding = 5      # number of lines kept visible below/above cursor

    def __init__(self, pkg):
        self.pkg = pkg
        keys = [
            ["F1", "Pkg-Info"],
            ["Enter", "Accept"],
            ["Space", "Select"],
            ["Escape", "Abort"],
        ]
        #self.footer = " | ".join(f"\033[38;5;123m{x[0]}\033[38;5;45m: {x[1]}\033[38;5;27m" for x in keys)
        self.footer = fg(" | ", 27).join(fg(x[0], 123) + fg(f": {x[1]}", 45) for x in keys)
        
        try:
            self.cols, self.rows = os.get_terminal_size()
        except OSError:
            self.cols, self.rows = 80, 25

        lines = self.pkg.to_list(self.cols-1) # bei langen listen dauert das!
        self.header = lines[0][0]
        self.items = lines[1:]
        self.doscrollbar = False

        self._cursor = 0        # current cursor position
        self._offset = 0        # skip first n items in list (scrolled down)
        self.selected = set()   # keep track of selected row indices
        self.installed = set(i for i, r in enumerate(self.pkg.rows) if r.ins)


    @property
    def items(self): return self._items

    @items.setter
    def items(self, val):
        self._items = val
        # calculate number of displayed lines
        self.height = sum(len(x) for x in val or [[]])


    @property
    def cursor(self): return self._cursor

    @cursor.setter
    def cursor(self, val):
        if val < 0: val = 0
        if val >= len(self.items): val = len(self.items)-1
        self._cursor = val

        # check if cursor is in view. scroll if neccessary
        maxh = self.rows - 2  # (header & footer)
        crow = sum(len(x) for x in self.items[:self.cursor] or [[]])
        if crow < self.offset + 5: self.offset = crow - 5
        if crow > self.offset + maxh - 5: self.offset = crow - maxh + 5


    @property
    def offset(self): return self._offset

    @offset.setter
    def offset(self, val):
        if val < 0: val = 0
        maxo = self.height - (self.rows - 2)
        if maxo < 0: maxo = 0
        if val > maxo: val = maxo
        self._offset = val


    def display(self):
        """
        draw header, list, progressbar and footer
        return first and last displayed item index
        """
        # TODO: measure time: if terminal is slow, use jump-scroll.
        # otherwise scroll row by row

        out = sys.stdout.write
        out(f"\033[H{self.header}\033[K\r\n")

        maxh = self.rows - 2

        # render only what is visible... keep track of what is where
        self.ymap = []
        output = []
        i = 0   # item index
        r = 0   # rendered rows
        f = -1  # first displayed item index
        self.doscrollbar = False
        while i < len(self.items):
            fitm = self.items[i]
            r += len(fitm)
            if r > self.offset:
                if f < 0: f = i
                if r - self.offset < len(fitm): fitm = fitm[r - self.offset:]
                color = csi(f"48;5;{Style.zebra[i % len(Style.zebra)]}")
                if i in self.selected:
                    color += csi(Style.selected[i in self.installed])
                if i == self.cursor:
                    color += csi(Style.cursor)
                output += [f"{color}{ir}{csi()}\r\n" for ir in fitm]
                self.ymap += [i for _ in fitm]
                if len(output) >= maxh:
                    output = output[:maxh]
                    self.doscrollbar = True
                    break
            i += 1
        out("".join(output))
        out(f"\033[J")

        # plot a scrollbar if needed
        if self.doscrollbar:
            top = int(f / len(self.items) * maxh) + 2
            low = int(i / len(self.items) * maxh) + 2
            sh = "".join(f"\033[{x};{self.cols}H" + (" " if x < top or x > low else "█") for x in range(2, self.rows))
            out(f"\033[44;36m{sh}\033[m");

        # Footer
        a = len(str(len(self.items)))
        info = f"\033[48;5;18m [{self.cursor+1:{a}} / {len(self.items)}] "
        if len(self.selected) > 0:
            rem = len(self.selected.intersection(self.installed))
            ins = len(self.selected.difference(self.installed))
            if rem > 0: info += f"\033[38;5;196m [- {rem}] "
            if ins > 0: info += f"\033[38;5;118m [+ {ins}] "

        out(f"\033[{self.rows}H{info}\033[K")
        out(f"\033[{self.rows};{self.cols - alen(self.footer)}H{self.footer}")

        sys.stdout.flush()
        return f, i


    def findfirst(self, char):
        for i, r in enumerate(self.pkg.rows):
            if r.pkg.lower().startswith(char.lower()): return i
        return None


    def mainloop(self, scr):
        """Mainloop must be called in curses.wrapper"""
        loop = True
        result = None
        doresize = False

        curses.curs_set(0)
        curses.mousemask(-1)

        # better selection-colors, when available:
        if curses.tigetnum("colors") > 16:
            Style.selected = "1;48;5;22", "1;48;5;52"

        def toggle(x):
            if x in self.selected:  self.selected.remove(x)
            else:                   self.selected.add(x)

        def showpkginfo():
            pkgname = self.pkg.rows[self.cursor].pkg
            nfo = Pkg.info(pkgname, self.cols - 4)
            nr = min(len(nfo), self.rows - 2)
            nw = min(max(alen(x) for x in nfo), self.cols - 4)
            left = (self.cols - 4 - nw) // 2
            top = (self.rows - nr) // 2

            def output(offset=0):
                sys.stdout.write(f"\033[{top};{left}H" + bg(fg(f"█▀{'▀' * nw}▀█", 33), 18))
                for i, r in enumerate(nfo[offset:(offset + nr)]):
                    sys.stdout.write(f"\033[{top+i+1};{left}H" + bg(f"{fg('█', 33)} {r} {fg('█', 33)}", 18))
                sys.stdout.write(f"\033[{top+i+2};{left}H" + bg(fg(f"█▄{'▄' * nw}▄█", 33), 18))
                sys.stdout.flush()

            keh = None
            infotafel = True
            offset = 0
            scr.timeout(-1) # no resize-support, so getch may block (this allows for mouse selection)
            while infotafel:
                output(offset)
                keh = scr.getch()
                match keh:
                    case curses.KEY_UP:    offset -= 1
                    case curses.KEY_DOWN:  offset += 1
                    case curses.KEY_PPAGE: offset -= nr
                    case curses.KEY_NPAGE: offset += nr
                    case curses.KEY_HOME:  offset = 0
                    case curses.KEY_END:   offset = 2**63
                    case curses.KEY_MOUSE:
                        match curses.getmouse()[4]:
                            case curses.BUTTON5_PRESSED: offset += 3
                            case curses.BUTTON4_PRESSED: offset -= 3
                    case _: infotafel = False

                offset = max(0, offset)
                offset = min(offset, len(nfo) - nr)
            scr.timeout(100)    # reset getch-timeout to 100

        scr.timeout(100)        # getch-timeout is used for delayed resize
        while loop:
            fr, tr = self.display()
            keh = scr.getch()

            match keh:
                case -1:
                    if doresize:
                        self.rows, self.cols = scr.getmaxyx()
                        lines = self.pkg.to_list(self.cols-1) # bei langen listen dauert das!
                        self.header = lines[0][0]
                        self.items = lines[1:]
                        doresize = False
                case 27 | curses.KEY_F10:  # escape
                    result = None
                    loop = False

                case 10:  # return
                    result = self.cursor
                    loop = False

                case 32:  # space
                    toggle(self.cursor)
                    self.cursor += 1

                # NAvigation
                case curses.KEY_UP:     self.cursor -= 1                        # 259
                case curses.KEY_DOWN:   self.cursor += 1                        # 258
                case curses.KEY_HOME:   self.cursor = 0                         # 262
                case curses.KEY_END:    self.cursor = len(self.items) - 1       # 360
                case curses.KEY_PPAGE:  self.offset, self.cursor = 0, fr        # 339
                case curses.KEY_NPAGE:  self.offset, self.cursor = 2**63, tr    # 338

                # jump to char
                case x if 'a' <= chr(x).lower() <= 'z': # 97-122
                    new = self.findfirst(chr(x))
                    if new is not None: self.cursor = new

                case curses.KEY_F1: # 265
                    showpkginfo()

                case curses.KEY_RESIZE: # 410
                    doresize = True

                # MOUSE! scrollwheel scrolls. leftclick sets cursor. rightclick (de)selects
                case curses.KEY_MOUSE:
                    mous = curses.getmouse()    # (id, x, y, z, bstate)
                    if mous[2] < 1 or mous[2] >= self.rows-1 or mous[2]-1 >= len(self.ymap) : continue
                    if mous[4] == curses.BUTTON5_PRESSED: self.offset += 3
                    if mous[4] == curses.BUTTON4_PRESSED: self.offset -= 3
                    if mous[4] == curses.BUTTON3_CLICKED: toggle(self.ymap[mous[2]-1])
                    if mous[4] == curses.BUTTON1_CLICKED: self.cursor = self.ymap[mous[2]-1]
        curses.curs_set(1)
        return result

    def main(self):
        curses.set_escdelay(50)
        res = curses.wrapper(self.mainloop)

        if res is not None:
            if len(self.selected) == 0: self.selected = set([res])
            
            def header(s, c):
                s = f"──══▶ {s} ◀══──"
                print(bg(hl(fg(f"{s:^{self.cols}}", 15), 1), Style.selected[c]))
                
            pkgwech = self.selected.intersection(self.installed)
            if pkgwech:
                header("REMOVE", 1)
                print("\n".join("\n".join(self.items[s]) for s in pkgwech))
                print()

            pkghin = self.selected.difference(self.installed)
            if pkghin:
                header("INSTALL", 0)
                print("\n".join("\n".join(self.items[s]) for s in pkghin))
                print()

            if pkgwech: sudopacman(["-Rsc"] + [self.pkg.rows[s].pkg for s in pkgwech])
            if pkghin: sudopacman(["-S"] + [self.pkg.rows[s].pkg for s in pkghin])

        else:
            if not self.doscrollbar:
                self.pkg.to_ansi(self.cols)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="""
        Search for packages with pacman.
        Show results in an interactive list, allowing for installation.
        
        If no option is given and stdout is a TTY, interactive mode will be started.
        If stdout is not a TTY, a tab-separated table will be written. (like with -c)
        
        Other output options are available and mutually exclusive.
    """)
    
    parser.add_argument("searchterm", type=str, nargs=1, help="regex to search for")
    group = parser.add_mutually_exclusive_group()
    
    group.add_argument("-j", "--json", action="store_true", help="""
        output result as JSON
    """)
    group.add_argument("-c", "--csv", action="store_true", help="""
        output result as tab-separated table
    """)
    group.add_argument("-a", "--ansi", nargs="?", metavar="width", type=int, default=None, const=0, help="""
        output result pretty formated and colored. 
        if width is not specified or 0, autodetection will be tried.
        If stdout is not a terminal, width will default to 80.
    """)
    
    args = parser.parse_args()
    pkg = Pkg()
    pkg.search(args.searchterm[0])
    
    if args.json: pkg.to_json()
    elif args.csv: pkg.to_csv()
    elif args.ansi is not None:
        if args.ansi == 0: 
            try:
                args.ansi = os.get_terminal_size().columns
            except OSError:
                args.ansi = 80
        pkg.to_ansi(args.ansi)
        # same but without zebra-background:
        #for l in pkg.to_list(args.ansi): print("\n".join(l))
    elif pkg.rows:
        if sys.stdout.isatty() and sys.stdin.isatty():
            ls = LineSelect(pkg)
            ls.main()
        else:
            pkg.to_csv()
