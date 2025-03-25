#!/usr/bin/env python3

# BGI script inserter

import glob
import os
import re
import struct
import sys

import bgi_common
import bgi_setup

re_line = re.compile(r'<(\d+?)>(.*)')

def get_text(file, language):
    re_line = re.compile(r'<(\w\w)(\w)(\d+?)>(.*)')
    texts = {}
    
    for line in file:
        line = line.rstrip('\n')
        match = re_line.match(line)
        if match:
            lang, marker, id_str, text = match.groups()
            id_num = int(id_str)
            if lang == language:
                record = (marker, id_num)
                texts[record] = bgi_common.unescape(text)
    
    return texts

def insert_unique(code_bytes, code_section, texts, text_bytes, marker):
    text_dict = {}
    code_size = len(code_bytes)
    offset = len(text_bytes)
    
    for addr in sorted(code_section):
        text, id_num, code_marker, comment = code_section[addr]
        if code_marker == marker:
            if text in text_dict:
                _, _, doffset = text_dict[text]
                code_bytes[addr:addr + 4] = struct.pack('<I', doffset + code_size)
            else:
                new_text = texts.get((code_marker, id_num), text)  # Use original text if not found
                new_bytes = new_text.encode(bgi_setup.ienc, errors='replace') + b'\x00'  # Handle encoding issues
                text_bytes.extend(new_bytes)
                text_dict[text] = (code_marker, id_num, offset)
                code_bytes[addr:addr + 4] = struct.pack('<I', offset + code_size)
                offset += len(new_bytes)
    
    return text_bytes

def insert_sequential(code_bytes, code_section, texts, text_bytes, marker):
    code_size = len(code_bytes)
    offset = len(text_bytes)
    
    for addr in sorted(code_section):
        text, id_num, code_marker, comment = code_section[addr]
        if code_marker == marker:
            new_text = texts.get((code_marker, id_num), text)  # Use original text if not found
            new_bytes = new_text.encode(bgi_setup.ienc, errors='replace') + b'\x00'  # Handle encoding issues
            text_bytes.extend(new_bytes)
            code_bytes[addr:addr + 4] = struct.pack('<I', offset + code_size)
            offset += len(new_bytes)
    
    return text_bytes

def insert_script(out_dir, script, language):
    with open(script, 'rb') as file:
        data = file.read()
    
    hdr_bytes, code_bytes, text_bytes, config = bgi_common.split_data(data)
    text_section = bgi_common.get_text_section(text_bytes)
    code_section = bgi_common.get_code_section(code_bytes, text_section, config)

    # Open script for reading text
    with open(script + bgi_setup.dext, 'r', encoding=bgi_setup.denc) as text_file:
        texts = get_text(text_file, language)

    code_bytes = bytearray(code_bytes)
    text_bytes = bytearray(text_bytes)  # Ensure text_bytes is a bytearray

    # Insert names, text, and other
    text_bytes = insert_unique(code_bytes, code_section, texts, text_bytes, 'N')  # names
    text_bytes = insert_sequential(code_bytes, code_section, texts, text_bytes, 'T')  # text
    text_bytes = insert_unique(code_bytes, code_section, texts, text_bytes, 'Z')  # other

    # Write output
    with open(os.path.join(out_dir, os.path.split(script)[1]), 'wb') as output_file:
        output_file.write(hdr_bytes)
        output_file.write(code_bytes)
        output_file.write(text_bytes)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: bgi_insert.py <out_dir> <file(s)>')
        print("(<out_dir> will be created if it doesn't exist)")
        print('(only extension-less files amongst <file(s)> will be processed)')
        sys.exit(1)

    out_dir = sys.argv[1]

    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    for arg in sys.argv[2:]:
        for script in glob.glob(arg):
            base, ext = os.path.splitext(script)
            if not ext and os.path.isfile(script):
                print(f'Inserting {script}...')
                insert_script(out_dir, script, bgi_setup.ilang)
