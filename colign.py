#!/usr/bin/env python3

# A custom column-command.
# colign.py '#' ':' <"$1"
# should be equivalent to:
# cat $1 | column -t -o"#" -s "#"| column -t -o":" -s ":"

# but since it is quite dumb and unoptimzed, it's only suitable for smaller
# files, up to a few MB.

import sys, re
import tkinter


def tabulate(txt, splitter="[,;\t]", trim="\n"):
    if isinstance(txt, str): txt = txt.splitlines()
    tok = [re.split(f"({splitter})", s.strip(trim)) for s in txt]               # split
    mto = [0,] * max(len(t) for t in tok)                                       # store max len of token
    aln = ["<",] * len(mto)                                                     # and align-vector
    for line in tok:
        for i, wrd in enumerate(line): mto[i] = max(mto[i], len(wrd))
        if len(line) < len(mto): line += ['',] * (len(mto) - len(line))         # also pad shorter lines
    fmt = "".join(f"{{:{a}{w}}}" for a,w in zip(aln, mto))                      # create final format string
    return [fmt.format(*line) for line in tok]


# simplified way of getting tk.checkbutton state without tkVar.
def is_checked(what): return what.getvar(what.cget('variable')) == "1"


class gui(tkinter.Tk):
    COLORSCHEME = {
        'win_bg': "#033A4C",
        'txt_bg': "#324247",
        'txt_fg': "#F6FFCF",
        'error' : "#FF7465",
        'btn_bg': "#195351",
        'btn_hl': "#206B69",
        'btn_fg': "#D3DA24",
    }


    def style(self, th):
        self.config(bg=th['win_bg'])
        self.txview. config(bg=th['txt_bg'], fg=th['txt_fg'], highlightthickness=0, relief="flat")
        self.txscrx. config(bg=th['btn_bg'],                  highlightthickness=0, relief="flat")
        self.txscry. config(bg=th['btn_bg'],                  highlightthickness=0, relief="flat")
        self.entry.  config(bg=th['btn_bg'], fg=th['txt_fg'], highlightthickness=0)
        self.message.config(bg=th['win_bg'], fg=th['btn_fg'], highlightthickness=0)
        self.ctrim.  config(bg=th['win_bg'], fg=th['btn_fg'], highlightthickness=0)
        self.cwrap.  config(bg=th['win_bg'], fg=th['btn_fg'], highlightthickness=0)
        self.button. config(bg=th['btn_bg'], fg=th['btn_fg'], highlightthickness=0)

        self.txscrx. config(activebackground=th['btn_hl'], troughcolor=th['win_bg'])
        self.txscry. config(activebackground=th['btn_hl'], troughcolor=th['win_bg'])
        self.entry.  config(insertbackground=th['btn_fg'])
        self.ctrim.  config(activebackground=th['win_bg'], activeforeground=th['btn_fg'], selectcolor=th['btn_bg'])
        self.cwrap.  config(activebackground=th['win_bg'], activeforeground=th['btn_fg'], selectcolor=th['btn_bg'])
        self.button. config(activebackground=th['btn_hl'], activeforeground=th['btn_fg'])


    def __init__(self, txt):
        if isinstance(txt, str): txt = txt.splitlines()
        super().__init__()
        self.title("Columnice")
        self.protocol("WM_DELETE_WINDOW", lambda: self.die(1))
        self.txt = txt
        self.splitter = '[,;\t]'
        self.trim = '\n'
        self.wrap = "none"
        self.result = self.txt

        ##** Create Widgets **##
        self.txview = tkinter.Text(self, state='disabled', width=160, height=30, wrap=self.wrap)
        self.txscrx = tkinter.Scrollbar(self, command=self.txview.xview, orient="horizontal")
        self.txscry = tkinter.Scrollbar(self, command=self.txview.yview, orient="vertical")
        self.txview.config(xscrollcommand=self.txscrx.set, yscrollcommand=self.txscry.set)

        self.entry = tkinter.Entry(self)
        self.entry.bind("<KeyRelease>", self.resplit)
        self.entry.insert("end", repr(self.splitter)[1:-1])
        self.entry.bind('<Return>', lambda _: self.die(0))
        self.message = tkinter.Label(self)
        self.ctrim = tkinter.Checkbutton(self, text="trim", command=self.set_trim)
        self.cwrap = tkinter.Checkbutton(self, text="wrap", command=self.set_wrap)
        self.button = tkinter.Button(self, text="OK", command=lambda: self.die(0))

        ##** Place Widgets **##
        self.txview. grid(row=0, column=0,            columnspan=3, sticky="nsew")
        self.txscrx. grid(row=1, column=0,            columnspan=3, sticky="sew")
        self.txscry. grid(row=0, column=3,                          sticky="nse")
        self.entry.  grid(row=2, column=0, padx=1,                  sticky="sew")
        self.message.grid(row=3, column=0,                          sticky="sew")
        self.ctrim.  grid(row=2, column=1, padx=4,                  sticky="w")
        self.cwrap.  grid(row=3, column=1, padx=4,                  sticky="w")
        self.button. grid(row=2, column=2, rowspan=2, columnspan=2, sticky="nsew")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.style(gui.COLORSCHEME)

        self.resplit(True)
        
        self.entry.focus_set()
        
        self.mainloop()


    def set_trim(self):
        self.trim = None if is_checked(self.ctrim) else "\n"
        self.resplit(True)


    def set_wrap(self):
        self.wrap = "word" if is_checked(self.cwrap) else "none"
        self.txview.config(wrap=self.wrap)


    def resplit(self, force=False):
        fmtstr = self.entry.get()
        for ch in "tnr": fmtstr = fmtstr.replace("\\\\"+ch, "\\"+ch)
        if fmtstr == self.splitter and not force: return
        try:
            re.compile(fmtstr)
            self.message.config(text="")
        except Exception as e:
            self.message.config(text=str(e))
            return

        self.splitter = self.entry.get()
        self.result = tabulate(self.txt, self.splitter, self.trim)
        self.txview.config(state='normal')
        self.txview.delete('1.0', "end")
        self.txview.insert("end", "\n".join(self.result))
        self.txview.config(state='disabled')


    def die(self, n):
        print("\n".join([self.result, self.txt][n]))
        self.quit()


if __name__ == '__main__':
    gui(sys.stdin.read())
    # TODO: argparse und dann GUI nur optional
