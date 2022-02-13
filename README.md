# PyBookBuilder
 Python terminal app that allows structured editing of markdown novels

## Project Status

This project is paused. I have shifted to making a native MacOS application called [BookFramer](https://github.com/sbiickert/BookFramer). If you would like to make contributions, I will do my best to help you out, but I am not skilled with GitHub.

## What is it?

- I write novels.
- I like Markdown for text.
- I wanted to leverage my favorite text editor while adding metadata and big-picture structure management.

![Book Structure](https://github.com/sbiickert/PyBookBuilder/blob/main/ScreenShots/PyBookBuilder_Book_Structure.png)

In short, if you have a novel-like Markdown file that can extend to hundreds of thousands of words, this application works with JSON metadata that is embedded at the top of each section to add some intelligence. The JSON is in HTML comment tags that are automatically invisible when viewed, so the preview only shows the book content, titles, chapters, etc.

There is a master list of characters for the novel, and that allows PyBookBuilder to dynamically generate lists of what characters appear where in the book.

![Scene Info](https://github.com/sbiickert/PyBookBuilder/blob/main/ScreenShots/PyBookBuilder_Scene_Info.png)

There is Regex searching of the content, the ability to rearrange sections, add new sections, etc.

![Sample Help Screen](https://github.com/sbiickert/PyBookBuilder/blob/main/ScreenShots/PyBookBuilder_Help_Structure.png)

When you want to write or edit, select the scene and hit Enter. The document opens in your configured text editor, scrolled to the scene. I personally work on a Mac using BBEdit, although I have done some preliminary testing with vim. As long as your text editor can open from the command line with a file name and a line number to jump to, it should work.

## Dependencies

I use conda to manage the python virtual environment. There is an environment.yml file in the repo that can be used to rebuild the environment to run PyBookBuilder. The key dependencies are:

1. [npyscreen](https://npyscreen.readthedocs.io): widget library built on top on ncurses
2. [markdown-it-py](https://pypi.org/project/markdown-it-py/): Markdown parser/tokenizer
3. [nltk](https://www.nltk.org): Natural language toolkit used to evaluate grammar
4. [pandoc](https://pandoc.org): Universal document converter. To turn markdown into PDF.

Thanks for looking. Drop me a note if you find this useful.
