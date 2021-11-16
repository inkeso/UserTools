#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0') 
from gi.repository import Gtk, Gdk
from gi.repository import WebKit2
from fontTools import ttLib

# Config:
BodyCSS = "background: #222; color:#eee;"

def shortName(targ, dirname, fnames):
    """Get the short name from the font's names table"""
    
    FONT_SPECIFIER_NAME_ID = 4
    
    for fnam in fnames:
        ffile = os.path.join(dirname, fnam)
        try:
            font = ttLib.TTFont(ffile, fontNumber=0)
            name = ""
            for record in font['name'].names:
                if record.nameID == FONT_SPECIFIER_NAME_ID and not name:
                    if b'\000' in record.string:
                        name = record.string.decode('utf-16-be')
                    else:
                        name = record.string.decode("utf-8")
                    break
            genname = os.path.join(dirname, fnam).replace(os.path.sep, "-")
            targ.append((dirname, fnam, name, genname))
        except Exception as r:
            print (ffile, r)
    return

def loadfrompath(ev=None):
    global broz, fpath, files, BodyCSS
    files = []
    
    header = "<body style=\"%s font-size:12pt; font-weight: bold;\">" % BodyCSS
    broz.load_html(header + "reading files...", "file://")
    while Gtk.events_pending(): Gtk.main_iteration()
    #try:
    for rt, dr, fl in os.walk(fpath.get_text()):
        shortName(files, rt, fl)
    
    #os.path.walk(fpath.get_text(), shortName, files)
    files.sort()
    broz.load_html(header + "rendering %d files..." % len(files), "file://")
    while Gtk.events_pending(): Gtk.main_iteration()
    render()
    #except Exception as e:
    #    broz.load_html(header + "Error: " + str(e), "file://")
        
    return

def render():
    global files, broz, BodyCSS
    html = """<html><head><style>
        body { 
            %s
            font-family: sans-serif;
        }
        p {
            font-weight: bold;
        }
        
        td,th,table {
            font-size: 10pt;
            border:4px solid rgba(0,0,0,0.2);
            border-collapse:collapse;
        }
        th { 
            background: rgba(0,0,0,0.2);
            
        }
        
        .filename {
            font-family: monospace;
            font-weight: normal;
            text-align: left;
            padding:0.5em;
        }
        small {
            font-size:8pt;
            color:#777;
        }
        b { 
            display: block;
            text-align: center;
            font-size: 1.2em;
            margin-bottom:0.6em;
        }
        .example {
            font-size: 20pt;
            padding:0.5em;
        }
        
    """ % BodyCSS
    for x in files:
        html += "@font-face { font-family: '%s'; src: url('file://%s') format('truetype'); }\n" % (x[3], os.path.join(x[0], x[1]))
    html += """
    </style></head><body>
    <p>%d files found</p>
    <table>
    """ % len(files)
    example = """
        The quick brown Fox jumped over The Lazy Dogs back. <br/>
        0134567890 !?\"§$&[{(<>)}];:.,=-_ ÄäÖöÜü ß <br/>
        AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz
    """
    for x in files:
        html += """<tr>
        <th class="filename"><b>%s</b><small>%s/</small><br/>%s</td>
        <td class="example" style="font-family: '%s';">%s</td>
        </tr>""" % (x[2], x[0], x[1], x[3], example)
    html += "</table></body></html>"
    broz.load_html(html, "file://")
    return

##### MAIN #####
files = [] # contains a list of tuples: ("/full/path/to", "fontfile.ttf", "FontName")

# The Browser
broz = WebKit2.WebView()

sw = Gtk.ScrolledWindow()
sw.add(broz)

wind = Gtk.Window()
wind.connect("destroy", Gtk.main_quit)
wind.set_title("TTFview")
wind.resize(1600, 1000)

fpath = Gtk.Entry()
fpath.set_text(os.getcwd() if len(sys.argv) < 2 else os.path.realpath(sys.argv[1]))
butt = Gtk.Button(label="Reload Fonts")
butt.connect("clicked", loadfrompath)

hbox = Gtk.HBox()
hbox.pack_start(fpath, True, True, 0)
hbox.pack_start(butt, False, False, 0)

vbox = Gtk.VBox()
vbox.pack_start(sw, True, True, 0)
vbox.pack_start(hbox,False, False, 0)
wind.add(vbox)
wind.set_focus(butt)

wind.show_all()
loadfrompath()

Gtk.main()

