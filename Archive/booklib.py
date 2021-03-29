#!/usr/bin/env python3

""" Business objects for PyBookBuilder """

import json
import os.path
import logging
import shutil
import datetime
import random
import string
import weakref
import re

from typing import Optional, List, Dict, Any, Tuple
from distutils.dir_util import copy_tree
from markdown_it import MarkdownIt

import bookanalytics as ba

BOOK_DATA = 'book.md'

logging.basicConfig(filename='bookbuilder.log', level=logging.DEBUG)
logging.getLogger("markdown_it").setLevel(logging.WARNING)


########################################################################################
# 
#       ########   ######   #######   ##   ##   #######
#      ##        ##        ##        ###  ##   ##
#     #######   ##        #######   ## # ##   ######
#         ##   ##        ##        ##  ###   ##
#   #######    ######   #######   ##   ##   #######
#
########################################################################################

class Scene():
    """ Represents a scene from the book """

    def __init__(self, header: Dict[str, Any] = None):
        """
        Initializes the :class:`booklib.Scene`.
        """

        self.description = ""
        self.location = ""
        self.pov = ""
        self.status = ""

        self.analytic_info: Dict[str, Any] = {}

        self.start_line_number = 0
        self.paragraphs: List[str] = []

        self.__chapter_ref = None

        if header is not None:
            self.set_header(header)

    def get_chapter(self):
        # pylint: disable=not-callable
        if self.__chapter_ref is not None:
            return self.__chapter_ref()
        return None

    def set_chapter(self, chapter):
        if chapter is None:
            self.__chapter_ref = None
        else:
            self.__chapter_ref = weakref.ref(chapter)

    def word_count(self):
        """Splits paragraphs and returns the length"""
        wc = 0
        for p in self.paragraphs:
            wc += len(p.split())
        return wc

    def get_readability(self):
        """ Returns readability assessment code for FRES. """
        if self.has_analytics():
            return ba.classify_FRES(self.analytic_info['fres'])
        return "N/A"
    
    def get_characters(self) -> List[str]:
        """ Searches for known characters in the Scene """
        found_characters: List[str] = []
        for character in self.get_chapter().get_book().characters:
            for paragraph in self.paragraphs:
                if character in paragraph:
                    found_characters.append(character)
                    break
        return found_characters

    def set_header(self, header_dict: Dict[str, Any]):
        """
        Populates the member variables from dict
        :param header_dict: the scene header that was parsed from JSON
        """
        try:
            self.description = header_dict['description']
            self.location = header_dict['location']
            self.pov = header_dict['pov']
            self.status = header_dict['status']
            if 'analytic_info' in header_dict:
                self.analytic_info = header_dict['analytic_info']
        except KeyError:
            logging.info("Missing header key.")

    def write_header(self) -> str:
        """
        Outputs the :class:`booklib.Scene` ivars to the JSON header format.
        """
        header_dict: Dict[str, Any] = {}
        header_dict['description'] = self.description
        header_dict['location'] = self.location
        header_dict['pov'] = self.pov
        header_dict['status'] = self.status
        header_dict['analytic_info'] = self.analytic_info
        json_text = json.dumps(header_dict, indent=2)
        return f"<!-- {json_text} -->"

    def to_markdown(self) -> str:
        """ Combines into a Markdown string for writing back to the source file. """
        markdown_strings = [self.write_header()]
        for paragraph in self.paragraphs:
            markdown_strings.append(paragraph)
        return "\n\n".join(markdown_strings)

    def compile(self) -> List[str]:
        """
        Combines all paragraphs into a list of Markdown strings for printing.
        At the moment, trivial implementation that just returns the paragraphs.
        """
        return self.paragraphs


    def __eq__(self, other):
        """ Checks for equality of all ivars """
        if other is None:
            return False
        if not isinstance(other, Scene):
            return False
        return self.description == other.description and \
               self.location == other.location and \
               self.pov == other.pov and \
               self.paragraphs == other.paragraphs

    def search(self, search_pattern) -> bool:
        """ Does a regex search against the paragraph text(s) and description. """
        try:
            text_to_search = [self.description]
            text_to_search.extend(self.paragraphs)
            for text in text_to_search:
                if re.search(search_pattern, text):
                    return True
        except re.error as err:
            status_msg = "Regex message: {}".format(err)
            logging.debug("Error in Scene.search for '%s': %s", search_pattern, status_msg)
        return False
    
    def analyze(self):
        """
        Creates readability stats, marks specific issues:
            - complex sentences
            - passive voice
            - adverbs
        """
        self.clear_markup()
        scene_text = " ".join(self.paragraphs)
        self.analytic_info['ttr'] = round(ba.calc_TTR(scene_text), 1)
        self.analytic_info['fres'] = round(ba.calc_FRES(scene_text), 1)

        marked_paragraphs = []
        for paragraph in self.paragraphs:
            adverbs = ba.find_adverbs(paragraph)
            sentences = ba.split_sentences(paragraph)
            for sentence in sentences:
                difficulty = ba.classify_FRES(ba.calc_FRES(sentence))
                passive_voice = ba.find_passive_voice(sentence)
                if difficulty == "VHARD":
                    paragraph = Scene.mark_text(paragraph, sentence, "Sentence v. difficult to read", "#e4b9b9")
                elif difficulty == "HARD":
                    paragraph = Scene.mark_text(paragraph, sentence, "Sentence difficult to read", "#f7ecb5")
                if passive_voice is not None:
                    paragraph = Scene.mark_text(paragraph, passive_voice, "Passive voice", "#c4ed9d")
            for adverb in adverbs:
                paragraph = Scene.mark_text(paragraph, adverb, "Adverb", "#c4e3f3")
            marked_paragraphs.append(paragraph)
        self.paragraphs = marked_paragraphs

    @staticmethod
    def mark_text(full_text: str, text_to_mark: str, title: str, background_color: str) -> str:
        """
        Finds the range of the start and end of the text to mark, and then substitutes
        <mark title="title" style="background-color: background_color">text_to_mark</mark>
        """
        marked = full_text
        start_idx = full_text.lower().rfind(text_to_mark.lower())
        while start_idx >= 0:
            end_idx = start_idx + len(text_to_mark)
            marked = marked[:end_idx] + "</mark>" + marked[end_idx:]
            opening_tag = f'<mark title="{title}" style="background-color: {background_color}">'
            marked = marked[:start_idx] + opening_tag + marked[start_idx:]
            start_idx = full_text.lower().rfind(text_to_mark.lower(), 0, start_idx)

        return marked

    def clear_markup(self):
        """ Clears all markups from the text. """
        cleaned = []
        for paragraph in self.paragraphs:
            cleaned.append(re.sub(r'</?mark[^>]*>', '', paragraph))
        self.paragraphs = cleaned

    def has_analytics(self) -> bool:
        """
        Returns true if the Scene has been analyzed and there
        is a analytic_info header.
        """
        return "ttr" in self.analytic_info and 'fres' in self.analytic_info

    def has_markup(self) -> bool:
        """
        Returns True if there are any markups in the Scene's paragraphs.
        """
        for paragraph in self.paragraphs:
            if re.match(r'</?mark[^>]*>', paragraph):
                return True
        return False


########################################################################################
# 
#        ######   ##   ##    #####    ######   #######  #######   ######   
#      ##        ##   ##   ##   ##   ##   ##    ##     ##        ##   ##  
#     ##        #######   #######   ######     ##     #######   ###### 
#    ##        ##   ##   ##   ##   ##         ##     ##        ##   ## 
#    ######   ##   ##   ##   ##   ##         ##     #######   ##    ##  
#  
########################################################################################

class Chapter():
    """ Represents a collection of scenes with a title and subtitle """
    def __init__(self):
        """ Initializes title, subtitle, path and scene file names to empty """
        self.title = ""
        self.subtitle = ""
        self.number = 0
        self.start_line_number = 0
        self.scenes = []
        self.__book_ref = None

    def get_book(self):
        # pylint: disable=not-callable
        if self.__book_ref is not None:
            return self.__book_ref()
        return None

    def set_book(self, book):
        if book is None:
            self.__book_ref = None
        else:
            self.__book_ref = weakref.ref(book)

    def word_count(self) -> int:
        """ Sums the word counts of all the Scenes. """
        w_count = 0
        for scene in self.scenes:
            w_count = w_count + scene.word_count()
        return w_count
    
    def get_characters(self) -> List[str]:
        """ Searches for known characters in the Chapter's Scenes """
        all_characters: List[str] = []
        for scene in self.scenes:
            all_characters.extend(scene.get_characters())
        uniques = set(all_characters)
        return sorted(uniques)

    def set_title_subtitle(self, value: str):
        """ value might be Title: Subtitle or just Title """
        components = value.split(":")
        self.title = components[0].strip()
        if len(components) > 1:
            self.subtitle = components[1].strip()
        
    def append_scene(self, scene: Scene):
        scene.set_chapter(self)
        self.scenes.append(scene)
    
    def reorder_scene(self, scene: Scene, earlier: bool):
        all_scenes = self.scenes
        idx = -1
        for scene_index, a_scene in enumerate(all_scenes):
            if scene == a_scene:
                idx = scene_index
                break
        if idx >= 0:
            if earlier and idx > 0:
                all_scenes[:] = all_scenes[0:idx-1] + all_scenes[idx:idx+1] + all_scenes[idx-1:idx] + all_scenes[idx+1:]
            elif not earlier and idx < len(all_scenes):
                all_scenes[:] = all_scenes[0:idx] + all_scenes[idx+1:idx+2] + all_scenes[idx:idx+1] + all_scenes[idx+2:]
            self.scenes = all_scenes

    def replace_scene(self, old_scene: Scene, new_scene: Scene):
        all_scenes = self.scenes
        idx = -1
        for scene_index, a_scene in enumerate(all_scenes):
            if old_scene == a_scene:
                idx = scene_index
                break
        if idx >= 0:
            all_scenes[:] = all_scenes[0:idx] + [new_scene] + all_scenes[idx+1:]
            self.scenes = all_scenes

    def to_markdown(self) -> str:
        """ Combines into a Markdown string for writing back to the source file. """
        markdown_strings: List[str] = [f'## {self.title}: {self.subtitle}']
        for scene in self.scenes:
            markdown_strings.append(scene.to_markdown())
        return "\n\n".join(markdown_strings)

    def compile(self) -> List[str]:
        """Combines all scenes into a list of Markdown strings for printing."""
        markdown_strings: List[str] = ['\\newpage', f'## Chapter {self.number}: {self.title}']
        if len(self.subtitle.strip()) > 0:
            markdown_strings.append(f'### {self.subtitle}')
        for scene in self.scenes:
            markdown_strings.extend(scene.compile())
            markdown_strings.append('***')
        # Remove the last scene break, b/c we've added one too many
        markdown_strings.pop()
        return markdown_strings

    def __eq__(self, other):
        """ Checks for equality of all ivars """
        if other is None:
            return False
        if not isinstance(other, Chapter):
            return False
        return self.title == other.title and \
               self.subtitle == other.subtitle

    def search(self, search_pattern) -> bool:
        try:
            text_to_search = [self.title, self.subtitle]
            for text in text_to_search:
                if re.search(search_pattern, text):
                    return True
            for scene in self.scenes:
                if scene.search(search_pattern):
                    return True
        except re.error as err:
            status_msg = "Regex message: {}".format(err)
            logging.debug("Error in Chapter.search for '%s': %s", search_pattern, status_msg)
        return False


########################################################################################
#
#       ######     #####     #####    ##   ##  
#      ##   ##   ##   ##   ##   ##   ## ##  
#     ######    ##   ##   ##   ##   ####   
#    ##   ##   ##   ##   ##   ##   ##  ##  
#   ######     #####     #####    ##   ##  
#
########################################################################################

class Book():
    """ Metadata about a book and an ordered list of chapters."""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, file_name=None):
        """
        Initializes all ivars, then parses the named file if passed.

        :param file_name: Absolute or relative file name of book_data JSON file.
        :type file_name: str, optional
        """
        self.__file_name = ""

        self.read_at = datetime.datetime.now() # Every time it is read from the md file, update

        self.__clear_ivars()

        if file_name is not None:
            self.__file_name = file_name
            self.open_file(file_name)

    def __clear_ivars(self):
        self.title = ""
        self.subtitle = ""
        self.author = ""
        self.year = ""
        self.keywords = []
        self.genres = []
        self.chapters = []
        self.characters = []

    def get_file_name(self) -> str:
        """ Accessor method for private ivar """
        return self.__file_name

    def path(self) -> str:
        """
        Convenience method that returns the path part of the book_data file name.
        :return: Book data file path
        :rtype: str
        """
        return os.path.dirname(self.__file_name)

    @classmethod
    def build_book_file_name(cls, book_path: str) -> str:
        return os.path.join(book_path, BOOK_DATA)

    @classmethod
    def is_book_path_valid(cls, book_path: str) -> bool:
        """
        Determines if a path points to a directory with a book data file in it.
        :param book_path: Absolute or relative path to directory.
        :type book_path: str
        :return: True if valid.
        :rtype: bool
        """
        if os.path.isdir(str(book_path)):
            book_data_file = Book.build_book_file_name(str(book_path))
            if os.path.isfile(book_data_file):
                # ok
                return True
            logging.info("%s is missing from directory %s", BOOK_DATA, book_path)
        else:
            logging.info("Directory %s doesn't exist", book_path)
        return False

    def set_title_subtitle(self, value: str):
        """ value might be Title: Subtitle or just Title """
        components = value.split(":")
        self.title = components[0].strip()
        if len(components) > 1:
            self.subtitle = components[1].strip()

    def append_chapter(self, new_chapter: Chapter):
        """ Adds the passed Chapter to the chapters list """
        new_chapter.set_book(self)
        self.chapters.append(new_chapter)
        # self.save_to_file()
    
    def reorder_chapter(self, chapter: Chapter, earlier: bool):
        """
        Finds the Chapter in the chapters list and moves it earlier or later
        in the Book. If it can't move further, nothing happens.
        """
        idx = self.chapters.index(chapter)
        if earlier and idx > 0:
            self.chapters[:] = self.chapters[0:idx-1] + self.chapters[idx:idx+1] + self.chapters[idx-1:idx] + self.chapters[idx+1:]
        elif not earlier and idx < len(self.chapters):
            self.chapters[:] = self.chapters[0:idx] + self.chapters[idx+1:idx+2] + self.chapters[idx:idx+1] + self.chapters[idx+2:]
        # self.save_to_file()

    def delete_chapter(self, chapter_to_delete: Chapter):
        """ Removes the passed Chapter from the Book """
        self.chapters.remove(chapter_to_delete)
        # self.save_to_file()

    def __renumber_chapters(self):
        """ Lets each Chapter know what ordinal it is in the Book """
        for (idx, chapter) in enumerate(self.chapters):
            chapter.number = idx
    
    def file_updated_since_read(self) -> bool:
        """
        Returns true if the Markdown file modification datetime is more recent
        than the time when it was read from disk. False otherwise.
        """
        modified_dt = datetime.datetime.fromtimestamp(os.path.getmtime(self.__file_name))
        # logging.debug("Book file read at %s", self.read_at)
        # logging.debug("Book file modified at %s", modified_dt)
        return modified_dt > self.read_at
    
    def guard_against_editing_modified_file(self):
        """ Call before any operation that would modify the in-memory Book """
        if self.file_updated_since_read():
            logging.exception("Attempt to save file when modified.")
            raise BookFileModifiedException

    def open_file(self, file_name: Optional[str] = None):
        """
        Opens the specified file and parses Markdown text. Populates self if successful.
        Passing no file_name causes the book to reopen and reparse its file.
        :param file_name: The absolute or relative book_data file name
        :type file_name: str
        """
        self.__clear_ivars()

        if file_name is None:
            file_name = self.__file_name

        try:
            with open(file_name) as markdown_file:
                markdown_text = markdown_file.read()
                self.load_from_markdown(markdown_text)
                self.read_at = datetime.datetime.now()
        except FileNotFoundError:
            logging.error("Could not open book data file %s", file_name)

    def reopen_file(self):
        """ Convenience method that calls open_file without a file_name argument. """
        assert self.__file_name != ""
        self.open_file()

    def load_from_markdown(self, markdown_text:str):
        """
        Uses the markdown-it library to tokenize the markdown text.
        :param markdown_text: The string containg the book's markdown content.
        :type markdown_text: str
        """
        md = MarkdownIt()
        tokens = md.parse(markdown_text)

        # Tokens are a stream. When we find one that flags something we are interested in, the
        # content is in the next token.
        # "heading_open": the title, or a chapter title
        # "paragraph_open": a new paragraph
        # "html_block": the HTML comments that have JSON metadata inside.
        # "inline": the content token that will follow the above tokens
        following_inline_content_is = None
        current_chapter = Chapter() # Placeholder value
        current_scene = Scene() # Placeholder value
        for token in tokens:
            if token.type == 'heading_open':
                if token.markup == '#':
                    following_inline_content_is = 'book_title'
                elif token.markup == '##':
                    following_inline_content_is = 'chapter_title'
            elif token.type == 'paragraph_open':
                following_inline_content_is = 'paragraph'
            elif token.type == 'html_block':
                header_dict = self.parse_json_header(token.content)
                if following_inline_content_is == 'book_info':
                    self.set_header(header_dict)
                    following_inline_content_is = None
                else:
                    current_scene = Scene()
                    current_scene.set_header(header_dict)
                    current_scene.start_line_number = token.map[0] + 1
                    current_chapter.append_scene(current_scene)
                    following_inline_content_is = None
            elif token.type == 'inline':
                if following_inline_content_is == 'book_title':
                    self.set_title_subtitle(token.content)
                    following_inline_content_is = 'book_info'
                elif following_inline_content_is == 'chapter_title':
                    current_chapter = Chapter()
                    current_chapter.set_title_subtitle(token.content)
                    current_chapter.start_line_number = token.map[0] + 1
                    self.append_chapter(current_chapter)
                    following_inline_content_is = 'scene_info'
                elif following_inline_content_is == 'paragraph':
                    current_scene.paragraphs.append(token.content)
                    following_inline_content_is = None
        self.__renumber_chapters()

    def parse_json_header(self, comment_content: str) -> Dict[str, Any]:
        """
        Takes the HTML comment block, strips the delimiters, and 
        then parses the content as JSON.
        """
        try:
            json_text = comment_content.replace("<!--", "").replace("-->", "")
            return json.loads(json_text)
        except json.decoder.JSONDecodeError:
            logging.error("Could not parse JSON from header %s", json_text)
        return {'error': 'JSON parser'}

    def set_header(self, header_dict: Dict[str, Any]):
        """
        Populates self with the contents of header_dict read from JSON
        """
        self.author = header_dict['author']
        self.year = header_dict['year']
        self.keywords = list(header_dict['keywords'])
        self.genres = list(header_dict['genres'])
        self.characters = []
        for ch_data in header_dict['characters']:
            self.characters.append(ch_data) # Just a name for now, but might include more later
    
    def to_markdown(self) -> str:
        """
        Returns the Book as a Markdown string, including the JSON
        metadata blocks. i.e. for saving, not exporting for PDF.
        """
        markdown_strings = [f"# {self.title}:{self.subtitle}"]
        markdown_strings.append(self.write_header())
        for chapter in self.chapters:
            markdown_strings.append(chapter.to_markdown())
        return "\n\n".join(markdown_strings)
        
    def save_to_file(self, file_name: Optional[str] = None, force: Optional[bool] = False):
        """
        Writes self to a markdown file with JSON metadata intact
        File is overwritten if it exists.
        If no file name is passed, the content is written back to the file it was read from.
        :param file_name: The book markdown file to write to.
        :type file_name: str, optional
        """
        if file_name is None:
            # Save
            file_name = self.__file_name
            logging.debug("Saving book to original file: %s", file_name)
            if not force:
                logging.debug("Checking that the file has not been modified.")
                self.guard_against_editing_modified_file()
        else:
            # Save As
            logging.debug("Saving book to new file %s", file_name)
            self.__file_name = file_name

        markdown_text = self.to_markdown()

        with open(file_name, "w") as books_file:
            books_file.write(markdown_text)

        self.read_at = datetime.datetime.now() # We updated the file: the content matches in memory
        self.__renumber_chapters()

    def write_header(self) -> str:
        """
        Outputs the :class:`booklib.Book` ivars to the JSON header format.
        """
        header_dict: Dict[str, Any] = {}
        header_dict['author'] = self.author
        header_dict['year'] = self.year
        header_dict['keywords'] = self.keywords
        header_dict['genres'] = self.genres
        header_dict['characters'] = self.characters
        json_text = json.dumps(header_dict, indent=2)
        return f"<!-- {json_text} -->"

    def compile(self) -> str:
        """
        Combines all chapters into a single Markdown string, suitable
        for printing. Metadata is stripped and breaks are added between Scenes.
        """
        markdown_content = [f'# {self.title}',
                            f'{self.subtitle}',
                            f'©{self.author}, {self.year}']
        for chapter in self.chapters:
            markdown_content.extend(chapter.compile())

        return "\n\n".join(markdown_content)

    def __eq__(self, other):
        """ Checks for equality by exporting to dict and comparing """
        if isinstance(other, Book):
            self_md = self.to_markdown()
            other_md = other.to_markdown()
            return self_md == other_md
        return False

    def search(self, search_pattern) -> bool:
        try:
            text_to_search = [self.title, self.subtitle]
            for text in text_to_search:
                if re.search(search_pattern, text):
                    return True
            for chapter in self.chapters:
                if chapter.search(search_pattern):
                    return True
        except re.error as err:
            status_msg = "Regex message: {}".format(err)
            logging.debug("Error in Book.search for '%s': %s", search_pattern, status_msg)
        return False

########################################################################################
#
#       ######     #####     #####    ##   ##      ######    ######   
#      ##   ##   ##   ##   ##   ##   ## ##        ##   ##   ##   ##  
#     ######    ##   ##   ##   ##   ####         ##   ##   ######    
#    ##   ##   ##   ##   ##   ##   ##  ##       ##   ##   ##   ##  
#   ######     #####     #####    ##   ##      ######    ######  
#
########################################################################################


class BookDatabase():
    """
    Encapsulates interactions with books.json
    """
    def __init__(self, file_name=None):
        """
        Initializes books list. If file name is passed, it is parsed an populates books list.
        """
        self.books = []
        self.__file_name = None
        if file_name is not None:
            self.open_file(file_name)

    def is_index_valid(self, index: int) -> bool:
        if index < 0:
            return False
        if index >= len(self.books):
            return False
        return True

    def index_of_book(self, book: Book) -> Optional[int]:
        try:
            book_index = self.books.index(book.path())
        except ValueError:
            return None
        return book_index

    def book(self, index: int) -> Optional[Book]:
        if self.is_index_valid(index):
            return Book(Book.build_book_file_name(self.books[index]))
        return None

    def all_books(self) -> List[Book]:
        ret_list = []
        for book_path in self.books:
            ret_list.append(Book(Book.build_book_file_name(book_path)))
        return ret_list
        
    def add_book(self, book_path: str, insert_first: bool = False):
        """
        Adds a book to the list.
        Checks that the book path is a directory with a book data file in it.
        :param book_path: Path to directory with book data.
        :type book_path: str
        :param insert_first: Inserts to the front of the book list if True.
        :type insert_first: bool, optional
        """
        if Book.is_book_path_valid(book_path):
            if insert_first:
                self.books.insert(0, book_path)
            else:
                self.books.append(book_path)
            # DB is changed, save file
            self.save_to_file()

    def remove_book(self, index: int, archive_path: str):
        """
        Removes a book from the list. Archives the contents before removing directory.
        :param index: Index of the book to remove.
        :type index: int
        :param archive_path: Directory path to save the archive file to.
        :type archive_path: str
        """
        if self.is_index_valid(index):
            book_path = self.books[index]
            if self.archive_book(index, archive_path) is not None:
                shutil.rmtree(book_path)
                del self.books[index]
                # DB is changed, save file
                self.save_to_file()

    def move_book(self, current_book_path:str, new_book_path: str, archive_path: str) -> bool:
        # Check if current_book_path is a valid book
        try:
            current_index = self.books.index(current_book_path)
        except ValueError:
            logging.error("move_book: could not find book at %s", current_book_path)
            return False
       # Make sure new_book_path is NOT a valid book (i.e. already exists)
        try:
            _ = self.books.index(new_book_path)
            logging.error("move_book: a book already exists at %s", new_book_path)
            return False
        except ValueError:
            pass
        # Check that the new location exists
        if os.path.isdir(new_book_path) == False:
            # Create the directory
            os.mkdir(new_book_path)
        # Archive the book before doing anything destructive
        if self.archive_book(current_index, archive_path) is None:
             logging.error("move_book: could not archive book at %s. Stopping.", current_book_path)
             return False
        # Copy the book directory contents
        copy_tree(current_book_path, new_book_path)
        # Remove the current directory
        shutil.rmtree(current_book_path)
        # Update the books list
        del self.books[current_index]
        self.books.insert(0, new_book_path)
        # DB is changed, save file
        self.save_to_file()
        return True

    def archive_book(self, index: int, archive_path: str) -> Optional[str]:
        """
        Zips the contents of the book directory and saves it to the archive.
        :param index: Index of the book to archive.
        :type index: int
        :param archive_path: Directory path to save the archive file to.
        :type archive_path: str
        :return: Archive file name if the archive was successful.
        :rtype: str, optional
        """
        if self.is_index_valid(index):
            book_path = self.books[index]
            if os.path.isdir(str(archive_path)):
                time_stamp = datetime.datetime.now().strftime("_%Y-%m-%d-%H-%M")
                archive_name = os.path.join(archive_path, os.path.basename(book_path) + time_stamp)
                created_archive = shutil.make_archive(archive_name, 'zip', book_path)
                logging.info("Archive created %s", created_archive)
                return archive_name + '.zip'
        return None

    def move_book_to_most_recent(self, idx: int):
        """Convenience method to rearrange a book to the front of the list"""
        if self.is_index_valid(idx):
            self.books[:] = self.books[idx:idx+1] + self.books[0:idx] + self.books[idx+1:]
            # DB is changed, save file
            self.save_to_file()

    def open_file(self, file_name: str):
        """
        Opens specified file and populates the books list.
        File is expected to be JSON with a "books" key with a list of directory names.
        Does a check to see if each directory appears to be a valid book.
        :param file_name: The books database JSON file.
        :type file_name: str
        """
        self.books = []
        self.__file_name = file_name
        book_path_list: List[str] = []
        try:
            with open(file_name) as books_file:
                json_text = books_file.read()
                db_dict = json.loads(json_text)
                book_path_list = list(db_dict["books"])
        except FileNotFoundError:
            logging.debug("Could not open file %s", file_name)
        for book_path in book_path_list:
            self.add_book(book_path)

    def save_to_file(self, file_name: Optional[str] = None):
        """
        Writes the list of books to the books database file
        """
        if file_name is None:
            # Save
            file_name = self.__file_name
        else:
            # Save As
            self.__file_name = file_name
        db_dict = {}
        db_dict["books"] = self.books
        json_text = json.dumps(db_dict)
        with open(file_name, "w") as books_file:
            books_file.write(json_text)

    def __eq__(self, other):
        """ Check for equality of book list. """
        return self.books == other.books

class BookFileModifiedException(Exception):
    pass

if __name__ == '__main__':
    print("booklib.py is not to be called directly.")
