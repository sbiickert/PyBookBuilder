#!/usr/bin/env python3

from markdown_it import MarkdownIt

END_LINE = "\n\n"

md_file = open("test_book.md")
md_text = md_file.read()
md_file.close()

md = MarkdownIt()
tokens = md.parse(md_text)

print(tokens)
exit(0)

out_file = open("test.md", "w")

next_token_is = ""
for token in tokens:
	if token.type == 'heading_open':
	    if token.markup == '#':
	        # Book title
	        print("Book Start")
	        next_token_is = 'book_title'
	    elif token.markup == '##':
	        # Chapter title
	        print("Chapter Start")
	        next_token_is = 'chapter_title'
	        
	elif token.type == 'paragraph_open':
	    next_token_is = 'paragraph'
	    
	elif token.type == 'html_block':
	    if next_token_is == 'book_info':
	        #print("Book info JSON in HTML comment")
	        next_token_is = ''
	    else:
	        #print("Scene info JSON in HTML comment")
	        next_token_is = ''
	    out_file.write(token.content + END_LINE)
	    
	elif token.type == 'inline':
	    # Content of the block
	    if next_token_is == 'book_title':
	        print(f'Book Title is {token.content}')
	        out_file.write("# " + token.content + END_LINE)
	        next_token_is = 'book_info'
	    elif next_token_is == 'chapter_title':
	        print(f'Chapter Title is {token.content}')
	        next_token_is == 'scene_info'
	        out_file.write("## " + token.content + END_LINE)
	    elif next_token_is == 'paragraph':
	        #print(f'{token.content[0:20]}...')
	        next_token_is = ''
	        out_file.write(token.content + END_LINE)

print("End")
out_file.close()