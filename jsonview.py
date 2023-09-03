#!/bin/env python3

# e.g.
# youtube-dl -j "..." | gtkjsonview.py

import sys, re
import gi
try:    import json
except: import simplejson as json
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Pango

raw_data = ''

if len(sys.argv) == 2:
    try:
        raw_data = open(sys.argv[1]).read().strip()
    except Exception as e:
        raw_data = json.dumps(str(e))
        
    
elif not sys.stdin.isatty():
    raw_data = sys.stdin.read().strip()
else:
    raw_data = json.dumps("Pipe me some input or give a filename as parameter...")

if raw_data and raw_data[0] == '(' and raw_data[-1] == ')': raw_data = raw_data[1:-1]

is_dark = Gtk.Settings.get_default().get_property("gtk-application-prefer-dark-theme")
if is_dark:
    color_key = 'light green'
    color_type = {
        dict      : 'yellow',
        list      : 'yellow',
        str       : 'pink',
        int       : 'red',
        float     : 'red',
        bool      : 'lime',
        type(None): 'gray'
    }
else:
    color_key = 'dark green'
    color_type = {
        dict      : 'blue',
        list      : 'magenta',
        str       : 'purple',
        int       : 'red',
        float     : 'red',
        bool      : 'green',
        type(None): 'gray'
    }

def add_item(key, data, model, parent=None):
    
    keystr = '<span foreground="'+color_key+'">'+str(key)+'</span><b>:</b> '
    objstr = '<span foreground="'+color_type[type(data)]+'">%s</span>'
    
    if isinstance(data, dict):
        if len(str(key)):
            obj = model.append(parent, [keystr + objstr % ('{'+str(len(data))+'}')])
            walk_tree(data, model, obj)
        else:
            walk_tree(data, model, parent)
    elif isinstance(data, list):
        arr = model.append(parent, [keystr + objstr % ('['+str(len(data))+']')])
        for index in range(len(data)):
            add_item(index, data[index], model, arr)
    else:
        model.append(parent, [keystr + objstr % str(data).replace('&','&amp;').replace('>','&gt;').replace('<','&lt;')])

def walk_tree(data, model, parent = None):
    if isinstance(data, list):
        add_item('', data, model, parent)
    elif isinstance(data, dict):
        for key in sorted(data):
            add_item(key, data[key], model, parent)
    else:
        add_item('', data, model, parent)


class JSONViewerWindow(Gtk.Window):
    # Key/property names which match this regex syntax may appear in a
    # JSON path in their original unquoted form in dotted notation.
    # Otherwise they must use the quoted-bracked notation.
    jsonpath_unquoted_property_regex = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

    def __init__(self):
        Gtk.Window.__init__(self, title="JSON Viewer")
        self.set_default_size(700, 900)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.label = Gtk.TextView()
        self.label.buffer = self.label.get_buffer()
        self.label.set_editable(False)
        self.label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.label.set_size_request(700,0)
        self.label.set_monospace(True)
        
        self.model = Gtk.TreeStore(str)
        self.tree = Gtk.TreeView(model=self.model)
        self.tree.get_selection().connect("changed", self.on_selection_changed)
        self.tree.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(), markup=0))
        self.tree.set_headers_visible(False)
        self.tree.set_enable_tree_lines(True)

        self.data = None
        try:
            self.data = json.loads(raw_data)
        except Exception as e:
            tagred = self.label.buffer.create_tag("bold", foreground="red")
            self.label.buffer.set_text(str(e))
            self.label.buffer.apply_tag(tagred, self.label.buffer.get_start_iter(), self.label.buffer.get_end_iter())
            self.tree = Gtk.TextView()
            self.tree.buffer = self.tree.get_buffer()
            self.tree.set_editable(False)
            self.tree.set_monospace(True)
            self.tree.buffer.set_text(raw_data)
        
        if self.data: 
            walk_tree(self.data, self.model)
            fi = self.model.get_iter_first()
            while fi:
                if(self.to_jq(fi).startswith(".url = ")):
                    path = self.model.get_path(fi)
                    self.tree.set_cursor(path, None, False)
                    self.tree.scroll_to_cell(path, None)
                    break
                fi = self.model.iter_next(fi)

        box = Gtk.Paned.new(Gtk.Orientation.VERTICAL)
        box.set_wide_handle(True)
        box.pack1(Gtk.ScrolledWindow(child=self.label), False, False)
        box.pack2(Gtk.ScrolledWindow(child=self.tree), True, False)
        self.add(box)
        box.get_child1().set_size_request(700,54)
        self.tree.grab_focus()

    #return the json query given a path
    def to_jq(self, xiter):
        path = self.model.get_path(xiter)
        indices = path.get_indices()
        jq = ''
        is_array_index = False
        data = self.data
        
        #the expression must begins with identity `.`
        #if the first element is not a dict, add a dot
        if not isinstance(data, dict): jq += '.'
      
        for index in indices:
            if isinstance(data, dict):
                key = (list(sorted(data))[index])
                if len(key)==0 or not self.jsonpath_unquoted_property_regex.match(key):
                    jq += '[\'{}\']'.format(key) # bracket notation (no initial dot)
                else:
                    jq += '.' + key # dotted notation
                data = data[key]
                if isinstance(data, list):
                    jq += '[]'
                    is_array_index = True
            elif isinstance(data, list):
                if is_array_index:
                    selected_index = index
                    jq = jq[:-2]   #remove []
                    jq += '[{}]'.format(selected_index)
                    data = data[selected_index]
                    is_array_index = False
                else:
                    jq += '[]'
                    is_array_index = True
      
        if isinstance(data, str): 
            data = '"'+data.replace('"','\\"')+'"'
        return jq + ' = ' + str(data)

    def on_selection_changed(self, tree_selection) :
        iter_current = tree_selection.get_selected()[1]
        jq = self.to_jq(iter_current) if iter_current else ''
        self.label.buffer.set_text(jq)
  
win = JSONViewerWindow()
win.connect("delete-event", Gtk.main_quit)
win.show_all()
Gtk.main()


#TODO:
# - "url" wählen, wenn vorhanden
# - wertanzeige oben
