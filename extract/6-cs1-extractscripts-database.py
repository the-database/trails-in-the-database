import re, os, csv, sys, struct, operator

vita_jpn_path = './cs1-scena/'
pc_eng_path = './cs1-scena/'
jpn_encode = 'cp932'
eng_encode = 'utf8'

displaytbl = []
displaytbl2 = {}
footer = {}

# remove all lines which contain any of the following strings
blacklist_contains = []

# remove all lines which start with any of the following strings
blacklist_startswith = []

# remove all lines which end with any of the following strings
blacklist_endswith = []

blacklist_contains_test = []
blacklist_startswith_test = []
blacklist_endswith_test = []

translatorEng = str.maketrans('', '', '"#$%&\'()*+,-/:;<=>@[\\]^_`{|}~ \n\x7f')
translatorJpn = str.maketrans('', '',
                              '!"#$%&\'()*+,-/:;<=>?@[\\]^_`{|}~ '
                              '\n.\x7f')

testTranslator = str.maketrans('', '', '!"#$%&\'()*+,-/:;<=>?@[\\]^_`{|}~ \n0987654321')


def goodLenEng(string):
    strings = string.split('\n')
    return max([len(re.sub(r'<<.+?>>', '', s.translate(translatorEng))) for s in strings])
    # return len(string.translate(translatorEng))


def goodLenJpn(string):
    strings = string.split('\n')
    return max([len(re.sub(r'<<.+?>>', '', s).translate(translatorJpn)) for s in strings])
    # return len(string.translate(translatorJpn))


def testLenJpn(string):
    strings = string.split('\n')
    return max([len(s.translate(translatorJpn)) for s in strings])


total_delta = 0
total_jpn = 0
total_eng = 0


# def parse_obj(fs):
#
#     while True:
#         char = fs.read(1)
#
#         if char == b'\x00':
#             return None
#         if char == b'\x5d':
#             fs.read(1)
#             name = parse_str(fs)
#             fs.read(1)
#             return char, name
#         elif char == b'\x05':
#             fs.read(8)
#             return char, None
#         elif char == b'\x13':  # NPC
#             fs.read(2)
#             parse_str(fs)
#             name = parse_str(fs)
#             fs.read(35)
#             parse_str(fs)
#             fs.read(14)
#             return char, name
#         elif char == b'\x2f':
#             fs.read(3)
#             name = parse_str(fs)
#             return char, name
#         elif char == b'\x2b':
#             fs.read(5)
#             return char, None
#         elif char == b'\x2c':
#             fs.read(5)
#             return char, None
#         elif char == b'\x20':
#             fs.read(3)
#             parse_str(fs)
#             name = parse_str(fs)
#             return char, name
#         else:
#             print(fs.tell())
#             exit(char)


def get_npc_table(path, encode):
    npcs = []

    with open(path, 'rb') as f:
        # junk = f.read(32)
        junk = f.read(20)
        num_things = struct.unpack('<I', f.read(4))[0]
        junk = f.read(8)
        fname = parse_str(f)
        # junk = f.read(12)

        positions = [struct.unpack('<I', f.read(4))[0] for _ in range(num_things)]

        print(num_things)

        num = 0

        for pos in positions:
            f.seek(pos)

            stuff = f.read(100)

            print(num, '%08X' % pos, stuff)
            num += 1

        # while True:
        #     obj = parse_obj(f)
        #     if obj:
        #         print(hex(obj[0][0]), obj[1])
        # obj_type = f.read(1)
        # try:
        #     print(path, hex(obj_type[0]))
        # except IndexError:
        #     pass
        # npc = parse_str(f)
        # junk = f.read(2)

    return npcs


def get_talk_npcs():
    files = ['c0010.dat', 'c0310.dat', 'm0530.dat', 'm2500.dat', 'm3001.dat', 'm3008.dat', 't0000.dat', 't0000b.dat',
             't0000c.dat', 't0010.dat', 't0020.dat', 't0031.dat', 't0032.dat', 't0050.dat', 't0060.dat', 't0070.dat',
             't0080.dat', 't0090.dat', 't0200.dat', 't0201.dat', 't1000.dat', 't1010.dat', 't1020.dat', 't1030.dat',
             't1040.dat', 't1050.dat', 't1060.dat', 't1080.dat', 't1090.dat', 't1110.dat', 't1120.dat', 't1150.dat',
             't1160.dat', 't3510.dat', 't3550.dat']

    eng_talk_npcs = {}
    jpn_talk_npcs = {}

    result = {}

    for fname in files:
        with open(os.path.join(vita_jpn_path, 'scena/dat/', fname), 'rb') as f_jpn, \
                open(os.path.join(vita_jpn_path, 'scena/dat_us/', fname), 'rb') as f_eng:

            # print(fname)

            all_bytes_jpn = f_jpn.read()
            all_bytes_eng = f_eng.read()

            search = rb'\x13[\s\S]{2}([^\x00\xff]+?)\x00([^\x00\xff]+?)\x00[\s\S]{35}TK_[^\x00\xff]+?\x3a(tk_[^\x00\xff]+?)\x00'

            jpn_talks = [m for m in re.finditer(search, all_bytes_jpn)]
            eng_talks = [m for m in re.finditer(search, all_bytes_eng)]

            for m in eng_talks:
                # print(m.group(3), m.group(2), m.group(1), m.group(0))
                if m.group(3).decode(eng_encode) not in eng_talk_npcs:
                    eng_talk_npcs[m.group(3).decode(eng_encode)] = {}

                if m.group(2).decode(eng_encode) not in eng_talk_npcs[m.group(3).decode(eng_encode)]:
                    eng_talk_npcs[m.group(3).decode(eng_encode)][m.group(2).decode(eng_encode)] = 0

                eng_talk_npcs[m.group(3).decode(eng_encode)][m.group(2).decode(eng_encode)] += 1

            for m in jpn_talks:
                if m.group(3).decode(jpn_encode) not in jpn_talk_npcs:
                    jpn_talk_npcs[m.group(3).decode(jpn_encode)] = {}

                if m.group(2).decode(jpn_encode) not in jpn_talk_npcs[m.group(3).decode(jpn_encode)]:
                    jpn_talk_npcs[m.group(3).decode(jpn_encode)][m.group(2).decode(jpn_encode)] = 0

                jpn_talk_npcs[m.group(3).decode(jpn_encode)][m.group(2).decode(jpn_encode)] += 1

    for fname, thing in eng_talk_npcs.items():
        # print(fname, thing)
        result[fname] = {'eng': max(thing.items(), key=operator.itemgetter(1))[0]}
        # print(fname,

    for fname, thing in jpn_talk_npcs.items():
        # print(fname, thing)
        # print(fname, )
        result[fname]['jpn'] = max(thing.items(), key=operator.itemgetter(1))[0]

    return result


def get_npc_name(index, all_bytes, encode, fname, text):
    search = rb'\x13' + re.escape(index) + rb'([^\x00]+?)\x00([^\x00]+?)\x00'
    matches = [m for m in re.finditer(search, all_bytes)]
    names = []
    for m in matches:
        try:
            name = m.group(2).strip()
            if len(name) > 0:
                names.append(name.decode(encode))
        except UnicodeDecodeError:
            print("WARNING NPC DECODE FAILED")
            pass
    if len(set(names)) != 1:
        print(fname, "WARNING NORMAL NPC LOOKUP WEIRDNESS", "%04X" % struct.unpack('<H', index)[0], index, len(names), names, text.replace('\n', '<br/>'))
    if len(names) > 0:
        return names.pop()

    return ''


def get_npc_name_by_func_name_direct(all_bytes_by_func, func_names, func_index, encode, fname, text):
    all_bytes = b''.join(all_bytes_by_func[:func_index])
    func_name = func_names[func_index]
    search = rb'\x13[\s\S]{2}([^\x00]+?)\x00([^\x00]+?)\x00([\s\S]{35})' + re.escape(func_name)
    matches = [m for m in re.finditer(search, all_bytes)]
    names = []
    for m in matches:
        try:
            name = m.group(2).strip().decode(encode)
            if len(name) > 0:
                if name not in names:
                    names.append(name)
                    # print(name.decode(encode))
                    # print(("%02X " * 35) % struct.unpack('B' * 35, m.group(3)))
        except UnicodeDecodeError:
            print("WARNING NPC DECODE FAILED")
            pass

    # if len(set(names)) != 1:
    #     print(fname, "WARNING FUNC NPC LOOKUP WEIRDNESS", func_name, len(names), names, text.replace('\n', '<br/>'))

    return names


def get_calling_funcs(all_bytes_by_func, func_names, func_index):
    calling_funcs = [i for i in range(len(func_names)) if re.search(b'\x02[\x0b\x00]' + func_names[func_index] + b'\x00', all_bytes_by_func[i])]
    for calling_func_index in calling_funcs:
        calling_funcs += get_calling_funcs(all_bytes_by_func, func_names, calling_func_index)

    return calling_funcs


def get_npc_name_by_func_name(all_bytes_by_func, func_names, func_index, encode, fname, text):

    func_name = func_names[func_index]
    names = get_npc_name_by_func_name_direct(all_bytes_by_func, func_names, func_index, encode, fname, text)

    # couldn't find NPC mapped directly to this func, so check all funcs which called this func instead
    if len(names) == 0:
        calling_funcs = get_calling_funcs(all_bytes_by_func, func_names, func_index)
        # print('calling funcs for', func_name, [func_names[i] for i in calling_funcs])
        for calling_func_index in calling_funcs:
            names += get_npc_name_by_func_name_direct(all_bytes_by_func, func_names, calling_func_index, encode, fname, text)

    if len(set(names)) != 1:
        print(fname, "WARNING FUNC NPC LOOKUP WEIRDNESS", func_name, len(names), names, text.replace('\n', '<br/>'))
    if len(names) > 0:
        return names.pop()

    return ''


def get_voices_jpn():
    voices = {}

    with open('cs1-text/dat/t_voice.tbl', 'rb') as f:
        num_voices = struct.unpack('<H', f.read(2))[0]  # size

        # junk = f.read(0xe)

        while len(voices) < num_voices:
            junk = parse_str(f)  # voice

            if len(junk) == 0:
                break

            voice_size = struct.unpack('<H', f.read(2))[0]  # size
            voice_code = struct.unpack('<H', f.read(2))[0]
            # junk = f.read(1)

            remainder = f.read(voice_size - 2)
            strings = remainder.split(b'\x00')
            voices[voice_code] = strings[0].decode(jpn_encode)

    return voices


def get_items(path, encode):
    items = {}

    with open(path, 'rb') as f:
        size = struct.unpack('<H', f.read(2))[0]

        while len(items) < size:
            parse_str(f)  # "item"
            f.read(2)  # junk
            item_code = struct.unpack('<H', f.read(2))[0]
            f.read(2)  # junk
            parse_str(f)  # flags string "SLCBPM"
            f.read(46)  # junk

            item_name = parse_str(f)
            item_desc = parse_str(f)

            # items.append(item_name)
            items[item_code] = item_name

    return items


def get_items_jpn():
    return get_items('./cs1-text/dat/t_item.tbl', jpn_encode)


def get_items_eng():
    return get_items('./cs1-text/dat_us/t_item.tbl', eng_encode)


def get_names(path, encode):
    names = {}

    with open(path, 'rb') as f:
        size = struct.unpack('<H', f.read(2))[0]

        while True:
            junk = f.read(16)

            if len(junk) == 0:
                break

            index = struct.unpack('<H', f.read(2))[0]

            name = parse_str(f)

            junk = parse_str(f)
            junk = parse_str(f)
            junk = parse_str(f)
            junk = parse_str(f)
            junk = parse_str(f)

            # print('ok', size, name.decode(jpn_encode))

            if index in names:
                new_name = name.decode(jpn_encode)
                if len(new_name) < len(names[index]):
                    names[index] = new_name
                # print('collision:', hex(index),  names[index])
            else:
                names[index] = name.decode(jpn_encode)

    return names


def get_names_jpn():
    return get_names('./cs1-text/dat/t_name.tbl', jpn_encode)


def get_names_eng():
    return get_names('./cs1-text/dat_us/t_name.tbl', eng_encode)


def parse_num_code(fs):
    '''
    rb'#4C##0T|#2#M0|#0T|#\d?K|#\d?P|#E\[[\dEFGHCLKIJADBM]\]|#F|'
    rb'#\d*S|#\d?C|#\d*?R.+?#|'
    rb'#E\d|#M\d|#M\[[\dABGEZ]\]|#\d+W|#MA|#E[EFIJ]|#\d+I|#\d+y|#e\[[\dG]\]|'
    rb'#M\[\[autoM0\]\]|#M\[\[autoM[\d]\]\]|#H\[[\d]\]|#H\d|#\d+c|#\d?T|'
    rb'#M\[0\[autoM0\]\]|#\d+G|#E\[\d+\]|#M\[\[autoMA\]\]'
    '''
    result = []

    while True:

        char = fs.read(1)

        if not char:
            break

        if char == b'':
            pass

    return b''.join(result)


def parse_str_with_voice(fs, is_jpn=False):
    global items_eng, items_jpn, voices_jpn
    result = []
    voice_files = []

    while True:
        char = fs.read(1)

        if not char:
            break

        # Voice BBBB
        if char == b'\x11':
            voice_code = struct.unpack('<H', fs.read(2))[0]  # voice index
            fs.read(2)  # junk?
            if voice_code not in voices_jpn:
                pass
            #     print('BAD VOICE CODE', b''.join(result))
            else:
                voice_files.append(voices_jpn[voice_code])
        # Item BB
        elif char == b'\x10':
            item_code = struct.unpack('<H', fs.read(2))[0]  # item index

            # invalid item code
            if item_code not in items_eng:
                if item_code == 9998:
                    result.append(b'<<0x270e>>')
                else:
                    # print("BAD ITEM CODE", item_code, b''.join(result))
                    return None, []
            else:
                if is_jpn:
                    result.append(b"<<%s>>" % items_jpn[item_code])
                else:
                    result.append(b"<<%s>>" % items_eng[item_code])
        # start green color text
        elif char == b'\x07':
            pass
        # start red color text
        elif char == b'\x0c':
            pass
        elif char == b'\x00':
            break
        # elif char == b'#':
        #     num_code = parse_num_code(fs)
        elif char == b'\xff':
            return None, []  # invalid string?
        else:
            result.append(char)

    return b''.join(result), voice_files


def parse_str(fs, is_jpn=False):
    parsed_str, voice_files = parse_str_with_voice(fs, is_jpn)
    return parsed_str


def valid_param(op, param):
    # return True  # TODO
    if op == b'\x1a':
        # return param in [b'\xfe\xff', b'\xff\xff']
        # return param != '\x00\x00'
        return True
    elif op == b'\x18':
        # return param.endswith(b'\x00\x00')
        return True
    # elif op == b'\x1d':
    #     return True
    return False


def valid_text(op, text):
    if text is not None:
        if op in (b'\x1a', b'\x18'):
            if text.endswith(b'\x02'):
                if True in [black.encode(jpn_encode) in text for black in blacklist_contains_test]:
                    print('skip', text.decode(jpn_encode))
                # if text.endswith(b'\x02\x02'):
                #     return False
                return True not in [black.encode(jpn_encode) in text for black in blacklist_contains]
        elif op == b'\x1d':
            return re.search(rb'[\x00-\x1f]', text) is None
    return False


def get_func_positions(fs):
    junk = fs.read(20)
    num_funcs = struct.unpack('<I', fs.read(4))[0]
    junk = fs.read(8)
    fname = parse_str(fs)

    func_positions = [struct.unpack('<I', fs.read(4))[0] for _ in range(num_funcs)]
    func_name_positions = [struct.unpack('<H', fs.read(2))[0] for _ in range(num_funcs)]

    func_names = []

    for pos in func_name_positions:
        fs.seek(pos)
        func_names.append(parse_str(fs))

    return func_positions, func_names


def parse_file(fs, func_positions, encode):
    all_parts = []

    # func_positions, func_names = get_func_positions(fs)
    # func_positions.sort()

    for i in range(len(func_positions)):

        parts = []

        fs.seek(func_positions[i])

        op_params = {
            # ChrTalk BB STR
            b'\x1a': 2,
            # AnonymousTalk BB STR
            b'\x18': 2,
            # SetChrName STR (???)
            b'\x1d': 0,
        }

        last_set_chr_name = b''

        while True:
            op = fs.read(1)

            if not op or (i + 1 < len(func_positions) and fs.tell() > func_positions[i + 1]):
                break

            if op in op_params:
                curr_pos = fs.tell()
                param = fs.read(op_params[op])
                text, voice_files = parse_str_with_voice(fs, encode == jpn_encode)

                if op == b'\x1d' and valid_text(op, text):
                    try:
                        text.decode(encode)
                        param2 = fs.read(2)
                        # print('SetChrNameTest', text.decode(encode), fs.read(2))  # test
                        if param2 == b'\xfd\xff':
                            last_set_chr_name = text
                    except UnicodeDecodeError:
                        pass

                if valid_param(op, param) and valid_text(op, text):
                    parts.append((op, param, text, curr_pos, last_set_chr_name, voice_files))
                else:
                    fs.seek(curr_pos)

        # if len(parts) > 0:
        all_parts.append(parts)

    return all_parts


def get_all_bytes_by_func(fs, func_positions):
    all_bytes = fs.read()
    fs.seek(0)

    # func_positions, func_names = get_func_positions(fs)
    # func_positions.sort()

    partitioned = [all_bytes[i:j] for i, j in zip([0] + func_positions, func_positions + [None])]
    del partitioned[0]

    return partitioned


def apply_ruby(text, fname=None, second_attempt=False):
    rubyJpnLines = [line for line in text.split(b'\x02\x03')]

    for j in range(len(rubyJpnLines)):
        rubyMatches = [m for m in re.finditer(br'#(\d+)R(.+?)(#)', rubyJpnLines[j])]
        for m in reversed(rubyMatches):

            end_index = m.start(1) - 1
            start_index = end_index - int(m.group(1))

            if second_attempt:
                # WARNING sen 1 hack
                if fname == 't0000' and int(m.group(1)) == 3:
                    start_index += 1
                else:
                    start_index -= 1

            main_text = rubyJpnLines[j][start_index:end_index]
            extra_text = m.group(2)
            rubyJpnLines[j] = rubyJpnLines[j][:start_index] + b'<ruby>%s<rt>%s</rt></ruby>' % (
                main_text, extra_text) + rubyJpnLines[j][(m.start(3) + 1):]
            if int(m.group(1)) % 2 == 1:
                # print('odd ruby')
                try:
                    rubyJpnLines[j].decode(jpn_encode)
                    # if second_attempt:
                    #     print('second attempt ruby result', rubyJpnLines[j].decode(jpn_encode))
                except UnicodeDecodeError:
                    # print('failed result', text.decode(jpn_encode))
                    if not second_attempt:
                        return apply_ruby(text, fname, True)

                    raise UnicodeDecodeError

    return b'\x02\x03'.join(rubyJpnLines)


def apply_voice_codes(text, voice_files):
    if len(voice_files) == 0:
        return text

    lines = text.split('\n\n')

    # print('lens', len(lines), len(voice_files))

    new_lines = []

    for i in range(len(lines)):
        if i < len(voice_files) and not voice_files[i].startswith('pc'):
            new_lines.append(
                f'<audio id="{voice_files[i]}"><source src="talk/6/{voice_files[i]}.ogg" '
                f'type="audio/ogg; codecs=vorbis"></audio><a href="javascript:void(0)" '
                f'onclick="document.getElementById(\'{voice_files[i]}\').play()">{lines[i]}</a>'
            )
        else:
            new_lines.append(lines[i])

    return '\n\n'.join(new_lines)


def strip_text(text_bytes, encode):
    return re.sub(rb'#4C##0T|#2#M0|#0T|#\d?K|#\d?P|#E\[[\dEFGHCLKIJADBM]\]|#F|'
                  rb'#\d*S|#\d?C|#\d*?R.+?#|'
                  rb'#E\d|#M\d|#M\[[\dABGEZ]\]|#\d+W|#MA|#E[EFIJ]|#\d+I|#\d+y|#e\[[\dG]\]|'
                  rb'#M\[\[autoM0\]\]|#M\[\[autoM[\d]\]\]|#H\[[\d]\]|#H\d|#\d+c|#\d?T|'
                  rb'#M\[0\[autoM0\]\]|#\d+G|#E\[\d+\]|#M\[\[autoMA\]\]', b'',
                  re.sub(rb'[\x00-\x09\x0b-\x1f]+', b' ',
                         text_bytes.replace(b'\x01', b'\n').replace(b'\x02\x03', b'\n\n').replace(b'\\n', b'\n'))) \
        .decode(encode).strip()


def sanitize_item_text(text_str):
    return text_str.replace('<<', '').replace('>>', '')


def do_everything2(jpn_subpath, eng_subpath, fname):
    global total_delta, total_jpn, total_eng, names_eng, names_jpn, talk_npcs

    if fname.endswith('.dat'):
        with open(os.path.join(vita_jpn_path, jpn_subpath, fname), 'rb') as f_jpn, open(
                os.path.join(pc_eng_path, eng_subpath, fname), 'rb') as f_eng:

            fname = os.path.splitext(fname)[0]

            displaytbl2[fname] = []

            rownum = 1

            all_stripped_jpn = []
            all_stripped_eng = []

            all_eng_bytes = f_eng.read()
            f_eng.seek(0)
            eng_func_positions, eng_func_names = get_func_positions(f_eng)
            f_eng.seek(0)
            all_eng_bytes_by_func = get_all_bytes_by_func(f_eng, eng_func_positions)
            f_eng.seek(0)

            all_jpn_bytes = f_jpn.read()
            f_jpn.seek(0)
            jpn_func_positions, jpn_func_names = get_func_positions(f_jpn)
            f_jpn.seek(0)
            all_jpn_bytes_by_func = get_all_bytes_by_func(f_jpn, jpn_func_positions)
            f_jpn.seek(0)

            all_eng_parts = parse_file(f_eng, eng_func_positions, eng_encode)
            all_jpn_parts = parse_file(f_jpn, jpn_func_positions, jpn_encode)

            good_params = {
                b'\x1a': set(),
                b'\x18': set()
            }

            for jpn_scene_num in range(len(all_jpn_parts)):
                for jpn_part in all_jpn_parts[jpn_scene_num]:
                    if jpn_part[2].endswith(b'\x02'):
                        try:
                            # TODO: extract #S size codes and #C color codes, and maybe #R ruby codes
                            stripped_jpn = strip_text(jpn_part[2], jpn_encode)
                        except UnicodeDecodeError:
                            continue

                        # WARNING sen 1 hack
                        if goodLenJpn(stripped_jpn) > 1 or stripped_jpn in ['！', '？', 'え']:

                            stripped_jpn = sanitize_item_text(stripped_jpn)
                            jpn_chr_name = ''

                            if jpn_part[0] == b'\x1a':
                                jpn_chr_index = struct.unpack('<H', jpn_part[1])[0]
                                # check if SetChrName overrides:
                                if jpn_part[4] != b'':
                                    # print("SetChrName override:", jpn_part[4].decode(jpn_encode), stripped_jpn.replace('\n', ' '))
                                    jpn_chr_name = jpn_part[4].decode(jpn_encode)
                                # lookup in names table
                                elif jpn_chr_index in names_jpn:
                                    jpn_chr_name = names_jpn[jpn_chr_index]
                                # lookup in function thing
                                elif jpn_part[1] == b'\xfe\xff':
                                    if fname in talk_npcs:
                                        jpn_chr_name = talk_npcs[fname]['jpn']
                                    else:
                                        jpn_chr_name = get_npc_name_by_func_name(all_jpn_bytes_by_func,
                                                                                 jpn_func_names,
                                                                                 jpn_scene_num,
                                                                                 jpn_encode,
                                                                                 fname,
                                                                                 stripped_jpn)
                                        # all_jpn_bytes_by_func[jpn_scene_num]
                                        # if jpn_chr_name != '':
                                        #     print('NPC FUNC NAME RESULT', jpn_chr_name)
                                # lookup in NPC table
                                elif jpn_chr_index >= 0x3e8:
                                    jpn_chr_name = get_npc_name(jpn_part[1], all_jpn_bytes[:jpn_part[3]], jpn_encode, fname, stripped_jpn)
                                    if jpn_chr_name == '':
                                        print('NPC NAME RESULT FAILED', jpn_chr_name, stripped_jpn.replace('\n', ' '))
                                else:
                                    print('weird chr index:', hex(jpn_chr_index), stripped_jpn.replace('\n', ' '))
                                # print('jpn_chr_name', jpn_chr_name)

                            jpn_html_text = sanitize_item_text(strip_text(apply_ruby(jpn_part[2], fname), jpn_encode).replace('\n',
                                                                                                           '<br/>'))
                            all_stripped_jpn.append((
                                jpn_chr_name,
                                stripped_jpn.replace('\n', ' '),  # jpn_search_text
                                jpn_html_text,  # jpn_html_text
                                jpn_scene_num,
                                jpn_func_names[jpn_scene_num],
                                jpn_part[5],
                            ))
                            good_params[jpn_part[0]].add(jpn_part[1])

                            if '#' in stripped_jpn:
                                print(hex(jpn_part[0][0]), jpn_part[1], stripped_jpn.replace('\n', '<br/>'))

                            # print(len(all_stripped_jpn), all_stripped_jpn[-1][0], all_stripped_jpn[-1][1])
                        # elif goodLenJpn(stripped_jpn) == 1:
                        #     print('bye', stripped_jpn)

            for eng_scene_num in range(len(all_eng_parts)):
                for eng_part in all_eng_parts[eng_scene_num]:
                    if eng_part[2].endswith(b'\x02'):
                        try:
                            icon_str = ''
                            # WARNING: sen 1 hack
                            encode = eng_encode if fname != 't0600' else jpn_encode

                            stripped_eng = strip_text(eng_part[2], encode)

                            if (goodLenEng(stripped_eng) > 1 or stripped_eng in ['?', '!']) and eng_part[1] in \
                                    good_params[
                                        eng_part[0]]:

                                stripped_eng = sanitize_item_text(stripped_eng)
                                eng_chr_name = ''

                                if eng_part[0] == b'\x1a':
                                    eng_chr_index = struct.unpack('<H', eng_part[1])[0]
                                    # check if SetChrName overrides:
                                    if eng_part[4] != b'':
                                        # print("SetChrName override:", eng_part[4].decode(eng_encode), stripped_eng.replace('\n', ' '))
                                        eng_chr_name = eng_part[4].decode(eng_encode)
                                    elif eng_chr_index in names_eng:
                                        eng_chr_name = names_eng[eng_chr_index]
                                        # if eng_chr_index in all_icons:
                                        #     icon_str = f'<img class="itp-note" src="itp/6/note_chr{eng_chr_index:03}.webp"/>'
                                    # lookup in function thing
                                    elif eng_part[1] == b'\xfe\xff':
                                        if fname in talk_npcs:
                                            eng_chr_name = talk_npcs[fname]['eng']
                                        else:
                                            eng_chr_name = get_npc_name_by_func_name(all_eng_bytes_by_func,
                                                                                     eng_func_names,
                                                                                     eng_scene_num,
                                                                                     eng_encode,
                                                                                     fname,
                                                                                     stripped_eng)
                                            # if eng_chr_name != '':
                                            #     print('NPC FUNC NAME RESULT', eng_chr_name)
                                    # lookup in NPC table
                                    elif eng_chr_index >= 0x3e8:
                                        eng_chr_name = get_npc_name(eng_part[1], all_eng_bytes[:eng_part[3]],
                                                                    eng_encode, fname, stripped_eng)
                                        # print('NPC NAME RESULT', eng_chr_name)
                                    else:
                                        print('weird chr index:', hex(eng_chr_index), stripped_eng.replace('\n', ' '))

                                if eng_chr_name in face_icons:
                                    icon_str = f'<img class="itp-face" src="itp/6/avf{face_icons[eng_chr_name]:04}.webp"/>'
                                elif eng_chr_name in reverse_names_eng and reverse_names_eng[eng_chr_name] in all_icons:
                                    icon_str = f'<img class="itp-note" src="itp/6/note_chr{reverse_names_eng[eng_chr_name]:03}.webp"/>'

                                all_stripped_eng.append((
                                    eng_chr_name,
                                    stripped_eng.replace('\n', ' '),  # eng_search_text
                                    stripped_eng,  # eng_html_text
                                    eng_scene_num,
                                    eng_func_names[eng_scene_num],
                                    eng_part[5],
                                    icon_str
                                ))
                                # print(len(all_stripped_eng), stripped_eng.replace('\n', '<br/>'))
                            # else:
                            #     print('skipped', stripped_eng)
                        except UnicodeDecodeError:
                            pass

            # WARNING sen 1 hacks
            if fname == 'c0400':
                del all_stripped_jpn[148]
            # elif fname == 'm1200':
            #     del all_stripped_jpn[50]
            elif fname == 't0080':
                del all_stripped_jpn[1331]
                del all_stripped_jpn[1301]
            elif fname == 't0000':
                del all_stripped_jpn[863]
                del all_stripped_jpn[858]
            elif fname == 't1010':  # Abend time
                all_stripped_jpn.insert(206, (' ', ' ', ' ', '44', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(206, (' ', ' ', ' ', '44', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(359, (' ', ' ', ' ', '49', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(359, (' ', ' ', ' ', '49', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(466, (' ', ' ', ' ', '60', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(466, (' ', ' ', ' ', '60', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(466, (' ', ' ', ' ', '60', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(690, (' ', ' ', ' ', '72', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(690, (' ', ' ', ' ', '72', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(690, (' ', ' ', ' ', '72', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(834, (' ', ' ', ' ', '79', '', all_stripped_eng[206][5]))
                all_stripped_jpn.insert(834, (' ', ' ', ' ', '79', '', all_stripped_eng[206][5]))

            for i in range(max(len(all_stripped_jpn), len(all_stripped_eng))):
                try:
                    stripped_jpn = all_stripped_jpn[i]
                except IndexError:
                    stripped_jpn = ('', '', '', '', [])

                try:
                    stripped_eng = all_stripped_eng[i]
                except IndexError:
                    stripped_eng = ('', '', '', '', '', '', '')

                # print(i + 1, stripped_jpn, stripped_eng)

                eng_html_text = apply_voice_codes(stripped_eng[2], stripped_jpn[5]).replace('\n', '<br/>')

                newrow = ['6', fname, str(stripped_jpn[3]), str(rownum),
                          stripped_eng[0], stripped_eng[1], eng_html_text,
                          stripped_jpn[0], stripped_jpn[1], stripped_jpn[2], '',
                          stripped_eng[6]]
                displaytbl.append(newrow)

                rownum += 1

            delta = abs(len(all_stripped_jpn) - len(all_stripped_eng))
            total_jpn += len(all_stripped_jpn)
            total_eng += len(all_stripped_eng)

            total_delta += delta

            print("%04d" % delta, fname, len(all_stripped_jpn), len(all_stripped_eng))

            os.system("title " + fname)


talk_npcs = get_talk_npcs()

names_jpn = get_names_jpn()
names_eng = get_names_eng()

items_eng = get_items_eng()
items_jpn = get_items_jpn()

voices_jpn = get_voices_jpn()

face_icons = {
    'Rean': 0,
    'Alisa': 10,
    'Elliot': 20,
    'Laura': 30,
    'Machias': 40,
    'Emma': 50,
    'Jusis': 60,
    'Fie': 70,
    'Gaius': 80,
    'Millium': 90,
    'Crow': 100,
    'Instructor Sara': 110,
    'Angelica': 120,
    'Sharon': 530,
    'Celine': 990
}

reverse_names_eng = dict((v, k) for k, v in names_eng.items())

for k, v in face_icons.items():
    print(k, k in reverse_names_eng)

all_icons = {9,98,56,52,11,10,127,8,1,7,60,5,6,0,58,53,93,59,77,4,3,57,2,73,72,61,92,97,78,63,64,71,86,96,88,95,84,90,12,69,79,76,67,68,80,62,89,94,87,85,66,83,70,81,102,74,82,75,65,91}

for fname in os.listdir(vita_jpn_path + 'scena/dat/'):
    do_everything2('scena/dat/', 'scena/dat_us/', fname)
for fname in os.listdir(vita_jpn_path + 'talk/dat/'):
    do_everything2('talk/dat/', 'talk/dat_us/', fname)

# do_everything2('scena/dat/', 'scena/dat_us/', 't5530.dat')
# do_everything2('scena/dat/', 'scena/dat_us/', 'c0110.dat')
# do_everything2('scena/dat/', 'scena/dat_us/', 't3500.dat')
# do_everything2('talk/dat/', 'talk/dat_us/', 'tk_vincent.dat')

print('TOTAL DELTA = %d\nTOTAL JPN = %d\nTOTAL ENG = %d' % (total_delta, total_jpn, total_eng))

# print('exit early')
# exit()

with open(r'sen1.sql', 'w', encoding='utf-8') as sqlfile:
    sqlfile.write('delete from script where game_id = 6;\n')
    for row in displaytbl:
        newrow = []
        for cell in row:
            if type(cell) is list:
                cell = str([line.decode(jpn_encode) for line in cell])
            elif type(cell) is bytes:
                cell = str(cell)
            newrow.append(cell)

        sqlfile.write(
            'insert into script (game_id, fname, scene, row, eng_chr_name, eng_search_text, eng_html_text, '
            'jpn_chr_name, jpn_search_text, jpn_html_text, op_name, pc_icon_html) values\n')
        sqlfile.write("('%s');\n" % ("','".join(
            [c.replace('\\', '\\\\').replace("'", "''").replace('\x1a', '\\Z') for c in
             newrow])))
