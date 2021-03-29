#!/usr/bin/env python3

from datetime import datetime
import json
import logging
import os
import os.path
import re
import subprocess
import textwrap

from copy import copy
from typing import Optional, List, Dict, Any

import npyscreen

from booklib import BookDatabase, Book, Chapter, Scene, BookFileModifiedException, Character

# Section ASCII art from https://onlineasciitools.com/convert-text-to-ascii-art

MARKDOWN_EDITOR = '/usr/local/bin/bbedit'
# MARKDOWN_EDITOR = '/usr/bin/vi'
BOOKS_DB = './books.json'
LISTS_FILE = './lists.json'
ARCHIVE_DIR = '/Users/sbiickert/Dropbox/OurFolder/Simon Writer/PyBookBuilder Archive'
PANDOC = '/Users/sbiickert/miniconda3/bin/pandoc'
PRINT_DIR = 'PDF'

logging.basicConfig(filename='bookbuilder.log', level=logging.DEBUG)


# d8888b.  .d88b.   .d88b.  db   dD   d8888b.  .d8b.  d888888b  .d8b.  d8888b.  .d8b.  .d8888. d88888b 
# 88  `8D .8P  Y8. .8P  Y8. 88 ,8P'   88  `8D d8' `8b `~~88~~' d8' `8b 88  `8D d8' `8b 88'  YP 88'     
# 88oooY' 88    88 88    88 88,8P     88   88 88ooo88    88    88ooo88 88oooY' 88ooo88 `8bo.   88ooooo 
# 88~~~b. 88    88 88    88 88`8b     88   88 88~~~88    88    88~~~88 88~~~b. 88~~~88   `Y8b. 88~~~~~ 
# 88   8D `8b  d8' `8b  d8' 88 `88.   88  .8D 88   88    88    88   88 88   8D 88   88 db   8D 88.     
# Y8888P'  `Y88P'   `Y88P'  YP   YD   Y8888D' YP   YP    YP    YP   YP Y8888P' YP   YP `8888Y' Y88888P 
                                                                                                     
                                                                                                     
class BookListActionController(npyscreen.ActionControllerSimple):
    """Controller class for the book list"""
    def create(self):
        """Called after __init__ and an opportunity to add actions."""
        #self.add_action('^/.*', self.set_search, True)
        self.add_action('^:.*', self.command, False)

    def command(self, command_line, widget_proxy, live):
        """Interprets the an entered command (prefixed with a colon)."""
        # pylint: disable=unused-argument
        cmd = command_line[1:].lower()
        logging.debug("Command given: %s", str(cmd))
        if cmd == 'q':
            self.parent.parentApp.quit()
        if cmd == 'n':
            self.parent.new_book()
        if cmd == 'i':
            self.parent.edit_book_info()
        if cmd == 'o':
            self.parent.open_directory()
        if cmd == 'p':
            self.parent.print_book()
        if cmd == 'x':
            self.parent.delete_book()
        if cmd == 'r':
            self.parent.refresh_list()
        if cmd == 'h':
            self.parent.show_help()


class BookList(npyscreen.MultiLineAction):
    def __init__(self, *args, **keywords):
        super(BookList, self).__init__(*args, **keywords)
        self.add_handlers({
            "^R": self.parent.refresh_list,
            "^N": self.parent.new_book,
            "^I": self.parent.edit_book_info,
            "^O": self.parent.open_directory,
            "^P": self.parent.print_book,
            "^X": self.parent.delete_book,
            "^H": self.parent.show_help,
            "^Q": self.parent.parentApp.quit
        })

    def display_value(self, vl):
        """
        Creates a formatted string for the passed book for use in the display.

        :param vl: The :class:`booklib.Book` to generate a display value for.
        :type vl: booklib.Book
        :return: The display in the main list view.
        :rtype: str
        """
        book: Book = vl
        return "{} {}: {}, {}".format(book.year, book.title, book.subtitle, book.author)

    def actionHighlighted(self, act_on_this, key_press):
        """Method called when the user hits Enter."""
        book: Book = act_on_this
        # Open book for editing
        self.parent.parentApp.getForm('BOOK').value = book
        self.parent.parentApp.switchForm('BOOK')


class BookListForm(npyscreen.FormMuttActiveTraditional):
    # pylint: disable=too-many-ancestors
    """
    The initial form of the application.
    Has a status1, paginated list of books, status2 and command line.
    """
    MAIN_WIDGET_CLASS = BookList
    ACTION_CONTROLLER = BookListActionController

    def beforeEditing(self):
        # pylint: disable=invalid-name
        """Called before the form is activated."""
        self.update_list()

    def new_book(self, arg=None):
        """
        Opens the book detail form and allows the user to define a new book.
        """
        self.parentApp.getForm('BOOK_INFO').value = None
        self.parentApp.switchForm('BOOK_INFO')

    def edit_book_info(self, arg=None):
        """
        Opens the book detail form and allows the user to modify the book metadata.
        """
        # doesn't work: sel_objs = self.wMain.get_selected_objects()
        book: Book = self.wMain.values[self.wMain.cursor_line]
        self.parentApp.getForm('BOOK_INFO').value = book
        self.parentApp.getForm('BOOK_INFO').next_form_name = 'MAIN'
        self.parentApp.switchForm('BOOK_INFO')

    def open_directory(self, ctrl_arg=None):
        """ Passes the book directory to the MARKDOWN_EDITOR """
        book: Book = self.wMain.values[self.wMain.cursor_line]
        subprocess.run([MARKDOWN_EDITOR, book.path()], check=True)

    def print_book(self, arg=None):
        """
        Compiles the highlighted book and exports it to PDF
        """
        book: Book = self.wMain.values[self.wMain.cursor_line]
        self.parentApp.print_book(book)

    def delete_book(self, arg=None):
        """
        Archives then deletes the book after confirmation.
        """
        # doesn't work: sel_objs = self.wMain.get_selected_objects()
        book: Book = self.wMain.values[self.wMain.cursor_line]
        msg = "Delete book '{}'?".format(book.title)
        if npyscreen.notify_ok_cancel(msg, "Confirm Delete"):
            books_db = self.parentApp.books_db
            books_db.remove_book(books_db.index_of_book(book), ARCHIVE_DIR)
            self.update_list()

    def refresh_list(self, arg=None) -> None:
        """
        Refreshes the books from books db.
        Called from action controller, list actions, menus.
        """
        self.update_list()

    def update_list(self) -> None:
        """Called regularly. Updates status values and repopulates the list."""
        self.wStatus1.value = " Books Dashboard "
        self.wStatus2.value = ": for Commands. :h for Help"

        # Will re-parse all books
        self.wMain.values = self.parentApp.books_db.all_books()

        self.wMain.display()
        self.wStatus1.display()
        self.wStatus2.display()

    def show_help(self, ctrl_arg=None):
        self.parentApp.getForm('HELP').value = 'help_main.txt'
        self.parentApp.getForm('HELP').next_form_name = 'MAIN'
        self.parentApp.switchForm('HELP')


# d8888b.  .d88b.   .d88b.  db   dD   d888888b d8b   db d88888b  .d88b.  
# 88  `8D .8P  Y8. .8P  Y8. 88 ,8P'     `88'   888o  88 88'     .8P  Y8. 
# 88oooY' 88    88 88    88 88,8P        88    88V8o 88 88ooo   88    88 
# 88~~~b. 88    88 88    88 88`8b        88    88 V8o88 88~~~   88    88 
# 88   8D `8b  d8' `8b  d8' 88 `88.     .88.   88  V888 88      `8b  d8' 
# Y8888P'  `Y88P'   `Y88P'  YP   YD   Y888888P VP   V8P YP       `Y88P'                                                                

class BookInfoForm(npyscreen.ActionForm):
    """Form that edits the selected book or defines a new book"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-ancestors
    def create(self):
        """Called after __init__ and creates all UI elements in the form."""
        self.value = None
        self.dir_location = self.add(
            npyscreen.TitleFilenameCombo,
            name="Directory:",
            select_dir=True,
            editable=True)
        self.title_text = self.add(
            npyscreen.TitleText,
            name='Title:',
            editable=True)
        self.subtitle_text = self.add(
            npyscreen.TitleText,
            name='Subtitle:',
            editable=True)
        self.author_text = self.add(
            npyscreen.TitleText,
            name='Author:',
            editable=True)
        self.year_text = self.add(
            npyscreen.TitleText,
            name='Year:',
            editable=True)
        self.keywords_text = self.add(
            npyscreen.TitleText,
            name='Keywords:',
            editable=True)
        self.genres_multiselect = self.add(
            npyscreen.TitleMultiSelect,
            name="Genres:",
            max_height=15,
            editable=True)
        self.characters_text = self.add(
            npyscreen.TitleFixedText,
            name="Characters:")
        self.edit_characters = self.add(
            npyscreen.ButtonPress,
            name='Edit Character List',
            when_pressed_function=self.on_edit_characters)
        self.nextrely = self.nextrely + 1
        self.open_dir_button = self.add(
            npyscreen.ButtonPress,
            name='Open Book Directory',
            when_pressed_function=self.open_directory)
        self.next_form_name = "MAIN" # Default, but set by calling form

    def beforeEditing(self):
        """Called before the form is shown."""
        # pylint: disable=invalid-name
        # Store a copy to see if it is edited
        self.original_value = copy(self.value)
        if self.value is None:
            # New book
            book = Book()
            book.year = str(datetime.today().year)
            self.value = book
        else:
            # Edit book
            book: Book = self.value
        # Populate the UI
        self.dir_location.value = book.path()
        self.title_text.value = book.title
        self.subtitle_text.value = book.subtitle
        self.author_text.value = book.author
        self.year_text.value = book.year
        self.keywords_text.value = ", ".join(book.keywords)
        # Genres: have to get the selected indexes for the widget
        all_genres: List[str] = self.parentApp.lists['genres']
        self.genres_multiselect.values = all_genres
        selected_indexes = []
        for idx, known_genre in enumerate(all_genres):
            if known_genre in book.genres:
                selected_indexes.append(idx)
        self.genres_multiselect.value = selected_indexes
        self.characters_text.value = f'{len(book.major_characters)} major and {len(book.minor_characters)} minor.'

    def open_directory(self):
        book: Book = self.value
        subprocess.run([MARKDOWN_EDITOR, book.path()], check=True)
    
    def on_edit_characters(self):
        self.parentApp.getForm("CHAR_LIST").value = self.value
        self.parentApp.switchForm("CHAR_LIST")

    def on_ok(self):
        book: Book = self.value
        # Transfer form values
        book.title = self.title_text.value
        book.subtitle = self.subtitle_text.value
        book.author = self.author_text.value
        book.year = self.year_text.value
        book.keywords = re.split(r'\s*[,;]\s*', self.keywords_text.value)
        book.genres = self.genres_multiselect.get_selected_objects()

        book_path = self.dir_location.value
        is_new = self.original_value is None

        if book == self.original_value:
            if self.original_value.path() == book_path:
                # No changes, just return
                self.parentApp.switchForm(self.next_form_name)
                return
        books_db: BookDatabase = self.parentApp.books_db
        if is_new:
            # Have to save first, because add_book checks if dir contains book file
            if os.path.isdir(book_path) == False:
                # Create the directory
                os.mkdir(book_path)
            book.save_to_file(Book.build_book_file_name(book_path))
            books_db.add_book(book.path(), True)
        else:
            did_move = book_path != self.original_value.path()
            if did_move:
                # Will archive first, then move content to location
                books_db.move_book(self.original_value.path(), book_path, ARCHIVE_DIR)
                book.save_to_file(Book.build_book_file_name(book_path))
            else:
                try:
                    book.save_to_file()
                except BookFileModifiedException:
                    if npyscreen.notify_ok_cancel("Book file was modified outside PyBookBuilder. Overwrite?", "Warning"):
                        book.save_to_file(force=True)
        self.parentApp.switchForm(self.next_form_name)

    def on_cancel(self):
        self.parentApp.switchForm(self.next_form_name)


#  .o88b. db   db  .d8b.  d8888b.  .d8b.   .o88b. d888888b d88888b d8888b.   db      d888888b .d8888. d888888b 
# d8P  Y8 88   88 d8' `8b 88  `8D d8' `8b d8P  Y8 `~~88~~' 88'     88  `8D   88        `88'   88'  YP `~~88~~' 
# 8P      88ooo88 88ooo88 88oobY' 88ooo88 8P         88    88ooooo 88oobY'   88         88    `8bo.      88    
# 8b      88~~~88 88~~~88 88`8b   88~~~88 8b         88    88~~~~~ 88`8b     88         88      `Y8b.    88    
# Y8b  d8 88   88 88   88 88 `88. 88   88 Y8b  d8    88    88.     88 `88.   88booo.   .88.   db   8D    88    
#  `Y88P' YP   YP YP   YP 88   YD YP   YP  `Y88P'    YP    Y88888P 88   YD   Y88888P Y888888P `8888Y'    YP    

class CharacterListForm(npyscreen.ActionForm):
    """Form that shows and edits the list of characters"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-ancestors
    def create(self):
        """Called after __init__ and creates all UI elements in the form."""
        self.value = None
        self.major_select = self.add(
            npyscreen.TitleSelectOne, #TitleMultiLine
            name='Major:',
            editable=True, max_height=33, max_width=50)
        self.major_new_button = self.add(
            npyscreen.ButtonPress,
            name='New Major Character',
            when_pressed_function=self.on_new_major)
        self.major_edit_button = self.add(
            npyscreen.ButtonPress,
            name='Edit Major Character',
            when_pressed_function=self.on_edit_major)
        self.major_delete_button = self.add(
            npyscreen.ButtonPress,
            name='Delete Major Character',
            when_pressed_function=self.on_delete_major)
        self.nextrelx = 55
        self.nextrely = 2
        self.minor_select = self.add(
            npyscreen.TitleSelectOne,
            name='Minor:',
            editable=True, max_height=33)
        self.minor_new_button = self.add(
            npyscreen.ButtonPress,
            name='New Minor Character',
            when_pressed_function=self.on_new_minor)
        self.minor_edit_button = self.add(
            npyscreen.ButtonPress,
            name='Edit Minor Character',
            when_pressed_function=self.on_edit_minor)
        self.minor_delete_button = self.add(
            npyscreen.ButtonPress,
            name='Delete Minor Character',
            when_pressed_function=self.on_delete_minor)
 
    def beforeEditing(self):
        """Called before the form is shown"""
        # pylint: disable=invalid-name
        # self.value will be Book. Book has major_characters and minor_characters
        self.update_content()
        self.parentApp.setNextForm("BOOK_INFO")
        self.keypress_timeout = 10

    def update_content(self):
        book: Book = self.value
        self.major_select.values = list(map(lambda ch: ch.name, book.major_characters))
        self.minor_select.values = list(map(lambda ch: ch.name, book.minor_characters))

    def while_waiting(self):
        try:
            book: Book = self.value
            book.guard_against_editing_modified_file()
        except BookFileModifiedException:
            book.reopen_file()
            self.update_content()
            self.display()
    
    def on_new_major(self):
        book:Book = self.value
        new_character = Character()
        book.major_characters.append(new_character)
        self.parentApp.getForm("CHAR_INFO").value = new_character
        self.parentApp.switchForm("CHAR_INFO")

    def on_edit_major(self):
        book:Book = self.value
        if len(self.major_select.value) > 0:
            selected_idx = self.major_select.value[0]
            selected_character = book.major_characters[selected_idx]
            self.parentApp.getForm("CHAR_INFO").value = selected_character
            self.parentApp.switchForm("CHAR_INFO")
    
    def on_delete_major(self):
        book:Book = self.value
        if len(self.major_select.value) > 0:
            selected_idx = self.major_select.value[0]
            selected_character = book.major_characters[selected_idx]
            # Confirm
            if npyscreen.notify_ok_cancel(f'Delete {selected_character.name}?', 'Confirm Delete'):
                del book.major_characters[selected_idx]
                self.major_select.values = list(map(lambda ch: ch.name, book.major_characters))
                self.major_select.value = []
                self.display()
    
    def on_new_minor(self):
        book:Book = self.value
        new_character = Character()
        book.minor_characters.append(new_character)
        self.parentApp.getForm("CHAR_INFO").value = new_character
        self.parentApp.switchForm("CHAR_INFO")

    def on_edit_minor(self):
        book:Book = self.value
        if len(self.minor_select.value) > 0:
            selected_idx = self.minor_select.value[0]
            selected_character = book.minor_characters[selected_idx]
            self.parentApp.getForm("CHAR_INFO").value = selected_character
            self.parentApp.switchForm("CHAR_INFO")
    
    def on_delete_minor(self):
        book:Book = self.value
        if len(self.minor_select.value) > 0:
            selected_idx = self.minor_select.value[0]
            selected_character = book.minor_characters[selected_idx]
            # Confirm
            if npyscreen.notify_ok_cancel(f'Delete {selected_character.name}?', 'Confirm Delete'):
                del book.minor_characters[selected_idx]
                self.minor_select.values = list(map(lambda ch: ch.name, book.minor_characters))
                self.minor_select.value = []
                self.display()

    def on_ok(self):
        book:Book = self.value
        book.save_to_file()

    def on_cancel(self):
        book:Book = self.value
        book.open_file()



#  .o88b. db   db  .d8b.  d8888b.  .d8b.   .o88b. d888888b d88888b d8888b. 
# d8P  Y8 88   88 d8' `8b 88  `8D d8' `8b d8P  Y8 `~~88~~' 88'     88  `8D 
# 8P      88ooo88 88ooo88 88oobY' 88ooo88 8P         88    88ooooo 88oobY' 
# 8b      88~~~88 88~~~88 88`8b   88~~~88 8b         88    88~~~~~ 88`8b   
# Y8b  d8 88   88 88   88 88 `88. 88   88 Y8b  d8    88    88.     88 `88. 
#  `Y88P' YP   YP YP   YP 88   YD YP   YP  `Y88P'    YP    Y88888P 88   YD 
                                                                         
class CharacterForm(npyscreen.ActionPopupWide):
    """Form that shows and edits a character"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-ancestors
    def create(self):
        """Called after __init__ and creates all UI elements in the form."""
        self.value = None
        self.name_text = self.add(
            npyscreen.TitleText,
            name='Name:',
            editable=True)
        self.description_text = self.add(
            npyscreen.TitleText,
            name='Description:',
            editable=True)
        self.alias_text = self.add(
            npyscreen.TitleText,
            name='Aliases:',
            editable=True)
    
    def beforeEditing(self):
        # pylint: disable=invalid-name
        """Called before the form is shown."""
        character:Character = self.value
        self.name_text.value = character.name
        self.description_text.value = character.description
        self.alias_text.value = ", ".join(character.aliases)
        self.parentApp.setNextForm("CHAR_LIST")
    
    def on_ok(self):
        character:Character = self.value
        character.name = self.name_text.value
        character.description = self.description_text.value
        character.aliases = self.alias_text.value.split(', ')


# d8888b.  .d88b.   .d88b.  db   dD    .o88b.  .d88b.  d8b   db d888888b d88888b d8b   db d888888b 
# 88  `8D .8P  Y8. .8P  Y8. 88 ,8P'   d8P  Y8 .8P  Y8. 888o  88 `~~88~~' 88'     888o  88 `~~88~~' 
# 88oooY' 88    88 88    88 88,8P     8P      88    88 88V8o 88    88    88ooooo 88V8o 88    88    
# 88~~~b. 88    88 88    88 88`8b     8b      88    88 88 V8o88    88    88~~~~~ 88 V8o88    88    
# 88   8D `8b  d8' `8b  d8' 88 `88.   Y8b  d8 `8b  d8' 88  V888    88    88.     88  V888    88    
# Y8888P'  `Y88P'   `Y88P'  YP   YD    `Y88P'  `Y88P'  VP   V8P    YP    Y88888P VP   V8P    YP    
                                                                                                                                                                            
class BookContentActionController(npyscreen.ActionControllerSimple):
    """ Controller class for the book structure. """
    def create(self):
        """Called after __init__ and an opportunity to add actions."""
        self.add_action('^/.*', self.set_search, True)
        self.add_action('^:.*', self.command, False)
    
    def command(self, command_line, widget_proxy, live):
        """Interprets the an entered command (prefixed with a colon)."""
        # pylint: disable=unused-argument
        cmd = command_line[1:].lower()
        logging.debug("Command given: %s", str(cmd))
        if cmd == 'u':
            self.parent.move_node_up()
        if cmd == 'd':
            self.parent.move_node_down()
        if cmd == 'n':
            self.parent.on_append_chapter()
        if cmd == 'h':
            self.parent.show_help()
        if cmd == 'a':
            self.parent.on_analyze()
        if cmd == 'i':
            self.parent.on_get_info()
        if cmd == 'p':
            self.parent.on_print()
        if cmd == 'r':
            self.parent.on_refresh()
        if cmd == 'x':
            self.parent.on_delete_chapter()
        if cmd == 'w':
            self.parent.close_book()
        if cmd == 'q':
            self.parent.parentApp.quit()

    def set_search(self, command_line, widget_proxy, live):
        """Sets the search string and updates the list of notes."""
        # pylint: disable=unused-argument
        self.parent.filter_value = command_line[1:]
        self.parent.update_list()


class BookContentList(npyscreen.MultiLineAction):
    def __init__(self, *args, **keywords):
        super(BookContentList, self).__init__(*args, **keywords)
        self.add_handlers({
            "^U": self.parent.move_node_up,
            "^D": self.parent.move_node_down,
            "^N": self.parent.on_append_chapter,
            "^H": self.parent.show_help,
            "^R": self.parent.on_refresh,
            "^I": self.parent.on_get_info,
            "^A": self.parent.on_analyze,
            "^P": self.parent.on_print,
            "^X": self.parent.on_delete_chapter,
            "^W": self.parent.close_book,
            "^Q": self.parent.parentApp.quit
        })

    def display_value(self, vl):
        """
        Creates a formatted string for the passed book element for use in the display.

        :param vl: The Book, Chapter or Scene to generate a display value for.
        :type vl: Book, Chapter or Scene
        :return: The display in the main list view.
        :rtype: str
        """
        if isinstance(vl, Book):
            book: Book = vl
            return f" {book.title}: {book.subtitle}"
        if isinstance(vl, Chapter):
            chapter: Chapter = vl
            w_count = chapter.word_count()
            graph_length = int(w_count / 250)
            bar_ch = '*' # '├─┤
            graph = f'{(bar_ch * graph_length)}'
            if "Chapter" in chapter.title:
                return f"  └─ {chapter.title} - {chapter.subtitle}".ljust(self.width - 41) + graph.rjust(40)
            else:
                return f"  └─ Chapter {chapter.number}: {chapter.title} - {chapter.subtitle}".ljust(self.width - 41) + graph.rjust(40)
        if isinstance(vl, Scene):
            scene: Scene = vl
            PADDING_AND_OTHER = 18
            POV_WIDTH = 20
            WC_WIDTH = 8
            variable_width = self.width - (PADDING_AND_OTHER + WC_WIDTH + POV_WIDTH)
            pov = fit_str(scene.pov, POV_WIDTH) # Fixed width
            loc = fit_str(scene.location, round(variable_width * 0.3))
            desc = fit_str(scene.description, round(variable_width * 0.7)) 
            w_count = f'({scene.word_count()})'.rjust(WC_WIDTH) # Fixed width
            return f'  │  └─ ({scene.status[0]}) {desc}  {pov}  {loc} {w_count}'

    def actionHighlighted(self, act_on_this, key_press):
        """Method called when the user hits Enter."""
        self.parent.open_selected(act_on_this)


class BookForm(npyscreen.FormMuttActiveTraditional):
    """Form that shows and edits the open book content"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-ancestors
    MAIN_WIDGET_CLASS = BookContentList
    ACTION_CONTROLLER = BookContentActionController
    filter_value = ''

    def beforeEditing(self):
        """Called before the form is shown."""
        # pylint: disable=invalid-name
        self.update_display()
        self.keypress_timeout = 10

    def while_waiting(self):
        try:
            book: Book = self.value
            book.guard_against_editing_modified_file()
        except BookFileModifiedException:
            #if npyscreen.notify_ok_cancel("Book file was modified outside PyBookBuilder. Reload from file?", "Warning"):
            logging.debug("Book file on disk was modified. Reloading.")
            self.on_refresh()

    def get_selected_object(self):
        return self.wMain.values[self.wMain.cursor_line]

    def select_object(self, vl_to_select):
        """ Ability to move the cursor to an object """
        for idx, vl in enumerate(self.wMain.values):
            if vl == vl_to_select:
                self.wMain.cursor_line = idx

    def get_selected_chapter(self) -> Optional[Chapter]:
        selected_chapter: Optional[Chapter] = None
        selected_object = self.get_selected_object()
        if isinstance(selected_object, Chapter):
            selected_chapter = selected_object
        elif isinstance(selected_object, Scene):
            selected_scene: Scene = selected_object
            selected_chapter = selected_scene.get_chapter()
        return selected_chapter

    def get_selected_scene(self) -> Optional[Scene]:
        selected_scene: Optional[Scene] = None
        selected_object = self.get_selected_object()
        if isinstance(selected_object, Scene):
            selected_scene = selected_object
        return selected_scene

    def open_selected(self, act_on_this=None):
        """
        Method called when the user hits the Open button.
        Item to open could be a Book, a Chapter or a Scene, based on selection.
        """
        if act_on_this is not None:
            selected_object = act_on_this
        else:
            selected_object = self.get_selected_object()
        if isinstance(selected_object, Book):
            # Eventually compile this into a single Markdown file?
            book: Book = selected_object
            file_name = book.get_file_name()
            logging.debug("opening book %s in file %s with %s", book.title, file_name, MARKDOWN_EDITOR)
            subprocess.run([MARKDOWN_EDITOR, '+1', file_name], check=True)
        if isinstance(selected_object, Chapter):
            # Combine the scenes into a chapter? But then what?
            chapter: Chapter = selected_object
            file_name = chapter.get_book().get_file_name()
            logging.debug("opening chapter %s in file %s with %s", chapter.title, file_name, MARKDOWN_EDITOR)
            subprocess.run([MARKDOWN_EDITOR, f'+{chapter.start_line_number}', file_name], check=True)
        if isinstance(selected_object, Scene):
            scene: Scene = selected_object
            file_name = scene.get_chapter().get_book().get_file_name()
            logging.debug("opening scene %s in file %s with %s", scene.description, file_name, MARKDOWN_EDITOR)
            subprocess.run([MARKDOWN_EDITOR, f'+{scene.start_line_number}', file_name], check=True)

    def on_analyze(self, ctrl_arg=None):
        selected_object = self.get_selected_object()
        if isinstance(selected_object, Scene):
            scene: Scene = selected_object
            scene.analyze()
            self.parentApp.print_scene(scene)
            scene.clear_markup()
            self.update_display()

    def on_get_info(self, ctrl_arg=None):
        selected_object = self.get_selected_object()
        if isinstance(selected_object, Book):
            book: Book = selected_object
            self.parentApp.getForm('BOOK_INFO').value = book
            self.parentApp.getForm('BOOK_INFO').next_form_name = 'BOOK'
            self.parentApp.switchForm('BOOK_INFO')
        if isinstance(selected_object, Chapter):
            chapter: Chapter = selected_object
            self.parentApp.getForm('CHAPTER_INFO').value = chapter
            self.parentApp.switchForm('CHAPTER_INFO')
        if isinstance(selected_object, Scene):
            scene: Scene = selected_object
            self.parentApp.getForm('SCENE_INFO').value = scene
            self.parentApp.switchForm('SCENE_INFO')

    def on_append_chapter(self, ctrl_arg=None):
        book: Book = self.value
        new_chapter = Chapter()
        new_chapter.set_book(book)
        self.parentApp.getForm('CHAPTER_INFO').value = new_chapter
        self.parentApp.switchForm('CHAPTER_INFO')

    def on_delete_chapter(self, ctrl_arg=None):
        selected_chapter = self.get_selected_chapter()
        if selected_chapter is None:
            # Can't delete None
            return
        message_to_display = f'You are about to delete chapter {selected_chapter.title}. This cannot be undone.'
        notify_result = npyscreen.notify_ok_cancel(message_to_display, title= 'Delete Chapter?')
        if notify_result:
            book: Book = self.value
            book.delete_chapter(selected_chapter)
            book.save_to_file()
        self.update_display()

    def on_print(self, ctrl_arg=None):
        self.parentApp.print_book(self.value)

    def on_refresh(self, ctrl_arg=None):
        book: Book = self.value
        book.reopen_file()
        self.update_display()

    def update_display(self, ctrl_arg=None):
        self.wStatus1.value = " Book Structure "
        self.wStatus2.value = "/ to Search, : for Commands. :h for Help"
        self.update_list()
        self.wStatus1.display()
        self.wStatus2.display()

    def update_list(self):
        book: Book = self.value
        
        all_book_elements = [book]
        for chapter in book.chapters:
            all_book_elements.append(chapter)
            all_book_elements.extend(chapter.scenes)
        # Apply filter here
        if self.filter_value.strip():
            searched_elements = list(filter(self.filter_element, all_book_elements))
        else:
            searched_elements = all_book_elements
        self.wMain.values = searched_elements
        self.wMain.display()
    
    def filter_element(self, book_element) -> bool:
        return book_element.search(self.filter_value)

    def move_node_up(self, ctrl_arg=None):
        self.move_node(True)

    def move_node_down(self, ctrl_arg=None):
        self.move_node(False)

    def move_node(self, up: bool):
        sel_scene = self.get_selected_scene()
        if sel_scene is not None:
            # Reorder scene
            chapter = sel_scene.get_chapter()
            if chapter is not None:
                chapter.reorder_scene(sel_scene, up)
                chapter.get_book().save_to_file()
        else:
            sel_chapter = self.get_selected_chapter()
            if sel_chapter is not None:
                # Reorder chapter
                book = sel_chapter.get_book()
                if book is not None:
                    book.reorder_chapter(sel_chapter, up)
                    book.save_to_file()
        self.update_display()
        if sel_scene is not None:
            self.select_object(sel_scene)
        else:
            self.select_object(sel_chapter)
        self.update_display()

    def show_help(self, ctrl_arg=None):
        self.parentApp.getForm('HELP').value = 'help_book.txt'
        self.parentApp.getForm('HELP').next_form_name = 'BOOK'
        self.parentApp.switchForm('HELP')

    def close_book(self, ctrl_arg=None):
        self.parentApp.switchForm("MAIN")



#  .o88b. db   db  .d8b.  d8888b. d888888b d88888b d8888b.   d888888b d8b   db d88888b  .d88b.  
# d8P  Y8 88   88 d8' `8b 88  `8D `~~88~~' 88'     88  `8D     `88'   888o  88 88'     .8P  Y8. 
# 8P      88ooo88 88ooo88 88oodD'    88    88ooooo 88oobY'      88    88V8o 88 88ooo   88    88 
# 8b      88~~~88 88~~~88 88~~~      88    88~~~~~ 88`8b        88    88 V8o88 88~~~   88    88 
# Y8b  d8 88   88 88   88 88         88    88.     88 `88.     .88.   88  V888 88      `8b  d8' 
#  `Y88P' YP   YP YP   YP 88         YP    Y88888P 88   YD   Y888888P VP   V8P YP       `Y88P'  
                                                                                              
class ChapterForm(npyscreen.ActionPopupWide):
    """Form that shows and edits the chapter metadata"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-ancestors
    def create(self):
        """Called after __init__ and creates all UI elements in the form."""
        self.value = None
        self.title_text = self.add(
            npyscreen.TitleText,
            name='Title:',
            editable=True)
        self.subtitle_text = self.add(
            npyscreen.TitleText,
            name='Subtitle:',
            editable=True)
        self.characters_text = self.add(
            npyscreen.TitleText,
            name='Characters:',
            editable=False)

    def beforeEditing(self):
        chapter: Optional[Chapter] = self.value
        if chapter is not None:
            self.title_text.value = chapter.title
            self.subtitle_text.value = chapter.subtitle
            all_characters = list(map(lambda ch: ch.name, chapter.get_characters()))
            self.characters_text.value = ", ".join(all_characters)

        self.parentApp.setNextForm("BOOK")

    def on_ok(self):
        chapter: Chapter = self.value
        chapter.title = self.title_text.value
        chapter.subtitle = self.subtitle_text.value
        book: Book = chapter.get_book()
        if chapter.start_line_number == 0:
            # New Chapter
            book.append_chapter(chapter)
        book.save_to_file()
        

# .d8888.  .o88b. d88888b d8b   db d88888b   d888888b d8b   db d88888b  .d88b.  
# 88'  YP d8P  Y8 88'     888o  88 88'         `88'   888o  88 88'     .8P  Y8. 
# `8bo.   8P      88ooooo 88V8o 88 88ooooo      88    88V8o 88 88ooo   88    88 
#   `Y8b. 8b      88~~~~~ 88 V8o88 88~~~~~      88    88 V8o88 88~~~   88    88 
# db   8D Y8b  d8 88.     88  V888 88.         .88.   88  V888 88      `8b  d8' 
# `8888Y'  `Y88P' Y88888P VP   V8P Y88888P   Y888888P VP   V8P YP       `Y88P'  
                                                                              
class SceneForm(npyscreen.ActionForm):
    """Form that shows and edits the scene header content"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-ancestors
    def create(self):
        """Called after __init__ and creates all UI elements in the form."""
        self.value = None
        self.desc_text = self.add(
            npyscreen.TitleText,
            name='Description:',
            editable=True)
        self.location_text = self.add(
            npyscreen.TitleText,
            name='Location:',
            editable=True)
        self.nextrely = self.nextrely + 1
        self.status_select = self.add(
            npyscreen.TitleSelectOne,
            name='Revision Status:',
            editable=True, max_height=6,
            values=self.parentApp.lists['status'])
        self.nextrely = self.nextrely + 1
        self.pov_select = self.add(
            npyscreen.TitleSelectOne,
            name='POV:',
            editable=True, max_height=10)
        self.characters_text = self.add(
            npyscreen.TitleText,
            name='Characters:',
            editable=False)
        self.nextrely = self.nextrely + 1
        self.readability_text = self.add(
            npyscreen.TitleFixedText,
            name="Readability:")
        self.analyze_button = self.add(
            npyscreen.ButtonPress,
            name='Analyze',
            when_pressed_function=self.on_analyze
        )
        # self.clear_button = self.add(
        #     npyscreen.ButtonPress,
        #     name='Clear Analytics',
        #     when_pressed_function=self.on_clear
        # )

    def beforeEditing(self):
        scene: Optional[Scene] = self.value
        if scene is not None:
            self.desc_text.value = scene.description
            self.location_text.value = scene.location
            scene_characters = scene.get_characters()
            self.characters_text.value = ', '.join(map(lambda ch: ch.name, scene_characters))
            all_status: List[str] = self.parentApp.lists['status']
            selected_index = 0
            for idx, known_status in enumerate(all_status):
                if known_status == scene.status:
                    selected_index = idx
            self.status_select.value = selected_index
            # Choose from character list
            the_book = scene.get_chapter().get_book()
            characters = the_book.major_characters + the_book.minor_characters
            pov_char = scene.get_pov_character()
            assert pov_char is not None
            idx = characters.index(pov_char)
            self.pov_select.values = list(map(lambda ch: ch.name, characters))
            self.pov_select.value = idx
            # Analytics
            self.update_analytic_display()
        self.parentApp.setNextForm("BOOK")

    def update_analytic_display(self):
        scene: Optional[Scene] = self.value
        if scene is not None:
            if scene.has_analytics():
                self.readability_text.value = f'TTR: {scene.analytic_info["ttr"]}, FRES: {scene.analytic_info["fres"]} ({scene.get_readability()})'
            else:
                self.readability_text.value = "Not analyzed"

    def on_ok(self):
        old_scene: Scene = self.value
        new_scene = copy(old_scene)
        new_scene.description = self.desc_text.value
        new_scene.location = self.location_text.value
        # new_scene.characters = re.split(r'\s*[;,]\s*', self.characters_text.value)
        selected_status_idx = self.status_select.value[0]
        new_scene.status = self.status_select.values[selected_status_idx]
        selected_pov_idx = self.pov_select.value[0]
        new_scene.pov = self.pov_select.values[selected_pov_idx]

        chapter: Chapter = old_scene.get_chapter()
        chapter.replace_scene(old_scene, new_scene)
        chapter.get_book().save_to_file()

    def on_analyze(self):
        scene: Optional[Scene] = self.value
        if scene is not None:
            scene.analyze()
            self.parentApp.print_scene(scene)
            scene.clear_markup()
            self.update_analytic_display()
            self.display()

    # def on_clear(self):
    #     scene: Optional[Scene] = self.value
    #     if scene is not None:
    #         scene.clear_analysis()
    #         self.update_analytic_display()
    #         self.display()


# db   db d88888b db      d8888b. 
# 88   88 88'     88      88  `8D 
# 88ooo88 88ooooo 88      88oodD' 
# 88~~~88 88~~~~~ 88      88~~~   
# 88   88 88.     88booo. 88      
# YP   YP Y88888P Y88888P 88      
                                
class HelpForm(npyscreen.Form):
    """Form that shows the contents of file passed as self.value."""
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-ancestors
    def create(self):
        """Called after __init__ and creates all UI elements in the form."""
        self.value = None
        self.help_multiline = self.add(
            npyscreen.MultiLineEdit,
            name='Preview',
            editable=False)
        self.next_form_name = "MAIN"

    def beforeEditing(self):
        # pylint: disable=invalid-name
        """Called before the form is shown."""
        with open(f"./{self.value}", 'r') as help_file:
            help_text = help_file.read()
            self.help_multiline.value = help_text
        self.parentApp.setNextForm(self.next_form_name)


#  .d8b.  d8888b. d8888b. 
# d8' `8b 88  `8D 88  `8D 
# 88ooo88 88oodD' 88oodD' 
# 88~~~88 88~~~   88~~~   
# 88   88 88      88      
# YP   YP 88      88      
                        
class BookBuilderApp(npyscreen.NPSAppManaged):
    def onStart(self):
        """
        The entry point to the application. The known forms are added here.
        Also load the books database.
        """
        # pylint: disable=invalid-name
        # pylint: disable=attribute-defined-outside-init
        npyscreen.setTheme(npyscreen.Themes.ElegantTheme)

        # Load books database
        self.books_db = BookDatabase(BOOKS_DB)
        
        # Load lists of lookup values
        self.load_lists()

        # Add forms
        self.addForm("MAIN", BookListForm, name="Books Dashboard")
        self.addForm("BOOK_INFO", BookInfoForm, name="Information About the Book")
        self.addForm("BOOK", BookForm, name="Edit the Book")
        self.addForm("CHAPTER_INFO", ChapterForm, name="Information About the Chapter")
        self.addForm("SCENE_INFO", SceneForm, name="Information About the Scene")
        self.addForm("HELP", HelpForm, name="Help")
        self.addForm("CHAR_LIST", CharacterListForm, name="List of Characters")
        self.addForm("CHAR_INFO", CharacterForm, name="Information About the Character")

    def load_lists(self):
        with open(LISTS_FILE) as lists_file:
            lists_text = lists_file.read()
            self.lists = json.loads(lists_text)
        
    def print_book(self, book: Book):
        md_text = book.compile()
        print_dir = os.path.join(book.path(), PRINT_DIR)
        if not os.path.isdir(print_dir):
            os.mkdir(print_dir)
        md_file_name = os.path.join(print_dir, 'book.md')
        with open(md_file_name, 'w') as md_file:
            md_file.write(md_text)
        pdf_file_name = os.path.join(print_dir, f'{book.title}.pdf')
        npyscreen.notify(f'Printing book to {pdf_file_name}', title="Printing")
        subprocess.run([PANDOC, md_file_name, '--pdf-engine=xelatex', '-o', pdf_file_name], check=True) # '--toc'
        npyscreen.notify_confirm(f'Printed book to {pdf_file_name}', title="Done")
        subprocess.run(['open', pdf_file_name], check=True)
        
    def print_scene(self, scene: Scene):
        """ For popping up a marked-up scene (analytics) """
        md_text = scene.to_markdown()
        print_dir = os.path.join(scene.get_chapter().get_book().path(), PRINT_DIR)
        if not os.path.isdir(print_dir):
            os.mkdir(print_dir)
        md_file_name = os.path.join(print_dir, 'scene.md')
        with open(md_file_name, 'w') as md_file:
            md_file.write(md_text)
        pdf_file_name = os.path.join(print_dir, 'scene.pdf')
        npyscreen.notify(f'Printing scene to {pdf_file_name}', title="Printing")
        subprocess.run([PANDOC, md_file_name, '--quiet', '-o', pdf_file_name, '--pdf-engine=wkhtmltopdf', "--pdf-engine-opt=-q"], check=True) #
        # npyscreen.notify_confirm(f'Printed book to {pdf_file_name}', title="Done")
        subprocess.run(['open', pdf_file_name], check=True)

    def quit(self, arg=None):
        """
        Simple implementation of a one-liner to exit the app
        """
        self.setNextForm(None)
        self.switchForm(None)

def fit_str(text: str, length: int) -> str:
    fit = text.ljust(length)
    if len(fit) > length:
        #fit = fit[:(length-6)] + '…' + fit[-5:]
        fit = fit[:5] + '…' + fit[(6-length):]
    return fit


if __name__ == '__main__':
    MY_APP = BookBuilderApp()
    MY_APP.run()
