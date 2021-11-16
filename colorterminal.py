#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys 

def echo(s="{0}0m\n", *arg): 
    sys.stdout.write(s.format("\033[", *arg))

def banner(s):
    spc = 80-len(s)-4
    spc = ("{:%d}" % (spc / 2)).format("") if spc > 0 else ""
    echo(spc + "{0}95m┌{1:─<%d}┐\n" % (len(s) + 2), "")
    echo(spc + "│{0}96m {1} {0}95m│\n", s)
    echo(spc + "{0}95m└{1:─<%d}┘\n" % (len(s) + 2), "")

def c16(show_banner=True):
   if show_banner: banner("ANSI-Colors")
   for f in range(8):
       for t in (3,9):
           for b in range(8):
               echo("{0}{3}{1};4{2}m {1}/{2} {0}{3}{1};10{2}m {1}/{2} {0}0m", f,b,t)
           echo("\n")
   echo("\nset FG/BG/SGR: ESC[__m    ESC[__;__m    0=reset             9=default\n")
   echo("{0}36m30..37 FG normal    {0}96m90..97 FG bright    {0}37;44m40..47 BG normal{0}0m    {0}37;104m100..107 BG bright{0}0m\n")
   echo(" {0}1m1=bold{0}0m     {0}3m3=italic{0}0m     {0}4m4=underline{0}0m     {0}5m5=blink{0}0m     {0}7m7=reverse{0}0m     {0}9m9=crossed{0}0m\n")
   echo("{0}22m22=nobold{0}0m  {0}23m23=noitalic{0}0m  {0}24m24=nounderline{0}0m  {0}25m25=noblink{0}0m  {0}27m27=noreverse{0}0m  {0}29m29=nocrossed{0}0m\n")

def c256(show_banner=True):
    if show_banner: 
        banner("XTERM-256-Colors")
    feld = "{0}{1}8;5;{2}m{2:^5}{0}0m"
    for r in range(36):
        # first column 0-15 standard colors (BG & FG)
        if r < 16: echo(feld, 4, r)
        elif r > 16 and r <= 32: echo(feld, 3, r-17)
        else: echo(" "*5)
        echo(" ")
        # second & thrid column: 218 6x6x6 rgb cube
        for c in range(6): echo(feld, 4, r*6+16+c)
        echo(" ")
        for c in range(6): echo(feld, 3, r*6+16+c)
        echo(" ")
        # gray "bg fg"
        if r < 24: [echo(feld, x, r+232) for x in (3,4)]
        echo("\n")
    echo("\n{0}0m0-7: standard colors (ESC[30-37m) / 8-15: high intensity colors (ESC[90-97m)\n")
    echo("16-231:  6×6×6 cube (216 colors): 16 + 36·r + 6·g + b (0 ≤ r,g,b ≤ 5)\n")
    echo("232-255: grayscale from black to white in 24 steps\n")
    echo("set FG with ESC[38;5;___m   |   BG with ESC[48;5;___m\n")

def crgb(show_banner=True):
    if show_banner: banner("XTERM-RGB-Colors")
    for b in range(0,32):
        be = b * 8
        bo = be + 4 
        for r in range(0,128,2):
            echo("{0}38;2;{1};{2};{3}m{0}48;2;{1};{2};{4}m▀", r*2, (127-r)*2, be, bo)
        echo("{0}0m {0}38;2;{1};{1};{1}m{0}48;2;{2};{2};{2}m▀▀▀", be, bo)
        echo("{0}0m {0}38;2;{1};0;0m{0}48;2;{2};0;0m▀▀▀", be, bo)
        echo("{0}0m {0}38;2;0;{1};0m{0}48;2;0;{2};0m▀▀▀", be, bo)
        echo("{0}0m {0}38;2;0;0;{1}m{0}48;2;0;0;{2}m▀▀▀", be, bo)
        echo("{0}0m\n")
    echo("\nset BG with ESC[48;2;R;G;Bm   |   FG with ESC[38;2;R;G;Bm   (R,G,B = 0..255)\n")

def call(): 
    c16()
    echo()
    c256()
    echo()
    crgb()

def keen(): 
    c16(False)
    echo()
    c256(False)
    echo("({0}38;2;255;0;0mR{0}0m,{0}38;2;0;255;0mG{0}0m,{0}38;2;0;0;255mB{0}0m = 0..255) set BG with ESC[48;2;R;G;Bm   |   FG with ESC[38;2;R;G;Bm  ")
    #block / swallow input

    import tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        echo("{0}?25l")
        sys.stdout.flush()
        tty.setraw(sys.stdin.fileno())
        while True:
            ch = sys.stdin.read(1)
            if ord(ch) == 3: break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        echo("{0}?25h\n")
    

if len(sys.argv) >= 2:
    pars = {'16': c16, '256': c256, 'rgb': crgb, 'all': call, 'keen': keen}
    for sav in sys.argv[1:]:
       if sav in pars:
           pars[sav]()
       else:
           echo("Unknown parameter »{1}«. Must be one of »{2}«\n", sav, "«, »".join(pars.keys()))
           sys.exit(1)
else:
    c16()
 
 
