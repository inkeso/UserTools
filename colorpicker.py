#!/usr/bin/env python3
import gi, subprocess
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

csd = Gtk.ColorSelectionDialog(title="Farbe")
csd.set_icon_name("applications-graphics")
cs = csd.get_property("color-selection")
nc = Gdk.RGBA()
proc = subprocess.Popen(("xclip", "-o"), stdout=subprocess.PIPE)
nc.parse(proc.communicate()[0].decode("utf-8"))
cs.set_current_rgba(nc)
res = csd.run()
quad = csd.get_color_selection().get_current_rgba().to_color().to_floats()
if res == Gtk.ResponseType.OK:
    hexa = "#%02x%02x%02x" % tuple(round(quad[i]*255) for i in range(3))
    proc = subprocess.Popen(("xclip", "-i", "-selection", "clipboard"), stdin=subprocess.PIPE)
    proc.communicate(hexa.encode("utf-8"))
    proc = subprocess.Popen(("xclip", "-i", "-selection", "primary"), stdin=subprocess.PIPE)
    proc.communicate(hexa.encode("utf-8"))
    print(hexa)
csd.destroy()
