#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# ilunote - markdown outliner
#
# Copyright (C) 2013 github.com/dayf/ilunote
# Copyright (C) 2012 based on Nota 0.16 by <ralf.hersel@gmx.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# from __future__ import unicode_literals

__version__ = "2012-04-24"

from gi.repository import Gtk, Gdk # Gtk3, Gdk3
import os
import shutil
import re
import time
import codecs
import markdown
import webbrowser
import json
import traceback

PROGRAM_NAME = 'ilunote'
FOLDER = os.path.expanduser("~/") + ".local/share/ilunote"
# FOLDER = os.path.expanduser("~/") + "Dropbox" # "Ubuntu One"
FILE_DEFAULT = "ilunote.text"
JSETFP = os.path.expanduser("~/") + ".local/share/ilunote/ilunote.json"
TEMPLATE_HTML = os.path.expanduser("~/") + ".local/share/ilunote/ilunote.template.html"
VERSION = __version__
YEAR = "2013"
BLANK_NODE = '...'
FONT_DESCRIPTION = "Monospace" # Monospace, Serif, Sans, '' ..
SEPN = ' - ' # program name and breadcrumb separator
SEPB = ' > ' # breadcrumb separator
BULLET = '* '
DATEFORMAT = "%Y-%m-%d"

# http://python-gtk-3-tutorial.readthedocs.org/en/latest/textview.html
# http://python-gtk-3-tutorial.readthedocs.org/en/latest/unicode.html#python-2

# In general it is recommended to not use unicode objects in GTK+ applications at all and only use UTF-8 encoded str objects since GTK+ does not fully integrate with unicode objects.

class Gui:

    def __init__(self):
        self.persistence = Persistence()
        self.finder = Finder()
        self.undo = Undo()
        self.keyname = None # name of the key pressed in textview
        self.indent_pending = False # bullet insertion ongoing flag
        self.editable_widget = None # for interupted treeitem naming (widget)
        self.editable_path = None   # for interupted treeitem naming (path)
        self.lastiter = None # keep last iter if current text has lost iter

        # widgets
        self.window = Gtk.Window()
        self.window.set_title(PROGRAM_NAME)
        self.window.set_icon_from_file('ilunote.png')

        self.box_top = Gtk.VBox()

        self.scrolled_left = Gtk.ScrolledWindow()
        self.scrolled_left.set_shadow_type(Gtk.ShadowType.IN)

        self.treestore = Gtk.TreeStore(str, object)
        self.treeview = Gtk.TreeView(self.treestore)
        self.treeview.set_reorderable(True)
        self.treeview.set_headers_visible(False)
        self.treeview_selection = self.treeview.get_selection()

        self.renderer = Gtk.CellRendererText()
        self.column = Gtk.TreeViewColumn('Notes', self.renderer, text=0)
        self.treeview.append_column(self.column)

        self.treestore = self.persistence.load(self.treestore)

        x, y = self.persistence.setting['window_size']
        self.window.set_default_size(x, y)
        x, y = self.persistence.setting['window_position']
        self.window.move(x, y)

        self.paned = Gtk.Paned()
        self.paned.set_property('margin_left', 4)
        self.paned.set_property('margin_right', 4)
        y = self.persistence.setting['paned_position']
        self.paned.set_position(y) # position of the paned middle handle

        self.scrolled_right = Gtk.ScrolledWindow()
        self.scrolled_right.set_shadow_type(Gtk.ShadowType.IN)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_left_margin(2)
        from gi.repository import Pango
        self.textview.modify_font(Pango.FontDescription(FONT_DESCRIPTION))

        self.textbuffer = self.textview.get_buffer()
        self.textbuffer.create_tag('highlight', background='yellow')

        self.box_bottom = Gtk.HBox()
        self.box_bottom.set_property('margin_right', 3)
        self.box_bottom.set_property('margin_top', 4)
        self.box_bottom.set_property('margin_bottom', 4)

        self.image_find = Gtk.Image.new_from_stock(Gtk.STOCK_FIND, Gtk.IconSize.LARGE_TOOLBAR)
        self.image_find.set_property('xpad', 7)

        self.label_find_count = Gtk.Label()

        self.entry_find = Gtk.Entry()

        # menubar
        self.ui = '''<ui>
            <menubar name="Menubar">
                <menu action="File">
                    <menuitem action="Open"/>               
                    <menuitem action="Save"/>
                    <separator/>
                    <menuitem action="Html"/>
                    <separator/>
                    <menuitem action="Exit"/>
                </menu>
                <menu action="Tree">
                    <menuitem action="Sibling"/>
                    <menuitem action="Child"/>
                    <separator/>
                    <menuitem action="Rename"/>
                    <menuitem action="Delete"/>
                </menu>
                <menu action="Text">
                    <menuitem action="Undo"/>
                    <menuitem action="Redo"/>
                    <separator/>
                    <menuitem action="DeleteLine"/>
                    <menuitem action="Unindent"/>
                    <menuitem action="Indent"/>
                    <separator/>
                    <menuitem action="Date"/>
                    <menuitem action="Find"/>                   
                </menu>
                <menu action="Help">
                    <menuitem action="HelpMe"/>
                    <menuitem action="About"/>
                </menu>
            </menubar>
            <toolbar name="Toolbar">
                <toolitem action="New"/>
                <toolitem action="Open"/>
                <toolitem action="Save"/>
                <toolitem action="Html"/>
                <separator/>
                <toolitem action="Sibling"/>
                <!--toolitem action="Child"/-->
                <toolitem action="Delete"/>
                <!-- toolitem action="Rename"/ -->
                <separator/>
                <toolitem action="Undo"/>
                <toolitem action="Redo"/>
                <!--
                <separator/>
                <toolitem action="Unindent"/>
                <toolitem action="Indent"/>
                -->
                <separator/>
                <toolitem action="Find"/>
                <separator expand="true"/>
                <toolitem action="Settings"/>
            </toolbar>
        </ui>'''

        self.uimanager = Gtk.UIManager()
        self.accelgroup = self.uimanager.get_accel_group()
        self.window.add_accel_group(self.accelgroup)
        self.actiongroup = Gtk.ActionGroup('ilunote_ag')
        self.actiongroup.add_actions([ \
            ('File', None,'File'),
            ('New', Gtk.STOCK_NEW, 'New', None, 'New file', self.on_open_clicked),
            ('Open', Gtk.STOCK_OPEN, 'Open', '<Control>o','Open file', self.on_open_clicked),
            ('Save', Gtk.STOCK_SAVE, 'Save', '<Control>s','Save data to file', self.on_save_clicked),
            ('Html', Gtk.STOCK_PRINT_PREVIEW, 'Export as HTML ...',   None, 'Export as HTML', self.on_export_html_clicked),
            ('Exit', Gtk.STOCK_QUIT, 'Exit', None, 'Close ' + PROGRAM_NAME, self.on_exit_clicked),
            ('Settings', Gtk.STOCK_PROPERTIES, 'Settings', '<Control>p', 'Preferences', self.on_pref_clicked),
            ('Tree', None, 'Tree'),
            ('Undo', Gtk.STOCK_UNDO, 'Undo', '<Control>z','Undo last action', self.on_undo_clicked),
            ('Redo', Gtk.STOCK_REDO, 'Redo', '<Control>y','Redo last action', self.on_redo_clicked),
            ('DeleteLine', None, 'Delete Line', '<Control>k','Delete current text line', self.on_delete_line_clicked),
            ('Rename', Gtk.STOCK_EDIT, 'Rename Node', 'F2', 'Rename selected tree item', self.on_rename_clicked),
            ('Delete', Gtk.STOCK_REMOVE, 'Delete Node', None, 'Delete selected tree item', self.on_delete_clicked), #clear remove delete
            ('Find', Gtk.STOCK_FIND, 'Find', '<Control>f','Search in tree and text', self.on_find_clicked),
            ('Text', None, 'Text'),
            ('Child', Gtk.STOCK_GOTO_LAST, 'Add Child', '<Control>t','Add child to current node', self.on_insert_child_clicked),
            ('Sibling', Gtk.STOCK_ADD, 'Append Sibling', '<Control>n','Append sibling below', self.on_insert_sibling_clicked),
            ('Date', None, 'Insert Date', '<Control>d','Insert current date', self.on_insert_date_clicked),
            ('Unindent', Gtk.STOCK_UNINDENT, 'Unindent', '<Control>u','Unindent selected text', self.on_indent_clicked),
            ('Indent', Gtk.STOCK_INDENT, 'Indent', '<Control>i','Indent selected text', self.on_indent_clicked),
            ('Help', None, 'Help'),
            ('HelpMe', Gtk.STOCK_HELP, 'Help', 'F1', 'Show help', self.on_help_clicked),
            ('About', Gtk.STOCK_ABOUT, 'About', None, 'Show about', self.on_about_clicked)])

        self.uimanager.insert_action_group(self.actiongroup, 0)
        self.uimanager.add_ui_from_string(self.ui)
        self.menubar = self.uimanager.get_widget('/Menubar')
        self.toolbar = self.uimanager.get_widget('/Toolbar')

        # === Packing ===
        #~ window - GtkWindow
            #~ box_top - GtkBox
                #~ menubar
                #~ toolbar
                #~ paned - GtkPaned
                    #~ scrolled_left - GtkScrolledWindow
                        #~ treeview - GtkTreeView
                    #~ scrolled_right - GtkScrolledWindow
                        #~ textview - GtkTextView
                #~ box_bottom - GtkBox
                    #~ image_find - GtkImage
                    #~ label_find_count - GtkLabel
                    #~ entry_find - GtkEntry

        self.window.add(self.box_top)
        self.box_top.pack_start(self.menubar, expand=False, fill=True, padding=0)
        self.box_top.pack_start(self.toolbar, expand=False, fill=True, padding=0)
        self.box_top.pack_start(self.paned, expand=True, fill=True, padding=0)
        self.paned.add1(self.scrolled_left)
        self.scrolled_left.add(self.treeview)
        self.paned.add2(self.scrolled_right)
        self.scrolled_right.add(self.textview)
        self.box_top.pack_start(self.box_bottom, expand=False, fill=True, padding=0)

        self.label_status = Gtk.Label()
        self.box_bottom.pack_start(self.image_find, expand=False, fill=True, padding=0)
        self.box_bottom.pack_start(self.label_find_count, expand=False, fill=True, padding=0)
        self.box_bottom.pack_start(self.entry_find, expand=True, fill=True, padding=0)
        self.box_bottom.pack_start(self.label_status, expand=False, fill=True, padding=0)        

        # event binding
        self.window.connect('delete_event', self.on_window_delete)
        self.window.connect('key-press-event', self.on_window_key_pressed)
        self.treeview.connect('button-press-event', self.on_treeview_clicked) # Treeview item clicked
        self.treeview_selection.connect('changed', self.on_treeview_selection_changed)
        self.renderer.connect('edited', self.on_cell_edited) # Treecell edited and left with: Return or Tab or ClickInTree
        self.renderer.connect('editing-started', self.on_cell_editing_started)
        self.renderer.connect('editing-canceled', self.on_cell_editing_canceled)
        self.entry_find.connect('changed', self.on_find_changed)
        self.entry_find.connect('activate', self.on_find_return)
        self.entry_find.connect('focus-out-event', self.on_find_focus_out)
        self.textbuffer.connect('changed', self.on_textbuffer_changed)

        # show gui
        self.window.show_all()
        path = self.persistence.setting['last_path']
        self.select_last_path(path) # open tree at path from last session
        self.entry_find.grab_focus()

    def on_window_delete(self, widget, event, data=None):
        my_action = Gtk.Action('Quit', None, None, None)
        self.on_exit_clicked(my_action)


    def on_window_key_pressed(self, widget, event):
        self.keyname = Gdk.keyval_name(event.keyval) # get key name
        if self.finder.mode and self.keyname in ['Page_Down','Page_Up']:
            self.on_find_return(self.entry_find) # issue 'on_find_return' event

    def on_treeview_selection_changed(self, selection):
        model, iter = selection.get_selected()
        
        title_path = []

        if iter is not None:

            # breadcrumb
            the_iter = iter
            while True:
                title = self.treestore[the_iter][0]
                title_path.append(title)
                the_iter = self.treestore.iter_parent(the_iter)
                if the_iter is None:
                    break

            text = self.treestore.get_value(iter, 1) # encoding?
            self.textbuffer.set_text(text)
            self.undo.clear() # clear undo stack when tree item changed
            self.undo.add(self.textbuffer, self.textview, text) # put entry situation in undo stack
            self.lastiter = iter
        else:
            print 'iter is none in on_treeview_selection_changed.'
            if self.treestore.get_value(self.lastiter, 0) == None: # happens after drag'n'drop
                self.select_last_path('0') # select first tree entry..
                # .. because we lost all info where we are in the tree

        title_path.reverse()
        self.window.set_title(PROGRAM_NAME + SEPN + SEPB.join(title_path))


    def on_cell_edited(self, cell, path, new_text): # Cell in treeview edited and left
        model, iter = self.treeview_selection.get_selected()
        if iter is not None:
            self.treestore.set_value(iter, 0, new_text) #todo: update breadcrumb
            text = self.treestore.get_value(iter, 1)
            self.textbuffer.set_text(text)
        else:
            print 'Error: no iter in on_cell_edited'


    def on_cell_editing_started(self, widget, editable_widget, path): # keep info of last edited treeitem name
        self.editable_widget = editable_widget
        self.editable_path = path


    def on_cell_editing_canceled(self, widget): # change treeitem name when interrupted
        text = self.editable_widget.get_text()
        path = self.editable_path
        iter = self.treestore.get_iter_from_string(path)
        self.treestore.set_value(iter, 0, text)


    def on_treeview_clicked(self, widget, event): # click on treeview item
        if event.type == Gdk.EventType._2BUTTON_PRESS: # but only doubleclick
            model, iter = self.treeview_selection.get_selected()
            path = self.treestore.get_path(iter)
            if self.treeview.row_expanded(path):
                self.treeview.collapse_row(path)
            else:
                self.treeview.expand_to_path(path)


    def select_last_path(self, str_path): # select first row in treeview
        path = Gtk.TreePath.new_from_string(str_path)
        copy_of_path = path.copy()
        copy_of_path.up() # get parent to avoid expansion of child
        self.treeview.expand_to_path(copy_of_path) # open treeview at last position
        self.treeview.set_cursor(path, self.column, start_editing=False)


    # textbuffer
    def on_textbuffer_changed(self, textbuffer):
        model, iter = self.treeview_selection.get_selected()
        if iter is None:
            print 'Error: no iter in on_textbuffer_changed. Taking lastiter'
            iter = self.lastiter

        start = textbuffer.get_start_iter()
        end = textbuffer.get_end_iter()
        text = textbuffer.get_text(start, end, True)
        self.treestore.set_value(iter, 1, text)

        start, end = textbuffer.get_bounds()
        text = textbuffer.get_text(start, end, True)

        self.undo.add(textbuffer, self.textview, text)

        # auto indent/bullet
        bullet = BULLET
        current_iter = textbuffer.get_iter_at_mark(textbuffer.get_insert())
        line_number = current_iter.get_line()
        new_line = current_iter.starts_line() # True if CR/LF

        outdent = True # True = go to position zero

        if new_line and self.keyname not in ('BackSpace','Delete') and self.indent_pending == False:
            last_line_iter = textbuffer.get_iter_at_line(line_number - 1) # get start iter of last line
            last_line = textbuffer.get_text(last_line_iter, current_iter, True) # get last line text
            tab_count = 0
            for char in last_line:
                if char == '\t': tab_count += 1 # count leading tabs
                else: break # stop at first non-tab char
            tabs = '\t' * tab_count # create string of tabs
            textbuffer.insert_at_cursor(tabs) # insert string of tabs
            cr_stripped_last_line = last_line.lstrip('\n') # strip leading CR from last line
            tab_stripped_last_line = cr_stripped_last_line.lstrip('\t') # strip leading tabs from last line
            if tab_stripped_last_line[:2] == bullet: # does tab stripped last line starts with a bullet?
                if len(tab_stripped_last_line) > 3: # has last line text on the right side of the bullet
                    textbuffer.insert_at_cursor(bullet) # insert bullet (after leading tabs)
                else: # bullet only in last line
                    last_line_iter = textbuffer.get_iter_at_line(line_number - 1) # get start iter of last line
                    last_line_iter.backward_char() # step one char back
                    current_iter = textbuffer.get_iter_at_mark(textbuffer.get_insert()) # get iter of current position
                    textbuffer.delete(last_line_iter, current_iter) # delete last line
                    if outdent: tabs = ""
                    textbuffer.insert_at_cursor('\n' + tabs + '\n' + tabs) # insert two CRs
            elif len(tab_stripped_last_line) == 1 and outdent: # last line has only a CR
                self.indent_pending = True # prevent running into the new_line branch
                last_line_iter = textbuffer.get_iter_at_line(line_number - 1) # get start iter of last line
                current_iter = textbuffer.get_iter_at_mark(textbuffer.get_insert()) # get iter of current position
                textbuffer.delete(last_line_iter, current_iter) # delete last line
                textbuffer.insert_at_cursor('\n') # insert CR
                self.indent_pending = False # reset prevention flag to default
        elif self.keyname == 'Tab': # further indentation with Tab after '- '
            last_iter = current_iter.copy() # get current position
            current_iter.backward_chars(3) # move three steps back, before the '- \t'
            last_text = textbuffer.get_text(current_iter, last_iter, True) # MIG get the text
            if last_text == bullet + '\t': # check if tab was pressed after '- '
                self.indent_pending = True # prevent running into new_line if-branch when further indented
                textbuffer.delete(current_iter, last_iter) # delete it
                textbuffer.insert_at_cursor('\t' + bullet) # do further indentation
                self.indent_pending = False # reset prevention flag to default
        elif self.keyname == 'BackSpace' and self.indent_pending == False: # outdent with Backspace after '- '
            start_line_iter = textbuffer.get_iter_at_line(line_number) # start of current line
            text_in_line = textbuffer.get_text(start_line_iter, current_iter, True) # MIG get text of current line
            cr_stripped_line = text_in_line.lstrip('\n') # strip leading CR from line
            tab_stripped_line = cr_stripped_line.lstrip('\t') # strip leading tabs from line
            if tab_stripped_line + ' ' == bullet:
                self.indent_pending = True # prevent running into this branch
                end_iter = start_line_iter.copy() # copy of line start
                end_iter.forward_char() # one step forward
                textbuffer.delete(start_line_iter, end_iter) # delete first tab in line
                textbuffer.insert_at_cursor(' ') # add missing blank near '-'
                self.indent_pending = False


    def on_indent_clicked(self, action): # Indent or Unindent selected text
        widget = self.window.get_focus()
        if isinstance(widget, Gtk.TextView):
            try:
                current_iter, end_iter = self.textbuffer.get_selection_bounds()
            except ValueError: # nothing selected
                current_iter = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert()) # current position
                end_iter = current_iter
            line_number = current_iter.get_line() # number of first selected line
            end_line_number = end_iter.get_line() # number of last selected line
            while line_number <= end_line_number:
                start_line_iter = self.textbuffer.get_iter_at_line(line_number) # start of current line
                if action.get_name() == 'Indent':
                    self.textbuffer.insert(start_line_iter, '\t')
                else: # Unindent
                    end_iter = start_line_iter.copy() # copy of line start
                    end_iter.forward_char()
                    first_char = self.textbuffer.get_text(start_line_iter, end_iter, True)
                    if first_char == '\t':
                        self.textbuffer.delete(start_line_iter, end_iter) # delete first tab in line

                line_number += 1


    # edit
    def on_delete_clicked(self, button): # Delete item
        model, iter = self.treeview_selection.get_selected()
        if iter is not None:
            if len(model) == 1 and model.iter_depth(iter) == 0:
                self.show_message("Delete", "Cannot delete the last item")
            else:
                title, desc = self.treestore[iter]
                if self.show_yesno_dialog("Delete", 'Delete the selected node "%s"?' % title):
                    path = self.treestore.get_path(iter)
                    model.remove(iter)
                    if path.prev(): pass
                    else: path.up()
                    self.treeview.set_cursor(path, self.column, start_editing=False)
        else:
            print 'Error: no iter in on_delete_clicked'


    def on_rename_clicked(self, button): # Rename clicked (F2)
        model, iter = self.treeview_selection.get_selected()
        if iter is not None:
            path = self.treestore.get_path(iter)
            self.renderer.set_property('editable', True)
            self.treeview.set_cursor(path, self.column, start_editing=True)
            self.renderer.set_property('editable', False)
        else:
            print 'Error: no iter in on_rename_clicked'


    def on_delete_line_clicked(self, button): # Delete text line
        widget = self.window.get_focus()
        if isinstance(widget, Gtk.TextView): # only in textview
            current_iter = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert()) # current position
            line_number = current_iter.get_line()
            start_iter = self.textbuffer.get_iter_at_line(line_number) # start of line
            end_iter = self.textbuffer.get_iter_at_line(line_number+1) # end of line
            if start_iter.get_offset() == end_iter.get_offset(): # last line?
                end_iter = self.textbuffer.get_end_iter()
            self.textbuffer.delete(start_iter, end_iter)


    def on_undo_clicked(self, button): # Undo clicked
        self.undo.undo('undo')


    def on_redo_clicked(self, button): # Redo clicked
        self.undo.undo('redo')


    # help
    def on_help_clicked(self, widget): # Help clicked
        self.show_message("Help", "sorry, not yet written.")
        # todo: open ilunote.markdown file in ilunote itself

    def on_about_clicked(self, widget): # About clicked
        about_text =  "ilunote\n\n"
        about_text += "markdown outline\n\n"
        about_text += "Version %s (%s)\n" % (VERSION, YEAR)
        self.show_message("About", about_text)


    def on_pref_clicked(self, widget):
        self.show_message("Settings", "Settings are stored as JSON in the following file:\n%s" % JSETFP)

    # search
    def on_find_return(self, widget): # RETURN pressed in Find entry
        if not self.finder.mode: # start find
            find_text = self.entry_find.get_text()
            if find_text != '':
                result = self.finder.find(find_text, self.treestore)
                if not result:
                    self.finder.reset() # nothing to find
                    self.label_find_count.set_text('0/0')
                    return False
            else:
                return False # nothing to find

        self.treeview.collapse_all() # collapse tree to avoid mess
        if self.keyname in ['Page_Down', 'Return']:
            iter = self.finder.get_next(self.label_find_count) # continue find
        if self.keyname == 'Page_Up':
            iter = self.finder.get_previous(self.label_find_count)

        path = self.treestore.get_path(iter)
        self.treeview.expand_to_path(path)
        self.treeview.set_cursor(path, self.column, start_editing=False)
        self.highlight_find(self.entry_find.get_text())


    def on_find_focus_out(self, widget, event): # leaving find widget
        self.finder.reset()
        self.label_find_count.set_text('')


    def on_find_changed(self, widget): # find text changed
        self.finder.reset()
        self.label_find_count.set_text('')


    def on_find_clicked(self, widget): # Menu Find or Ctrl+F
        self.entry_find.grab_focus()


    def highlight_find(self, find_text): # highlight found string in description
        tag_table = self.textbuffer.get_tag_table()
        tag_highlight = tag_table.lookup('highlight')
        searchiter = self.textbuffer.get_iter_at_offset(0) # start in textbuffer
        while True: # repeat search
            try:
                match_start, match_end = \
                    searchiter.forward_search(find_text, \
                    Gtk.TextSearchFlags.CASE_INSENSITIVE, \
                    self.textbuffer.get_end_iter())
                start_pos = match_start.get_offset() # get found positions ..
                end_pos = match_end.get_offset() # .. and ..
                start_iter = self.textbuffer.get_iter_at_offset(start_pos) # .. make them ..
                end_iter = self.textbuffer.get_iter_at_offset(end_pos) # .. the iters for textbuffer
                self.textbuffer.apply_tag(tag_highlight, start_iter, end_iter) # highlight search term in textbuffer
                searchiter = match_end # set new search start position
            except TypeError: break # stop if all strings found


    # insert
    def on_insert_sibling_clicked(self, widget):
        model, iter = self.treeview_selection.get_selected()
        if iter is not None:
            parent = self.treestore.iter_parent(iter)
            newiter =self.treestore.append(parent, ["New", ""])
            path = self.treestore.get_path(newiter)
            self.renderer.set_property('editable', True)
            self.treeview.set_cursor(path, self.column, start_editing=True)
            self.renderer.set_property('editable', False)
        else:
            print 'Error: no iter in on_insert_sibling_clicked'


    def on_insert_child_clicked(self, widget):
        model, iter = self.treeview_selection.get_selected()
        if iter is not None:
            path = self.treestore.get_path(iter) # get path of current iter
            newiter = self.treestore.append(iter, ["New", ""]) # create the new entry
            self.treeview.expand_row(path, False) # expand this branch (one level deep)
            path = self.treestore.get_path(newiter) # path of the new entry
            self.renderer.set_property('editable', True)
            self.treeview.set_cursor(path, self.column, start_editing=True) # focus on the new entry
            self.renderer.set_property('editable', False)
        else:
            print 'Error: no iter in on_insert_child_clicked'


    def on_insert_date_clicked(self, widget): # Insert date in textbuffer or editable
        widget = self.window.get_focus() # get the widget that has the focus
        text = time.strftime(DATEFORMAT)
        if isinstance(widget, Gtk.Editable): # if Editable
            widget.delete_selection() # delete selected text before inserting
            position = widget.get_position() # get text position
            widget.insert_text(text, position) # insert the text
            widget.set_position(position + len(text)) # set position after inserted text
        elif isinstance(widget, Gtk.TextView): # if TextView
            self.textbuffer.delete_selection(True, True) # delete selected text before inserting
            self.textbuffer.insert_at_cursor(text)


    def on_open_clicked(self, widget):
        # like on_exit_clicked:
        self.persistence.save_settings()
        if self.persistence.save_needed(self.treestore):
            if self.show_yesno_dialog("Close", "Save changes to %s?" % self.persistence.setting['filename'], default_button_yes=True):
                self.persistence.save(self.treestore, backup=True)        
        homefolder = os.path.expanduser("~/")
        openfile = self.show_file_chooser("Select file ...", "file", homefolder)
        if openfile is not False:       
            self.treestore = self.persistence.load(self.treestore, openfile)
            path = self.persistence.setting['last_path'] # todo: sense?
            self.select_last_path(path)

    def on_exit_clicked(self, widget):
        self.update_settings()
        self.persistence.save_settings()
        if self.persistence.save_needed(self.treestore):
            if self.show_yesno_dialog("Quit", "Save changes?", default_button_yes=True):
                # todo: return into program with resp=None (escape key)
                self.persistence.save(self.treestore, backup=True)
        Gtk.main_quit()


    def on_save_clicked(self, widget):
        self.update_settings() # read eg last path
        self.persistence.save_settings() # write eg last path to file   
        # self.save(backup=False)
        self.persistence.save(self.treestore, backup=False)
        mypath = self._current_path()
        # instant reload to reflect text entered ## headings as nodes
        self.treestore = self.persistence.load(self.treestore) #, self.persistence.setting['filename'])
        # path = self.persistence.setting['last_path']
        # self.select_last_path(path)
        # self.select_last_path(str(path))
        self.select_last_path(str(mypath))

        # self.window.set_title(PROGRAM_NAME + ' saved')
        self.label_status.set_text(' saved. ')
        while Gtk.events_pending(): Gtk.main_iteration()
        time.sleep(1.5)
        # self.window.set_title(PROGRAM_NAME)
        self.label_status.set_text('')
        while Gtk.events_pending(): Gtk.main_iteration()

        # set breadcrumb
        # self.on_treeview_selection_changed( ...

    def _current_path(self):
        path = 0
        model, iter = self.treeview_selection.get_selected() # self.treeview.get_selection()
        if iter is not None:
            path = self.treestore.get_path(iter) # get path of current iter
        return path


    def update_settings(self):
        self.persistence.setting['window_position'] = self.window.get_position()
        self.persistence.setting['window_size'] = self.window.get_size()
        self.persistence.setting['paned_position'] = self.paned.get_position()

        path = self._current_path()

        self.persistence.setting['last_path'] = str(path)


    def on_export_html_clicked(self, widget):
        homefolder = os.path.expanduser("~/")
        exportfilename = self.show_file_chooser("Select target file", "file", homefolder)
        # print 'exportfilename', exportfilename
        if exportfilename is not False:
            exp = True
            if os.path.exists(exportfilename):
                exp = False
                if self.show_yesno_dialog("File exists", "Overwrite %s?" % exportfilename):
                    exp = True
            if exp:
                success, filename = self.persistence.store_html(self.treestore, exportfilename)
                if success:
                    if self.show_yesno_dialog("Export", "Open %s?" % filename, default_button_yes=True):
                        webbrowser.open(filename)
                else:
                    self.show_message("Export", "Export failed.")

    # dialogs
    def show_message(self, title, text):
        message = Gtk.MessageDialog(self.window, Gtk.DialogFlags.MODAL,
            Gtk.MessageType.INFO, Gtk.ButtonsType.NONE, text)
        message.add_button(Gtk.STOCK_OK, Gtk.ResponseType.CLOSE)
        message.set_title(title)
        resp = message.run()
        if resp == Gtk.ResponseType.CLOSE:
            message.destroy()


    def show_yesno_dialog(self, title, text, default_button_yes=False):
        message = Gtk.MessageDialog(self.window, Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, text)
        message.set_title(title)
        #message.set_default_response(default)
        if default_button_yes:
            message.set_default_response(Gtk.ResponseType.YES)
        resp = message.run()
        # print resp # delete_event = Esc = -4, No = -9, Yes = -8
        message.destroy()
        if resp == Gtk.ResponseType.YES:
            return True
        if resp == Gtk.ResponseType.NO:
            return False
        #if resp == Gtk.ResponseType.DELETE_EVENT: #Escape
        return None


    def show_file_chooser(self, text, action, folder=None):
        if action == "file":
            dialog = Gtk.FileChooserDialog(text, None, Gtk.FileChooserAction.OPEN,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        if action == "folder":
            dialog = Gtk.FileChooserDialog(text, None, Gtk.FileChooserAction.SELECT_FOLDER,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        dialog.set_default_response(Gtk.ResponseType.OK) # set default button to OK
        if folder is not None:
            dialog.set_current_folder(folder) # preset folder
        response = dialog.run() # show file dialog
        if response == Gtk.ResponseType.OK:
            selection = dialog.get_filename(), 'selected' # get selected file
            pathfilename = selection[0] # get path and filename
        else:
            pathfilename = False
        dialog.destroy()
        return pathfilename




class Persistence(object):
    def __init__(self):
        # self.filename = FOLDER + "/" + FILE_DEFAULT
        # self.treestore = treestore
        # self.setting = self.load_settings()
        self.setting = {}
        self.load_settings()
        #self.filename = self.setting['filename']

    def save_needed(self, treestore):
        self.treestore = treestore
        markd = self.as_markdown()
        # load file again to compare
        try:
            # print 'comparing memory markd to', self.setting['filename']
            with codecs.open(self.setting['filename'], 'r', encoding='utf-8') as fh:
                markd_disk = fh.read()
                markd_disk = markd_disk.encode('utf-8')
                # print type(markd), type(markd_disk)
                if markd == markd_disk: # UnicodeWarning
                    return False
                else:
                    # print markd
                    return True
        except IOError:
            # file doesnt exist yet
            return True

    def save(self, treestore, backup=True):
        self.treestore = treestore

        markd = self.as_markdown()

        if backup:
            # print 'creating .backup(.backup)'
            try:
                shutil.copy2(self.setting['filename'] + '.backup', self.setting['filename'] + '.backup' + '.backup')
            except:
                pass
            try:
                shutil.copy2(self.setting['filename'], self.setting['filename'] + '.backup')
            except:
                print 'error copying to .backup'
                self.show_message('Warning', 'Could not create backup(s).')

        with codecs.open(self.setting['filename'], "w", encoding="utf-8") as fh:
            # fh.write(markd)
            fh.write(markd.decode('utf-8'))

    def save_settings(self):
        #conf = {'filename': self.filename}
        
        conf = {}
        for k in ['window_position', 'window_size', 'paned_position', 'last_path', 'filename']:
            conf[k] = self.setting[k] # get(k, None)
        for k in ['last_path']:
            conf[k] = str(self.setting[k])

        if not os.path.exists(FOLDER):
            os.popen("mkdir -p " + FOLDER)      

        with codecs.open(JSETFP, 'w', 'utf-8') as fh:
            json.dump(conf, fh)

    def load_settings(self):
        try:
            with open(JSETFP, 'r') as fh:
                conf = json.load(fh)
                for k in conf:
                    self.setting[k] = conf[k]
        except IOError: # first run, file doesn't exist
            self.setting['window_position'] = 100, 50
            self.setting['window_size'] = 700, 500
            self.setting['paned_position'] = 200
            self.setting['last_path'] = '0'
            self.setting['filename'] = FOLDER + "/" + FILE_DEFAULT

            self.save_settings()
        #     print 'stored default setting to %s: %s' % (JSETFP, self.setting)
        # else:
        #     print 'loaded setting from %s: %s' % (JSETFP, self.setting)

    def load(self, treestore, filename = None):
        # todo: display headings in desc?

        if not filename:
            filename = self.setting['filename'] # has default if new
        # print 'trying to open filename',filename
        treestore.clear()

        parent = None
        heading_path = {} #= {0:None}
        sections = []
        # title = None # "<%s>" % os.path.basename(self.filename)
        title = BLANK_NODE
        level = 1 # 0
        desc = ''
        line = None
        line_previous = ''

        try:

            with codecs.open(filename, 'r', encoding='utf-8') as fh:
                # use different approach than by line?
                for line_read in fh.readlines(): # has '\n' at the end
                    line_read = line_read.encode('utf-8')
                    line = line_read.rstrip("\n")
                    inhead = False
                    section = None
                    # check for ### hash symbole style headings
                    m = re.match(r'^(?P<hdr>#+) (?P<title>.*)#*$', line)
                    if m and line_previous == "": # require empty line above # heading
                        inhead = True
                        # store old values into section
                        section = {'desc':desc, 'title':title, 'level':level}
                        # new values:
                        level = len(m.group('hdr')) # len('####')
                        title = m.group('title')
                        desc = ''
                    
                    # the following re.search's for importing other markdown style headings only
                    # could use pandoc to convert html and others to markdown

                    # check for html head element headings like <h2 a=''>..</h2>
                    m = re.search(r'<h(?P<hlev>\d).*?>(?P<title>.*)</h.>', line)
                    if m:
                        inhead = True
                        # store old values into section
                        section = {'desc':desc, 'title':title, 'level':level}
                        # new values:
                        level = int(m.group('hlev')) # html h1..h9
                        title = m.group('title')
                        desc = ''

                    # check for ==== ---- style headings
                    m = re.search(r'^={3,}', line)
                    if m:
                        #print line, desc.split('\n')[-2]
                        inhead = True
                        # store old values into section
                        descr = "\n".join(desc.split("\n")[:-2]) # remove found title still in desc above
                        section = {'desc':descr, 'title':title, 'level':level}
                        # new values:
                        title = desc.split('\n')[-2]
                        level = 1
                        desc = ''
                    m = re.search(r'^-{3,}', line)
                    if m:
                        inhead = True
                        # store old values into section
                        descr = "\n".join(desc.split("\n")[:-2])
                        section = {'desc':descr, 'title':title, 'level':level}
                        # new values:
                        title = desc.split('\n')[-2]
                        level = 2
                        desc = ''

                    if not inhead:
                        desc += line + '\n'
                    else:
                        # add title into desc fix
                        # section['desc'] = '%s %s\n\n' % (section['level'] * '#', section['title'])
                        sections.append(section)

                    line_previous = line

                if len(desc) > 0:
                    # last section text
                    # desc = desc.strip()
                    # desc = '%s %s\n\n' % (level * '#', title) # title in desc?
                    section = {'desc': desc, 'title': title, 'level': level}
                    sections.append(section)
        
        except IOError, e:
            print 'open error', e
            sections.append({'desc': '\nWelcome to ilunote.', 'title': 'Welcome', 'level': 1})
        else:
            # loading succeeded
            self.setting['filename'] = filename
            self.save_settings()

        for section in sections:
            title = section['title']
            desc = section['desc']
            level = section['level']
            heading_path[level] = parent
            try:
                parent = heading_path[level - 1]
            except KeyError:
                parent = None
            heading = treestore.append(parent, [title, desc])
            heading_path[level] = heading

        return treestore

    def as_markdown(self):
        self.content = ''
        rootiter = self.treestore.get_iter_first()
        self.as_markdown_level(self.treestore, rootiter, 1)

        return self.content

    def as_markdown_level(self, treestore, treeiter, level):
        '''recurse tree; append to content; blank line before titles'''
        while treeiter != None:

            title, desc = treestore[treeiter]

            # todo: make headline style configurable
            # todo: displayed headings in desc?
            if title <> BLANK_NODE: # or not None
                self.content += "\n" + level * '#' + ' ' + title + "\n"
                # self.content += level * '#' + ' ' + title + "\n\n"
  
            if len(desc.rstrip("\n")) > 0:
                self.content += desc.rstrip("\n") + "\n"

            if treestore.iter_has_child(treeiter):
                childiter = treestore.iter_children(treeiter)
                self.as_markdown_level(treestore, childiter, level + 1)
            treeiter = treestore.iter_next(treeiter)

    def as_html(self):
        text = self.as_markdown()
        # Note: Markdown only accepts unicode input!
        return markdown.markdown(text.decode('utf-8')).encode('utf-8')

    def store_html(self, treestore, filename):
        # print 'store html', filename
        '''export to html file'''
        template = '<?xml version="1.0" encoding="UTF-8"?><html><body /></html>'
        try:
            with codecs.open(TEMPLATE_HTML, 'r', 'utf-8') as fh:
                template = fh.read()
                template = template.encode('utf-8')
        except Exception, e:
            print 'error', e

        try:
            self.treestore = treestore
            html = template.replace('<body />', '<body>%s</body>' % self.as_html())
            with codecs.open(filename, 'w', 'utf-8') as fh:
                # fh.write(html)
                fh.write(html.decode('utf-8'))
            #return True, filename
        except Exception, e:
            print 'error', e
            return False, None
        return True, filename




class Finder(list): # search in tree and texts

    def __init__(self):
        self.find_text = ''
        self.max = 0
        self.index = 0
        self.mode = False


    def find(self, find_text, treestore): # search treestore
        self.mode = True
        self.find_text = find_text.lower()
        rootiter = treestore.get_iter_first()
        self.recurse_find(treestore, rootiter)
        self.max = len(self) # number of found items
        if self: return True # something found
        else: return False # nothing found


    def recurse_find(self, treestore, iter): # recurse over treestore
        while iter != None:
            name, desc = treestore[iter]

            name_lower = name.lower()
            desc_lower = desc.lower()

            if self.find_text in name_lower or self.find_text in desc_lower:
                self.append(iter)

            if treestore.iter_has_child(iter):
                childiter = treestore.iter_children(iter)
                self.recurse_find(treestore, childiter)
            iter = treestore.iter_next(iter)


    def get_next(self, find_count): # get next search result
        if self.index == self.max:
            self.index = 0 # start from beginning
        result = self[self.index]
        self.index += 1 # next one
        count = ("%i/%i" % (self.index, self.max))
        find_count.set_text(count)
        return result


    def get_previous(self, find_count): # get previous search result
        if self.index == 1:
            self.index = self.max + 1 # start from end
        self.index -= 1 # previous one
        result = self[self.index-1]
        count = ("%i/%i" % (self.index, self.max))
        find_count.set_text(count)
        return result


    def reset(self): # clear Finder
        del self[:] # delete list content only
        self.find_text = ''
        self.max = 0
        self.index = 0
        self.mode = False


class Undo:

    def __init__(self):
        self.stack = [] # list of undoables
        self.textbuffer = None
        self.textview = None
        self.freeze = False # prevent unwanted undo.add when undo.back called
        self.pointer = 0 # stack position


    def add(self, textbuffer, textview, content): # add undo content
        if not self.freeze:
            self.textbuffer = textbuffer
            self.textview = textview
            iter = textbuffer.get_iter_at_mark(textbuffer.get_insert()) # current position
            if iter != None:
                position = iter.get_offset() # get current position of iter as int
                self.stack.append([content, position])
                self.pointer = len(self.stack) - 1 # last element in stack


    def undo(self, mode): # mode = 'undo' or 'redo'
        self.freeze = True
        if mode == 'undo':
            if self.pointer > 0: self.pointer -= 1
        else:     # redo
            if self.pointer < len(self.stack) - 1: self.pointer += 1

        content = self.stack[self.pointer][0] # get the text
        position = self.stack[self.pointer][1] # get the cursor position
        self.textbuffer.set_text(content) # set the text
        iter = self.textbuffer.get_iter_at_offset(position) # get iter from cursor position
        if iter != None:
            self.textbuffer.place_cursor(iter) # set the cursor
            mark = self.textbuffer.get_mark('insert') # get mark at cursor
            self.textview.scroll_to_mark(mark, 0, False, 0, 0) # scroll to cursor
            self.freeze = False


    def clear(self): # reset undo stack
        self.stack = []




def main():
    gui = Gui()
    Gtk.main()
    return 0

if __name__ == '__main__':
    main()
