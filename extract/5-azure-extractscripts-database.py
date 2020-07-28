# 0x58: NpcTalk
# 0x57: ChrTalk,
# 0x50: AnonymousTalk,

import re, os, csv, sys, struct, traceback

# vita_jpn_path = './ZNK-VITA-JPN-SOURCE/data1/data/scena/'
pc_jpn_path = 'D:/file/programming/kiseki-evo/Trails to Azure/scripts/scena/'
pc_eng_path = 'D:/file/programming/kiseki-evo/Trails to Azure/scripts/scena_en2-7'
jpn_encode = 'cp932'
utf8_encode = 'utf-8'

alldisplaytbl = []
footer = {}

SCPSTR_CODE_ITEM = None


def scpstr(junk, index):
    global items
    # if index in items:
    return items[index].decode(jpn_encode).encode(utf8_encode)
    # return b'Unknown Item '


def parse_str(fs, is_jpn=False):
    global items_eng, items_jpn, voices_jpn
    result = []

    while True:
        char = fs.read(1)

        if not char:
            break

        # Item BB
        if char == b'\x10':
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

    return b''.join(result)


def getpointers(path, fname):
    pointers = []
    with open(os.path.join(path, fname), 'rb') as f:

        pointers_addr = struct.unpack('<H', f.read(2))[0]

        f.seek(pointers_addr)

        while True:
            p = struct.unpack('<H', f.read(2))[0]

            if len(pointers) > 0 and f.tell() > pointers[0]:
                break
            pointers.append(p)

    return pointers


def getitems(path):
    all_items = {}

    for fname in ['t_ittxt._dt', 't_ittxt2._dt']:
        pointers = getpointers(path, fname)

        with open(os.path.join(path, fname), 'rb') as f:
            for p in pointers:
                f.seek(p)
                item_index = struct.unpack('<I', f.read(4))[0]
                f.read(4)  # junk
                item_name = parse_str(f)
                all_items[item_index] = item_name

    return all_items


def getnames(path, fname):
    all_names = {}

    lines = []
    with open(path + fname, 'rb') as f:

        body_start_addr = 0
        i = 0

        while True:

            index = struct.unpack('<H', f.read(2))[0]
            start_addr = struct.unpack('<H', f.read(2))[0]

            f.read(16)  # dummy

            if body_start_addr == 0:
                body_start_addr = start_addr

            # print(i, index, hex(start_addr))
            lines.append((index, start_addr))

            if f.tell() > body_start_addr:
                break

            i += 1

        # allbytes = f.read()

        f.seek(0)

        allbytes = f.read()

        for line in lines:
            part = allbytes[line[1]:]
            name = part[:part.find(b'\x00')].decode(jpn_encode)
            print(name)
            all_names[line[0]] = name

    return all_names


def BuildStringList(*args):
    result = []

    for arg in args:
        result.append(arg)

    return result


def DeclNpc(X, Z, Y, Direction, Unknown2, ChipIndex, Unknown_11, NpcIndex, Unknown_14, InitScenaIndex,
            InitFunctionIndex, TalkScenaIndex, TalkFunctionIndex, Unknown4, Unknown5):
    return NpcIndex, TalkScenaIndex, TalkFunctionIndex


def get_string_names(all_bytes):
    string_list = re.search(rb'BuildStringList\(\((.|\n)+?    \)\)', all_bytes).group(0)
    start_index = int(re.search(rb'# (\d+)', string_list).group(1))
    strings = eval(string_list.decode(utf8_encode))[0]
    return strings, start_index


def get_npc_index(all_bytes_main, scena_num, func_num):
    reg_npcs = [m for m in re.finditer(rb'DeclNpc\(.+\)', all_bytes_main)]
    npcs = {}

    for i in range(len(reg_npcs)):
        npc = eval(reg_npcs[i].group(0))
        # npcs[(npc[1], npc[2])] = i
        npcs[(npc[1], npc[2])] = i

    # print('npcs', npcs)
    # print('search',rb'TalkFunctionIndex\s+= %d,[\r\n]+\s+TalkScenaIndex\s+= %d' % (scena_num, func_num))
    # npc = [m for m in re.finditer(rb'TalkFunctionIndex\s+= %d,[\r\n]+\s+TalkScenaIndex\s+= %d' % (scena_num, func_num), all_bytes_main)][0]
    # npc = [m for m in re.finditer(rb'\d+\s*,\s*\d+,\s*,\s*\d+,')]
    # return [i for i in range(len(npcs)) if (npc.start() > npcs[i].start() and (i+1 == len(npcs) or npc.start() < npcs[i+1].start()))][0]
    return npcs[(scena_num, func_num)]


def get_chr_name_for_0xfe(scena_num, func_num, all_bytes_main, name_strings, lines):
    # print('get_chr_name_for_0xfe', scena_num, func_num)

    try:
        npc_index = get_npc_index(all_bytes_main, scena_num, func_num)
        return name_strings[npc_index + 1]
    except:
        print(traceback.format_exc())
        # find the function that called this function
        calls = [m for m in re.finditer(rb'Call\(%d, %d\)' % (scena_num, func_num), all_bytes_main)]
        print('notalkbegins!!!', fname, lines, calls)
        if len(calls) == 0:
            print('nocalls!!!', fname, lines, rb'Call\(%d, %d\)' % (scena_num, func_num))
        else:
            call = calls[0]
            main_funcs = [m for m in re.finditer(rb'def Function_(\d+)_', all_bytes_main) if m.start() < call.start()]
            main_func_num = eval(main_funcs[-1].group(1))
            try:
                npc_index = get_npc_index(all_bytes_main, 0, main_func_num)
                return name_strings[npc_index + 1]
            except:
                return get_chr_name_for_0xfe(scena_num, main_func_num, all_bytes_main, name_strings, lines)
    return ''


def get_chr_name_from_index(chr_index, full_lines, names, name_strings, name_start_index, all_bytes,
                            all_bytes_main, fname, lines):
    jpn_chr_name = ', fname'

    if chr_index == 0xfe:
        # print('0xfe attempt!', [line.decode(utf8_encode) for line in lines])

        pos = all_bytes.index(full_lines)
        talkbegins = [m for m in re.finditer(rb'TalkBegin\((.+)\)', all_bytes) if m.start() < pos]

        funcs = [m for m in re.finditer(rb'def Function_(\d+)_', all_bytes) if m.start() < pos]
        func_num = eval(funcs[-1].group(1))
        scena_num = 0
        if '_' in fname:
            scena_num = int(fname[(fname.index('_') + 1):])
            # pass

        talkbegin = 0xFE
        if len(talkbegins) > 0:
            talkbegin = eval(talkbegins[-1].group(1))

        # Determine the NPC by function numbers or find the function that called this function
        if talkbegin >= 0xFE:
            jpn_chr_name = get_chr_name_for_0xfe(scena_num, func_num, all_bytes_main, name_strings, lines)
        else:
            # print(name_strings[eval(talkbegin) - name_start_index + 1] )
            # print('talkbegin', hex(talkbegin), name_strings)
            jpn_chr_name = name_strings[talkbegin - name_start_index + 1]
        # print('0xfe!', jpn_chr_name, [line.decode(utf8_encode) for line in lines], talkbegin)
    elif chr_index > 0x100:
        # print('old chr index',chr_index, [line.decode(utf8_encode) for line in lines])
        chr_index -= 0x100
        chr_index -= 1
        # print(chr_index)

        jpn_chr_name = names[chr_index]
    else:
        # print('else', name_start_index, [line.decode(utf8_encode) for line in lines])
        jpn_chr_name = name_strings[chr_index - name_start_index + 1]

    return jpn_chr_name


def get_chr_name(op_name, full_lines, lines, names, name_strings, name_start_index,
                 fname, all_bytes, all_bytes_main, set_chr_names, set_chr_names2, encode):
    jpn_chr_name = ''

    if op_name == 'ChrTalk':
        try:
            chr_index = int(full_lines[full_lines.index(b'0x'):full_lines.index(b',')], 16)
            jpn_chr_name = get_chr_name_from_index(chr_index, full_lines, names, name_strings, name_start_index,
                                                   all_bytes, all_bytes_main, fname, lines)

        except IndexError as e:
            print('BadNpcIndexError', traceback.format_exc())
    elif op_name == 'NpcTalk':
        jpn_chr_name = lines[0].decode(jpn_encode)
    else:  # AnonymousTalk
        chr_index = int(full_lines[20:full_lines.index(b',')], 16)
        # print('anon chr index', chr_index)
        try:
            jpn_chr_name = get_chr_name_from_index(chr_index, full_lines, names, name_strings, name_start_index,
                                                   all_bytes, all_bytes_main, fname, lines)
            print('anon chr name', jpn_chr_name)
        except:
            print('BadNpcIndexError', traceback.format_exc())
            pos = all_bytes.index(full_lines)
            for i in range(len(set_chr_names)):
                if set_chr_names[i].start() > pos:
                    break
                jpn_chr_name = eval(set_chr_names2[i].group(1).decode(encode))

    return jpn_chr_name


def get_full_lines(all_bytes):
    tmp_lines = temp_full_jpn_lines = [
        m for m in re.finditer(rb'([a-zA-Z]+Talk)\(((.|\n)+?)    \)|def Function_.+?: pass', all_bytes)
    ]

    return tmp_lines


if len(sys.argv) > 1:
    fnames = sys.argv[1:]
else:
    fnames = os.listdir(pc_jpn_path)

jpn_names = getnames("D:/file/programming/kiseki-evo/Trails to Azure/scripts/text/", "t_name._dt")
eng_names = getnames("D:/file/programming/kiseki-evo/Trails to Azure/scripts/text_en2-7/", "t_name._dt")

jpn_items = getitems("D:/file/programming/kiseki-evo/Trails to Azure/scripts/text/")
eng_items = getitems("D:/file/programming/kiseki-evo/Trails to Azure/scripts/text_en2-7/")

# eng_items_map = {}
# jpn_items_map = {}
#
# for k, v in jpn_items.items():
#     eng_items_map[v.decode(jpn_encode)] = eng_items[k]
#     jpn_items_map[v.decode(jpn_encode)] = v

# for i in range(len(jpn_names)):
# print(i, jpn_names[i].decode(jpn_encode))


def do_everything(path, fname, jpn_names, itemz, encode, wordsep=''):

    global jpn_name_strings, all_bytes_main, items

    displaytbl = []

    try:
        with open(os.path.join(path, fname), 'rb') as f:

            # fname = os.path.splitext(fname)[0]
            fname = fname[:fname.index('.')]

            print('fname', fname)

            footer[fname] = []

            # print('======')
            # print(fname)
            # print('======')

            all_bytes = f.read()

            if '_' not in fname:
                jpn_name_strings, start_index = get_string_names(all_bytes)
                all_bytes_main = all_bytes

            lines = get_full_lines(all_bytes)

            scene_num = 1
            increment_scene = False

            for i in range(len(lines)):


                # this line is a function header
                if lines[i].group(1) is None:
                    if increment_scene:
                        scene_num += 1
                        increment_scene = False
                    continue

                op_name = lines[i].group(1).decode(jpn_encode)

                single_lines = [m.group(2) if m.group(2) is not None else m.group(1) for m in re.finditer(rb'"([^"]+?)"|(scpstr\(SCPSTR_CODE_ITEM, [^)]+\))', lines[i].group(0))]

                if op_name == 'NpcTalk':
                    npc_name = single_lines[0]
                    del single_lines[0]

                pages = [b'']

                for one_line in single_lines:

                    if one_line.startswith(b'scpstr'):
                        items = itemz
                        pages[-1] += eval(one_line)
                    else:
                        pages[-1] += one_line

                    if one_line.endswith(b'\\x02\\x03'):
                        pages.append(b'')

                    increment_scene = True

                html_pages = pages.copy()

                # pages = [m.group(1) for m in re.finditer(rb'"([^"]+?)"', lines[i].group(0))]

                # print(i, [page.decode(jpn_encode) for page in pages], lines[i].group(0).decode(jpn_encode))

                icons = []

                for j in range(len(html_pages)):
                    voice = re.search(rb'#(\d+?)v', html_pages[j])
                    icon = re.search(rb'#(\d+?)F', html_pages[j])

                    if voice:
                        html_pages[j] = b'<audio id="v%s"><source src="talk/5/v%s.ogg" ' \
                                   b'type="audio/ogg"></audio><a href="javascript:void(0)" ' \
                                   b'onclick="document.getElementById(\'v%s\').play()">%s</a>' \
                                   % (voice.group(1), voice.group(1), voice.group(1), html_pages[j])
                    if icon:
                        # if len(icon.group(1)) == 3:
                        # icon_str = '<img style="height:100px;" src="itp/c_kao%s.bmp"/> ' \
                        # % icon.group(1).decode(utf8_encode)
                        # else:
                        icon_code = icon.group(1).decode(jpn_encode)

                        if len(icon_code) < 5:
                            icon_code = '0' * (5 - len(icon_code)) + icon_code

                        icon_str = '<img class="itp-xb" src="itp/5/ka%s.webp"/> ' \
                                   % icon_code
                        icons.append(icon_str)

                # print('pages', [line.decode(jpn_encode) for line in pages], [line for line in pages])

                ruby_jpn_lines = [line.decode(encode).encode(jpn_encode) for line in html_pages]

                for j in range(len(ruby_jpn_lines)):
                    rubyMatches = [m for m in re.finditer(br'#(\d+)R(.+?)(#)', ruby_jpn_lines[j])]
                    if len(rubyMatches) > 0:
                        print('found ruby!!!')
                    for m in reversed(rubyMatches):
                        end_index = m.start(1) - 1
                        start_index = end_index - int(m.group(1))
                        extra_text = m.group(2)
                        if int(m.group(1)) % 2 == 1:
                            if fname in {'c0410', 'c0500', 'c1450', 't1550'}:
                                start_index += 1
                            elif fname in {'c1120', 't4010'}:
                                start_index -= 1
                        # ruby_jpn_lines[j][:start_index] + b'<ruby>' + ruby_jpn_lines[j][start_index:end_index] + b'</ruby>' + ruby_jpn_lines[j][end_index:]
                        main_text = ruby_jpn_lines[j][start_index:end_index]

                        print(fname, 'attempt on ', ruby_jpn_lines[j].decode(jpn_encode))
                        print('index', start_index, end_index)
                        print('main', main_text.decode(jpn_encode), main_text)
                        print('extra', extra_text.decode(jpn_encode))
                        ruby_jpn_lines[j] = ruby_jpn_lines[j][:start_index] + b'<ruby>%s<rt>%s</rt></ruby>' % (
                            main_text, extra_text) + ruby_jpn_lines[j][(m.start(3) + 1):]
                        print('ruby result', ruby_jpn_lines[j].decode(jpn_encode))

                jpn_html_text = re.sub(rb'#\d+[A-Zv]|#N|[\x00-\x09]|\\x0[\dCD]', b'',
                                      b''.join(ruby_jpn_lines).replace(b'\\x01', b'<br/>').replace(b'\\x02\\x03',
                                                                                                   b'<br/><br/>')).replace(
                    b'\\x02', b'').decode(jpn_encode)

                set_chr_names = [
                    m for m in re.finditer(rb'SetChrName\(((.|\n)+?)\)', all_bytes)
                ]

                start_index = 8  # hack

                if op_name == 'NpcTalk':
                    jpn_chr_name = npc_name.decode(encode) #pages[0].decode(jpn_encode)
                else:
                    jpn_chr_name = get_chr_name(op_name, lines[i].group(0), pages, jpn_names, jpn_name_strings,
                                                start_index, fname, all_bytes, all_bytes_main, set_chr_names,
                                                set_chr_names, encode)


                # jpn_search_text = display_text.replace('<br/>', wordsep)
                jpn_search_text =  re.sub(rb'#\d+[A-Z]|#N|[\x00-\x09]|\\x0[\dCD]', b'',
                                      b''.join(pages).replace(b'\\x01', wordsep.encode(encode)).replace(b'\\x02\\x03',
                                                                                                   wordsep.encode(encode))).replace(
                    b'\\x02', b'').decode(encode)
                # print('jpn_chr_name', op_name, jpn_chr_name, jpn_search_text)
                # jpn_html_text = display_text

                displaytbl.append(
                    ['5', fname, str(len(displaytbl) + 1), '', '', '',
                     jpn_chr_name, jpn_search_text, jpn_html_text, op_name, ''.join(icons), str(scene_num)]
                )

                # except UnicodeDecodeError as e:
                #     print('no!!!!!!!', traceback.format_exc())
                #     pass
    except FileNotFoundError:
        pass

    os.system("title " + fname)

    return displaytbl


alljpn = {}
alleng = {}

# fnames = ['c0110.bin.py']
# fnames = ['e440b.bin.py']
# fnames = ['c0100.bin.py', 'c0100_1.bin.py']

for fname in fnames:
    if fname.endswith('.py'):
        alljpn[fname] = do_everything(pc_jpn_path, fname, jpn_names, jpn_items, utf8_encode)

for fname in fnames:
    if fname.endswith('.py'):
        alleng[fname] = do_everything(pc_eng_path, fname, eng_names, eng_items, utf8_encode, ' ')

for k, v in alljpn.items():
    print(f"{abs(len(alljpn[k]) - len(alleng[k])) : 04} {k}: JPN={len(alljpn[k])}; ENG={len(alleng[k])}")

    if len(alljpn[k]) != len(alleng[k]):
        for i in range(len(alleng[k])):
            try:
                print(f"{i} {alljpn[k][i][7]} {alleng[k][i][7]}")
            except IndexError:
                print(f"{i} {alleng[k][i][7]}")

    for i in range(len(alleng[k])):
        try:
            alldisplaytbl.append(
                [alleng[k][i][0], alleng[k][i][1], alljpn[k][i][11], alleng[k][i][2], alleng[k][i][6], alleng[k][i][7], alleng[k][i][8],
                 alljpn[k][i][6], alljpn[k][i][7], alljpn[k][i][8], alleng[k][i][9], alleng[k][i][10]]
            )
        except IndexError:
            alldisplaytbl.append(
                [alleng[k][i][0], alleng[k][i][1], alljpn[k][i][11], alleng[k][i][2], alleng[k][i][6], alleng[k][i][7], alleng[k][i][8],
                 '', '', '', alleng[k][i][9], alleng[k][i][10]]
            )


with open(r'ank2-7.sql', 'w', encoding='utf-8') as sqlfile:
    sqlfile.write('delete from script where game_id = 5;\n')
    for row in alldisplaytbl:
        newrow = []
        for cell in row:
            if type(cell) is list:
                # print('cell=', cell)
                cell = str([line.decode(jpn_encode) for line in cell])
            elif type(cell) is bytes:
                cell = str(cell)
            newrow.append(cell)
        # csvwriter.writerow(newrow)
        sqlfile.write(
            'insert into script (game_id, fname, scene, row, eng_chr_name, eng_search_text, eng_html_text, '
            'jpn_chr_name, jpn_search_text, jpn_html_text, op_name, pc_icon_html) values\n')
        sqlfile.write("('%s');\n" % ("','".join([c.replace("'", "''").replace('\x1a', '\\Z') for c in newrow])))