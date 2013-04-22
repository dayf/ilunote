#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#	nota.py - A simple outliner from the shores of lake Zurich
#	Copyright 2012 Ralf Hersel <ralf.hersel@gmx.net>
#	Date: March 2012
#
#	This program is free software; you can redistribute it and/or modify
#	it under the terms of the GNU General Public License version 3 as
#	published by the Free Software Foundation.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program; if not, write to the Free Software
#	Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#	MA 02110-1301, USA.


from gi.repository import Gtk, Gdk										# Gtk3, Gdk3
import xml.etree.ElementTree as et										# XML handling
import os																# file system functions
import re																# regular expressions
import time																# insert date
import codecs															# write utf8 stream to file
import webbrowser														# open default webbrowser


# === Constants ========================================================

PROGRAM_NAME = 'Nota'
FOLDER = os.path.expanduser("~/") + ".local/share/nota"
VERSION = "0.16"


# === GUI ==============================================================

class Gui:

	def __init__(self):
		self.persistence = Persistence()								# Load/Save class
		self.impex = Impex()											# Import/Export class
		self.finder = Finder()											# Search class
		self.undo = Undo()												# Undo class
		self.setting = {}												# Configuration settings
		self.keyname = None												# name of the key pressed in textview
		self.indent_pending = False										# bullet insertion ongoing flag
		self.editable_widget = None										# for interupted treeitem naming (widget)
		self.editable_path = None										# for interupted treeitem naming (path)
		self.lastiter = None											# keep last iter if current text has lost iter

		# === Widgets ==================================================

		self.window = Gtk.Window()
		self.window.set_title(PROGRAM_NAME)
		self.window.set_icon_from_file('nota.png')

		self.box_top = Gtk.VBox()

		self.scrolled_left = Gtk.ScrolledWindow()
		self.scrolled_left.set_shadow_type(Gtk.ShadowType.IN)

		self.treestore = Gtk.TreeStore(str, object)
		self.treeview = Gtk.TreeView(self.treestore)
		self.treeview.set_reorderable(True)								# enable Drag'n'Drop
		self.treeview.set_headers_visible(False)
		self.treeview_selection = self.treeview.get_selection()

		self.renderer = Gtk.CellRendererText()
		self.column = Gtk.TreeViewColumn('Notes', self.renderer, text=0)
		self.treeview.append_column(self.column)

		self.treestore, self.setting = \
			self.persistence.load(self.treestore, self.setting, False)	# load nota.xml (not backup)

		x, y = self.setting['window_size']
		self.window.set_default_size(x, y)
		x, y = self.setting['window_position']
		self.window.move(x, y)

		self.paned = Gtk.Paned()
		self.paned.set_property('margin_left', 4)
		self.paned.set_property('margin_right', 4)
		y = self.setting['paned_position']
		self.paned.set_position(y)										# position of the paned middle handle

		self.scrolled_right = Gtk.ScrolledWindow()
		self.scrolled_right.set_shadow_type(Gtk.ShadowType.IN)

		self.textview = Gtk.TextView()
		self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
		self.textview.set_left_margin(2)

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


		# Menubar ======================================================

		self.ui = '''<ui>
			<menubar name="Menubar">
				<menu action="File">
					<menuitem action="Save"/>
					<menuitem action="Reload"/>
					<menuitem action="Restore"/>
					<separator/>
					<menuitem action="Gnote"/>
					<menuitem action="Tomboy"/>
					<menuitem action="Unitree"/>
					<separator/>
					<menuitem action="Html"/>
					<separator/>
					<menuitem action="Exit"/>
				</menu>
				<menu action="Edit">
					<menuitem action="Undo"/>
					<menuitem action="Redo"/>
					<menuitem action="DeleteLine"/>
					<separator/>
					<menuitem action="Rename"/>
					<menuitem action="Delete"/>
					<menuitem action="Find"/>
				</menu>
				<menu action="Insert">
					<menuitem action="Sibling"/>
					<menuitem action="Child"/>
					<separator/>
					<menuitem action="Date"/>
					<menuitem action="Unindent"/>
					<menuitem action="Indent"/>
				</menu>
				<menu action="Help">
					<menuitem action="HelpMe"/>
					<menuitem action="About"/>
				</menu>
			</menubar>
			<toolbar name="Toolbar">
				<toolitem action="Sibling"/>
				<toolitem action="Child"/>
				<separator/>
				<toolitem action="Rename"/>
				<toolitem action="Delete"/>
				<separator/>
				<toolitem action="Undo"/>
				<toolitem action="Redo"/>
				<separator/>
				<toolitem action="Unindent"/>
				<toolitem action="Indent"/>
				<separator/>
				<toolitem action="Find"/>
				<separator expand="true"/>
				<toolitem action="Exit"/>
			</toolbar>
		</ui>'''

		self.uimanager = Gtk.UIManager()								# GUI Manager
		self.accelgroup = self.uimanager.get_accel_group()		  		# Accelerator for Menu Shortcuts
		self.window.add_accel_group(self.accelgroup)					# add Accelerator to Window
		self.actiongroup = Gtk.ActionGroup('nota_ag')		  			# ActionGroup for Menu and Toolbar
		self.actiongroup.add_actions([ \
			('File',		None,						'File'),
			('Save',		Gtk.STOCK_SAVE,				'Save',			'<Control>s','Save data to file', self.on_save_clicked),
			('Reload',		Gtk.STOCK_REFRESH,			'Reload',		None,		'Reload from last save', self.on_reload_clicked),
			('Restore',		Gtk.STOCK_REVERT_TO_SAVED,	'Restore',		None,		'Restore from last session', self.on_restore_clicked),
			('Tomboy',		None,						'Import Tomboy',None,		'Import from Tomboy', self.on_import_tomboy_clicked),
			('Gnote',		None,						'Import Gnote', None,		'Import from Gnote', self.on_import_gnote_clicked),
			('Unitree',		None,						'Import Unitree', None,		'Import from Unitree', self.on_import_unitree_clicked),
			('Html',		None,						'Export Html',	None,		'Export to Html', self.on_export_html_clicked),
			('Exit',		Gtk.STOCK_QUIT,				'Exit', 		None,		'Close Nota', self.on_exit_clicked),
			('Edit',		None,						'Edit'),
			('Undo',		Gtk.STOCK_UNDO,				'Undo',			'<Control>z','Undo last action', self.on_undo_clicked),
			('Redo',		Gtk.STOCK_REDO,				'Redo',			'<Control>y','Redo last action', self.on_redo_clicked),
			('DeleteLine',	None,						'Delete Line',	'<Control>k','Delete current text line', self.on_delete_line_clicked),
			('Rename',		Gtk.STOCK_EDIT,				'Rename',		'F2',		'Rename selected tree item', self.on_rename_clicked),
			('Delete',		Gtk.STOCK_DELETE,			'Delete Item',	None,		'Delete selected tree item', self.on_delete_clicked),
			('Find',		Gtk.STOCK_FIND,				'Find',			'<Control>f','Search in tree and text', self.on_find_clicked),
			('Insert',		None,						'Insert'),
			('Sibling',		Gtk.STOCK_GOTO_BOTTOM,		'Sibling',		'<Control>n','Insert sibling', self.on_insert_sibling_clicked),
			('Child',		Gtk.STOCK_GOTO_LAST,		'Child',		'<Control>m','Insert child', self.on_insert_child_clicked),
			('Date',		None,						'Date',			'<Control>d','Insert current date', self.on_insert_date_clicked),
			('Unindent',	Gtk.STOCK_UNINDENT,			'Unindent',		'<Control>u','Unindent selected text', self.on_indent_clicked),
			('Indent',		Gtk.STOCK_INDENT,			'Indent',		'<Control>i','Indent selected text', self.on_indent_clicked),
			('Help',		None,						'Help'),
			('HelpMe',		Gtk.STOCK_HELP,				'Help',			'F1',		'Show help', self.on_help_clicked),
			('About',		Gtk.STOCK_ABOUT,			'About',		None,		'Show about', self.on_about_clicked)])

		self.uimanager.insert_action_group(self.actiongroup, 0)
		self.uimanager.add_ui_from_string(self.ui)
		self.menubar = self.uimanager.get_widget('/Menubar')
		self.toolbar = self.uimanager.get_widget('/Toolbar')

		# === Packing ==================================================
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
		self.box_bottom.pack_start(self.image_find, expand=False, fill=True, padding=0)
		self.box_bottom.pack_start(self.label_find_count, expand=False, fill=True, padding=0)
		self.box_bottom.pack_start(self.entry_find, expand=True, fill=True, padding=0)

		# === Event binding ============================================
		self.window.connect('delete_event', self.on_window_delete)		# Window red-cross clicked
		self.window.connect('key-press-event', self.on_window_key_pressed)
		self.treeview.connect('button-press-event', self.on_treeview_clicked)	# Treeview item clicked
		self.treeview_selection.connect('changed', self.on_treeview_selection_changed)
		self.renderer.connect('edited', self.on_cell_edited)			# Treecell edited and left with: Return or Tab or ClickInTree
		self.renderer.connect('editing-started', self.on_cell_editing_started)
		self.renderer.connect('editing-canceled', self.on_cell_editing_canceled)
		self.entry_find.connect('changed', self.on_find_changed)
		self.entry_find.connect('activate', self.on_find_return)
		self.entry_find.connect('focus-out-event', self.on_find_focus_out)
		self.textbuffer.connect('changed', self.on_textbuffer_changed)

		# === Show GUI =================================================
		self.window.show_all()
		path = self.setting['last_path']
		self.select_last_path(path)										# open tree at path from last session
		self.entry_find.grab_focus()

		self.save(True)													# save backup file

	# === Window =======================================================

	def on_window_delete(self, widget, event, data=None):				# close the window by red cross
		my_action = Gtk.Action('Quit', None, None, None)
		self.on_exit_clicked(my_action)									# issue exit event


	def on_window_key_pressed(self, widget, event):						# Key pressed
		self.keyname = Gdk.keyval_name(event.keyval)					# get key name
		#~ print self.keyname												# debug
		if self.finder.mode and self.keyname in ['Page_Down','Page_Up']:
			self.on_find_return(self.entry_find)						# issue 'on_find_return' event


	# === Treeview =====================================================

	def on_treeview_selection_changed(self, selection):					# treeview selection changed
		model, iter = selection.get_selected()
		if iter != None:
			text = self.treestore.get_value(iter, 1)
			self.textbuffer.set_text(text)
			self.undo.clear()											# clear undo stack when tree item changed
			self.undo.add(self.textbuffer, self.textview, text)			# put entry situation in undo stack
			self.lastiter = iter
		else:
			print 'Error: iter is none in on_treeview_selection_changed.'	# debug
			if self.treestore.get_value(self.lastiter, 0) == None:		# happens after drag'n'drop
				self.select_last_path('0')								# select first tree entry..
				# .. because we lost all info where we are in the tree


	def on_cell_edited(self, cell, path, new_text):						# Cell in treeview edited and left
		model, iter = self.treeview_selection.get_selected()
		if iter is not None:
			self.treestore.set_value(iter, 0, new_text)
			text = self.treestore.get_value(iter, 1)
			self.textbuffer.set_text(text)
		else:
			print 'Error: no iter in on_cell_edited'


	def on_cell_editing_started(self, widget, editable_widget, path):	# keep info of last edited treeitem name
		self.editable_widget = editable_widget
		self.editable_path = path


	def on_cell_editing_canceled(self, widget):							# change treeitem name when interrupted
		text = self.editable_widget.get_text()
		path = self.editable_path
		iter = self.treestore.get_iter_from_string(path)
		self.treestore.set_value(iter, 0, text)


	def on_treeview_clicked(self, widget, event):						# click on treeview item
		if event.type == Gdk.EventType._2BUTTON_PRESS:					# but only doubleclick
			model, iter = self.treeview_selection.get_selected()
			path = self.treestore.get_path(iter)
			if self.treeview.row_expanded(path):
				self.treeview.collapse_row(path)
			else:
				self.treeview.expand_to_path(path)


	def select_last_path(self, str_path):								# select first row in treeview
		path = Gtk.TreePath.new_from_string(str_path)
		copy_of_path = path.copy()
		copy_of_path.up()												# get parent to avoid expansion of child
		self.treeview.expand_to_path(copy_of_path)						# open treeview at last position
		self.treeview.set_cursor(path, self.column, start_editing=False)


	# === Textbuffer ===================================================

	def on_textbuffer_changed(self, textbuffer):						# textbuffer changed
		model, iter = self.treeview_selection.get_selected()
		if iter is None:
			print 'Error: no iter in on_textbuffer_changed. Taking lastiter'
			iter = self.lastiter

		start = textbuffer.get_start_iter()
		end = textbuffer.get_end_iter()
		text = textbuffer.get_text(start, end, True)
		self.treestore.set_value(iter, 1, text)

		start, end = textbuffer.get_bounds()							# get start and end of the text
		text = textbuffer.get_text(start, end, True)

		self.undo.add(textbuffer, self.textview, text)					# undo

		# === Auto Indent and Auto Bullet ===
		bullet = '- '
		current_iter = textbuffer.get_iter_at_mark(textbuffer.get_insert())
		line_number = current_iter.get_line()
		new_line = current_iter.starts_line()							# True if CR/LF

		outdent = True													# True = go to position zero

		if new_line and self.keyname not in ('BackSpace','Delete') and self.indent_pending == False:
			last_line_iter = textbuffer.get_iter_at_line(line_number - 1)	# get start iter of last line
			last_line = textbuffer.get_text(last_line_iter, current_iter, True)	# get last line text
			tab_count = 0
			for char in last_line:
				if char == '\t': tab_count += 1							# count leading tabs
				else: break												# stop at first non-tab char
			tabs = '\t' * tab_count										# create string of tabs
			textbuffer.insert_at_cursor(tabs)							# insert string of tabs
			cr_stripped_last_line = last_line.lstrip('\n')				# strip leading CR from last line
			tab_stripped_last_line = cr_stripped_last_line.lstrip('\t')	# strip leading tabs from last line
			if tab_stripped_last_line[:2] == bullet:					# does tab stripped last line starts with a bullet?
				if len(tab_stripped_last_line) > 3:						# has last line text on the right side of the bullet
					textbuffer.insert_at_cursor(bullet)					# insert bullet (after leading tabs)
				else:													# bullet only in last line
					last_line_iter = textbuffer.get_iter_at_line(line_number - 1)	# get start iter of last line
					last_line_iter.backward_char()						# step one char back
					current_iter = textbuffer.get_iter_at_mark(textbuffer.get_insert()) # get iter of current position
					textbuffer.delete(last_line_iter, current_iter)		# delete last line
					if outdent: tabs = ""
					textbuffer.insert_at_cursor('\n' + tabs + '\n' + tabs)	# insert two CRs
			elif len(tab_stripped_last_line) == 1 and outdent:			# last line has only a CR
				self.indent_pending = True								# prevent running into the new_line branch
				last_line_iter = textbuffer.get_iter_at_line(line_number - 1)		# get start iter of last line
				current_iter = textbuffer.get_iter_at_mark(textbuffer.get_insert()) # get iter of current position
				textbuffer.delete(last_line_iter, current_iter)			# delete last line
				textbuffer.insert_at_cursor('\n')						# insert CR
				self.indent_pending = False								# reset prevention flag to default
		elif self.keyname == 'Tab':										# further indentation with Tab after '- '
			last_iter = current_iter.copy()								# get current position
			current_iter.backward_chars(3)								# move three steps back, before the '- \t'
			last_text = textbuffer.get_text(current_iter, last_iter, True)	# MIG get the text
			if last_text == bullet + '\t':								# check if tab was pressed after '- '
				self.indent_pending = True								# prevent running into new_line if-branch when further indented
				textbuffer.delete(current_iter, last_iter)				# delete it
				textbuffer.insert_at_cursor('\t' + bullet)				# do further indentation
				self.indent_pending = False								# reset prevention flag to default
		elif self.keyname == 'BackSpace' and self.indent_pending == False:	# outdent with Backspace after '- '
			start_line_iter = textbuffer.get_iter_at_line(line_number)	# start of current line
			text_in_line = textbuffer.get_text(start_line_iter, current_iter, True)	# MIG get text of current line
			cr_stripped_line = text_in_line.lstrip('\n')				# strip leading CR from line
			tab_stripped_line = cr_stripped_line.lstrip('\t')			# strip leading tabs from line
			if tab_stripped_line + ' ' == bullet:
				self.indent_pending = True								# prevent running into this branch
				end_iter = start_line_iter.copy()						# copy of line start
				end_iter.forward_char()									# one step forward
				textbuffer.delete(start_line_iter, end_iter)			# delete first tab in line
				textbuffer.insert_at_cursor(' ')						# add missing blank near '-'
				self.indent_pending = False


	def on_indent_clicked(self, action):								# Indent or Unindent selected text
		widget = self.window.get_focus()
		if isinstance(widget, Gtk.TextView):
			try:
				current_iter, end_iter = self.textbuffer.get_selection_bounds()
			except ValueError:											# nothing selected
				current_iter = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert()) # current position
				end_iter = current_iter
			line_number = current_iter.get_line()						# number of first selected line
			end_line_number = end_iter.get_line()						# number of last selected line
			while line_number <= end_line_number:
				start_line_iter = self.textbuffer.get_iter_at_line(line_number)	# start of current line
				if action.get_name() == 'Indent':
					self.textbuffer.insert(start_line_iter, '\t')
				else:													# Unindent
					end_iter = start_line_iter.copy()					# copy of line start
					end_iter.forward_char()
					first_char = self.textbuffer.get_text(start_line_iter, end_iter, True)
					if first_char == '\t':
						self.textbuffer.delete(start_line_iter, end_iter)	# delete first tab in line

				line_number += 1


	# === Edit =========================================================

	def on_delete_clicked(self, button):								# Delete item
		model, iter = self.treeview_selection.get_selected()
		if iter is not None:
			if len(model) == 1 and model.iter_depth(iter) == 0:
				self.show_message("Delete", "Cannot delete the last item")
			else:
				if self.show_yesno_dialog("Delete", "Delete the selected item?"):
					path = self.treestore.get_path(iter)
					model.remove(iter)
					if path.prev(): pass
					else: path.up()
					self.treeview.set_cursor(path, self.column, start_editing=False)
		else:
			print 'Error: no iter in on_delete_clicked'


	def on_rename_clicked(self, button):								# Rename clicked (F2)
		model, iter = self.treeview_selection.get_selected()
		if iter is not None:
			path = self.treestore.get_path(iter)
			self.renderer.set_property('editable', True)
			self.treeview.set_cursor(path, self.column, start_editing=True)
			self.renderer.set_property('editable', False)
		else:
			print 'Error: no iter in on_rename_clicked'


	def on_delete_line_clicked(self, button):							# Delete text line
		widget = self.window.get_focus()
		if isinstance(widget, Gtk.TextView):							# only in textview
			current_iter = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert()) # current position
			line_number = current_iter.get_line()
			start_iter = self.textbuffer.get_iter_at_line(line_number)	# start of line
			end_iter = self.textbuffer.get_iter_at_line(line_number+1)	# end of line
			if start_iter.get_offset() == end_iter.get_offset():		# last line?
				end_iter = self.textbuffer.get_end_iter()
			self.textbuffer.delete(start_iter, end_iter)


	def on_undo_clicked(self, button):									# Undo clicked
		self.undo.undo('undo')


	def on_redo_clicked(self, button):									# Redo clicked
		self.undo.undo('redo')


	# === Help =========================================================

	def on_help_clicked(self, widget):									# Help clicked
		os.system("/usr/bin/xdg-open nota_help_en.pdf")					# open pdf in standard PDF viewer


	def on_about_clicked(self, widget):									# About clicked
		about_text =  "Nota\n\n"
		about_text += "The clean and simple note outliner\n"
		about_text += "for your everyday info sniplets\n\n"
		about_text += "Version " + VERSION + "\n"
		about_text += "GPL 3 - Python 2.7 - Gtk 3\n\n"
		about_text += "Ralf Hersel - 2012"
		self.show_message("About", about_text)


	# === Search =======================================================

	def on_find_return(self, widget):									# RETURN pressed in Find entry
		if not self.finder.mode:										# start find
			find_text = self.entry_find.get_text()
			if find_text != '':
				result = self.finder.find(find_text, self.treestore)
				if not result:
					self.finder.reset()									# nothing to find
					self.label_find_count.set_text('0/0')
					return False
			else:
				return False											# nothing to find

		self.treeview.collapse_all()									# collapse tree to avoid mess
		if self.keyname in ['Page_Down', 'Return']:
			iter = self.finder.get_next(self.label_find_count)			# continue find
		if self.keyname == 'Page_Up':
			iter = self.finder.get_previous(self.label_find_count)

		path = self.treestore.get_path(iter)
		self.treeview.expand_to_path(path)
		self.treeview.set_cursor(path, self.column, start_editing=False)
		self.highlight_find(self.entry_find.get_text())


	def on_find_focus_out(self, widget, event):							# leaving find widget
		self.finder.reset()
		self.label_find_count.set_text('')


	def on_find_changed(self, widget):									# find text changed
		self.finder.reset()
		self.label_find_count.set_text('')


	def on_find_clicked(self, widget):									# Menu Find or Ctrl+F
		self.entry_find.grab_focus()


	def highlight_find(self, find_text):								# highlight found string in description
		tag_table = self.textbuffer.get_tag_table()
		tag_highlight = tag_table.lookup('highlight')
		searchiter = self.textbuffer.get_iter_at_offset(0)				# start in textbuffer
		while True:														# repeat search
			try:
				match_start, match_end = \
					searchiter.forward_search(find_text, \
					Gtk.TextSearchFlags.CASE_INSENSITIVE, \
					self.textbuffer.get_end_iter())
				start_pos = match_start.get_offset()					# get found positions ..
				end_pos = match_end.get_offset()						# .. and ..
				start_iter = self.textbuffer.get_iter_at_offset(start_pos)	# .. make them ..
				end_iter = self.textbuffer.get_iter_at_offset(end_pos)	# .. the iters for textbuffer
				self.textbuffer.apply_tag(tag_highlight, start_iter, end_iter)	# highlight search term in textbuffer
				searchiter = match_end									# set new search start position
			except TypeError: break										# stop if all strings found


	# === Insert =======================================================

	def on_insert_sibling_clicked(self, widget):						# Insert sibling
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


	def on_insert_child_clicked(self, widget):							# Insert child
		model, iter = self.treeview_selection.get_selected()
		if iter is not None:
			path = self.treestore.get_path(iter)						# get path of current iter
			newiter = self.treestore.append(iter, ["New", ""])			# create the new entry
			self.treeview.expand_row(path, False)						# expand this branch (one level deep)
			path = self.treestore.get_path(newiter)						# path of the new entry
			self.renderer.set_property('editable', True)
			self.treeview.set_cursor(path, self.column, start_editing=True)	# focus on the new entry
			self.renderer.set_property('editable', False)
		else:
			print 'Error: no iter in on_insert_child_clicked'


	def on_insert_date_clicked(self, widget):							# Insert date in textbuffer or editable
		format = "%d.%m.%Y"
		widget = self.window.get_focus()								# get the widget that has the focus
		text = time.strftime(format)
		if isinstance(widget, Gtk.Editable):							# if Editable
			widget.delete_selection()									# delete selected text before inserting
			position = widget.get_position()							# get text position
			widget.insert_text(text, position)							# insert the text
			widget.set_position(position + len(text))					# set position after inserted text
		elif isinstance(widget, Gtk.TextView):							# if TextView
			self.textbuffer.delete_selection(True, True)				# delete selected text before inserting
			self.textbuffer.insert_at_cursor(text)


	# === File =========================================================

	def on_restore_clicked(self, widget):								# Restore data from nota.xml.bac
		if self.show_yesno_dialog("Restore", \
		"You will lose all changes of this session.\nRestore to beginning of this session?"):
			self.treestore, self.setting = \
				self.persistence.load(self.treestore, self.setting, True) # restore
			path = self.setting['last_path']
			self.select_last_path(path)


	def on_reload_clicked(self, widget):								# Reload data from current nota.xml
		if self.show_yesno_dialog("Reload", \
		"You will lose all changes after the last save.\nReload from last save?"):
			self.treestore, self.setting = \
				self.persistence.load(self.treestore, self.setting, False) # no restore
			path = self.setting['last_path']
			self.select_last_path(path)


	def on_exit_clicked(self, widget):									# Exit clicked
		self.save(False)												# save without backup
		Gtk.main_quit()


	def on_save_clicked(self, widget):									# Save clicked
		self.save(False)												# save without backup
		self.window.set_title(PROGRAM_NAME + ' saved')
		while Gtk.events_pending(): Gtk.main_iteration()
		time.sleep(1)
		self.window.set_title(PROGRAM_NAME)
		while Gtk.events_pending(): Gtk.main_iteration()


	def save(self, backup):												# save all content and settings
		self.setting['window_position'] = self.window.get_position()
		self.setting['window_size'] = self.window.get_size()
		self.setting['paned_position'] = self.paned.get_position()

		model, iter = self.treeview_selection.get_selected()
		if iter is not None:
			path = self.treestore.get_path(iter)						# get path of current iter
		else:
			path = '0'

		self.setting['last_path'] = path

		self.persistence.save(self.treestore, self.setting, backup)


	def on_import_gnote_clicked(self, widget):							# Import Gnote files
		self.treestore, success = self.impex.gnote(self.treestore, "gnote")
		if not success:
			self.show_message("Import", "Cannot import from Gnote")


	def on_import_tomboy_clicked(self, widget):							# Import Tomboy files
		self.treestore, success = self.impex.gnote(self.treestore, "tomboy")
		if not success:
			self.show_message("Import", "Cannot import from Tomboy")


	def on_import_unitree_clicked(self, widget):						# Import Unitree xml file
		if self.show_yesno_dialog("Import", "Please export from Unitree in XML format\nbefore you start the import."):
			pathfilename = self.show_file_chooser("Open..", "file")
			if pathfilename is not False:
				self.treestore, success = self.impex.unitree(self.treestore, pathfilename)
				if not success:
					self.show_message("Import", "Cannot import from Unitree")


	def on_export_html_clicked(self, widget):							# Export to Html
		homefolder = os.path.expanduser("~/")
		folder = self.show_file_chooser("Select folder to save nota.html..", "folder", homefolder)
		if folder is not False:
			success, filename = self.impex.html(self.treestore, folder)
			if success:
				if self.show_yesno_dialog("Export", "The html file is here:\n\n" + \
					filename + "\n\nDo you want to open it?"):
					webbrowser.open(filename)							# open html in standard webbrowser
			else:
				self.show_message("Export", "Cannot export to Html")


	# === Dialogs ======================================================

	def show_message(self, title, text):								# Dialog with Quit button
		message = Gtk.MessageDialog(self.window, Gtk.DialogFlags.MODAL,
			Gtk.MessageType.INFO, Gtk.ButtonsType.NONE, text)
		message.add_button(Gtk.STOCK_QUIT, Gtk.ResponseType.CLOSE)
		message.set_title(title)
		resp = message.run()
		if resp == Gtk.ResponseType.CLOSE:
			message.destroy()


	def show_yesno_dialog(self, title, text):							# Dialog with Yes/No button
		message = Gtk.MessageDialog(self.window, Gtk.DialogFlags.MODAL,
			Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, text)
		message.set_title(title)
		resp = message.run()
		message.destroy()
		if resp == Gtk.ResponseType.YES:
			return True
		else:
			return False


	def show_file_chooser(self, text, action, folder=None):				# Open File
		if action == "file":
			dialog = Gtk.FileChooserDialog(text, None, Gtk.FileChooserAction.OPEN,
				(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
		if action == "folder":
			dialog = Gtk.FileChooserDialog(text, None, Gtk.FileChooserAction.SELECT_FOLDER,
				(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

		dialog.set_default_response(Gtk.ResponseType.OK)				# set default button to OK
		if folder is not None:
			dialog.set_current_folder(folder)							# preset folder
		response = dialog.run()											# show file dialog
		if response == Gtk.ResponseType.OK:								# if OK clicked
			selection = dialog.get_filename(), 'selected'				# get selected file
			pathfilename = selection[0]									# get path and filename
		else:															# not OK clicked
			pathfilename = False
		dialog.destroy()												# close file dialog
		return pathfilename


# === PERSISTENCE ======================================================

class Persistence:														# Load and Save XML file
	def __init__(self):
		self.filename = FOLDER + "/nota.xml"
		self.filename_restore = self.filename + ".bac"					# Name of the backup file


	def create_default_xml(self):										# Write default XML if anything goes wrong
		if not os.path.exists(FOLDER):
			os.popen("mkdir -p " + FOLDER)

		f = open(self.filename, "wb")
		xml = """<?xml version='1.0' encoding='UTF-8'?>
				<Nota>
					<Configuration>
						<Version>""" + VERSION + """</Version>
						<WindowPosition>100,50</WindowPosition>
						<WindowSize>700,500</WindowSize>
						<PanedPosition>200</PanedPosition>
						<LastPath>0</LastPath>
					</Configuration>
					<Tree>
						<Item>
							<Name>Welcome</Name>
							<Desc>Welcome to Nota. Please read the Help to get the best out of it.

If you expected to see your existing Nota data, something went wrong.
This is the default content if the file nota.xml could not be found
at: 'home/user/.local/share/' or if an existing nota.xml is corrupt.</Desc>
						</Item>
					</Tree>
				</Nota>"""
		f.write(xml)
		f.close()


	def save(self, treestore, setting, backup=True):
		root = et.Element(PROGRAM_NAME)

		configuration = et.SubElement(root, "Configuration")
		version = et.SubElement(configuration, "Version")
		version.text = VERSION
		window_position = et.SubElement(configuration, "WindowPosition")
		window_position.text = ','.join(str(i) for i in setting['window_position'])	# tupel to string
		window_size = et.SubElement(configuration, "WindowSize")
		window_size.text = ','.join(str(i) for i in setting['window_size'])	# tupel to string
		paned_position = et.SubElement(configuration, "PanedPosition")
		paned_position.text = str(setting['paned_position'])
		last_path = et.SubElement(configuration, "LastPath")
		last_path.text = str(setting['last_path'])

		rootiter = treestore.get_iter_first()
		self.recurse_save(root, treestore, rootiter)
		f = open(self.filename, "wb")
		tree = et.ElementTree(root)
		tree.write(f, encoding="UTF-8")
		f.close()

		if backup:
			f = open(self.filename_restore, "wb")						# Save backup file
			tree.write(f, encoding="UTF-8")
			f.close()


	def recurse_save(self, element, treestore, treeiter):
		tree = et.SubElement(element, "Tree")
		while treeiter != None:
			item = et.SubElement(tree, "Item")
			name = et.SubElement(item, "Name")
			desc = et.SubElement(item, "Desc")

			try: name.text = unicode(treestore[treeiter][0], 'utf8')
			except TypeError: name.text = treestore[treeiter][0]		# don't make it utf8 a second time
			try: desc.text = unicode(treestore[treeiter][1], 'utf8')
			except TypeError: desc.text = treestore[treeiter][1]

			if treestore.iter_has_child(treeiter):
				childiter = treestore.iter_children(treeiter)
				self.recurse_save(item, treestore, childiter)
			treeiter = treestore.iter_next(treeiter)


	def load(self, treestore, setting, restore):						# Load xml file to treestore
		treestore.clear()
		if restore:
			filename = self.filename_restore
		else:
			filename = self.filename

		try:
			xml = et.parse(filename)
		except:
			self.create_default_xml()
			xml = et.parse(filename)

		root = xml.getroot()
		version = root.find("Configuration/Version").text
		window_position = root.find("Configuration/WindowPosition").text
		setting['window_position'] = tuple(map(int, window_position.split(',')))	# string to tuple
		window_size = root.find("Configuration/WindowSize").text
		setting['window_size'] = tuple(map(int, window_size.split(',')))	# string to tuple
		setting['paned_position'] = int(root.find("Configuration/PanedPosition").text)
		setting['last_path'] = root.find("Configuration/LastPath").text

		tree = root.find("Tree")
		if tree is not None:
			treestore = self.recurse_load(tree, treestore, None)
		return treestore, setting


	def recurse_load(self, tree, treestore, parent):
		items = tree.iterfind("Item")
		for item in items:
			name = item.find("Name").text
			desc = item.find("Desc").text
			if name is None: desc = "?"
			if desc is None: desc = ""
			child = treestore.append(parent, [name, desc])
			subtree = item.find("Tree")
			if subtree is not None:
				treestore = self.recurse_load(subtree, treestore, child)
		return treestore


# === IMPORTER =========================================================

class Impex:															# Import from foreign formats

	def gnote(self, treestore, source):									# Import from Gnote/Tomboy
		folder = os.path.expanduser("~/") + ".local/share/" + source	# source = 'gnote' or 'tomboy'

		if os.path.exists(folder):
			files = os.listdir(folder)
			try: files.remove("Backup")									# Omit subdirectory
			except ValueError: pass										# if 'Backup' doesn't exist

			content = {}

			for filename in files:
				f = open(folder + "/" + filename, 'r')
				text = f.read()
				f.close()

				name = self.get_content_by_tag(text, "title")
				desc = self.get_content_by_tag(text, "note-content")
				desc = self.convert_escape_chars(desc)					# convert html escape chars
				book = self.get_content_by_tag(text, "tag")

				book = book.replace("system:notebook:", "")				# Strip that prefix stuff
				if "system:template" in book: continue					# Skip gnote templates
				if "Notizbuch-Vorlage" in name: continue				# Skip gnote templates

				if book not in content:	content[book] = []				# Create first dict entry

				array = content[book]									# get existing book content
				array.append([name, desc])								# add next child to that book
				content[book] = array									# put enhanced content back in book

			parent = None
			name = "Gnote"
			desc = "Imported from Gnote"
			parent = treestore.append(parent, [name, desc])				# top level entry

			for entry in content:										# loop over whole gnote content
				child = treestore.append(parent, [entry, ""])			# book level entry
				branch = content[entry]									# get book content
				for array in branch:									# loop over one book
					name = array[0]
					desc = array[1]
					subchild = treestore.append(child, [name, desc])	# book level entry

			success = True
		else:
			success = False

		return treestore, success


	def get_content_by_tag(self, text, tag):
		start_tag = "<" + tag											# <tag
		end_tag = "</" + tag + ">"										# </tag>
		start_tag_start = text.find(start_tag)							# find <tag
		start_tag_end = text.find(">", start_tag_start) + 1				# find >
		end_tag_start = text.find(end_tag, start_tag_end)				# find </tag>
		content = text[start_tag_end:end_tag_start]						# extract text from <tag..>text</tag>
		content = re.sub('<[^<]+?>', '', content)						# remove inner tags
		return content


	def convert_escape_chars(self, text):								# convert html special chars
		return (text
			.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
			.replace("&#39;", "'").replace("&quot;", '"')
			)


	def unitree(self, treestore, pathfilename):							# import Unitree xml file
		xml = et.parse(pathfilename)
		tree = xml.getroot()

		parent = None
		name = tree.find("Name").text
		name = "Unitree - " + name
		desc = "Imported from " + pathfilename
		parent = treestore.append(parent, [name, desc])					# top level entry
		kids = tree.find("Kids")
		level = "Kids"
		treestore = self.recurse_unitree(kids, treestore, parent, level)
		return treestore, True


	def recurse_unitree(self, tree, treestore, parent, level):			# recurse over Unitree XML
		for element in tree:
			name = element.find("Name").text
			if not name: name = '???'									# avoid None object
			type = element.find("Type").text
			if type == "ins":
				desc = element.find("Attributes/Atr").text
				if not desc: desc = ''									# avoid None object
				level = "Kids"
			else:
				desc = ''
				level = "Instances"

			child = treestore.append(parent, [name, desc])

			subelement = element.find(level)
			if subelement is not None:
				treestore = self.recurse_unitree(subelement, treestore, child, level)

		return treestore


	def html(self, treestore, folder):									# export to Html
		template_name = 'nota_template.html'
		filename = folder + '/nota.html'

		try:
			f = open(template_name)										# read html template
			template = f.read()
			template = unicode(template, 'utf8')
			f.close()

			rootiter = treestore.get_iter_first()						# walk the tree
			content = ''
			body = ''
			content, body = self.recurse_html(treestore, rootiter, content, body)
			body = body.replace('\n', '<br>')
			body = body.replace('\t', '&nbsp'*10)
			template = template.replace('|nota-content|', content)
			template = template.replace('|nota-body|', body)

			f = codecs.open(filename, encoding='utf-8', mode='w')		# write the html
			f.write(template)
			f.close()
			return True, filename
		except:
			return False, None


	def recurse_html(self, treestore, iter, content, body):				# recurse over treestore
		while iter != None:
			path = treestore.get_path(iter)
			pathlist = path.get_indices()
			depth = path.get_depth() - 1
			indent = '&nbsp' * depth * 5
			pathstring = ''
			for i in pathlist:
				pathstring += str(i+1) + '.'
			pathstring = pathstring[:-1]								# strip last '.'

			try: name = unicode(treestore[iter][0], 'utf8')
			except TypeError: name = treestore[iter][0]
			try: desc = unicode(treestore[iter][1], 'utf8')
			except TypeError: desc = treestore[iter][1]

			content += ('<li>%s%s&nbsp&nbsp&nbsp<a href="#%s">%s</a></li>' % \
					(indent, pathstring, name, name))

			body += ('<p><h2 style="margin-top:3em"><a name="%s">%s&nbsp&nbsp&nbsp%s</a></h2>' % \
					(name, pathstring, name))	# titel
			body += '<hr />'											# horizontal line
			body += ('%s</p>' % desc)									# description text

			if treestore.iter_has_child(iter):
				childiter = treestore.iter_children(iter)
				content, body = self.recurse_html(treestore, childiter, content, body)
			iter = treestore.iter_next(iter)
		return content, body


# === FINDER ===========================================================

class Finder(list):														# search in tree and texts

	def __init__(self):
		self.find_text = ''
		self.max = 0
		self.index = 0
		self.mode = False


	def find(self, find_text, treestore):								# search treestore
		self.mode = True
		try: self.find_text = unicode(find_text.lower(), 'utf8')
		except TypeError: self.find_text = find_text.lower()
		rootiter = treestore.get_iter_first()
		self.recurse_find(treestore, rootiter)
		self.max = len(self)											# number of found items
		if self: return True											# something found
		else: return False												# nothing found


	def recurse_find(self, treestore, iter):							# recurse over treestore
		while iter != None:
			name = treestore[iter][0]
			try: name_lower = unicode(name.lower(), 'utf8')
			except TypeError: name_lower = name.lower()
			desc = treestore[iter][1]
			try: desc_lower = unicode(desc.lower(), 'utf8')
			except TypeError: desc_lower = desc.lower()

			if self.find_text in name_lower or self.find_text in desc_lower:
				self.append(iter)

			if treestore.iter_has_child(iter):
				childiter = treestore.iter_children(iter)
				self.recurse_find(treestore, childiter)
			iter = treestore.iter_next(iter)


	def get_next(self, find_count):										# get next search result
		if self.index == self.max:
			self.index = 0												# start from beginning
		result = self[self.index]
		self.index += 1													# next one
		count = ("%i/%i" % (self.index, self.max))
		find_count.set_text(count)
		return result


	def get_previous(self, find_count):									# get previous search result
		if self.index == 1:
			self.index = self.max + 1									# start from end
		self.index -= 1													# previous one
		result = self[self.index-1]
		count = ("%i/%i" % (self.index, self.max))
		find_count.set_text(count)
		return result


	def reset(self):													# clear Finder
		del self[:]														# delete list content only
		self.find_text = ''
		self.max = 0
		self.index = 0
		self.mode = False


# UNDO =================================================================
class Undo:

	def __init__(self):
		self.stack = []													# list of undoables
		self.textbuffer = None
		self.textview = None
		self.freeze = False												# prevent unwanted undo.add when undo.back called
		self.pointer = 0												# stack position


	def add(self, textbuffer, textview, content):						# add undo content
		if not self.freeze:
			self.textbuffer = textbuffer
			self.textview = textview
			iter = textbuffer.get_iter_at_mark(textbuffer.get_insert()) # current position
			if iter != None:
				position = iter.get_offset()							# get current position of iter as int
				self.stack.append([content, position])
				self.pointer = len(self.stack) - 1						# last element in stack


	def undo(self, mode):												# mode = 'undo' or 'redo'
		self.freeze = True
		if mode == 'undo':
			if self.pointer > 0: self.pointer -= 1
		else:	  # redo
			if self.pointer < len(self.stack) - 1: self.pointer += 1

		content = self.stack[self.pointer][0]							# get the text
		position = self.stack[self.pointer][1]							# get the cursor position
		self.textbuffer.set_text(content)								# set the text
		iter = self.textbuffer.get_iter_at_offset(position)				# get iter from cursor position
		if iter != None:
			self.textbuffer.place_cursor(iter)							# set the cursor
			mark = self.textbuffer.get_mark('insert')					# get mark at cursor
			self.textview.scroll_to_mark(mark, 0, False, 0, 0)			# scroll to cursor
			self.freeze = False


	def clear(self):													# reset undo stack
		self.stack = []


# === MAIN =============================================================

def main():
	gui = Gui()
	Gtk.main()
	return 0

if __name__ == '__main__':
	main()
