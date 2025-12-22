#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: pms [-h] [-j | -c | -a [width]] searchterm

Search for packages with pacman or apt and show results in an interactive list.
Installed packages are highlighted/marked and available updates are shown as
well.

- scroll through the results using arrow keys, PageUp/PageDown, Home/End
- show package info (F1)
- show package file list (F2)
- hit Return to install an uninstalled package or uninstall an installed one
- use Spacebar to de/select several packages to (de)install, Return to do it.
- update all needed package-databases (F5)
- quit (F10 or Esc)

If no option is given and stdout is a TTY, interactive mode will be started.
If no option is given and stdout is NOT a TTY, a tab-separated table will be
written. (like with -c)

Other output options are available and mutually exclusive.

positional arguments:
  searchterm            regex to search for

options:
  -h, --help            show this help message and exit
  -j, --json            output result as JSON
  -c, --csv             output result as tab-separated table
  -a [width], --ansi [width]
                        output result pretty formated and colored. if width is
                        not specified or 0, autodetection will be tried. If
                        stdout is not a terminal, width will default to 80.

"""
import os
import re
import io
import sys
import json
import shlex
import curses
import argparse
import threading
import subprocess
import concurrent.futures
from collections import namedtuple


#┌─────────────────────────────────────────────────────────────────────────────┐
#│                       STYLES USED FOR TERMINAL OUTPUT                       │
#└─────────────────────────────────────────────────────────────────────────────┘
class Style:
    ext_str = "Foreign"     # string to show in db-column for external packages
    min_desc = 30           # minimal width of description-column
    scroll_padding = 5      # number of lines kept visible below/above cursor

    # colors/formatting.
    header  = "40;97;4;1"   # bold white underline on black background (full CSI-Sequence)
    zebra   = "", ""        # alternating row background disabled on 16 color

    # foreground-colors for various columns/fields:
    # don't use bright colors in 8-color mode as they also (inadvertently) set bold
    db      = 5             # repo
    ext     = 1             # external
    grps    = 3             # groups
    pkg     = 7 #15         # package
    ver     = 6             # version
    ins     = 2 #10         # installed package
    old     = 9             # old version
    desc    = 7             # description

    # hightlight match. Only use one of:
    # 1=bold  2=dim  3=italic  4=underline  5=blink  7=reverse  9=crossed
    highlight = 4

    # CSI-sequences used in interactive mode (LineSelect)
    cursor = "44"
    scrollbar = "36;44"         # scrollbar-color (complete CSI)
    selected = "1;42", "1;41"   # highlight selected item (16 color)

    # Colors for info-windows
    infobg = 4
    infoborder = 6

    # Colors for the footer and hotkeys
    footerbg  = 4
    footersel = 10, 9
    footersep = " ║ ", 12
    footerkey = 14
    footertxt = 6



# Better colors, if terminal is capable
class Style256(Style):
    zebra      = "48;5;233", "48;5;234"
    scrollbar  = "38;5;118;48;5;57"
    selected   = "1;48;5;22", "1;48;5;52"
    pkg        = 15
    ins        = 10
    infobg     = 18
    infoborder = 30
    footerbg   = 18
    footersel  = 118, 196
    footertxt  = 37



#┌─────────────────────────────────────────────────────────────────────────────┐
#│                              HELPER FUNCTIONS                               │
#└─────────────────────────────────────────────────────────────────────────────┘
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


def wrapml(s, w):
    """Same, but keep linebreaks"""
    result = []
    for l in s.split("\n"): result += wrap(l, w)
    return result


def byte2hr(size):  # binary prefixes
    if size < 1024: return f'{size} B'
    f = (len(bin(size))-3) // 10
    return f'{size/(1<<10*f):.2f} {" KMGTPEZY"[f]}iB'


def cmd(binary, args):
    """thin wrapper for calling a program and returning its output"""
    procrun = subprocess.run([binary] + args,
        encoding="utf-8",
        env= dict(os.environ, LC_ALL="C"),
        capture_output=True
    )
    if procrun.stderr or procrun.returncode > 0:
        raise subprocess.CalledProcessError(
            procrun.returncode,
            " ".join([binary] + args),
            procrun.stdout,
            procrun.stderr
        )
    return procrun.stdout.splitlines()


def sudocmd(binary, args):
    """interactive command with sudo"""
    os.system(shlex.join(["sudo", binary] + args))


def checkcmd(binary):
    """
    Simple & stupid way to check if a binary is available:
    assume each command contains it's own name in the first few lines of its
    own usage info. This is a bit slow, because the binary is actually spawned.
    But this way we make sure it's not only present but also is working.
    """
    try:    return binary in "\n".join(cmd(binary, ["-h"])[:3])
    except: return False


def csi(code=""): return f"\033[{code}m"


def fg(string="", code=None):
    if code is None: return string
    if code < 8: return f"\033[3{code}m{string}\033[39m"
    # in linux-terminal, setting a bright color also sets bold,
    # which will not be reverted here.
    if code < 16: return f"\033[9{code-8}m{string}\033[39m"
    return f"\033[38;5;{code}m{string}\033[39m"


def bg(string="", code=None):
    if code is None: return string
    if code < 8: return f"\033[4{code}m{string}\033[49m"
    return f"\033[48;5;{code}m{string}\033[49m"


def hl(string="", code=1):
    return csi(code) + string + csi(f"2{code if code != 1 else 2}")


def alen(astr):
    """calculate length of string, ignoring ANSI-colorcodes"""
    return len(re.sub("\033\\[.*?m", "", astr))


def columnize(lst, width=80, height=None):
    """
    display a list of strings in columns
    lst may be a list of strings or a list of tuples (str, fg-color) for formatting.
    (Or a mix of both)
    if height is set, columns will be longer and probaböy fewer
    """
    # Calculate number of columns with max. width per column
    lst = [(x, None) if type(x) is str else x for x in lst]
    if len(lst) < 1: return []
    cwidth = max(len(x[0]) for x in lst)
    ncols = min(len(lst), width // (cwidth + 2))
    res = []
    if ncols < 1:   # wordwrap needed...
        for l in lst:
            res += [fg(f"{w:{width}}", l[1]) for w in wrap(l[0], width)]
    else:
        # calculate rows
        nrows = len(lst) // ncols + (len(lst) % ncols > 0)
        if height and nrows < height: nrows = min(height, len(lst))
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



#┌─────────────────────────────────────────────────────────────────────────────┐
#│                       PACKAGE LIST AND INFO, Generic                        │
#└─────────────────────────────────────────────────────────────────────────────┘
class Pkg:
    Row = namedtuple("Row", "db pkg ver grps ins old desc")
    Col = namedtuple("Col", "db pkg ver grps desc")
    Installed = {}  # cache dict of `pkgname` => "version" (see info())

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
            self._cols = Pkg.Col(
                max(len(r.db) for r in self.rows),
                max(len(r.pkg) for r in self.rows),
                max(max(len(r.ver), len(r.old) if r.old else 0) for r in self.rows),
                max(max((len(g) for g in gp.grps.split()) if gp.grps else (0,)) for gp in self.rows),
                max(len(r.desc) for r in self.rows)
            )
        return self._cols


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
        print(sep.join(Pkg.Row._fields)+"\n")
        for r in self.rows:
            print(sep.join(s if s else "" for s in r))


    def _highlight(self, s):
        """
        highlight search
        """
        return self.regex.sub(hl("\\g<0>", Style.highlight), s)


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
                grs = [fg(self._highlight(f" {g:{grpswidth}} "), Style.grps) for g in grps]
                frow.append(grs + [" " * (grpswidth + 2)] * (rol - len(grs)))

            pkg = [fg(self._highlight(f" {r.pkg:{self.cols.pkg}} "), Style.ins if r.ins else Style.pkg)]
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
            des = [fg(self._highlight(f" {d:{descwidth}}"), Style.desc) for d in desc]

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
                rowtxt = "\n".join(csi(Style.zebra[n % 2])+"".join(c[i] for c in r)+csi() for i in range(len(r[0])))
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
            ret.append(["",fg(e, 9)])
        return ret


    def filelist(self, name, width=80, height=25):
        """
        Show filelist for package.
        pkgfile is faster but may be not installed.
        pacman -Fl is quite slow.
        """
        last = ""
        res = []
        packagefiles = self._get_packagefiles(name, width, height)
        if len(packagefiles) < 1: return ["Package contains no files"]
        for s in packagefiles:
            if s.endswith("/"): continue    # do not list plain directories
            p, f = s.rsplit("/", maxsplit=1)
            if p != last:
                if last: res += [""]
                last = p
                res += [(p, Style.pkg)]
            res += ["  " + f]
        return columnize(res, width, height)

    
    # Implement these:
    def _get_installed(self): pass
    def search(self, search="."): pass
    def _get_packagefiles(self, name, width=80, height=25): pass
    def info(self, name, width=80, height=25): pass
    def updateDB(self): pass


#┌─────────────────────────────────────────────────────────────────────────────┐
#│                      Custom Formats for Apt and Pacman                      │
#└─────────────────────────────────────────────────────────────────────────────┘
class AptPkg(Pkg):
    def __init__(self):
        super().__init__()
        import apt
        apt.apt_pkg.init()

        #AptPkg.Cache = apt.Cache()
        class NotI386Filter(apt.cache.Filter):
            def apply(self, pkg):
                return not pkg.name.endswith(":i386")
        AptPkg.Cache = apt.cache.FilteredCache(apt.Cache())
        AptPkg.Cache.set_filter(NotI386Filter())


    def _get_installed(self):
        # Cache This!
        if self.Installed: return
        self.Installed = {}
        for pkg in self.Cache:
            if not pkg.installed: continue
            self.Installed[pkg.name] = pkg.installed.version
            # TODO: also add "provides" to this
            for prov in pkg.installed.provides:
                self.Installed[prov] = pkg.installed.version


    def search(self, search="."):
        """
        Perform a search in local and remot databases.
        The results are stored in self.rows. Use to_*() functions to retrieve.
        """
        self.regex = re.compile(search, re.IGNORECASE)
        self._cols = None


        self.rows = [Pkg.Row(
            pkg.candidate.origins[0].component,
            pkg.name,
            pkg.installed.version if pkg.installed else pkg.candidate.version,
            pkg.candidate.section,
            "installed" if pkg.installed else None,
            pkg.candidate.version if pkg.installed and pkg.candidate.version != pkg.installed.version else None,
            pkg.candidate.summary
        ) for pkg in self.Cache if pkg.candidate is not None and self.regex.search(pkg.name + "\t" + pkg.candidate.summary)]
        self.rows.sort(key=lambda x: x.pkg)


    def _get_packagefiles(self, name, width=80, height=25):
        try:
            return [s.split(": ", maxsplit=2)[1] for s in cmd("apt-file", ["list", name])]
        except Exception as e:
            return str(e).splitlines()


    def info(self, name, width=80, height=25):
        """
        show fancy package-info.
        Highlight installed packages.
        """
        if width < 40: return ["Width too small"]
        if name not in self.Cache: return [f"No such package »{name}«"]

        # ignore this (partly used in header):
        #hfields = ("Repository", "Name", "Version", "Description", "Groups", "Licenses")
        # Dies sind Paketlisten und werden anders formatiert:
        plists = ("Depends On", "Required By", "Optional For", "Replaces", "Conflicts With")

        if not self.Installed: self._get_installed()
        p = self.Cache[name].candidate

        CW = 17  # number of chars for left column

        origin = fg(p.origins[0].archive, Style.grps) + "  /  " +\
                 fg(p.origins[0].component, Style.grps) + "  /  " +\
                 fg(p.section, Style.grps)

        def pkgcol(what):
            if type(what) is str:    # for provides
                nom = what
            else:
                nom = what[0].name  # for dependency & recommends.
            return fg(nom, Style.ins if nom in self.Installed else Style.pkg)

        required = set() # reverse deps are a bit costly: we have to iterate!
        for othr in self.Cache:
            if not othr.installed: continue
            if name in (d[0].name for d in othr.installed.dependencies):
                required.add(othr.name)

        provides    = columnize([pkgcol(dep) for dep in p.provides], width - CW)
        depends     = columnize([pkgcol(dep) for dep in p.dependencies], width - CW)
        recommends  = columnize([pkgcol(dep) for dep in p.recommends], width - CW)
        required    = columnize([pkgcol(dep) for dep in required], width - CW)

        def addif(title, stuff):
            if len(stuff) == 0: return []
            return [""] + [fg(title.ljust(CW-2), 14) + ": " + stuff[0]] +\
                   [" "*CW + x for x in stuff[1:]]

        depblocks = [
            ] + addif("Provides    ", provides) + [
            ] + addif("Depends On  ", depends) + [
            ] + addif("Recommends  ", recommends) + [
            ] + addif("Required By ", required) + [
        ]

        # reduce width if possible
        width = min(
            width,
            max(
                width//2,
                len(name + p.version) - 1,
                alen(origin),
                max(alen(x) for x in depblocks) if len(depblocks) > 0 else 0
            )
        )
        BR = " "*width

        result = [
            fg(name, Style.ins if self.Cache[name].installed else Style.pkg) + " " +
            fg(p.version, Style.ver) + " " * (width - len(name + p.version) - 1),
            BR,
            origin + " " * (width - alen(origin)),
            BR,
            ] + [fg(f"{v:{width}}", 154) for v in wrap(p.summary, width)] + [
            ] + [f"{v:{width}}" for v in wrapml(p.description, width)] + [
            BR,
            fg("Architecture".ljust(CW-2), 14) + ": " + p.architecture.ljust(width - CW),
            fg("URL         ".ljust(CW-2), 14) + ": " + p.homepage.ljust(width - CW),
            fg("Size        ".ljust(CW-2), 14) + ": " + byte2hr(p.size).ljust(width - CW),
        ] + [x + " " * (width - alen(x)) for x in depblocks]
        return result


    def updateDB(self):
        sudocmd("apt", ["update"])


    def install(self, pkglist): sudocmd("apt", ["install"] + pkglist)


    def uninstall(self, pkglist): sudocmd("apt", ["autopurge"] + pkglist)


class PacPkg(Pkg):
    def _get_installed(self):
        if self.Installed: return
        self.Installed = dict(x.split() for x in cmd("pacman", ["-Q"]))
        # "Provided" packagenames/version. Etwas langsamer.
        for x in cmd("pacman", ["-Qi"]):
            if not x.startswith("Provides") or x.endswith("None"): continue
            for y in x.split(" : ")[1].split():
                pv = y.split("=")
                if pv[0] not in self.Installed:
                    self.Installed[pv[0]] = pv[1] if len(pv) > 1 else None


    def search(self, search="."):
        """
        Perform a search in local and remot databases.
        The results are stored in self.rows. Use to_*() functions to retrieve.
        """
        def get_foreign():
            rows = []
            cur = {}
            for l in cmd("pacman", ["-Qmi"]):
                if l:       # collect info
                    if ":" not in l: continue
                    cur.update(((x.strip() for x in l.split(":", maxsplit=1)),))
                elif cur:   # new entry is about to start
                    cur['Groups'] = cur['Groups'].replace('None', '')
                    gr_ds = f"{cur['Groups']} {cur['Name']} {cur['Description']}"
                    if self.regex.search(gr_ds):
                        rows += [Pkg.Row(Style.ext_str, cur["Name"], cur["Version"],
                            cur["Groups"] or None, "installed", None, cur["Description"]
                        )]
                    cur = {}
            return rows

        def get_sync():
            # repack 2 consecutive lines
            try:
                pm = cmd("pacman", ["-Ss", self.regex.pattern])
            except subprocess.CalledProcessError:
                pm = []
            pacsync = "\n".join(pm).replace("\n    ", " »» ").splitlines()
            pattern = r"^([^ ]+?)/([^ ]+?) ([^ ]+?)(?: \((.+?)\))?(?: \[(installed)(?:\]|: ([^ ]+?)\]))? »» (.+)$"
            return [
                Pkg.Row(*re.match(pattern, entry).groups())
                for entry in pacsync if self.regex.search(entry)
            ]

        self.regex = re.compile(search, re.IGNORECASE)
        self._cols = None
        with concurrent.futures.ThreadPoolExecutor() as executor:
            f1 = executor.submit(get_foreign)
            f2 = executor.submit(get_sync)
            self.rows = f1.result() + f2.result()
            self.rows.sort(key=lambda x: x.pkg)


    def _get_packagefiles(self, name, width=80, height=25):
        try:
            return cmd("pacman", ["-Qlq", name])
        except subprocess.CalledProcessError:
            try:      # try pkgfile first (is faster) but may be not installed
                return cmd("pkgfile", ["-lq", name])
            except FileNotFoundError:
                try:
                    return cmd("pacman", ["-Flq", name])
                except subprocess.CalledProcessError as spe:
                    err = [f"pacman returned exitcode {spe.returncode}",""]
                    err += spe.stdout.splitlines() + spe.stderr.splitlines()
                    return columnize(err, width, height)
            except subprocess.CalledProcessError as spe:
                err = [f"pkgfile returned exitcode {spe.returncode}",""]
                err += spe.stdout.splitlines() + spe.stderr.splitlines()
                return columnize(err, width, height)


    def info(self, name, width=80, height=25):
        """
        show fancy package-info.
        Highlight installed packages.
        """
        if width < 40: return ["Width too small"]
        try:
            pacinfo = cmd("pacman", ["-Qi", name])
        except subprocess.CalledProcessError:
            try:  # maybe a foreign package
                pacinfo = cmd("pacman", ["-Sii", name])
            except subprocess.CalledProcessError as spe:
                err = [f"pacman returned exitcode {spe.returncode}",""]
                err += spe.stdout.splitlines() + spe.stderr.splitlines()
                return columnize(err, width, height)

        if not pacinfo: return [f"No such package »{name}«"]

        # ignore this (partly used in header):
        hfields = ("Repository", "Name", "Version", "Description", "Groups", "Licenses")
        # Dies sind Paketlisten und werden anders formatiert:
        plists = ("Depends On", "Required By", "Optional For", "Replaces", "Conflicts With")

        if not self.Installed: self._get_installed()

        # TODO: check version instead of ignoring
        def nover(x):
            return re.split("[<=>]", x, maxsplit=1)[0]

        def getnover(x):
            return nover(x), Style.ins if nover(x) in self.Installed else Style.pkg

        info = {}
        last = ""
        for l in pacinfo:
            if ":" in l and l[0] != " ":
                k, v = l.split(":", maxsplit=1)
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
                    odh = lw[0].split(": ", maxsplit=1)
                    if len(odh) == 2:
                        lw[0] = f"{fg(odh[0], Style.pkg if odh[0] not in self.Installed else Style.ins)}: {odh[1]}"
                elif k in plists:   # colorize package-list
                    lw = columnize([getnover(x) for x in r.split()], width - CW)

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
            fg(info['Name'], Style.pkg if info['Name'] not in self.Installed else Style.ins) + " " +
            fg(info['Version'], Style.ver) + " " * (width - len(info['Name'] + info['Version']) - 1)
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


    def updateDB(self):
        sudocmd("pacman", ["-Sy"])
        try:
            cmd("pkgfile", ["-V"])
            sudocmd("pkgfile", ["-u"])
        except:
            sudocmd("pacman", ["-Fy"])


    def uninstall(self, pkglist): 
        sudocmd("pacman", ["-Rsc"] + pkglist)


    def install(self, pkglist): 
        sudocmd("pacman", ["-S"] + pkglist)



#┌─────────────────────────────────────────────────────────────────────────────┐
#│                              INTERACTIVE MODE                               │
#└─────────────────────────────────────────────────────────────────────────────┘
class LineSelect():
    """
    Select a line interactively. We only use curses to some extend, since
    input is already ANSI-formated.
    """
    def keystr(self, k,t):
        return fg(k, Style.footerkey) + fg(f": {t}", Style.footertxt)


    def __init__(self, pkg):
        self.pkg = pkg
        keys = [
            ["Space", "Select"],
            ["F1", "Info"],
            ["F2", "Files"],
            ["F5", "Update DB"],
            ["Esc/F10", "Quit"],
        ]
        self.footer = fg(*Style.footersep).join(self.keystr(*x) for x in keys)

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
        if crow < self.offset + Style.scroll_padding:
            self.offset = crow - Style.scroll_padding
        if crow > self.offset + maxh - Style.scroll_padding - 1:
            self.offset = crow - maxh + Style.scroll_padding + 1


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
                color = csi(Style.zebra[i % len(Style.zebra)])
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
            top = int(f / len(self.items) * maxh * 2) / 2
            low = int(i / len(self.items) * maxh * 2) / 2
            def gx(x):
                if x + 0.5 < top or x - 0.5 > low: return " "
                if x < top: return "▄"
                if x > low: return "▀"
                return "█"
            sh = "".join(f"\033[{x+2};{self.cols}H" + gx(x) for x in range(maxh))
            out(csi(Style.scrollbar)+sh+csi())
        else:
            sh = "".join(f"\033[{x+2};{self.cols}H " for x in range(maxh))
            out(csi()+sh)

        # Footer: Keys on the left...
        action = ""
        if len(self.selected) > 0:
            rem = len(self.selected.intersection(self.installed))
            ins = len(self.selected.difference(self.installed))
            if rem > 0: action += fg(f"[- {rem}]", Style.footersel[1])+" "
            if ins > 0: action += fg(f"[+ {ins}]", Style.footersel[0])
            action = action.strip()
            action += " "*(11 - alen(action))    # at least 11 chars, like ↓
        else:
            if self.cursor in self.installed: action = "Deinstall  "
            else:                             action = "  Install  "
        keys = self.keystr("Return", action) + fg(*Style.footersep) + self.footer
        out(f"\033[{self.rows}H"+bg(f"{keys}\033[K", Style.footerbg))

        # ...current position on the right
        info = f" {self.cursor+1:{len(str(len(self.items)))}} / {len(self.items)} "
        out(f"\033[{self.rows};{self.cols - alen(info) + 1}H{csi(Style.scrollbar)}{info}{csi()}")
        sys.stdout.flush()
        return f, i


    def findfirst(self, char):
        for i, r in enumerate(self.pkg.rows):
            if r.pkg.lower().startswith(char.lower()): return i
        return None


    def mainloop(self, scr):
        """Mainloop must be called in curses.wrapper"""
        curses.curs_set(0)
        curses.mousemask(-1)

        def toggle(x):
            if x in self.selected:  self.selected.remove(x)
            else:                   self.selected.add(x)

        def showinfo(infofun):
            pkgname = self.pkg.rows[self.cursor].pkg
            H = self.rows - 2
            nfo = infofun(pkgname, self.cols - 4, H)
            nr = min(len(nfo), H)
            nw = min(max(alen(x) for x in nfo), self.cols - 4)
            left = (self.cols - 4 - nw) // 2
            top = (self.rows - nr) // 2

            def output(offset=0):
                out = sys.stdout.write
                out(f"\033[{top};{left}H")
                out(bg(fg(f"█▀{'▀' * nw}▀█", Style.infoborder), Style.infobg))
                t, l = int(offset / len(nfo) * H), int((offset+H) / len(nfo) * H)
                for i, r in enumerate(nfo[offset:(offset + nr)]):
                    prg = fg('▐' if i < t or i > l else '█', Style.infoborder)
                    out(f"\033[{top+i+1};{left}H")
                    out(bg(f"{fg('█', Style.infoborder)} {r} {prg}", Style.infobg))
                out(f"\033[{top+i+2};{left}H")
                out(bg(fg(f"█▄{'▄' * nw}▄█", Style.infoborder), Style.infobg))
                sys.stdout.flush()

            keh = None
            infotafel = True
            offset = 0
            # no resize-support, so getch may as well block
            scr.timeout(-1)
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

        def updateDB():
            self.pkg.updateDB()
            # reload package list but keep selection & cursor
            self.pkg.search(self.pkg.regex.pattern)
            self.items = self.pkg.to_list(self.cols-1)[1:]
            self.installed = set(i for i, r in enumerate(self.pkg.rows) if r.ins)

        scr.timeout(100)        # getch-timeout is used for delayed resize
        result, loop = None, True
        repaint = True
        doresize = False
        fr, tr = self.display()
        while loop:
            keh = scr.getch()
            match keh:
                case curses.KEY_RESIZE: doresize = True                         # 410
                case -1:
                    if doresize:
                        self.rows, self.cols = scr.getmaxyx()
                        lines = self.pkg.to_list(self.cols-1)
                        self.header = lines[0][0]
                        self.items = lines[1:]
                        doresize = False
                        repaint = True

                # Navigation
                case curses.KEY_UP:     self.cursor -= 1                        # 259
                case curses.KEY_DOWN:   self.cursor += 1                        # 258
                case curses.KEY_HOME:   self.cursor = 0                         # 262
                case curses.KEY_END:    self.cursor = len(self.items) - 1       # 360
                case curses.KEY_PPAGE:  self.offset, self.cursor = 0, fr        # 339
                case curses.KEY_NPAGE:  self.offset, self.cursor = 2**63, tr    # 338

                # jump to char
                case x if 'a' <= chr(x).lower() <= 'z':                         # 97-122
                    new = self.findfirst(chr(x))
                    if new is not None: self.cursor = new

                # MOUSE! scrollwheel scrolls. leftclick sets cursor. rightclick (de)selects
                case curses.KEY_MOUSE:
                    mous = curses.getmouse()    # (id, x, y, z, bstate)
                    if mous[2] < 1 or mous[2] >= self.rows-1 or mous[2]-1 >= len(self.ymap) : continue
                    if mous[4] == curses.BUTTON5_PRESSED: self.offset += 3
                    if mous[4] == curses.BUTTON4_PRESSED: self.offset -= 3
                    if mous[4] == curses.BUTTON3_CLICKED: toggle(self.ymap[mous[2]-1])
                    if mous[4] == curses.BUTTON1_CLICKED: self.cursor = self.ymap[mous[2]-1]

                # Hotkeys
                case curses.KEY_F1:     showinfo(self.pkg.info)                 # 265
                case curses.KEY_F2:     showinfo(self.pkg.filelist)             # 266
                case curses.KEY_F5:     result, loop = updateDB, False          # 269
                case 10:                result, loop = self.cursor, False       # return
                case 32:                toggle(self.cursor); self.cursor += 1   # space
                case 27 | curses.KEY_F10: result, loop = None, False            # escape

            if keh > -1 or repaint:
                fr, tr = self.display()
                repaint = False

        curses.curs_set(1)
        return result


    def main(self):
        # start loading all installed packages in the background for pkg.info()
        threading.Thread(target=pkg._get_installed).start()
        curses.set_escdelay(50)

        def header(s, c):
            s = f"──══▶ {s} ◀══──"
            print(csi(Style.selected[c])+hl(fg(f"{s:^{self.cols-1}}", 15), 1)+csi())

        while True:
            res = curses.wrapper(self.mainloop)
            if callable(res):
                header(res.__name__, 0)
                res()

            elif res is not None:
                if len(self.selected) == 0: self.selected = set([res])
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

                if pkgwech: self.pkg.uninstall([self.pkg.rows[s].pkg for s in pkgwech])
                if pkghin:  self.pkg.install([self.pkg.rows[s].pkg for s in pkghin])
                break
            else:
                if not self.doscrollbar:
                    self.pkg.to_ansi(self.cols-1)
                break


#┌─────────────────────────────────────────────────────────────────────────────┐
#│                                    MAIN                                     │
#└─────────────────────────────────────────────────────────────────────────────┘
if __name__ == '__main__':
    class MultiForm(argparse.HelpFormatter):
        # for linebreaks in descriptiontext:
        def _fill_text(self, t, w, i):
            return ''.join("\n".join(wrap(p, w))+'\n' for p in t.split('\n\n'))

    parser = argparse.ArgumentParser(formatter_class=MultiForm, description="""
        Search for packages with pacman or apt and show results in an interactive
        list. Installed packages are highlighted/marked and available updates
        are shown as well.

        If no option is given and stdout is a TTY, interactive mode will be
        started.

        If no option is given and stdout is NOT a TTY, a tab-separated table
        will be written. (like with -c)

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
    group.add_argument("-i", "--info", action="store_true", help="""
        Show package info instead of searchresults.
        Searchterm must be the exact packagename (or yield exactly one result)
    """)
    args = parser.parse_args()

    # Use better colors, if available and detect terminal size
    w, h, tty = 80, 25, (sys.stdout.isatty() and sys.stdin.isatty())
    if tty:
        curses.setupterm()
        if curses.tigetnum("colors") > 16: Style = Style256
        ts = os.get_terminal_size()
        w, h = ts.columns, ts.lines

    # Try Autodetecting PACKAGE MANAGER                      │
    PkgMgr = None
    if checkcmd("apt") and not checkcmd("pacman"): PkgMgr = AptPkg
    if checkcmd("pacman") and not checkcmd("apt"): PkgMgr = PacPkg
    assert PkgMgr is not None, "Could not detect packagemanager"
    
    pkg = PkgMgr()
    pkg.search(args.searchterm[0])
    if len(pkg.rows) == 0: sys.exit(1)  # nothing found

    if args.json: pkg.to_json()
    elif args.csv: pkg.to_csv()
    elif args.info:
        if len(pkg.rows) > 1:
            pkg.rows = [x for x in pkg.rows if x.pkg==args.searchterm[0]]
        if len(pkg.rows) != 1:
            print("Error: Package not found")
            sys.exit(1)
        nfo = pkg.info(pkg.rows[0].pkg, w, h)
        lst = pkg.filelist(pkg.rows[0].pkg, w, max(h-len(nfo)-7, 1))
        print("\n"+"\n".join(nfo+["","\x1b[97;1mFiles:\x1b[m",""]+lst)+"\n")
    elif args.ansi is not None:
        if args.ansi > 0: w = args.ansi
        pkg.to_ansi(w)
    else:
        if tty: LineSelect(pkg).main()
        else: pkg.to_csv()
