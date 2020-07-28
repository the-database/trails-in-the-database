import re, os, csv, sys, struct, operator

vita_jpn_path = './cs3-scripts/'
pc_eng_path = './cs3-scripts/'
jpn_encode = 'utf8'

displaytbl = []
displaytbl2 = {}
footer = {}

translatorEng = str.maketrans('', '', '"#$%&\'()*+,-/:;<=>@[\\]^_`{|}~ \n\x7fף׳Б¬хЕЬЭнАθοξνμλκιΨВωψχφ')
translatorJpn = str.maketrans('', '',
                              '!"#$%&\'()*+,-/:;<=>?@[\\]^_`{|}~ '
                              '\n.\x7f0123456789I')

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

    return npcs


def get_talk_npcs():
    # files = ['c0010.dat', 'c0310.dat', 'm0530.dat', 'm2500.dat', 'm3001.dat', 'm3008.dat', 't0000.dat', 't0000b.dat',
    #          't0000c.dat', 't0010.dat', 't0020.dat', 't0031.dat', 't0032.dat', 't0050.dat', 't0060.dat', 't0070.dat',
    #          't0080.dat', 't0090.dat', 't0200.dat', 't0201.dat', 't1000.dat', 't1010.dat', 't1020.dat', 't1030.dat',
    #          't1040.dat', 't1050.dat', 't1060.dat', 't1080.dat', 't1090.dat', 't1110.dat', 't1120.dat', 't1150.dat',
    #          't1160.dat', 't3510.dat', 't3550.dat']

    eng_talk_npcs = {}
    jpn_talk_npcs = {}

    result = {}

    for fname in os.listdir(vita_jpn_path + 'scena/dat/'):
        with open(os.path.join(vita_jpn_path, 'scena/dat/', fname), 'rb') as f_jpn, \
                open(os.path.join(vita_jpn_path, 'scena/dat_en/', fname), 'rb') as f_eng:

            # print(fname)

            all_bytes_jpn = f_jpn.read()
            all_bytes_eng = f_eng.read()

            search = rb'\x1d[\s\S]{2}([^\x00\xff]+?)\x00([^\x00\xff]+?)\x00[\s\S]{35}TK_[^\x00\xff]+?\x3a(tk_[^\x00\xff]+?)\x00'

            jpn_talks = [m for m in re.finditer(search, all_bytes_jpn)]
            eng_talks = [m for m in re.finditer(search, all_bytes_eng)]

            for m in eng_talks:
                # print(m.group(3), m.group(2), m.group(1), m.group(0))
                if m.group(3).decode(jpn_encode) not in eng_talk_npcs:
                    eng_talk_npcs[m.group(3).decode(jpn_encode)] = {}

                if m.group(2).decode(jpn_encode) not in eng_talk_npcs[m.group(3).decode(jpn_encode)]:
                    eng_talk_npcs[m.group(3).decode(jpn_encode)][m.group(2).decode(jpn_encode)] = 0

                eng_talk_npcs[m.group(3).decode(jpn_encode)][m.group(2).decode(jpn_encode)] += 1

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
    search = rb'\x1d' + re.escape(index) + rb'([^\x00]+?)\x00([^\x00]+?)\x00'
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
        print(fname, "WARNING NORMAL NPC LOOKUP WEIRDNESS", "%04X" % struct.unpack('<H', index)[0], index, len(names),
              names, text.replace('\n', '<br/>'))
    if len(names) > 0:
        return names.pop()

    return ''


def get_npc_name_by_func_name_direct(all_bytes_by_func, func_names, func_index, encode, fname, text):
    all_bytes = b''.join(all_bytes_by_func[:func_index])
    func_name = func_names[func_index]
    search = rb'\x1d[\s\S]{2}([^\x00]+?)\x00([^\x00]+?)\x00([\s\S]{35})' + re.escape(func_name)
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
    calling_funcs = [i for i in range(len(func_names)) if
                     re.search(b'\x02[\x0b\x00]' + func_names[func_index] + b'\x00', all_bytes_by_func[i])]
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
            names += get_npc_name_by_func_name_direct(all_bytes_by_func, func_names, calling_func_index, encode, fname,
                                                      text)

    if len(set(names)) != 1:
        print(fname, "WARNING FUNC NPC LOOKUP WEIRDNESS", func_name, len(names), names, text.replace('\n', '<br/>'))
    if len(names) > 0:
        return names.pop()

    return ''


def get_voices_jpn():
    voices = {}

    with open('cs3-text/dat/t_voice.tbl', 'rb') as f:
        num_voices = struct.unpack('<H', f.read(2))[0]  # size

        junk = f.read(0xe)

        while len(voices) < num_voices:
            junk = parse_str(f)  # voice

            if len(junk) == 0:
                break

            voice_size = struct.unpack('<H', f.read(2))[0]  # size
            voice_code = struct.unpack('<H', f.read(2))[0]
            junk = f.read(1)

            remainder = f.read(voice_size - 3)
            strings = remainder.split(b'\x00')
            voices[voice_code] = strings[0].decode(jpn_encode)

    return voices


def get_items(path, encode):
    items = {}

    with open(path, 'rb') as f:
        num_entries = struct.unpack('<H', f.read(2))[0]
        f.read(4)
        parse_str(f)  # item
        num_items = struct.unpack('<H', f.read(2))[0]
        f.read(2)
        parse_str(f)  # item_q
        num_quarts = struct.unpack('<H', f.read(2))[0]

        size = num_items + num_quarts
        f.read(0x2)

        while len(items) < size:

            junk1 = parse_str(f)  # "item"

            if len(junk1) == 0:
                break

            item_size = struct.unpack('<H', f.read(2))[0]

            item_code = struct.unpack('<H', f.read(2))[0]
            junk3 = f.read(2)
            flags = parse_str(f)
            junk4 = f.read(0x7f)
            item_name = parse_str(f)
            item_desc = parse_str(f)
            read_length = item_size - (2 + 2 + len(flags) + 1 + 0x7f + len(item_name) + 1 + len(item_desc) + 1)
            # print(read_length)
            junk4 = f.read(read_length)

            # print(len(items), size, "%04X" % item_code, junk1,  item_name, item_desc, "%04X" % item_size)

            items[item_code] = item_name

    return items


def get_items_jpn():
    return get_items('./cs3-text/dat/t_item.tbl', jpn_encode)


def get_items_eng():
    return get_items('./cs3-text/dat_en/t_item_en.tbl', jpn_encode)


def get_names(path, encode):
    names_by_code = {}  # >= 0x3e8 codes
    names_by_func = {}  # func names from 0xfffe codes

    with open(path, 'rb') as f:
        size = struct.unpack('<H', f.read(2))[0]

        f.read(4)
        parse_str(f)
        f.read(4)

        while True:
            # junk = f.read(4)
            junk = parse_str(f)  # NameTableData

            if len(junk) == 0:
                break

            length = struct.unpack('<H', f.read(2))[0]

            index = struct.unpack('<H', f.read(2))[0]

            names = (f.read(length - 2)).split(b'\x00')
            # print('name', names, names[6])

            name = names[0]

            # print([nm.decode(encode) for nm in names])
            print (name.decode(encode))
            for nm in names[1:]:
                try:
                    print(f'\t{nm.decode(encode)}')
                except:
                    pass


            func = names[5].decode(encode)

            # parse_str(f)  # NameTableData

            if index in names_by_code:
                new_name = name.decode(encode)
                if len(new_name) < len(names_by_code[index]):
                    names_by_code[index] = new_name
                # print('collision:', hex(index),  names_by_code[index])
            else:
                names_by_code[index] = name.decode(encode)

            if func != 'null':
                if func in names_by_func:
                    new_name = name.decode(encode)
                    if len(new_name) < len(names_by_func[func]):
                        # print('collision:', func, new_name, names_by_func[func])
                        names_by_func[func] = new_name
                else:
                    names_by_func[func] = name.decode(encode)

    return names_by_code, names_by_func


def get_names_jpn():
    return get_names('./cs3-text/dat/t_name.tbl', jpn_encode)


def get_names_eng():
    return get_names('./cs3-text/dat_en/t_name.tbl', jpn_encode)


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
    if op == b'\x22':
        return param in [b'\xfe\xff', b'\xff\xff']
    elif op == b'\x24':
        return param.endswith(b'\x00\x00')
    return False


def valid_text(op, text):
    if text is not None:
        if op in (b'\x22', b'\x24'):
            if text.endswith(b'\x02'):
                # if True in [black.encode(jpn_encode) in text for black in blacklist_contains_test]:
                #     print('skip', text.decode(jpn_encode))
                # if text.endswith(b'\x02\x02'):
                #     return False
                return True  # not in [black.encode(jpn_encode) in text for black in blacklist_contains]
        elif op == b'\x27':
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


def parse_file(fs, func_positions, is_jpn=False):
    all_parts = []

    # func_positions, func_names = get_func_positions(fs)
    # func_positions.sort()

    for i in range(len(func_positions)):

        parts = []

        fs.seek(func_positions[i])

        op_params = {
            # AnonymousTalk BB STR
            b'\x22': 2,
            # ChrTalk BB STR
            b'\x24': 6,
            # SetChrName STR (???)
            b'\x27': 0,
        }

        last_set_chr_name = b''

        while True:
            op = fs.read(1)

            if not op or (i + 1 < len(func_positions) and fs.tell() > func_positions[i + 1]):
                break

            if op in op_params:
                curr_pos = fs.tell()
                param = fs.read(op_params[op])
                # text, voice_files = parse_str_with_voice(fs, is_jpn)
                text, voice_files = parse_str_with_voice(fs, is_jpn)

                if op == b'\x27' and valid_text(op, text):
                    try:
                        text.decode(jpn_encode)
                        param2 = fs.read(2)
                        # print('SetChrNameTest', text.decode(jpn_encode), param2)  # test
                        if param2 == b'\xff\xff':
                            if len(text) > 0 and last_set_chr_name.endswith(text):
                                pass
                            else:
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
    rubyJpnLines = [line.decode(jpn_encode).encode('cp932') for line in text.split(b'\x02\x03')]

    for j in range(len(rubyJpnLines)):
        rubyMatches = [m for m in re.finditer(br'#(\d+)R(.+?)(#)', rubyJpnLines[j])]
        for m in reversed(rubyMatches):

            end_index = m.start(1) - 1

            start_index = end_index - int(m.group(1))

            # sen 3 hack
            if fname in {'e3500', 'm0000', 'r2290', 't0030', 't0040', 't0200', 't0210', 't0260', 't2040', 't3000',
                         't3600', 't4000', 't4020'} \
                    and int(m.group(1)) % 2 == 1:
                start_index -= 1

            main_text = rubyJpnLines[j][start_index:end_index]
            extra_text = m.group(2)
            rubyJpnLines[j] = rubyJpnLines[j][:start_index] + b'<ruby>%s<rt>%s</rt></ruby>' % (
                main_text, extra_text) + rubyJpnLines[j][(m.start(3) + 1):]
            if int(m.group(1)) % 2 == 1:
                print('odd ruby', fname, m.group(2).decode('cp932'), text.decode(jpn_encode))
                # try:
                #     rubyJpnLines[j].decode(jpn_encode)
                # if second_attempt:
                #     print('second attempt ruby result', rubyJpnLines[j].decode(jpn_encode))
                # except UnicodeDecodeError:
                # print('failed result', text.decode(jpn_encode))
                # if not second_attempt:
                #     return apply_ruby(text, fname, True)

                # raise UnicodeDecodeError

    return b'\x02\x03'.join([line.decode('cp932').encode(jpn_encode) for line in rubyJpnLines])


def apply_voice_codes(text, voice_files):
    if len(voice_files) == 0:
        return text

    lines = text.split('\n\n')

    # print('lens', len(lines), len(voice_files))

    new_lines = []

    for i in range(len(lines)):
        if i < len(voice_files):
            new_lines.append(
                f'<audio id="{voice_files[i]}"><source src="talk/8/{voice_files[i]}.opus" '
                f'type="audio/ogg; codecs=opus"></audio><a href="javascript:void(0)" '
                f'onclick="document.getElementById(\'{voice_files[i]}\').play()">{lines[i]}</a>'
            )
        else:
            new_lines.append(lines[i])

    return '\n\n'.join(new_lines)


def strip_text(text_bytes, encode):
    # Acknowledged: sen 2 hack
    return re.sub(rb'#E\[9\]#M_2#B_0#H_2|#E\[9\]#M_0#B_0#H_2|#4C##0T|#2#M0|#0T|#\d?K|#\d?P|#E\[[\dA-Z#_a-z]+\]|#F|'
                  rb'#\d*S|#\d?C|#\d*?R[^#]+?#|'
                  rb'#E\d|#M\d|#M\[[\dABGEZ]\]|#\d+W|#MA|#E[EFIJ]|#\d+I|#\d+y|#e\[[\dG]\]|'
                  rb'#M\[\[autoM0\]\]|#M\[\[autoM[\d]\]\]|#H\[[\d]\]|#H\d|#\d+c|#\d?T|'
                  rb'#M\[0\[autoM0\]\]|#\d+G|#E\[[\d,A-Z]+\]|#M\[\[autoMA\]\]|#E_[\dA-Z]|#M_[\dA-Z]|'
                  rb'#M_A|#OT|#e_E|#e\[[Il5]*\]|#DF|#M_B|#k|#B_\d|#\dU|#B\[[A-Z\d]+\]|#\d+s|#\d+F|#M\[[\d,A-Z]+\]|'
                  rb'#e_\d|#B_A|#e\[E\]|#E\[[E\d]+\[autoE\d\]\]|#E\[88888888\[autoE0\]\]|'
                  rb'#E\[222222222222222\[autoE6\]\]|#e\[\d+\]|##0T|##2F|##F|H_\d|#OU|#B\[7c\]|#\dk|'
                  rb'#B\[\d\[autoB\d\]\]|##E\[\d\]|#M\[HHHH\[autoM0\]\]', b'',
                  re.sub(rb'[\x00-\x09\x0b-\x1f]+', b' ',
                         text_bytes.replace(b'\x01', b'\n').replace(b'\x02\x03', b'\n\n').replace(b'\\n', b'\n')
                         .replace(b'#2RAcknowledged!#', b'Acknowledged!'))) \
        .decode(encode).strip()


def sanitize_item_text(text_str):
    return text_str.replace('<<', '').replace('>>', '')


def do_everything2(jpn_subpath, eng_subpath, fname):
    global total_delta, total_jpn, total_eng, \
        names_eng_by_code, names_eng_by_func, names_jpn_by_code, names_jpn_by_code

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

            all_eng_parts = parse_file(f_eng, eng_func_positions)
            all_jpn_parts = parse_file(f_jpn, jpn_func_positions, True)

            good_params = {
                b'\x22': set(),
                b'\x24': set()
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
                        if goodLenJpn(stripped_jpn) > 1 or stripped_jpn in ['！', '？', 'え', '記', '眼']:

                            stripped_jpn = sanitize_item_text(stripped_jpn)
                            jpn_chr_name = ''

                            jpn_chr_param = jpn_part[1][:2]  # TEST

                            if jpn_part[0] == b'\x24':
                                jpn_chr_index = struct.unpack('<H', jpn_chr_param)[0]
                                # print('JPN CHR INDEX', jpn_chr_index)
                                # check if SetChrName overrides:
                                if jpn_part[4] != b'':
                                    # print("SetChrName override:", jpn_part[4].decode(jpn_encode), stripped_jpn.replace('\n', ' '))
                                    jpn_chr_name = jpn_part[4].decode(jpn_encode)
                                # lookup in names table
                                elif jpn_chr_index in names_jpn_by_code:
                                    jpn_chr_name = names_jpn_by_code[jpn_chr_index]
                                # lookup in function thing
                                elif jpn_chr_param == b'\xfe\xff':
                                    func_name = jpn_func_names[jpn_scene_num]
                                    if func_name.startswith(b'TK_'):
                                        key = func_name[3:].decode(jpn_encode)

                                        # sen 3 hack
                                        if key == b'TK_3T_05_t4000_ridnor':
                                            key = b'ridnor'

                                        if key in names_jpn_by_func:
                                            jpn_chr_name = names_jpn_by_func[key]
                                        else:
                                            jpn_chr_name = get_npc_name_by_func_name(all_jpn_bytes_by_func,
                                                                                     jpn_func_names,
                                                                                     jpn_scene_num,
                                                                                     jpn_encode,
                                                                                     fname,
                                                                                     stripped_jpn)
                                    else:
                                        print(fname, "NPC FUNC LOOKUP WEIRDNESS", func_name)
                                    # jpn_chr_name = get_npc_name_by_func_name(all_jpn_bytes_by_func,
                                    #                                          jpn_func_names,
                                    #                                          jpn_scene_num,
                                    #                                          jpn_encode,
                                    #                                          fname,
                                    #                                          stripped_jpn)
                                    # all_jpn_bytes_by_func[jpn_scene_num]
                                    # if jpn_chr_name != '':
                                    #     print('NPC FUNC NAME RESULT', jpn_chr_name)
                                # lookup in NPC table
                                elif jpn_chr_index >= 0x2f7:
                                    jpn_chr_name = get_npc_name(jpn_chr_param, all_jpn_bytes[:jpn_part[3]], jpn_encode,
                                                                fname, stripped_jpn)
                                    if jpn_chr_name == '':
                                        print('NPC NAME RESULT FAILED', jpn_chr_name, stripped_jpn.replace('\n', ' '))
                                else:
                                    print('weird chr index:', hex(jpn_chr_index), stripped_jpn.replace('\n', ' '))
                                    continue

                                # sen 3 hack
                                if fname == 'm1420' and jpn_chr_name == 'トワ' and len(all_stripped_jpn) < 275:
                                    jpn_chr_name = ''

                                # print('jpn_chr_name', jpn_chr_name, stripped_jpn)

                            # first apply ruby codes
                            # then, apply voice codes
                            # then strip other # codes we don't care about
                            # then remove the << >> surrounding items
                            jpn_html_text = sanitize_item_text(
                                    strip_text(
                                        apply_ruby(jpn_part[2], fname), jpn_encode
                                    )
                                ).replace('\n', '<br/>')

                            all_stripped_jpn.append((
                                jpn_chr_name,
                                stripped_jpn.replace('\n', ' '),  # jpn_search_text
                                jpn_html_text,  # jpn_html_text
                                jpn_scene_num,
                                jpn_func_names[jpn_scene_num]
                            ))
                            good_params[jpn_part[0]].add(jpn_part[1])

                            if '#' in stripped_jpn:
                                print('###', fname, hex(jpn_part[0][0]), jpn_chr_param,
                                      stripped_jpn.replace('\n', '<br/>'), '|||', jpn_part[2].decode(jpn_encode))

                            # print(len(all_stripped_jpn), all_stripped_jpn[-1][0], all_stripped_jpn[-1][1])
                        # elif goodLenJpn(stripped_jpn) == 1:
                        #     print('bye', stripped_jpn)

            for eng_scene_num in range(len(all_eng_parts)):
                for eng_part in all_eng_parts[eng_scene_num]:
                    if eng_part[2].endswith(b'\x02'):
                        try:
                            icon_str = ''
                            stripped_eng = strip_text(eng_part[2], jpn_encode)

                            if (goodLenEng(stripped_eng) > 1 or stripped_eng in ['?', '!']) and eng_part[1] in \
                                    good_params[
                                        eng_part[0]]:

                                stripped_eng = sanitize_item_text(stripped_eng)
                                eng_chr_name = ''

                                eng_chr_param = eng_part[1][:2]

                                if eng_part[0] == b'\x24':
                                    eng_chr_index = struct.unpack('<H', eng_chr_param)[0]
                                    # check if SetChrName overrides:
                                    if eng_part[4] != b'':
                                        # print("SetChrName override:", eng_part[4].decode(jpn_encode), stripped_eng.replace('\n', ' '))
                                        eng_chr_name = eng_part[4].decode(jpn_encode)
                                    elif eng_chr_index in names_eng_by_code:
                                        eng_chr_name = names_eng_by_code[eng_chr_index]
                                    # lookup in function thing
                                    elif eng_chr_param == b'\xfe\xff':
                                        func_name = eng_func_names[eng_scene_num]
                                        if func_name.startswith(b'TK_'):
                                            key = func_name[3:].decode(jpn_encode)

                                            # sen 3 hack
                                            if key == b'TK_3T_05_t4000_ridnor':
                                                key = b'ridnor'

                                            if key in names_eng_by_func:
                                                eng_chr_name = names_eng_by_func[key]
                                            else:
                                                eng_chr_name = get_npc_name_by_func_name(all_eng_bytes_by_func,
                                                                                         eng_func_names,
                                                                                         eng_scene_num,
                                                                                         jpn_encode,
                                                                                         fname,
                                                                                         stripped_eng)
                                        else:
                                            print(fname, "NPC FUNC LOOKUP WEIRDNESS", func_name)

                                        # if eng_chr_name != '':
                                        #     print('NPC FUNC NAME RESULT', eng_chr_name)
                                    # lookup in NPC table
                                    elif eng_chr_index >= 0x2f7:
                                        eng_chr_name = get_npc_name(eng_chr_param, all_eng_bytes[:eng_part[3]],
                                                                    jpn_encode, fname, stripped_eng)
                                        # print('NPC NAME RESULT', eng_chr_name)
                                    else:
                                        print('weird chr index:', hex(eng_chr_index), stripped_eng.replace('\n', ' '))
                                        continue

                                if eng_chr_name in face_icons:
                                    icon_str = f'<img class="itp-face3" src="itp/8/avf{face_icons[eng_chr_name]:04}.webp"/>'
                                elif eng_chr_name in all_icons:
                                    icon_str = f'<img class="itp-note3" src="itp/8/note_chr{all_icons[eng_chr_name]:03}.webp"/>'

                                eng_html_text = apply_voice_codes(stripped_eng, eng_part[5]).replace('\n', '<br/>')

                                all_stripped_eng.append((
                                    eng_chr_name,
                                    stripped_eng.replace('\n', ' '),  # eng_search_text
                                    eng_html_text,  # eng_html_text
                                    eng_scene_num,
                                    eng_func_names[eng_scene_num],
                                    icon_str
                                ))
                                # print(len(all_stripped_eng), stripped_eng.replace('\n', '<br/>'))
                            # else:
                            #     print('skipped', stripped_eng)
                        except UnicodeDecodeError:
                            pass

            # WARNING: hard-coded solution for sen 3 tk_wayne mismatch
            if fname == 'tk_wayne':
                all_stripped_eng[70] = (all_stripped_eng[70][0],
                                        all_stripped_eng[70][1] + ' ' + all_stripped_eng[71][1],
                                        all_stripped_eng[70][2] + '<br/><br/>' + all_stripped_eng[71][2],
                                        all_stripped_eng[70][3],
                                        all_stripped_eng[70][4],
                                        all_stripped_eng[70][5],)
                # all_stripped_eng[70] += '\n\n' + all_stripped_eng[71]
                del all_stripped_eng[71]

            for i in range(max(len(all_stripped_jpn), len(all_stripped_eng))):
                try:
                    stripped_jpn = all_stripped_jpn[i]
                except IndexError:
                    stripped_jpn = ('', '', '', '')

                try:
                    stripped_eng = all_stripped_eng[i]
                except IndexError:
                    stripped_eng = ('', '', '', '', '', '')

                # print(i + 1, stripped_jpn[0], stripped_jpn[1], stripped_eng[0], stripped_eng[1])

                newrow = ['8', fname, str(stripped_jpn[3]), str(rownum),
                          stripped_eng[0], stripped_eng[1], stripped_eng[2],
                          stripped_jpn[0], stripped_jpn[1], stripped_jpn[2], '',
                          stripped_eng[5]]
                displaytbl.append(newrow)

                rownum += 1
                MapName                     = 'Rolent'

            delta = abs(len(all_stripped_jpn) - len(all_stripped_eng))
            total_jpn += len(all_stripped_jpn)
            total_eng += len(all_stripped_eng)

            total_delta += delta

            print("%04d" % delta, fname, len(all_stripped_jpn), len(all_stripped_eng))

            os.system("title " + fname)


# talk_npcs = get_talk_npcs()

names_jpn_by_code, names_jpn_by_func = get_names_jpn()
names_eng_by_code, names_eng_by_func = get_names_eng()

items_eng = get_items_eng()
# print(len(items_eng))
items_jpn = get_items_jpn()

voices_jpn = get_voices_jpn()

for k, v in names_eng_by_code.items():
    print(f'"{v}": {k},')

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
    'Juna': 100,
    'Kurt': 110,
    'Altina': 120,
    'Musse': 130,
    'Ash': 140,
    'Sara': 150,
    'Principal Aurelia': 160,
    'Agate': 170,
    'Angelica': 180,
    'Olivier': 190,
    'Tita': 200,
    'Tio': 210,
    'Sharon': 220,
    'Major Claire': 230,
    'Major Lechter': 240,
    'Towa': 250,
    'Patrick': 260,
    'Celine': 600,
    'Major Michael': 1200,
    'Randy': 1210,
    'Professor Schmidt': 1230,
    'George': 1410,
    'Freddy': 1520,
    'Gustaf': 1530,
    'Leonora': 2010,
    'Maya': 2020,
    'Louise': 2030
}

all_icons = {
    "Rean": 0,
    "Alisa": 1,
    "Elliot": 2,
    "Laura": 3,
    "Machias": 4,
    "Emma": 5,
    "Jusis": 6,
    "Fie": 7,
    "Gaius": 8,
    "Millium": 9,
    "Kurt": 10,
    "Juna": 11,
    "Ash": 12,
    "Musse": 13,
    "Altina": 15,
    "Agate": 16,
    "Sara": 17,
    "Olivier": 18,
    "Angelica": 19,
    "Principal Aurelia": 21,
    "Major Claire": 23,
    "Major Lechter": 24,
    "Sharon": 25,
    "Tita": 27,
    "Tio": 29,
    "Major Michael": 40,
    "Towa": 41,
    "Randy": 42,
    "Elise": 43,
    "Professor Schmidt": 44,
    "Toval": 46,
    "Patrick": 50,
    "Thomas": 58,
    "Princess Alfin": 63,
    "Crimson Roselia": 67,
    "George": 72,
    "Celine": 955,
    "Wayne": 200,
    "Sidney": 201,
    "Freddy": 202,
    "Gustaf": 203,
    "Kairi": 204,
    "Stark": 205,
    "Pablo": 206,
    "Munk": 210,
    "Alan": 211,
    "Kenneth": 212,
    "Hugo": 213,
    "Celestin": 214,
    "Jessica": 600,
    "Leonora": 601,
    "Maya": 602,
    "Louise": 603,
    "Tatiana": 604,
    "Sandy": 605,
    "Valerie": 606,
    "Sister Rosine": 610,
    "Mint": 611,
    "Linde": 612,
    "Becky": 614,
    "Vivi": 613,
    "Ferris": 615,
    "Jingo": 621,
    "Annabelle": 628
}

for k, v in face_icons.items():
    print(k, k in all_icons)

for fname in os.listdir(vita_jpn_path + 'scena/dat/'):
    do_everything2('scena/dat/', 'scena/dat_en/', fname)
for fname in os.listdir(vita_jpn_path + 'talk/dat/'):
    do_everything2('talk/dat/', 'talk/dat_en/', fname)

# do_everything2('scena/dat/', 'scena/dat_en', 'm1420.dat')
# do_everything2('scena/dat/', 'scena/dat_en', 'm0100.dat')
# do_everything2('talk/dat/', 'talk/dat_en', 'tk_benet.dat')
# do_everything2('talk/dat/', 'talk/dat_en', 'tk_vivi.dat')
# do_everything2('scena/dat/', 'scena/dat_en', 'c0210.dat')
# do_everything2('talk/dat/', 'talk/dat_en', 'tk_wayne.dat')

print('TOTAL DELTA = %d\nTOTAL JPN = %d\nTOTAL ENG = %d' % (total_delta, total_jpn, total_eng))

# print('exit early')
# exit()

with open(r'sen3.sql', 'w', encoding='utf-8') as sqlfile:
    sqlfile.write('delete from script where game_id = 8;\n')
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
