#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, gi, argparse
gi.require_version('WebKit2', '4.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, WebKit2, GdkPixbuf

parser = argparse.ArgumentParser()
parser.add_argument("URL", help="URL", nargs="?")
for ao in [ 
    ["--borderless", '-b', False,                "Do not draw window decoration"],
    ["--no-escape",  '-n', False,                "Do not Exit on Escape"],
    ["--title",      '-t', '',                   "Window title. Defaults to URL."],
    ["--geometry",   '-g', '1024x768+center',    "Window geometry. "
                                                 "<Width>x<Height>[+<x+y|center>]"],
    ["--icon",       '-i', '',                   "Set icon from imagefile"],
    ["--javascript", '-j', '',                   "Start some javascript after loading. May be a long string containing JS or a filename."],
    ["--css",        '-c', '',                   "Apply user-css. May be a long string containing CSS or a filename."],
    ["--cookies",    '-o', '',                   "Keep cookies in a file"],
    ]:
    if type(ao[2]) == bool: prm = { 'action': "store_true" }
    else: prm = { 'type': type(ao[2]), 'default': ao[2] }
    parser.add_argument(ao[1], ao[0], help=ao[3], **prm)
args = parser.parse_args()

if args.URL is None:
    parser.print_help()
    exit(1)

def fileorstring(stuff):
    """
    return the contents of the file named stuff, if it exists,
    otherwise return stuff itself
    """
    res = stuff
    try:
        with open(stuff) as fi: res = "".join(fi.readlines())
    except (FileNotFoundError, OSError) as e:
        #sys.stderr.write(str(e)+", Assuming string\n")
        pass
    return res


manager = WebKit2.UserContentManager()
style = WebKit2.UserStyleSheet(
    fileorstring(args.css),
    WebKit2.UserContentInjectedFrames.ALL_FRAMES,
    WebKit2.UserStyleLevel.USER
)
manager.add_style_sheet(style)

if args.cookies:
    context = WebKit2.WebContext.get_default()
    cookies = context.get_cookie_manager()
    cookies.set_persistent_storage(args.cookies, WebKit2.CookiePersistentStorage.TEXT)

broz = WebKit2.WebView.new_with_user_content_manager(manager)

broz.vscroll = Gtk.ScrolledWindow(child=broz)
broz.loadpb = Gtk.ProgressBar(fraction=0.0, show_text=True, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
broz.window = Gtk.Window(type=Gtk.WindowType(0), child=broz.loadpb)
broz.window.connect("destroy", Gtk.main_quit)

if not args.no_escape: # Exit on escape?
    def clack(widget, event):
        if event.keyval == Gdk.KEY_Escape: Gtk.main_quit()
    broz.window.connect("key_press_event", clack)

broz.window.set_title(args.URL if not args.title else args.title)
if args.icon: broz.window.set_icon(GdkPixbuf.Pixbuf.new_from_file(args.icon))

if args.borderless:
    broz.window.set_decorated(False)

# Assign thumb-Buttons
def click(widget, event):
    if event.button == 8 and broz.can_go_back(): return not broz.go_back()
    if event.button == 9 and broz.can_go_forward(): return not broz.go_forward()
broz.connect("button-press-event", click)

# Loading...
broz.finished = False
def ready(widget, event):
    if event is WebKit2.LoadEvent.FINISHED:
        broz.finished = True
        broz.disconnect(broz.onready)
        return

def loading():
    fort = broz.get_estimated_load_progress()
    broz.loadpb.set_fraction(fort)
    if fort < 1 or not broz.finished: return True

    # Switch to page, run JS
    broz.window.remove(broz.loadpb)
    broz.window.add(broz.vscroll)
    broz.vscroll.show_all()
    broz.window.set_focus(broz)
    if (args.javascript): GLib.idle_add(
        broz.evaluate_javascript, fileorstring(args.javascript), -1
    )
    return False

GLib.timeout_add(100, loading)
broz.onready = broz.connect("load-changed", ready)
broz.load_uri(args.URL)
broz.window.show_all()

# parse and set Position
try:
    sipo = args.geometry.split("+", 1)
    size = [int(x) for x in sipo[0].split("x")]
    if len(sipo) > 1:
        if sipo[1].lower() == "center":
            broz.window.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        else:
            pos = [int(x) for x in sipo[1].split("+")]
            broz.window.move(*pos)
    broz.window.resize(*size)
except Exception as e:
    print("Error parsing geometry:", e)

Gtk.main()
