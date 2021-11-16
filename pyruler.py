#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import cairo

class Ruler(Gtk.Window):

    ### "CONFIG" ###

    WIDTH = 42              # Width of each ruler in pixels
    TICKS1 = WIDTH / 8      # Length of short tickmarks (every 2 pixels)
    TICKS2 = WIDTH / 5      # Length of middle tickmarks (every 10 pixels)
    TICKS3 = WIDTH / 4      # Length of long tickmarks (every 50 pixels, at number)
    GRIPSIZE = WIDTH / 3    # Size of (invisible) resize-grip at the edge of each ruler
    STARTSIZE = WIDTH * 11  # Size of initial (square) window (one value for x == y)

    FONT = "Sans"   # Font used for Ruler & Label
    FONTSIZE = 10

    RULERCOLOR =    (0.9, 0.9, 0.0, 0.7)    # Ruler background color RGBA
    RULERTEXT =     (0.0, 0.0, 0.0, 1.0)    # Text & Tickmark color RGBA
    CURSORCOLOR =   (0.3, 0.3, 0.3, 0.7)    # Cursor color
    MARKERCOLOR =   (1.0, 0.0, 0.0, 0.5)    # Marker color
    DIMCOLOR =      (0.0, 0.0, 0.0, 0.3)    # Dim color to highlight selection
    LABELCOLOR =    (0.0, 0.0, 0.0, 0.5)    # Label background
    LABELTEXT =     (1.0, 1.0, 1.0, 1.0)    # Label text color

    def __init__(self, *args, **kwds):
        super(Ruler, self).__init__(*args, **kwds)
        self.set_size_request(self.WIDTH, self.WIDTH)
        self.set_default_size(self.STARTSIZE, self.STARTSIZE)
        self.set_title("PyRuler")
        self.set_icon_name("applications-engineering")
        self.connect("delete-event", Gtk.main_quit)
        self.set_keep_above(True)
        self.set_decorated(False)
        # Enable RGBA / Transparency
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is None:
            print("[W]: Your screen does not support alpha channels!")
            visual = screen.get_system_visual()
        self.set_visual(visual)

        self.k1 = None # first coordinate-picker (x,y)
        self.k2 = None # second coordinate-picker (x,y)
        self.ursprung = Gdk.Gravity.NORTH_WEST # one of the 4 corners. this is the default.

        # manual window-movement and resizing. Just for convenience,
        # your windowmanager is probably better with this
        self.ismove = None
        self.resizeH = None
        self.resizeV = None

        # drawingarea and buffer-surface.
        self.surface = None
        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.on_draw)
        self.area.connect('configure-event', self.redraw)
        self.area.add_events(Gdk.EventMask.ALL_EVENTS_MASK)
        self.area.connect("button-press-event", self.klack)
        self.area.connect("motion-notify-event", self.cursormove)
        self.area.connect("button-release-event", self.released)
        self.area.connect("leave-notify-event", self.redraw)
        self.w, self.h = self.area.get_allocated_width(), self.area.get_allocated_height()

        self.add(self.area)
        self.show_all()

        self.menu = Gtk.Menu()
        def setur(wd, n):
            self.ursprung = n
            self.redraw()

        def kreset(wd, no):
            self.k1 = None
            self.k2 = None
            self.redraw()

        buttons = [ [Gtk.MenuItem(label="┌ "), setur, Gdk.Gravity.NORTH_WEST],
                    [Gtk.MenuItem(label=" ┐"), setur, Gdk.Gravity.NORTH_EAST],
                    [Gtk.MenuItem(label=" ┘"), setur, Gdk.Gravity.SOUTH_EAST],
                    [Gtk.MenuItem(label="└ "), setur, Gdk.Gravity.SOUTH_WEST],
                    [Gtk.SeparatorMenuItem(), None],
                    [Gtk.MenuItem(label="Reset Marker"), kreset],
                    [Gtk.SeparatorMenuItem(), None],
                    [Gtk.MenuItem(label="Quit"), Gtk.main_quit]
        ]
        for i in buttons:
            self.menu.append(i[0])
            if i[1]: i[0].connect("activate", i[1], i[2] if len(i) > 2 else None)
        self.menu.show_all()

        #self.area.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "crosshair"))
        self.area.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "none"))


    def redraw(self, area=None, event=None, data=None):
        # Destroy previous buffer
        if self.surface is not None:
            self.surface.finish()
            self.surface = None

        # Create a new buffer
        self.w = self.area.get_allocated_width()
        self.h = self.area.get_allocated_height()
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)

        ctx = cairo.Context(self.surface)
        self.plotbars(ctx)
        self.plotcursors(ctx)
        self.surface.flush()
        self.queue_draw()


    def on_draw(self, area, context):
        if self.surface is not None:
            context.set_source_surface(self.surface, 0.0, 0.0)
            context.paint()
        else:
            print('Invalid surface')
        return False


    def abs2rel(self, x, y):
        """
        turn absolute coordinates (screen) to relative coordinates (ruler-coords),
        depending on self.ursprung
        """
        urnick = self.ursprung.value_nick
        xoff = x if x is None else x - self.WIDTH if "west"  in urnick else self.w - self.WIDTH - x
        yoff = y if y is None else y - self.WIDTH if "north" in urnick else self.h - self.WIDTH - y
        return xoff, yoff


    def rel2abs(self, x, y):
        """
        turn relative coordinates (ruler-coords) to absolute coordinates (screen),
        depending on self.ursprung
        """
        urnick = self.ursprung.value_nick
        xoff = x if x is None else x + self.WIDTH if "west"  in urnick else self.w - self.WIDTH - x
        yoff = y if y is None else y + self.WIDTH if "north" in urnick else self.h - self.WIDTH - y
        return xoff, yoff


    def plotbars(self, ctx):
        w, h = self.w, self.h
        urnick = self.ursprung.value_nick

        # Rulers
        ctx.set_source_rgba(*self.RULERCOLOR)
        if "north" in urnick: ctx.rectangle(0, 0,            w, self.WIDTH)   # Top
        if "south" in urnick: ctx.rectangle(0, h-self.WIDTH, w, h         )   # Bottom
        if "east"  in urnick: ctx.rectangle(w-self.WIDTH, 0, w,          h)   # Right
        if "west"  in urnick: ctx.rectangle(0,            0, self.WIDTH, h)   # Left
        ctx.fill()

        # Scales
        ctx.set_source_rgba(*self.RULERTEXT)
        ctx.select_font_face(self.FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(self.FONTSIZE)
        ctx.set_line_width(1)

        xoff = (self.WIDTH if "west" in urnick else w - self.WIDTH) + 0.5
        yoff = (self.WIDTH if "north" in urnick else h - self.WIDTH) + 0.5
        xinc = 1 if "west" in urnick else -1
        yinc = 1 if "north" in urnick else -1

        for i in range(0, max(w-self.WIDTH, h-self.WIDTH), 2):
            x2 = xoff + i * xinc
            y2 = yoff + i * yinc
            # horizontal ticks
            ctx.move_to(x2, yoff)
            if i % 2  == 0: ctx.line_to(x2, yoff + self.TICKS1 * -yinc)
            if i % 10 == 0: ctx.line_to(x2, yoff + self.TICKS2 * -yinc)
            if i % 50 == 0: ctx.line_to(x2, yoff + self.TICKS3 * -yinc)
            # vertical ticks
            ctx.move_to(xoff, y2)
            if i % 2  == 0: ctx.line_to(xoff + self.TICKS1 * -xinc, y2)
            if i % 10 == 0: ctx.line_to(xoff + self.TICKS2 * -xinc, y2)
            if i % 50 == 0: ctx.line_to(xoff + self.TICKS3 * -xinc, y2)
            ctx.stroke()

            # text
            if i % 50 != 0: continue

            txt = ctx.text_extents("%d" % i)
            xtxt = xoff - xinc * (self.TICKS3 + txt.width + 3) - (txt.width if xinc < 0 else 0)
            ytxt = yoff - yinc * (self.TICKS3 + txt.height/3) + (txt.height if yinc < 0 else 0)
            # horizontal
            ctx.move_to(x2 + txt.width/2, ytxt)
            ctx.show_text("%d" % i)
            # vertical
            ctx.move_to(xtxt, y2 + txt.height/2)
            ctx.show_text("%d" % i)


    def shadowtext(self, cx, cy, txt):
        ctx = cairo.Context(self.surface)
        ctx.select_font_face(self.FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(self.FONTSIZE)
        ctx.set_source_rgba(*self.LABELCOLOR)
        for fy in range(-2,3):
            for fx in range(-2,3):
                ctx.move_to(cx+fx, cy+fy)
                ctx.show_text(txt)
        ctx.set_source_rgba(*self.LABELTEXT)
        ctx.move_to(cx, cy)
        ctx.show_text(txt)


    def plotcursors(self, ctx):
        # self.k1 and .k2 are absolute coords
        w, h = self.w, self.h
        urnick = self.ursprung.value_nick

        if self.k1 is not None and self.k2 is not None:
            ctx.set_source_rgba(0, 0, 0, 0.3)
            # if both x are set: dim left and right
            if self.k1[0] is not None and self.k2[0] is not None:
                minw = min(self.k1[0], self.k2[0])+0.5
                maxw = max(self.k1[0], self.k2[0])+0.5
                ctx.rectangle(0, 0, minw, h)   # Left
                ctx.rectangle(maxw, 0, w, h)   # Right

            # if both y are set: dim top and bottom
            if self.k1[1] is not None and self.k2[1] is not None:
                minh = min(self.k1[1], self.k2[1])+0.5
                maxh = max(self.k1[1], self.k2[1])+0.5
                ctx.rectangle(0, 0, w, minh)   # Top
                ctx.rectangle(0, maxh, w, h)   # Bottom
            ctx.fill()

            # show dimensions in the middle
            res = []
            mx, my = None, None # middle

            if self.k1[0] is not None and self.k2[0] is not None: # vertical, x is set
                res += ["%d" % abs(self.k1[0]-self.k2[0])]
                mx = (self.k1[0] + self.k2[0]) / 2
            if self.k1[1] is not None and self.k2[1] is not None: # horizontal, y is set
                res += ["%d" % abs(self.k1[1]-self.k2[1])]
                my = (self.k1[1] + self.k2[1]) / 2
            res = "x".join(res)
            txt = ctx.text_extents(res)
            if mx is None: mx = w/2
            if my is None: my = h/2
            mx -= txt.width/2
            my += txt.height/2
            self.shadowtext(mx, my, res)

        # Draw markers(s) itself
        def draw(k):
            if not k: return
            ctx.set_source_rgba(*self.MARKERCOLOR)

            if k[0] is not None:
                ctx.move_to(k[0]+0.5, 0+0.5)
                ctx.line_to(k[0]+0.5, h+0.5)
            if k[1] is not None:
                ctx.move_to(0+0.5, k[1]+0.5)
                ctx.line_to(w+0.5, k[1]+0.5)
            ctx.stroke()
            cx, cy = self.abs2rel(*k)
            if k[0] is not None and k[1] is not None:
                res = "%d, %d" % (cx,cy)
                txt = ctx.text_extents(res)
                dx = k[0] + 3  # show coordinates of marker at this position
                dy = k[1] - 3
                # calculate nicer position, if both markers are set
                otherk = self.k1 if k == self.k2 else self.k2
                if otherk is not None and otherk[0] is not None and otherk[1] is not None:
                    if k[0] < otherk[0]: dx -= txt.width + 6
                    if k[1] > otherk[1]: dy += txt.height + 6
                self.shadowtext(dx, dy, res)
            if k[0] is None: # Horizontal, y is set
                res = "%d" % cy
                txt = ctx.text_extents(res)
                txtx = self.WIDTH - self.TICKS3 - txt.width if "west" in urnick else self.w - self.WIDTH + self.TICKS3
                self.shadowtext(txtx, k[1]+txt.height/2, res)
            if k[1] is None: # Vertical, x is set
                res = "%d" % cx
                txt = ctx.text_extents(res)
                txty = self.WIDTH - self.TICKS3 if "north" in urnick else self.h - self.WIDTH + self.TICKS3 + txt.height
                self.shadowtext(k[0]-txt.width/2, txty, res)

        draw(self.k1)
        draw(self.k2)


    def getzone(self,x,y):
        """
        return a string representing the zone (x,y) is in.
        """
        rx, ry = self.abs2rel(x,y)
        if rx > 0 and ry > 0: return "cu"           # cursor/measurement area
        if rx < 0 and ry < 0: return "mv"           # move-area
        if ry < 0 and rx > self.w - self.WIDTH - self.GRIPSIZE: return "we" # west-east-resize-grip
        if rx < 0 and ry > self.h - self.WIDTH - self.GRIPSIZE: return "ns" # north-south-resize-grip
        if rx < 0 and ry > 0: return "vr"           # vertical ruler
        if rx > 0 and ry < 0: return "hr"           # horizontal ruler
        return "xx"


    def cursormove(self, wd, ev):
        self.redraw()
        self.area.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "none"))
        w, h = self.w, self.h

        # coords according to urpsrung
        cx, cy = self.abs2rel(ev.x, ev.y)

        ctx = cairo.Context(self.surface)
        ctx.set_line_width(1)
        ctx.set_source_rgba(*self.CURSORCOLOR)

        zone = self.getzone(ev.x, ev.y)
        # cursor in measurement-area
        if zone == "cu":
            ctx.move_to(int(ev.x)+0.5, 0)
            ctx.line_to(int(ev.x)+0.5, h)
            ctx.move_to(0, int(ev.y)+0.5)
            ctx.line_to(w, int(ev.y)+0.5)
            ctx.stroke()
            self.shadowtext(ev.x+3, ev.y-3, "%d, %d" % (cx, cy))

        # cursor on horiz-ruler
        if zone == "hr":
            txt = ctx.text_extents("%d" % cx)
            ctx.move_to(int(ev.x)+0.5, 0)
            ctx.line_to(int(ev.x)+0.5, h)
            ctx.stroke()
            self.shadowtext(ev.x - txt.width/2, ev.y + txt.height/2, "%d" % cx)

        # cursor on vert-ruler
        if zone == "vr":
            txt = ctx.text_extents("%d" % cx)
            ctx.move_to(0, int(ev.y)+0.5)
            ctx.line_to(w, int(ev.y)+0.5)
            ctx.stroke()
            self.shadowtext(ev.x - txt.width/2, ev.y + txt.height/2, "%d" % cy)

        # cursor in Corner (move)
        if zone == "mv":
            self.area.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "grabbing"))
        if self.ismove:
            self.move(ev.x_root-self.ismove[0], ev.y_root-self.ismove[1])

        # manual resize in corners.
        if self.resizeH or self.resizeV:
            self.set_gravity(self.ursprung)

        # horizontal resize
        if zone == "we":
            self.area.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "ew-resize"))
        if self.resizeH:
            self.resize(self.resizeH[0][0] + (ev.x_root - self.resizeH[1]) * (1 if "west" in self.ursprung.value_nick else -1), self.resizeH[0][1])
        # vertical resize
        if zone == "ns":
            self.area.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "ns-resize"))
        if self.resizeV:
            self.resize(self.resizeV[0][0], self.resizeV[0][1] + (ev.y_root - self.resizeV[1])*(1 if "north" in self.ursprung.value_nick else -1))


    def klack(self, wd=None, ev=None):
        w, h = self.w, self.h
        if ev.button == 3:
            self.menu.popup(None, None, None, None, ev.button, ev.time)

        if ev.button == 1:
            zone = self.getzone(ev.x, ev.y)
            ck = None
            #rx, ry = self.abs2rel(ev.x, ev.y)
            rx, ry = ev.x, ev.y
            if zone == "cu": ck = (rx, ry)      # click in measurement-area
            if zone == "hr": ck = (rx, None)    # click on horiz-ruler
            if zone == "vr": ck = (None, ry)    # cursor on vert-ruler
            # set next cursor, if any
            if ck:
                if not self.k1:
                    self.k1 = ck
                else:
                    if self.k2: self.k1 = self.k2
                    self.k2 = ck
            self.redraw()

            # cursor in Corner (move)
            if zone == "mv":
                self.ismove = (ev.x, ev.y)

            # manual resize in corners.
            # horizontal resize. keep only x_root
            if zone == "we": self.resizeH = (self.get_size(), ev.x_root)
            # vertical resize. keep only y_root
            if zone == "ns": self.resizeV = (self.get_size(), ev.y_root)


    def released(self, wd=None, ev=None):
        self.ismove = False
        self.resizeH = None
        self.resizeV = None


if __name__ == "__main__":
    w = Ruler()
    Gtk.main()
