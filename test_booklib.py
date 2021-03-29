#!/usr/bin/env python3

import os
import os.path
import subprocess
import booklib

# Parsing the list of books
book_db = booklib.BookDatabase('books.json')
name = os.path.join(book_db.books[1], booklib.BOOK_DATA)

# Parsing a book (for real: this is the first book in the book DB)
ff_book = booklib.Book(name)
assert len(ff_book.chapters) == 24, "Expected 24 chapters, got {}".format(len(ff_book.chapters))

# Switching to test data
test_book_name = os.path.join('/Users/sbiickert/OneDrive - Esri Canada/Code/PyBookBuilder', 'test_book.md')
test_book = booklib.Book(test_book_name)

def check_book(test_book: booklib.Book):
	# Checking the interpretation of the book header data
	author = 'Simon Biickert'
	assert test_book.author == author, 'Expected author to be {}, got {}'.format(author, test_book.author)
	title = 'Forbidden Forces'
	assert test_book.title == title, 'Expected title to be {}, got {}'.format(title, test_book.title)
	subtitle = 'A Nano Novel'
	assert test_book.subtitle == subtitle, 'Expected subtitle to be {}, got {}'.format(subtitle, test_book.subtitle)
	year = "2020"
	assert test_book.year == year, 'Expected year to be {}, got {}'.format(year, test_book.year)

	assert len(test_book.genres) == 2
	assert test_book.genres[0] == 'Fantasy'
	assert len(test_book.keywords) == 3
	assert test_book.keywords[2] == 'amazing'

	# Chapters
	assert len(test_book.chapters) == 24, "Expected 24 chapters, got {}".format(len(ff_book.chapters))

	prologue: booklib.Chapter = test_book.chapters[0]
	assert prologue.word_count() == 1624
	assert prologue.scenes[0].word_count() == 1624

	chapter_one: booklib.Chapter = test_book.chapters[1]
	assert chapter_one.title == 'Acolyte'
	assert chapter_one.subtitle == 'Age Seven'
	assert len(chapter_one.scenes) == 2

	# Reading scene header
	library_scene: booklib.Scene = chapter_one.scenes[1]
	assert library_scene.description == "Jerin meets Nessa in the library"
	assert library_scene.location == "Victoria, Temple, Library"
	assert library_scene.pov == "Jerin"
	assert library_scene.status == "Good"
	print(library_scene.description)

	# Scene paragraphs
	assert len(library_scene.paragraphs) == 58
	assert library_scene.word_count() == 3144

	# Characters
	assert len(test_book.major_characters) == 8
	assert test_book.major_characters[0].name == "Jerin N'patri"
	assert test_book.major_characters[3].name == 'Levifid'
	library_chars = library_scene.get_characters()

	assert test_book.major_characters[0] in library_chars
	assert test_book.major_characters[3] not in library_chars

	junkers_chapter:booklib.Chapter = test_book.chapters[9]
	assert junkers_chapter.title == "All Clear"
	junker_chars = junkers_chapter.get_characters()
	assert test_book.major_characters[0] not in junker_chars
	assert test_book.major_characters[3] in junker_chars
	assert test_book.minor_characters[7] in junker_chars

	# Compiling to Markdown
	md_string = ff_book.compile()
	assert len(md_string) > 0

check_book(test_book)

# Saving a book
test_file_name = os.path.join(test_book.path(), 'test_output_book.md')
test_book.save_to_file(test_file_name)
test_book_copy = booklib.Book(test_file_name)

check_book(test_book_copy)
assert test_book_copy == test_book

# Check if the file on disk has been modified since opening
assert test_book_copy.file_updated_since_read() == False
subprocess.run(["touch", test_file_name], check=True)
assert test_book_copy.file_updated_since_read() == True

# Reorder chapters
assert test_book_copy.chapters[1].title == 'Acolyte'
assert test_book_copy.chapters[2].title == 'Blood Friends'
test_book_copy.reorder_chapter(test_book_copy.chapters[1], False)
assert test_book_copy.chapters[2].title == 'Acolyte'
assert test_book_copy.chapters[1].title == 'Blood Friends'
test_book_copy.reorder_chapter(test_book_copy.chapters[2], True)
assert test_book_copy.chapters[1].title == 'Acolyte'
assert test_book_copy.chapters[2].title == 'Blood Friends'

# Reorder scenes in chapter
chapter_one: booklib.Chapter = test_book_copy.chapters[1]
assert chapter_one.scenes[0].description == "Eyes in the Hallows"
assert chapter_one.scenes[1].description == "Jerin meets Nessa in the library"
chapter_one.reorder_scene(chapter_one.scenes[0], False)
assert chapter_one.scenes[1].description == "Eyes in the Hallows"
assert chapter_one.scenes[0].description == "Jerin meets Nessa in the library"
chapter_one.reorder_scene(chapter_one.scenes[1], True)
assert chapter_one.scenes[0].description == "Eyes in the Hallows"
assert chapter_one.scenes[1].description == "Jerin meets Nessa in the library"

# Analyze scene
scene_to_analyze: booklib.Scene = test_book_copy.chapters[4].scenes[0]
assert scene_to_analyze.has_analytics() == False
assert scene_to_analyze.has_markup() == False
word_count = scene_to_analyze.word_count()
scene_to_analyze.analyze()
assert scene_to_analyze.has_analytics() == True
assert scene_to_analyze.has_markup() == True
assert scene_to_analyze.analytic_info['ttr'] > 0.0
assert scene_to_analyze.analytic_info['fres'] > 0.0
# print(scene_to_analyze.to_markdown())
scene_to_analyze.clear_markup()
assert scene_to_analyze.has_analytics() == True
assert scene_to_analyze.has_markup() == False

assert scene_to_analyze.word_count() == word_count

os.remove(test_file_name)

exit(0)

# Ran these tests August 15, 2020. Passed. Further testing not needed.

# Saving the book database
test_file_name = 'test_db.json'
book_db.save_to_file(test_file_name)
test_db = booklib.BookDatabase(test_file_name)
assert book_db == test_db
os.remove(test_file_name)

# Archive a book
archive_path = '/Users/sbiickert/Dropbox/OurFolder/Simon Writer/PyBookBuilder Archive'
zip_file = book_db.archive_book(0, archive_path)
assert zip_file is not None

# Move a book
orig_path = ff_book.path()
dest_path = '/Users/sbiickert/Temp/Test Book'
assert book_db.move_book(orig_path, dest_path, archive_path)

# Move it back
os.mkdir(orig_path) # Was deleted during move
assert book_db.move_book(dest_path, orig_path, archive_path)

