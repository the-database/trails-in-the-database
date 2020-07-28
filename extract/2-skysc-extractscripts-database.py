import re, os, struct, csv, json, textwrap, html, csv, math, sys, traceback

# psp_eng_path = "D:/file/kiseki-evo/FC-PC-USA/ED6_DT01/"
psp_eng_path = "./SC-PC-USA-patched/"
vita_jpn_path = "./SC-VITA-JPN-SOURCE/PCSG00489.VPK/gamedata/data_sc/msg/"
psp_jpn_path = "./SC-VITA-JPN-SOURCE/PCSG00489.VPK/gamedata/data_sc/scenario/1/"

jpn_encode = "cp932"

template_start = '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="shift_jis">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- The above 3 meta tags *must* come first in the head; any other head content must come *after* these tags -->
    <title>%s</title>

    <!-- Bootstrap -->
    <link href="css/bootstrap.min.css" rel="stylesheet">
    <link href="css/bootstrap-theme.min.css" rel="stylesheet">

    <!-- HTML5 shim and Respond.js for IE8 support of HTML5 elements and media queries -->
    <!-- WARNING: Respond.js doesn't work if you view the page via file:// -->
    <!--[if lt IE 9]>
      <script src="https://oss.maxcdn.com/html5shiv/3.7.3/html5shiv.min.js"></script>
      <script src="https://oss.maxcdn.com/respond/1.4.2/respond.min.js"></script>
    <![endif]-->
    
    <style type="text/css">
        img.itp {
            margin: -16px 0px -16px 0px;
            height: 128px;
        }
    </style>

  </head>
  <body>
    <h1>%s</h1>
    <table class="table table-condensed">'''

template_mid = '''</table><footer><table class="table table-condensed">'''

template_end = '''</table></footer>
    <!-- jQuery (necessary for Bootstrap's JavaScript plugins) -->
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js"></script>
    <!-- Include all compiled plugins (below), or include individual files as needed -->
    <script src="js/bootstrap.min.js"></script>
  </body>
</html>'''


def getwords():
    worddict = {}

    with open("en_US-words.txt", 'r') as f:
        for line in f:
            worddict[line.strip()] = True

    return worddict


worddict = getwords()


def getnamepointers(path, fname):
    pointers = []
    with open(path + fname, 'rb') as f:

        header = struct.unpack('<H', f.read(2))[0]

        while True:
            p = struct.unpack('<H', f.read(2))

            if len(pointers) > 0 and f.tell() > pointers[0]:
                break
            pointers.append(p[0])

    return header, pointers


def getnames(path, fname, pointers, offset):
    lines = []
    with open(path + fname, 'rb') as f:
        allbytes = f.read()
        for i in range(len(pointers)):
            part1 = allbytes[pointers[i]:pointers[i] + offset]
            part2 = allbytes[pointers[i] + offset:]
            endIndex = part2.index(b'\x00')
            part2 = part2[:endIndex]
            # part3 = allbytes[pointers[i] + offset + endIndex + 1:]
            # endIndex = part3.index(b'\x00')
            # part3 = part3[:endIndex]
            lines.append((part1, part2))
    return lines


def BuildStringList(*args):
    result = []

    for arg in args:
        result.append(arg)

    return result


def get_string_names(path, fname):
    with open(path + fname, 'rb') as f:
        all_bytes = f.read()

        string_list = re.search(rb'BuildStringList\((.|\n)+?    \)', all_bytes).group(0)

        start_index = int(re.search(rb'# (\d+)', string_list).group(1))

        # print(string_list)

        strings = eval(string_list.decode(jpn_encode))

    return strings, start_index


def getpointers(fname):
    pointers = []
    with open(vita_jpn_path + fname, 'rb') as f:
        line = 0
        while True:
            line += 1
            length = struct.unpack('<i', f.read(4))

            if not length:
                break

            command = f.read(1)

            if not command:
                break

            command = ord(command)

            pointers.append([length[0], command])

            if command == 0:
                break

            f.read(3)  # dummy

    return pointers


def get_line_length(line, has_portrait):
    line_length = 48
    if not has_portrait and b'#1S' not in line:
        line_length += 11

    if b'#3S' in line:
        line_length = int(line_length * (2 / 3))
    elif b'#4S' in line:
        line_length = int(line_length * (2 / 4))
    elif b'#5S' in line:
        line_length = int(line_length * (2 / 5))

    # print('line_length', len(line), line_length, b'#1S' in line, line)
    if b'#1S' in line:
        print('SMALL!!!!!', line)

    # print("get_line_length", line, line_length)

    return line_length


# LINE_LENGTH = 50
def word_len(text):
    num_codes = len([m for m in re.finditer(r'\\x(?:.{2})', text)])
    num_icons = len([m for m in re.finditer(r'\\x07\\x02', text)])
    # print(text,num_codes,num_icons,len(text),len(text) - num_codes * 4 + num_icons * 3)
    # print('word_len',text,len(text.replace('\\x02\\x03','')), num_codes*4, num_icons*3)
    # print('word_lens',text,len(text) - num_codes * 4 + num_icons * 3)

    # print('word_len', text)
    num_wide_chars = len([m for m in re.finditer(r'■', text)])
    # if num_wide_chars > 0:
    #     print('numwide!!!', num_wide_chars)

    return len(text) - num_codes * 4 + num_icons * 3 + num_wide_chars


def get_num_lines(text, max_length):
    lines = []
    remaining_text = text

    chunks = re.split(r'(\s+|-+)', text)
    # print('chunks',chunks)
    for chunk in chunks:
        # print('chunk: [%s] [%s]' % (chunk,chunk.lstrip()))
        if len(lines) == 0 or word_len(lines[-1]) + word_len(chunk) > max_length:
            lines.append(chunk.lstrip())
        else:
            lines[-1] += chunk
    # print("stuf!!!",lines)
    return len(lines)


def wrap_text(text, max_length):
    # num_lines = math.ceil(word_len(text) / maxLength)
    num_lines = get_num_lines(text, max_length)
    line_length = math.ceil(word_len(text) / num_lines)

    # print('num_lines', num_lines, max_length, text)

    while True:
        # print('line_length', line_length)
        lines = []
        chunks = re.split(r'(\s+|-+)', text)
        # print('chunks',chunks)
        for chunk in chunks:
            # print('chunk: [%s] [%s]' % (chunk,chunk.lstrip()))
            # print('asd',word_len(lines[-1]) + word_len(chunk) , line_length)
            # if len(lines) > 0:
            # print('maxlen',maxLength)
            # add new line with first chunk
            if len(lines) == 0 or word_len(lines[-1]) + word_len(chunk) > line_length:
                lines.append(chunk.lstrip())
            # append chunk to end of last line
            else:
                lines[-1] += chunk

        # print('lenlines',len(lines),lines)

        if len(lines) <= num_lines or line_length == max_length:
            return lines

        line_length += 1


def rebalance_linebreaks(old_message_group, has_portrait, three_lines_max=False):
    new_message_group = []

    old_messages = re.split(br'\\x02\\x03', b''.join(old_message_group))

    for k in range(len(old_messages)):
        if k < len(old_messages) - 1:
            old_messages[k] = old_messages[k].strip() + b'\\x02\\x03'

        old_lines = b''
        old_line_list = [s.strip() for s in old_messages[k].split(b'\\x01')]

        for i in range(len(old_line_list)):
            if i < len(old_line_list) - 1:
                if old_line_list[i].endswith(b'-'):
                    currentchunks = re.split(rb'(\s+)', old_line_list[i])
                    nextchunks = re.split(rb'(\s+)', old_line_list[i + 1])

                    combinedword = currentchunks[-1][:-1] + nextchunks[0]
                    combinedword = re.sub(rb'[.,!?"\']', b'', combinedword)  # strip punctuation

                    if combinedword.decode(jpn_encode) in worddict:
                        # print("OLD!!!!isword", combinedword, old_lines)
                        old_lines += old_line_list[i][:-1]
                    else:
                        # print("OLD!!!!notword", currentchunks[-1] + nextchunks[0])
                        old_lines += old_line_list[i]
                else:
                    old_lines += old_line_list[i] + b' '
            else:
                old_lines += old_line_list[i]

        skip_rebalance_line_breaks = True
        line_length = get_line_length(old_lines, has_portrait)
        # print('oldll', old_line_list)
        for line in old_line_list:
            print((re.sub(rb'(?:#\d+[A-Z])|\\x02\\x03', b'', line)), line_length)
            if len(re.sub(rb'(?:#\d+[A-Z])|\\x02\\x03', b'', line)) > line_length:
                skip_rebalance_line_breaks = False
                break

        if skip_rebalance_line_breaks:
            # continue
            # print('skiprebalance', old_line_list)
            tmp_group = old_line_list
        else:
            # print('dontskip',old_line_list)
            tmp_group = rebalance_linebreaks_width(old_lines, has_portrait)

        tmp_joined = b'\x01'.join(tmp_group)

        if len(tmp_group) > 1:
            for i in range(len(tmp_group) - 1):
                tmp_group[i] = tmp_group[i].strip() + b'\\x01'
        new_message_group += tmp_group

    return new_message_group


def rebalance_linebreaks_width(old_lines, has_portrait):
    line_length = get_line_length(old_lines, has_portrait)

    old_lines = re.sub(rb'(?:#\d+[A-RT-Z])', b'', old_lines)  # remove number codes except #S font size
    old_lines = re.sub(rb'#C[A-Z]#', b'', old_lines)  # remove color codes like #CW#

    return [wrapped.encode(jpn_encode) for wrapped in wrap_text(old_lines.decode(jpn_encode), line_length)]


def escape(s, quote=True):
    s = s.replace(b"&", b"&amp;")  # Must be done first!
    s = s.replace(b"<", b"&lt;")
    s = s.replace(b">", b"&gt;")
    if quote:
        s = s.replace(b'"', b"&quot;")
        s = s.replace(b'\'', b"&#x27;")
    return s


def html_table(lol):
    display_reg = rb'((?:#\d+[A-QS-Z])+?|[\x00-\x1f\xff]+?)'
    display_reg_replace = rb'<small style="font-family:monospace;color:gray">\1</small>'

    tbl = '<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css" ' \
          'integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u" ' \
          'crossorigin="anonymous"><table class="table table-hover"style="width:auto">'

    for sublist in lol:
        tbl += '  <tr>'
        for cell in sublist:
            if type(cell) is list:
                cell = str([re.sub(display_reg, display_reg_replace, line).decode(jpn_encode) for line in cell])
            elif type(cell) is bytes:
                cell = str(re.sub(display_reg, display_reg_replace, escape(cell)))
            tbl += '<td>%s</td>' % cell
        tbl += '  </tr>'
    tbl += '</table>'
    return tbl


def rpl(m):
    # print(m.group(1))
    return chr(int(m.group(1), 16)).encode(jpn_encode)


def getsplitbodybytes(pointers, bodybytes):
    splitbodybytes = []
    # perform jpn -> eng replacements in bodybytes
    # store offsets for eng dialogue lines
    for index in range(1, len(pointers)):
        sliced = bodybytes[pointers[index][0]:]
        # sliced = sliced[:sliced.find(b'\x02\x00')].decode(jpn_encode)

        if index < len(pointers) - 1:
            end_index = pointers[index + 1][0] - pointers[index][0]
            # endIndex = sliced.find(b'\x02\x00')
            sliced = sliced[:end_index]

        splitbodybytes.append(sliced)
    return splitbodybytes


def export_patched_mbin(splitbodybytes, headerbytes, fname):
    new_offsets = [0]
    for index in range(len(splitbodybytes) - 1):
        new_offsets.append(len(splitbodybytes[index]) + new_offsets[-1])

    newheaderbytes = headerbytes[:4]
    for index in range(len(new_offsets)):
        # get 4 leading bytes from original header
        newheaderbytes += headerbytes[(index) * 8 + 4: (index) * 8 + 8]
        newheaderbytes += struct.pack('<i', new_offsets[index])

    # copy last 3 bytes from original header
    newheaderbytes += headerbytes[((len(new_offsets)) * 8 + 4):]

    with open('out/' + fname + '.mbin', 'wb') as wf:
        wf.write(newheaderbytes)
        wf.write(b''.join(splitbodybytes))


def get_original_eng_lines(full_eng_line):
    all_lines = []

    m = re.search(rb'scpstr\(SCPSTR_CODE_COLOR,\s+0x([^)]+)\)', full_eng_line)
    color_str = b''
    if m:
        color_str = b'\x07' + chr(int(m.group(1), 16)).encode(jpn_encode)

    # apply colors
    full_eng_line = re.sub(rb'#(\d+)C', lambda m: b'\x07' + chr(int(m.group(1), 16)).encode(jpn_encode), full_eng_line)

    eng_parts = [m.group(1) for m in re.finditer(rb'"([^"]+?)"', full_eng_line)]

    if full_eng_line.startswith(b'NpcTalk'):
        eng_joined = eng_parts[0] + b'\x00' + color_str + b''.join(eng_parts[1:])
    else:
        eng_joined = color_str + b''.join(eng_parts)

    # insert missing color codes for #I icon codes
    eng_line = re.sub(rb'(?<!\x07\x02)(#\d+I)', b'\x07\x02\\1', eng_joined)

    eng_line = re.sub(rb'(?:#\d+[A-RT-Z])', b'', eng_line)  # remove number codes except #S font size
    eng_line = re.sub(rb'#C[A-Z]#', b'', eng_line)  # remove color codes like #CW#
    eng_line = re.sub(rb'\\x(.{2})', rpl, eng_line)  # apply control codes (\\x01 -> \x01)

    # replace every pair of spaces with a single space
    # hack attempt to fix sign text
    eng_line = re.sub(rb'  ', b' ', eng_line)
    # escape #
    # print('before',eng_line)
    eng_line = re.sub(rb'#(\d+)(?=[^A-Za-z\d])', rb'No. \1', eng_line)
    # print('after',eng_line)

    eng_lines = eng_line.split(b'\x02\x03')
    all_lines += [item for sublist in
                  [re.split(br'(?<![\x00-\x1f])\x00', line) for line in eng_lines] for item in sublist]

    return all_lines


def get_eng_lines(full_eng_line, has_portrait):
    all_lines = []

    m = re.search(rb'scpstr\(SCPSTR_CODE_COLOR,\s+0x([^)]+)\)', full_eng_line)
    color_str = b''
    if m:
        color_str = b'\x07' + chr(int(m.group(1), 16)).encode(jpn_encode)

    # apply colors
    full_eng_line = re.sub(rb'#(\d+)C', lambda m: b'\x07%02x' % struct.unpack('B', (m.group(1)))[0], full_eng_line)

    eng_parts = [m.group(1) for m in re.finditer(rb'"([^"]+?)"', full_eng_line)]

    if full_eng_line.startswith(b'NpcTalk'):
        eng_joined = eng_parts[0] + b'\x00' + color_str + b''.join(rebalance_linebreaks(eng_parts[1:], has_portrait))
    elif full_eng_line.startswith(b'AnonymousTalk'):
        tmp_joined = b''.join(eng_parts)
        if b'   ' in tmp_joined or b'\x81@' * 3 in tmp_joined:  # don't rebalance lines
            tmp_list = eng_parts
            # print("norebalance!!!", eng_parts)
            for part in eng_parts:
                if len(part) > 59:
                    print("TOOLONG!!!", len(part), part)
                    # lengths = [len(part) > 48 for part in eng_parts]
                    # if True in lengths:
                    # print("TOOLONG!!!!",eng_parts)
        else:
            tmp_list = rebalance_linebreaks(eng_parts, has_portrait, True)
        # if len(tmp_list) > 3:
        # 	tmp_list[2] += tmp_list[2].replace(b'\\x01', b'\\x02\\x03')
        # 	print('tmp_list',tmp_list)
        eng_joined = color_str + b''.join(tmp_list)
    else:
        eng_joined = color_str + b''.join(rebalance_linebreaks(eng_parts, has_portrait))

    # apply control codes

    # eng_line = eng_joined
    # print('eng_line',eng_line)
    eng_line = re.sub(rb'\\x(.{2})', rpl, eng_joined)
    eng_line = eng_line.replace(b'Zane', b'Zin')

    # replace every pair of spaces with a single space
    # hack attempt to fix sign text
    eng_line = re.sub(rb'  ', b' ', eng_line)
    # escape #
    eng_line = re.sub(rb'#(\d+)(?=[^A-Za-z\d])', rb'No. \1', eng_line)
    # print('bfeore',eng_line)
    # print('after',eng_line)

    eng_lines = eng_line.split(b'\x02\x03')
    all_lines += [item for sublist in [re.split(br'(?<![\x00-\x1f])\x00', line) for line in eng_lines] for item in
                  sublist]

    return all_lines


def get_jpn_lines(full_jpn_line):
    trimmed_jpn_line = full_jpn_line[:full_jpn_line.find(b'\x02\x00') + 1]

    jpn_lines = trimmed_jpn_line.split(b'\x02\x03')

    # print('trimmedJpn',trimmed_jpn_line.decode(jpn_encode))

    # jpn_lines = get_jpn_lines(
    #     re.sub(rb'(\x1f)(..)', lambda match: b'item(0x%02x)' % struct.unpack('<H', (match.group(2)))[0],
    #            splitbodybytes[i]))

    jpn_lines = [re.sub(rb'item\((0x.+?)\)', lambda m: b'\x1f' + struct.pack('<H', int(m.group(1), 16)), item) for sublist in [re.split(br'(?<![\x00-\x1f])\x00', line)
                                                                       for line in jpn_lines] for item in
                 sublist]

    return jpn_lines


def fix_eng_lines(eng_lines, jpn_lines, full_eng_lines, has_portrait, i):
    skip_line = False

    # engLine is empty
    if len(eng_lines) > 0 and re.search(br'[A-Za-z0-9.,!?\x81-\x9f\']', eng_lines[0]):
        # engLine has an extra leading character name; remove it
        # print('fixEngLines', i, len(eng_lines), len(jpn_lines), eng_lines)
        if full_eng_lines[i][0].startswith(b'NpcTalk'):  # and len(eng_lines) - 1 == len(jpn_lines):
            # print('charnamehax', eng_lines, [line.decode(jpn_encode) for line in jpn_lines])
            eng_lines = eng_lines[1:]

        # jpnLine is engLine + next engLine(s)
        # elif i < len(full_eng_lines) - 1 and len(eng_lines) + len(getEngLines(full_eng_lines[i+1])) == len(jpn_lines):
        k = 1
        while i + k < len(full_eng_lines) and len(eng_lines) < len(jpn_lines):

            if full_eng_lines[i + k] is not None:

                # print('??', full_eng_lines[i + k])
                eng_lines[-1] = eng_lines[-1][:-1]  # remove last char (\x02) from last line
                next_lines = get_eng_lines(full_eng_lines[i + k], has_portrait)
                if full_eng_lines[i + k][0].startswith(b'NpcTalk'):
                    eng_lines += next_lines[1:]
                # pass
                else:
                    eng_lines += next_lines
            k += 1
            # print('nextlinehax', eng_lines, [line.decode(jpn_encode) for line in jpn_lines])
    else:
        skip_line = True

    # can't reconcile differences; log and skip this line
    # print('lens',len(eng_lines),len(jpn_lines))
    if len(eng_lines) != len(jpn_lines):
        # print('len eng_lines: %d; len jpn_lines: %d' % (len(eng_lines), len(jpn_lines)))
        skip_line = True

    return eng_lines, skip_line


allcodes = set()

def get_npc_index(allbytes_main, scena_num, func_num):
    npcs = [m for m in re.finditer(rb'DeclNpc', allbytes_main)]
    # print('npcs', npcs)
    # print('search',rb'TalkFunctionIndex\s+= %d,[\r\n]+\s+TalkScenaIndex\s+= %d' % (scena_num, func_num))
    npc = [m for m in re.finditer(rb'TalkFunctionIndex\s+= %d,[\r\n]+\s+TalkScenaIndex\s+= %d' % (scena_num, func_num), allbytes_main)][0]
    return [i for i in range(len(npcs)) if (npc.start() > npcs[i].start() and (i+1 == len(npcs) or npc.start() < npcs[i+1].start()))][0]


# if allbytes is all bytes from an included scenario, then allbytes_main 
# is allbytes from the scenario that included it
def get_chr_name(op_name, full_lines, lines, names, name_strings, name_start_index,
                 fname, allbytes, allbytes_main, set_chr_names, set_chr_names2):
    eng_chr_name = ''

    if op_name == 'ChrTalk':
        try:
            chr_index = int(full_lines[20:full_lines.index(b',')], 16)

            if chr_index == 0xfe:
                # print('0xfe!!!')
                # find the nearest TalkBegin before this line
                # print (full_lines)
                # print('all', allbytes)
                pos = allbytes.index(full_lines)
                talkbegins = [m for m in re.finditer(rb'TalkBegin\((.+)\)', allbytes) if m.start() < pos]

                funcs = [m for m in re.finditer(rb'def Function_(\d+)_', allbytes) if m.start() < pos]
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
                    try:
                        # print('func_num', scena_num, func_num, lines)
                        # print('main', fname, allbytes_main )
                        # print('npc',npc.start(),[m.start() for m in npcs])
                        npc_index = get_npc_index(allbytes_main, scena_num, func_num)
                        # print('npc_index', npc_index, name_strings[npc_index])
                        eng_chr_name = name_strings[npc_index + 1]
                    except IndexError as e:
                        # print('InitialNpcIndexError', traceback.format_exc())

                        calls = [m for m in re.finditer(rb'Call\(%d, %d\)' % (scena_num, func_num), allbytes_main)]
                        # print('notalkbegins!!!', fname, lines, calls)
                        if len(calls) == 0:
                            print('nocalls!!!', fname, lines, rb'Call\(%d, %d\)' % (scena_num, func_num))
                        else:
                            call = calls[0]
                            main_funcs = [m for m in re.finditer(rb'def Function_(\d+)_', allbytes_main) if m.start() < call.start()]
                            main_func_num = eval(main_funcs[-1].group(1))
                            npc_index = get_npc_index(allbytes_main, 0, main_func_num)
                            eng_chr_name = name_strings[npc_index + 1]
                            # print(eng_chr_name)
                else:
                    # print(name_strings[eval(talkbegin) - name_start_index + 1] )
                    # print('talkbegin', hex(talkbegin), name_strings)
                    eng_chr_name = name_strings[talkbegin - name_start_index + 1]
            elif chr_index > 0x100:
                chr_index -= 0x100
                chr_index -= 1
                eng_chr_name = names[chr_index].decode(jpn_encode)
            else:
                # print(full_lines)
                eng_chr_name = name_strings[chr_index - name_start_index + 1]
        except IndexError as e:
            # print('BadNpcIndexError', traceback.format_exc())
            pass
            # print(op_name, eng_chr_name, full_lines)
    elif op_name == 'NpcTalk':
        eng_chr_name = lines[0].decode(jpn_encode)
    else:  # AnonymousTalk
        # setchrnames = [m for m in re.finditer(rb'SetChrName\((.+?)\)', allbytes[:allbytes.index(full_lines)])]
        # eng_chr_name = eval(setchrnames[-1].group(1).decode(jpn_encode))
        pos = allbytes.index(full_lines)

        for i in range(len(set_chr_names)):
            if set_chr_names[i].start() > pos:
                break
            # print(i, [m.group(1) for m in set_chr_names2], [m.group(1) for m in set_chr_names])
            # if eval(set_chr_names[i].group(1).decode(jpn_encode)) != '':
            eng_chr_name = eval(set_chr_names2[i].group(1).decode(jpn_encode))

    return eng_chr_name

def find_first_non_code_char(text):
    tmp = re.sub(b'\x1f..', b'', text) # strip item codes
    tmp_index = re.search(rb'[^\x00-\x1f\xfe-\xff]', tmp).start()
    return text.find(tmp[tmp_index:])

# def replace_after(search, repl, occurrences, i, text):
    # return text[:i] + text[i:].replace(search, repl, occurrences)

def insert_codes(eng_lines, jpn_lines, full_eng_line):
    # print('insertCodes')
    for j in range(len(eng_lines)):

        # copy over item codes
        jpn_items = [m for m in re.finditer(rb'\x1f((:?.|\n)(:?.|\n))', jpn_lines[j])]
        eng_items = [m for m in re.finditer(rb'#(\d+)i', eng_lines[j])]

        if len(jpn_items) != len(eng_items):
            raise RuntimeError("item count mismatch", len(jpn_items), len(eng_items), jpn_lines[j], eng_lines[j], [it.group(0) for it in eng_items])

        for i in range(len(jpn_items)):
            # print('item',i,jpn_items[i].group(0),eng_items[i].group(0))
            eng_lines[j] = eng_lines[j].replace(eng_items[i].group(0), jpn_items[i].group(0), 1)
        # print('copied item', eng_lines[j])

        # print(j,eng_lines[j])
        # print('before ...',eng_lines[j])

        # if not re.search (rb'((^|\s+)[\x00-\x1fa-zA-Z0-9]+\.\.\.)(?=[a-zA-Z0-9]+)', eng_lines[j]) and re.search(rb'([a-zA-Z0-9]+\.\.\.)(?=[a-zA-Z0-9]+)', eng_lines[j]):
        # 	print("REGEX!!",eng_lines[j])

        # fix "word...word" -> "word... word"
        eng_codes = [m for m in re.finditer(rb'#\d+[A-RT-Z]', eng_lines[j])]
        
        clean_eng = re.sub(rb'#\d+[A-Z]', b'', eng_lines[j])

        # ellipses = [m for m in re.finditer(rb'([a-zA-Z0-9%]+\.\.\.)(?=[a-zA-Z0-9]+\s*)', clean_eng)]

        # print('numellipses', len(ellipses), clean_eng)

        # for m in reversed(ellipses):
            # eng_lines[j] = eng_lines[j].replace(m.group(0), m.group(0) + b' ')
            # eng_lines[j] = replace_after(m.group(0), m.group(0) + b' ', 1, m.start(0), eng_lines[j])
            # print('do_replace', m.group(0), eng_lines[j])

        eng_lines[j] = re.sub(rb'([a-zA-Z0-9%]+\.\.\.)(?=[a-zA-Z0-9]+\s*)', lambda m: m.group(0) + b' ', eng_lines[j])

        # eng_lines[j] = re.sub(rb'((^|\s+)[\x00-\x1fa-zA-Z0-9]+\.\.\.)(?=[a-zA-Z0-9]+)', b'\\1 ', eng_lines[j]) # fix "word...word" -> "word... word"

        eng_lines[j] = re.sub(rb'([^. \]\x00-\x1f]+--)\s+([^. \]\x00-\x1f]+)', b'\\1\\2',
                              eng_lines[j])  # fix 'word-- word' -> 'word--word'

        # don't care about preserving #R codes used for furigana
        codes = [m for m in re.finditer(br'((?:#\d+[A-QT-Z])+?)', jpn_lines[j])]
        scodes = 0

        i_code_index = 0
        s_code_index = 0

        # print('str',[code.group(1) for code in codes])

        lens = []

        if len(codes) > 0:
            lens = [0]

        for code in codes[:-1]:
            lens.append(lens[-1] + len(code.group(1)))

        jpn_control_codes = [m.start() for m in re.finditer(rb'(?<![\x00-\x1f])\x01', jpn_lines[j])]
        eng_control_codes = [m.start() for m in re.finditer(rb'(?<![\x00-\x1f])\x01', eng_lines[j])]

        for code in codes:

            insert_index = find_first_non_code_char(eng_lines[j]) # first non-code char position in eng
            + code.start(1) # code position in jpn
            - find_first_non_code_char(jpn_lines[j])  # first non-code char position in jpn

            # print('code', code.group(1), code.start(1),
            #     find_first_non_code_char(jpn_lines[j]),
            #     find_first_non_code_char(eng_lines[j]),
            #     insert_index,
            #     jpn_lines[j], '\n', eng_lines[j])

            stuff = [code.start(1) < m for m in jpn_control_codes]

            # print('stuff',stuff, jpn_control_codes)

            # size code
            if b'S' in code.group(1):
                scodes += 1

                if scodes > 1:
                    # print('continue...', eng_lines[j])
                    continue

            # icon code
            if b'I' in code.group(1):
                # print('icode=', code.group(1))
                try:
                    print('things',[m.start() + 2 for m in re.finditer(br'\x07\x02', eng_lines[j])], i_code_index)
                    insert_index = [m.start() + 2 for m in re.finditer(br'\x07\x02', eng_lines[j])][i_code_index]
                    i_code_index += 1
                except IndexError:
                    print('IndexErrorI:', code.group(1))
                    print(eng_lines, [line.decode(jpn_encode) for line in jpn_lines], len(eng_lines), len(jpn_lines))
                    insert_index = -1
            elif False in stuff:
                if len(jpn_control_codes) != len(eng_control_codes):
                    insert_index = -1
                    try:
                        print('nolencode!!!', code.group(1), jpn_lines[j].decode(jpn_encode),
                              eng_lines[j].decode(jpn_encode))
                    except:
                        print('nolencode!!!', code.group(1), jpn_lines[j], eng_lines[j])
                    pass
                else:
                    eng_control_codes = [m for m in re.finditer(rb'\x01', eng_lines[j])]
                    insert_index = eng_control_codes[stuff.index(False)].start() + 1
                    # print(eng_control_codes, insert_index, eng_lines[j])

            if insert_index != -1:
                eng_lines[j] = eng_lines[j][:insert_index] + code.group(1) + eng_lines[j][insert_index:]
                # scount = [x.group(1) for x in codes if b'S' in x.group(1)]
                # if len(scount) > 1:
                # print('SCOUNT!!!',len(scount),scount,eng_lines,[line.decode(jpn_encode) for line in jpn_lines])

        # also copy color code: \x07\x##

        # try:
        #     prev_jpn_color_matches = [m for m in re.finditer(rb'\x07[\x00-\x1f]', jpn_lines[j-1])]
        #     prev_eng_color_matches = [m for m in re.finditer(rb'\x07[\x00-\x1f]', eng_lines[j-1])]
        # except IndexError:
        #     prev_jpn_color_matches = []
        #     prev_eng_color_matches = []

        jpn_color_matches = [m for m in re.finditer(rb'\x07[\x00-\x1f]', jpn_lines[j])]
        eng_color_matches = [m for m in re.finditer(rb'\x07[\x00-\x1f]', eng_lines[j])]
        # print('ecm', [m.group(0) for m in eng_color_matches])

        # print('colorMatch',colorMatch)
        # only get color from JPN line if Eng line has no colors already
        # print('colorlens', len(jpn_color_matches), len(eng_color_matches), eng_lines[j])
        if re.search(rb'\x1f', eng_lines[j]):
            # print('hasitem', eng_lines[j])
            eng_lines[j] = b'\x07\x00' + re.sub(rb'\x1f..', lambda m: b'\x07\x02' + m.group(0) + b'\x07\x00', eng_lines[j])
            # print('afterhasitem', eng_lines[j])
            # if True in [m.group(0) == b'\x07\x05' for m in jpn_color_matches]:
                # print('GREEN!!!')
        elif len(jpn_color_matches) > 0 and len(eng_color_matches) == 0:
            # print('colormatches!', len(jpn_color_matches), eng_lines[j], jpn_lines[j].decode(jpn_encode))
            if full_eng_line.startswith(b'NpcTalk'):
                parts = eng_lines[j].split(b'\x01')
                eng_lines[j] = parts[0] + b'\x01' + jpn_color_matches[0].group(0) + b'\x01'.join(parts[1:])
            else:
                eng_lines[j] = jpn_color_matches[0].group(0) + eng_lines[j]
        elif len(jpn_color_matches) > 0 and len(jpn_lines[j]) - jpn_color_matches[-1].end() == 1:
            print("WHAT!!!!!!!!")
            eng_lines[j] = eng_lines[j].replace(b'\x02', jpn_color_matches[-1].group(0) + b'\x02')

        # print('coderesult', eng_lines[j])

    return eng_lines


def get_scenes(allbytes):
    instructions = [
        m.group(1).decode(jpn_encode) for m in re.finditer(rb'NewScene.+?[/](.+?)[\'"]', allbytes)
    ]

    return instructions


def replace_nth(string, sub, wanted, n):
    # print('replace_nth', string, sub, wanted, n)
    where = [m.start() for m in re.finditer(sub, string)][n - 1]
    before = string[:where]
    after = string[where:]
    after = after.replace(sub, wanted, 1)
    new_string = before + after
    return new_string


def item_bytes_to_display(text):
    return re.sub(rb'(\x1f)(..)', lambda match: b'item(0x%02x)' % struct.unpack('<H', (match.group(2)))[0],
                               text)


nameDictBase = {
    'ブレードアンヘル'.encode(jpn_encode): b'Blade Angel',
    'ロレント市長邸'.encode(jpn_encode): b'Rolent - Mayor\'s Residence',
    'ルーアン市長邸'.encode(jpn_encode): b'Ruan - Mayor\'s Residence',
    '青年'.encode(jpn_encode): b'Young Man',
    'アイナ街道'.encode(jpn_encode): b'Aurian Road',
    '空賊たち'.encode(jpn_encode): b'Sky Bandits',
    '不精髭の男'.encode(jpn_encode): b'Unshaven Man',
    '貴族風の男性'.encode(jpn_encode): b'Nobleman',
    '黒服の老人'.encode(jpn_encode): b'Old Man in Black',
    '年配の整備員'.encode(jpn_encode): b'Old Technician',
    '女性の声'.encode(jpn_encode): b'Woman\'s Voice',
    '東方風の女性'.encode(jpn_encode): b'Eastern Woman',
    'ワイスマン'.encode(jpn_encode): b'Weissmann',
    '中年女性'.encode(jpn_encode): b'Middle-Aged Woman',
    'ドレス姿の娘'.encode(jpn_encode): b'Girl in Dress',
    '民家１'.encode(jpn_encode): b'Home 1',
    '⇒１Ｆ東展示室'.encode(jpn_encode): b'\x81\xcb Gallery 1F',
    '設計室'.encode(jpn_encode): b'Design Room',
    '中央工房１Ｆ'.encode(jpn_encode): b'Central Factory 1F',
    'ミルヒ街道方面'.encode(jpn_encode): b'Milch Main Road',
    'エレベータ'.encode(jpn_encode): b'Elevator',
    'ガソリンタンク'.encode(jpn_encode): b'Gasoline',
    'グラス'.encode(jpn_encode): b'Glass',
    'サラダ'.encode(jpn_encode): b'Salad',
    'パン'.encode(jpn_encode): b'Bread',
    'フォーク'.encode(jpn_encode): b'Fork',
    'ワイングラス'.encode(jpn_encode): b'Fancy Wine Glass',
    '地震制御用ダミーキャラ'.encode(jpn_encode): b'Quake-Setting Dummy',
    '料理'.encode(jpn_encode): b'Food',
    '町民１'.encode(jpn_encode): b'Villager 1',
    '紅茶'.encode(jpn_encode): b'Tea',
    '酒瓶'.encode(jpn_encode): b'Bottle',
    '銀髪の青年'.encode(jpn_encode): b'Silver-Haired Youth',
    'シード'.encode(jpn_encode): b'Cid',
    'ワイスマンの声'.encode(jpn_encode): b"Weissmann's Voice",
    '青年の声'.encode(jpn_encode): b"Man's Voice",
    '軽そうな青年'.encode(jpn_encode): b'Insensitive Jerk',
    '男の声'.encode(jpn_encode): b"Man's Voice",
    '娘の声'.encode(jpn_encode): b"Girl's Voice",
    '女性'.encode(jpn_encode): b'Woman',
    '軍装の青年'.encode(jpn_encode): b'Young Man in Uniform',
    '男性の声'.encode(jpn_encode): b"Man's Voice",
    '子供たち'.encode(jpn_encode): b'Children',
    '軍服の男'.encode(jpn_encode): b'Man in Uniform',

}

inverseNameDict = {}
dictFail = {}

def convertName(oldName):
    if oldName.encode(jpn_encode) in inverseNameDict:
        return inverseNameDict[oldName.encode(jpn_encode)].decode(jpn_encode)
    else:
        print('warning!!!!', oldName)

    return oldName


def getNames(path, fname):
    regex = r'(#\d+?F(#\d[A-Z])*)(.+?)\x02\x00'

    names = []

    with open(path + fname, 'rb') as f:
        allbytes = f.read()
        startIndex = allbytes.rindex(b'@FileName')
        nameStr = allbytes[startIndex:]

        # print(nameStr)

        names = nameStr.split(b'\x00')

    return [name for name in names if name.strip() != b'']


def setupNameDict():
    nameDict = {}

    for fname in os.listdir(vita_jpn_path):
        # for fname in ['t0311.mbin']:

        try:

            if fname.endswith('.py'):
                with open(psp_eng_path + fname, 'rb') as f:

                    all_bytes = f.read()

                    string_list = re.search(rb'BuildStringList\((.|\n)+?    \)', all_bytes).group(0)

                    start_index = int(re.search(rb'# (\d+)', string_list).group(1))

                    chr_talk_codes = [int(m.group(0)[20:m.group(0).index(b',')], 16) for m in re.finditer(rb'ChrTalk\((?:[^)])((.|\n)+?)    \)', all_bytes)]

                    strings = eval(string_list.decode(jpn_encode))

                    chr_talk_codes_filtered = [code - start_index + 1 for code in chr_talk_codes if code - start_index + 1 < len(strings)]

                    print(fname, len(strings), strings)

                    # print('chr_talk', fname, chr_talk_codes_filtered)
                    for code in chr_talk_codes_filtered:
                        # print(code, start_index)
                        # print('chr_talk', code, strings[code])
                        try:
                            chr_names[strings[code].encode(jpn_encode)] = True
                        except IndexError:
                            pass

                    pass

            fname = os.path.splitext(fname)[0]

            engNames = getNames(psp_eng_path, fname + '._SN')
            jpnNames = getNames(psp_jpn_path, fname + '.bin')
            # jpnNames = getNames(vita_jpn_path, fname + '.bin')

            if fname == 'c5201':
                engNames.append(b'Rod Angel')
            if fname == 'c5203':
                engNames.append(b'Arrow Angel')
            if fname == 'c5205':
                engNames.append(b'Blade Angel')
            if fname in ['t2101', 't2105']:
                engNames.append(b'Ruan - Mayor\'s Residence')


            print(fname, len(engNames), len(jpnNames), str(len(engNames) == len(jpnNames)) + '!!!!!!')
            print('engNames',[name.decode(jpn_encode) for name in engNames])
            print('jpnNames',[name.decode(jpn_encode) for name in jpnNames])

            for i in range(len(jpnNames)):
                if jpnNames[i] in nameDict and nameDict[jpnNames[i]] != engNames[i]:
                    print('dictfail!', jpnNames[i].decode(jpn_encode), nameDict[jpnNames[i]],
                          engNames[i].decode(jpn_encode))
                    dictFail[jpnNames[i]] = 1
                nameDict[jpnNames[i]] = engNames[i]

                # if '市長邸' in jpnNames[i].decode(jpn_encode):
                #   print('yes!!!!!!',jpnNames[i].decode(jpn_encode), engNames[i])
                # print(i, jpnNames[i].decode(jpn_encode))
        except FileNotFoundError:
            # print("NO!!!!",fname)
            pass

    for key in nameDictBase:
        nameDict[key] = nameDictBase[key]

    for k, v in nameDict.items():
        inverseNameDict[v] = k


def main():
    displaytbl = []
    displaytbl2 = {}
    footer = {}

    setupNameDict()

    eng_name_header, eng_name_pointers = getnamepointers("./SC-PC-USA-text/", "t_name._dt")
    eng_names_tmp = getnames("./SC-PC-USA-text/", "t_name._dt", eng_name_pointers, 34)
    # print(eng_names_tmp)
    eng_names = [line[1] for line in eng_names_tmp]
    # jpn_name_pointers = getnamepointers("./FC-VITA-JPN-SOURCE/PCSG00488.VPK/gamedata/data/text/", "t_name._dt")
    # jpn_names = getnames("./FC-VITA-JPN-SOURCE/PCSG00488.VPK/gamedata/data/text/", "t_name._dt", jpn_name_pointers, 38)

    if len(sys.argv) > 1:
        fnames = sys.argv[1:]
    else:
        fnames = os.listdir(vita_jpn_path)

    # for fname in os.listdir(vita_jpn_path):
    # for fname in ['c0300']:
    for fname in fnames:

        fname = os.path.splitext(fname)[0]

        # skip debug file
        if fname in ['a0020']:
            print('skip %s' % fname)
            continue

        print('=' * len(fname))
        print(fname)
        print('=' * len(fname))

        pointers = getpointers(fname + '.mbin')

        if len(pointers) == 0:
            continue

        splitbodybytes = []

        # if len(pointers) == 0:
        #     continue

        displaytbl2[fname] = []
        footer[fname] = []

        try:

            if '_' not in fname:
                eng_name_strings, name_start_index = get_string_names(psp_eng_path, fname + ".py")
                jpn_name_strings, jpn_start_index = get_string_names(
                    "./SC-VITA-JPN-SOURCE/PCSG00489.VPK/gamedata/data_sc/scenario/1/", fname + ".py")

            # get split body bytes from japanese vita script
            print('try open', vita_jpn_path + fname + '.mbin')
            with open(vita_jpn_path + fname + '.mbin', 'rb') as f:

                all_bytes = f.read()

                body_offset = pointers[0][0] * 8 + 7

                headerbytes = all_bytes[:body_offset]
                bodybytes = all_bytes[body_offset:]

                splitbodybytes = getsplitbodybytes(pointers, bodybytes)

            files = [i for i in os.listdir(psp_eng_path) if
                     os.path.isfile(os.path.join(psp_eng_path, i)) and i.startswith(fname.upper() + '.') and i.endswith(
                         '.py')]

            if len(files) != 1:
                print('no!!!!', len(files))

            print('try open', psp_eng_path + files[0])
            with open(psp_eng_path + files[0], 'rb') as f:

                all_bytes = f.read()

                # print('_?', fname)
                if '_' not in fname:
                    allbytes_main = all_bytes

                temp_full_eng_lines = [
                    m.group(0) for m in re.finditer(rb'[a-zA-Z]+Talk\(((.|\n)+?)    \)', all_bytes)
                ]

                # print('len temp_full_eng_lines', len(temp_full_eng_lines))

                # displaytbl.append([str(len(full_eng_lines) == len(splitbodybytes))+'!!!!!!!!',
                # str(len(full_eng_lines)), str(len(splitbodybytes)),''])

                with open(vita_jpn_path + '../scenario/1/%s.py' % fname, 'rb') as jf:

                    alljpnbytes = jf.read()

                    temp_full_jpn_lines = [
                        m for m in re.finditer(rb'([a-zA-Z]+Talk|OP_ED)\(((.|\n)+?)\)',
                                               alljpnbytes)
                    ]

                    ec_ref_matches = [
                        m.group(1) for m in re.finditer(rb'OP_EC\((.+?)\)', alljpnbytes)
                    ]

                    ec_refs = {}

                    for ref in ec_ref_matches:
                        ec_refs[int(ref, 16)] = True

                    funcs = [
                        m for m in re.finditer(rb'def Function_(\d+)_', alljpnbytes)
                    ]

                    set_chr_names_jpn = [
                        m for m in re.finditer(rb'SetChrName\(((.|\n)+?)\)', alljpnbytes)
                    ]

                    #
                    footer[fname] = get_scenes(alljpnbytes)

                    chest_indexes = {}

                    j = 0
                    offset = 0

                    for i in range(len(temp_full_jpn_lines)):
                        # if temp_full_jpn_lines[i].group(1) is None:
                        #     indexes[int(temp_full_jpn_lines[i].group(4), 16) + offset] = True
                        if temp_full_jpn_lines[i].group(1) == b'OP_ED':
                            # offset += 1
                            chest_indexes[i] = True

                    print('chest_indexes', sorted(chest_indexes.keys()))

                    print('ec refs', sorted(ec_refs.keys()))

                    print('missing', set(range(len(splitbodybytes))) - set(ec_refs))

                    full_eng_lines = [temp_full_eng_lines[i] for i in range(len(temp_full_eng_lines))
                                      if i not in chest_indexes]

                    full_jpn_lines = [temp_full_jpn_lines[i].group(0) for i in range(len(temp_full_jpn_lines))
                                      if i not in chest_indexes]

                    temp_scene_nums = []
                    for m_line in temp_full_jpn_lines:
                        temp_funcs = [m_func for m_func in funcs if m_func.start() < m_line.start()]
                        temp_scene_nums.append(len(temp_funcs))
                    scene_nums = [temp_scene_nums[i] for i in range(len(temp_scene_nums)) if i not in chest_indexes]

                    setChrNamesEng = [
                        m for m in re.finditer(rb'SetChrName\(((.|\n)+?)\)', all_bytes)
                    ]

                    # full_eng_lines = [temp_full_eng_lines[i] for i in range(len(temp_full_eng_lines)) if i in indexes]
                    # full_eng_lines = []
                    # last_index = -1
                    # for i in range(len(temp_full_eng_lines)):
                    #     if i in indexes:
                    #         full_eng_lines.append([temp_full_eng_lines[i]])
                    #         last_index += 1
                    #         print('new add; last index = ', last_index)
                    # elif 0 < len(full_eng_lines) < len(splitbodybytes):
                    #     full_eng_lines.append(None)

                print('%s!!!!!!!! USPC=%d; VitaJPN_msg=%d; len(indexes)=%d'
                      % (len(splitbodybytes) == len(full_eng_lines), len(full_eng_lines),
                         len(splitbodybytes), len(chest_indexes)))

                # for each jpn vita line
                # for i in range(len(splitbodybytes)):
                #     jpn_lines = get_jpn_lines(
                #         re.sub(rb'(\x1f)(..)', lambda match: b'item(0x%02x)' % struct.unpack('<H', (match.group(2)))[0],
                #                splitbodybytes[i]))

                    # jpn_html_text = '\n\n'.join(
                    #     [re.sub(rb'#\d+[A-QS-Z]|[\x00-\x09]', b'', line).decode(jpn_encode) for line in jpn_lines])

                    # print(i, jpn_html_text)
                #
                # print('lfel', len(full_eng_lines))
                # for i in range(len(temp_full_eng_lines)):
                #     print(i, i not in chest_indexes, temp_full_eng_lines[i].decode(jpn_encode))

                # for each jpn vita line

                scene_num = 1

                for i in range(len(splitbodybytes)):

                    try:
                        # new scene
                        if i > 0 and scene_nums[i-1] != scene_nums[i]:
                            scene_num += 1
                    except IndexError:
                        print('IndexError scene num skip')
                        continue

                    try:
                        op_name = full_eng_lines[i][:full_eng_lines[i].index(b'(')].decode(jpn_encode)
                    except IndexError:
                        print('IndexError op name')
                        continue

                    jpn_lines = get_jpn_lines(item_bytes_to_display(splitbodybytes[i]))

                    has_portrait = False

                    for m in [re.search(rb'#\d+F', jpnLine) for jpnLine in jpn_lines]:
                        if m:
                            has_portrait = True
                            break

                    # if i not in indexes:
                    if full_eng_lines[i] is None:
                        continue
                    else:
                        original_eng_lines = get_original_eng_lines(full_eng_lines[i])

                        # try:
                        #     print(i, [line.decode(jpn_encode) for line in jpn_lines], original_eng_lines)
                        # except:
                        #     print('BAD!!!!!!!!!', i, [line for line in jpn_lines], original_eng_lines)

                        good_line = True
                        line_lengths = [get_line_length(line, has_portrait) for line in original_eng_lines]
                        # print('line_lengths',line_lengths)
                        line_length = max(line_lengths)


                        # pgNum = 0
                        for row in original_eng_lines:
                            # lnNum = 0
                            for p in row.split(b'\x02\x03'):

                                # if not re.search(br'[a-gi-ln-zA-GI-LN-Z0-9]',p):
                                # 	print('NOWORDS!!!', fname, i, pgNum,lnNum,p,re.sub(rb'(?:#\d+[A-Z])|\x01|\x02|\x03',
                                # b'',jpn_lines[pgNum]).decode(jpn_encode))

                                for line in p.split(b'\x01'):
                                    line = line.replace(b'\x02', b'')
                                    # print('originalline',line)

                                    if len(line) > line_length:
                                        good_line = False  # line doesn't fit in text box; needs to be reformatted
                                        print("badline", line)
                                        break
                                        # lnNum += 1
                                        # pgNum += 1

                        # print("good_line=",good_line, i)

                        if good_line:
                            eng_lines = get_original_eng_lines(full_eng_lines[i])
                        else:
                            eng_lines = get_eng_lines(full_eng_lines[i], has_portrait)

                        # except IndexError:
                        #     pass

                        # test
                        jpn_npc_name = None
                        eng_npc_name = None

                        if op_name == 'NpcTalk':
                            npc_name = eng_lines[0].decode(jpn_encode)

                            if npc_name.encode(jpn_encode) in inverseNameDict or '#' not in npc_name:
                                print('HandleNpcTalk GOOD:', fname, npc_name)
                                if splitbodybytes[i].startswith(jpn_lines[0]):
                                    splitbodybytes[i] = splitbodybytes[i][len(jpn_lines[0]) + 1:]
                                    eng_npc_name = npc_name
                                    jpn_npc_name = jpn_lines[0].decode(jpn_encode)
                                    print("HandleNpcTalk YES", jpn_lines[0].decode(jpn_encode), eng_lines[0])
                                    del jpn_lines[0]
                                    del eng_lines[0]


                                else:
                                    raise RuntimeError("HandleNpcTalk NO!!!!!!!!!!")
                            else:
                                print('HandleNpcTalk BAD:', fname, npc_name, eng_lines)

                        ruby_jpn_lines = [line for line in jpn_lines]

                        for j in range(len(ruby_jpn_lines)):
                            rubyMatches = [m for m in re.finditer(br'#(\d+)R(.+?)(#)', ruby_jpn_lines[j])]
                            for m in reversed(rubyMatches):
                                end_index = m.start(1) - 1
                                start_index = end_index - int(m.group(1))
                                # ruby_jpn_lines[j][:start_index] + b'<ruby>' + ruby_jpn_lines[j][start_index:end_index] + b'</ruby>' + ruby_jpn_lines[j][end_index:]
                                main_text = ruby_jpn_lines[j][start_index:end_index]
                                extra_text = m.group(2)
                                print('attempt on ', ruby_jpn_lines[j].decode(jpn_encode))
                                print('index', start_index, end_index)
                                print('main', main_text.decode(jpn_encode), main_text)
                                print('extra', extra_text.decode(jpn_encode))
                                ruby_jpn_lines[j] = ruby_jpn_lines[j][:start_index] + b'<ruby>%s<rt>%s</rt></ruby>' % (
                                main_text, extra_text) + ruby_jpn_lines[j][(m.start(3) + 1):]
                                print('ruby result', ruby_jpn_lines[j].decode(jpn_encode))

                        jpn_html_text = '<br/><br/>'.join(
                            [re.sub(rb'#\d+[A-Z]|#N|[\x00-\x09]|\\x0[\dCD]', b'',
                                    item_bytes_to_display(line.replace(b'\x01', b'<br/>'))).decode(jpn_encode) for line
                             in ruby_jpn_lines])

                        jpn_search_text = ''.join([re.sub(rb'#\d*?R[^#]+?#|#\d+[A-Z]|#N|[\x00-\x09]|\\x0[\dCD]', b'',
                                    item_bytes_to_display(line.replace(b'\x01', b''))).decode(jpn_encode) for line
                             in jpn_lines])

                        # line counts don't match
                        if len(eng_lines) != len(jpn_lines) or not re.search(br'[^\x00-\x1f\xfe-\xff]', eng_lines[0]):

                            print(i, eng_lines, [line.decode(jpn_encode) for line in jpn_lines], len(eng_lines),
                                  len(jpn_lines))
                            raise RuntimeError("RuntimeError: could not match eng and jpn lines")
                            eng_lines, skip_line = fix_eng_lines(eng_lines, jpn_lines, full_eng_lines, has_portrait, i)
                            print('fixed', eng_lines)
                            # print(skip_line)
                            if skip_line:
                                # hax.append(b'[bad]')
                                print("skipline!!!!!", fname, eng_lines, jpn_html_text)
                                displaytbl2[fname].append(
                                    [str(i) + ' (skipped)', '', str(eng_lines), jpn_html_text, ''])
                                continue

                        # print(i,[line.decode(jpn_encode) for line in jpn_lines],eng_lines)

                        # copy # codes from jpn_lines to eng_lines
                        # print('before insert_codes',eng_lines)
                        eng_lines = insert_codes(eng_lines, jpn_lines, full_eng_lines[i])

                        if full_eng_lines[i].startswith(b'AnonymousTalk'):
                            for k in range(len(eng_lines)):
                                num_lines = eng_lines[k].count(b'\x01') + 1
                                if num_lines > 3:
                                    print("OVER3LINES!!!!", fname, i, k, eng_lines[k])

                        # print(i,[line.decode(jpn_encode) for line in jpn_lines],eng_lines)

                        # apply english lines to japanese script
                        for j in range(len(jpn_lines)):

                            # print(j,eng_lines[j])
                            # print(i,j,len(splitbodybytes),len(jpn_lines),len(eng_lines))
                            replaced = splitbodybytes[i].replace(jpn_lines[j], eng_lines[j], 1)
                            # print(i, j, jpn_lines[j].decode(jpn_encode), eng_lines[j])
                            # print('splitbodybytes',splitbodybytes[i].decode(jpn_encode))
                            # print(jpn_lines[j], jpn_lines[j] == eng_lines[j])
                            if splitbodybytes[i] == replaced and jpn_lines[j] != eng_lines[j]:
                                # print(i, j, jpn_lines[j].decode(jpn_encode), eng_lines[j])
                                print("FAILURE!!!")
                                print(splitbodybytes[i])
                                print(jpn_lines[j], jpn_lines[j] == eng_lines[j])
                            splitbodybytes[i] = replaced

                    # if len(occurrences) != len(splitbodybytes):
                    # displaytbl.append([str(i) + str(hax), splitbodybytes[i], jpn_lines])

                    # voice_links = b'\n'.join([b'http://platonicfuzz.com/evo/sc/talk/ch%s.ogg' % m.group(1) for m in
                    #                          re.finditer(rb'#(\d+)V', splitbodybytes[i])]).decode(jpn_encode)
                    # formatted_eng = re.sub(rb'#\d+[A-Z]|[\x00-\x09]', b'',
                    #                        b'\n\n'.join(original_eng_lines).replace(b'\x01', b'\n')).decode(jpn_encode)
                    # formatted_eng = b'\n'.join(original_eng_lines).replace(b'\x01', b'\n').decode(jpn_encode)

                    pages = splitbodybytes[i].split(b'\x02\x03')
                    icons = []
                    pc_icons = []

                    # print(i,full_eng_lines[i])
                    pc_icon = re.finditer(rb'#(\d+?)F', full_eng_lines[i])

                    if pc_icon:
                        for m in pc_icon:
                            icon_index = int(m.group(1).decode(jpn_encode))
                            if len(str(icon_index)) <= 3:
                                icon_index = f'{icon_index:03}'
                                icon_str = '<img class="itp" src="itp/2/pc/H_KAO%s.webp"/> ' \
                                               % icon_index
                            else:
                                icon_str = '<img class="itp" src="itp/2/pc/H_KA%s.webp"/> ' \
                                               % icon_index
                            pc_icons.append(icon_str)

                    eng_search_text = re.sub(rb'#\d+[A-Z]|[\x00-\x09\xfe-\xff]', b'',
                                                b'<br/><br/>'.join([item_bytes_to_display(line) for line in eng_lines]).replace(b'\x01', b' ')).decode(jpn_encode)

                    for j in range(len(pages)):
                        voice = re.search(rb'#(\d+?)V', pages[j])
                        icon = re.search(rb'#(\d+?)F', pages[j])

                        if voice:
                            pages[j] = b'<audio id="ch%s"><source src="talk/2/ch%s.ogg" ' \
                                       b'type="audio/ogg"></audio><a href="javascript:void(0)" ' \
                                       b'onclick="document.getElementById(\'ch%s\').play()">%s</a>' \
                                       % (voice.group(1), voice.group(1), voice.group(1), pages[j])
                        if icon:
                            icon_index = int(icon.group(1).decode(jpn_encode))
                            if len(str(icon_index)) <= 3:
                                icon_index = f'{icon_index:03}'
                                icon_str = '<img class="itp" src="itp/2/evo/c_kao%s.webp"/> ' \
                                           % icon_index
                            else:
                                icon_str = '<img class="itp" src="itp/2/evo/c_ka%s.webp"/> ' \
                                           % icon_index
                            icons.append(icon_str)

                    try:
                        display_text = re.sub(rb'#\d+[A-Z]|[\x00-\x09]', b'',
                                              b'<br/><br/>'.join(pages).replace(b'\x01', b'<br/>')).decode(jpn_encode)
                    except:
                        display_text = str(b''.join(pages))

                    # print(i, clean_display_text, jpn_html_text)

                    # jpn_html_text = b''

                    try:
                        eng_html_text = re.sub(rb'#\d+[A-Z]|[\x00-\x09\xfe-\xff]', b'',
                                              b'<br/><br/>'.join(pages).replace(b'\x01', b'<br/>')).decode(jpn_encode)
                    except:
                        print('except!!!', str(b''.join(pages)))
                        eng_html_text = str(b''.join(pages))
                    # print('eng_html', eng_html_text.encode(jpn_encode))
                    # displaytbl.append(
                    #     ['2', fname, str(i + 1), splitbodybytes[i], clean_display_text, jpn_html_text,
                    #                    full_eng_lines[i][:full_eng_lines[i].index(b'(')].decode(jpn_encode),
                    #                    'good_line=' + str(good_line)])

                    if eng_npc_name is not None:
                        eng_chr_name = eng_npc_name
                        jpn_chr_name = jpn_npc_name
                    else:
                        eng_chr_name = get_chr_name(op_name, full_eng_lines[i], original_eng_lines, eng_names,
                                                    eng_name_strings, name_start_index, fname, all_bytes, allbytes_main,
                                                    setChrNamesEng, setChrNamesEng)
                        jpn_chr_name = convertName(eng_chr_name)

                        if eng_chr_name != '' and jpn_chr_name == eng_chr_name and op_name == 'AnonymousTalk':
                            jpn_chr_name = get_chr_name(op_name, full_jpn_lines[i], None, None, None, None, fname,
                                                        alljpnbytes, alljpnbytes,
                                                        set_chr_names_jpn, set_chr_names_jpn)
                            print('jpn_chr_name RESULT', jpn_chr_name, jpn_search_text)

                    displaytbl.append(
                        ['2', fname, str(scene_num), str(i + 1), eng_chr_name, eng_search_text, eng_html_text,
                        jpn_chr_name, jpn_search_text, jpn_html_text, op_name, ''.join(pc_icons), ''.join(icons)]
                    )

                os.system("title " + fname)

        except FileNotFoundError as e:
            print('NOT FOUND', fname, traceback.format_exc())
            pass
        # except IndexError as e:
            # print('INDEX ERR', fname, err)
            # print(fname, 'Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)
            # pass
        # except RuntimeError as e:
        #     print(fname, e)
        #     break

    print(allcodes)
    if len(sys.argv) > 1:
        exit()

    with open(r'snkscevo.sql', 'w', encoding='utf-8') as sqlfile:
        sqlfile.write('delete from script where game_id = 2;\n')
        for row in displaytbl:
            newrow = []
            for cell in row:
                if type(cell) is list:
                    # print('cell=', cell)
                    cell = str([line.decode(jpn_encode) for line in cell])
                elif type(cell) is bytes:
                    cell = str(cell)
                newrow.append(cell)
            # csvwriter.writerow(newrow)
            sqlfile.write('insert into script (game_id, fname, scene, row, eng_chr_name, eng_search_text, eng_html_text, jpn_chr_name, jpn_search_text, jpn_html_text, op_name, pc_icon_html, evo_icon_html) values\n')
            sqlfile.write("('%s');\n" % ("','".join([c.replace("'", "''").replace('\x1a', '\\Z') for c in newrow])))


if __name__ == "__main__":
    main()
