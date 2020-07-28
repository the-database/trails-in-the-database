import re, os, struct, csv, json, textwrap, html, csv, math, traceback, sys

# psp_eng_path = "D:/file/kiseki-evo/FC-PC-USA/ED6_DT01/"
psp_eng_path = "./FC-PC-USA-patched/"
vita_jpn_path = "./FC-VITA-JPN-SOURCE/PCSG00488.VPK/gamedata/data/msg/"

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
    <div class="container">
        <h1>%s</h1>
        <table class="table table-condensed">'''

template_mid = '''</table><footer><table class="table table-condensed">'''

template_end = '''</table></footer></div>
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
        # size = struct.unpack('<H', f.read(2))[0]
        # for i in range(size):
        while True:
            p = struct.unpack('<H', f.read(2))
            pointers.append(p[0])
            if f.tell() >= pointers[0]:
                break

    return pointers


def getnames(path, fname, pointers, offset):
    lines = []
    with open(path + fname, 'rb') as f:
        allbytes = f.read()
        for i in range(len(pointers)):
            part = allbytes[pointers[i]:pointers[i] + offset]
            # part = part[:part.index(b'\x00') + 2]
            part2 = allbytes[pointers[i] + offset:]
            part2 = part2[:part2.index(b'\x00')]
            lines.append(part2)
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


def getLineLength(line, hasPortrait):
    lineLength = 48
    if not hasPortrait and b'#1S' not in line:
        lineLength += 11

    if b'#3S' in line:
        lineLength = int(lineLength * (2 / 3))
    elif b'#4S' in line:
        lineLength = int(lineLength * (2 / 4))
    elif b'#5S' in line:
        lineLength = int(lineLength * (2 / 5))

    return lineLength


# LINE_LENGTH = 50
def word_len(text):
    numCodes = len([m for m in re.finditer(r'\\x(?:.{2})', text)])
    numIcons = len([m for m in re.finditer(r'\\x07\\x02', text)])
    # print(text,numCodes,numIcons,len(text),len(text) - numCodes * 4 + numIcons * 3)
    # print('word_len',text,len(text.replace('\\x02\\x03','')), numCodes*4, numIcons*3)
    # print('word_lens',text,len(text) - numCodes * 4 + numIcons * 3)
    return len(text) - numCodes * 4 + numIcons * 3


def get_num_lines(text, maxLength):
    lines = []
    remainingText = text

    chunks = re.split(r'(\s+)', text)
    # print('chunks',chunks)
    for chunk in chunks:
        # print('chunk: [%s] [%s]' % (chunk,chunk.lstrip()))
        if len(lines) == 0 or word_len(lines[-1]) + word_len(chunk) > maxLength:
            lines.append(chunk.lstrip())
        else:
            lines[-1] += chunk
    # print("stuf!!!", lines)
    return len(lines)


def wrap_text(text, maxLength):
    # numLines = math.ceil(word_len(text) / maxLength)
    numLines = get_num_lines(text, maxLength)
    lineLength = math.ceil(word_len(text) / numLines)

    # print('numLines', numLines, text)

    while True:
        # print('lineLength', lineLength)
        lines = []
        chunks = re.split(r'(\s+)', text)
        # print('chunks', chunks)
        for chunk in chunks:
            # print('chunk: [%s] [%s]' % (chunk, chunk.lstrip()))
            # print('asd',word_len(lines[-1]) + word_len(chunk) , lineLength)
            # if len(lines) > 0:
            # print('hello?', word_len(lines[-1]), word_len(chunk), (word_len(lines[-1]) + word_len(chunk)),
            #       lineLength, lines)
            # print('maxlen', maxLength)
            # add new line with first chunk
            if len(lines) == 0 or word_len(lines[-1]) + word_len(chunk) > lineLength:
                lines.append(chunk.lstrip())
            # append chunk to end of last line
            else:
                lines[-1] += chunk

        # print('lenlines', len(lines), lines)

        if len(lines) <= numLines or lineLength == maxLength:
            return lines

        lineLength += 1


def rebalance_linebreaks(oldMessageGroup, hasPortrait, threeLinesMax=False):
    newMessageGroup = []

    oldMessages = re.split(br'\\x02\\x03', b''.join(oldMessageGroup))

    for k in range(len(oldMessages)):
        if k < len(oldMessages) - 1:
            oldMessages[k] = oldMessages[k].strip() + b'\\x02\\x03'

        oldLines = b''
        oldLineList = [s.strip() for s in oldMessages[k].split(b'\\x01')]

        for i in range(len(oldLineList)):
            if i < len(oldLineList) - 1:
                if oldLineList[i].endswith(b'-'):
                    currentchunks = re.split(rb'(\s+)', oldLineList[i])
                    nextchunks = re.split(rb'(\s+)', oldLineList[i + 1])

                    combinedword = currentchunks[-1][:-1] + nextchunks[0]
                    combinedword = re.sub(rb'[.,!?"\']', b'', combinedword)  # strip punctuation

                    if combinedword.decode(jpn_encode) in worddict:
                        print("OLD!!!!isword", combinedword, oldLines)
                        oldLines += oldLineList[i][:-1]
                    else:
                        print("OLD!!!!notword", currentchunks[-1] + nextchunks[0])
                        oldLines += oldLineList[i]
                else:
                    oldLines += oldLineList[i] + b' '
            else:
                oldLines += oldLineList[i]

        skipRebalanceLineBreaks = True
        lineLength = getLineLength(oldLines, hasPortrait)
        # print('oldll', oldLineList)
        for line in oldLineList:
            # print((re.sub(rb'(?:#\d+[A-Z])|\\x02\\x03', b'', line)), lineLength)
            if len(re.sub(rb'(?:#\d+[A-Z])|\\x02\\x03', b'', line)) > lineLength:
                skipRebalanceLineBreaks = False
                break

        if skipRebalanceLineBreaks:
            # continue
            # print('skiprebalance', oldLineList)
            tmpGroup = oldLineList
        else:
            # print('dontskip',oldLineList)
            tmpGroup = rebalance_linebreaks_width(oldLines, hasPortrait)

        tmpJoined = b'\x01'.join(tmpGroup)

        if len(tmpGroup) > 1:
            for i in range(len(tmpGroup) - 1):
                tmpGroup[i] = tmpGroup[i].strip() + b'\\x01'
        newMessageGroup += tmpGroup

    return newMessageGroup


def rebalance_linebreaks_width(oldLines, hasPortrait):
    lineLength = getLineLength(oldLines, hasPortrait)

    oldLines = re.sub(rb'(?:#\d+[A-Z])', b'', oldLines)  # remove number codes

    return [wrapped.encode(jpn_encode) for wrapped in wrap_text(oldLines.decode(jpn_encode), lineLength)]


def escape(s, quote=True):
    """
	Replace special characters "&", "<" and ">" to HTML-safe sequences.
	If the optional flag quote is true (the default), the quotation mark
	characters, both double quote (") and single quote (') characters are also
	translated.
	"""
    s = s.replace(b"&", b"&amp;")  # Must be done first!
    s = s.replace(b"<", b"&lt;")
    s = s.replace(b">", b"&gt;")
    if quote:
        s = s.replace(b'"', b"&quot;")
        s = s.replace(b'\'', b"&#x27;")
    return s


def html_table(lol):
    displayReg = rb'((?:#\d+[A-QS-Z])+?|[\x00-\x1f\xff]+?)'
    displayRegReplace = rb'<small style="font-family:monospace;color:gray">\1</small>'

    tbl = '<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css" integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u" crossorigin="anonymous"><table class="table table-hover"style="width:auto">'
    for sublist in lol:
        tbl += '  <tr>'
        for cell in sublist:
            if type(cell) is list:
                cell = str([re.sub(displayReg, displayRegReplace, line).decode(jpn_encode) for line in cell])
            elif type(cell) is bytes:
                cell = str(re.sub(displayReg, displayRegReplace, escape(cell)))
            tbl += '<td>%s</td>' % cell
        tbl += '  </tr>'
    tbl += '</table>'
    return tbl


def rpl(m):
    return chr(int(m.group(1), 16)).encode(jpn_encode)


def getsplitbodybytes(pointers, bodybytes):
    splitbodybytes = []
    # perform jpn -> eng replacements in bodybytes
    # store offsets for eng dialogue lines
    for index in range(1, len(pointers)):
        sliced = bodybytes[pointers[index][0]:]
        # sliced = sliced[:sliced.find(b'\x02\x00')].decode(jpn_encode)

        if index < len(pointers) - 1:
            endIndex = pointers[index + 1][0] - pointers[index][0]
            # endIndex = sliced.find(b'\x02\x00')
            sliced = sliced[:endIndex]

        splitbodybytes.append(sliced)
    return splitbodybytes


def exportPatchedMbin(splitbodybytes, headerbytes, fname):
    newOffsets = [0]
    for index in range(len(splitbodybytes) - 1):
        newOffsets.append(len(splitbodybytes[index]) + newOffsets[-1])

    newheaderbytes = headerbytes[:4]
    for index in range(len(newOffsets)):
        # get 4 leading bytes from original header
        newheaderbytes += headerbytes[(index) * 8 + 4: (index) * 8 + 8]
        newheaderbytes += struct.pack('<i', newOffsets[index])

    # copy last 3 bytes from original header
    newheaderbytes += headerbytes[((len(newOffsets)) * 8 + 4):]

    with open('out/' + fname + '.mbin', 'wb') as wf:
        wf.write(newheaderbytes)
        wf.write(b''.join(splitbodybytes))


def getOriginalEngLines(fullEngLine, hasPortrait):
    engLine = b''

    m = re.search(rb'scpstr\(SCPSTR_CODE_COLOR,\s+0x([^)]+)\)', fullEngLine)
    colorStr = b''

    engParts = [m.group(1) for m in re.finditer(rb'"([^"]+?)"', fullEngLine)]

    if fullEngLine.startswith(b'NpcTalk'):
        engJoined = engParts[0] + b'\x00' + colorStr + b''.join(engParts[1:])
    else:
        engJoined = colorStr + b''.join(engParts)

    engLine = re.sub(rb'(?:#\d+[A-Z])', b'', engJoined)  # remove number codes
    engLine = re.sub(rb'\\x(.{2})', rpl, engLine)  # apply control codes (\\x01 -> \x01)

    eng_lines = engLine.split(b'\x02\x03')
    eng_lines = [item for sublist in [re.split(br'(?<![\x00-\x1f])\x00', line) for line in eng_lines] for item in
                 sublist]

    return eng_lines


def getEngLines(fullEngLine, hasPortrait):
    engLine = b''

    m = re.search(rb'scpstr\(SCPSTR_CODE_COLOR,\s+0x([^)]+)\)', fullEngLine)
    colorStr = b''
    if m:
        colorStr = b'\x07' + chr(int(m.group(1), 16)).encode(jpn_encode)

    engParts = [m.group(1) for m in re.finditer(rb'"([^"]+?)"', fullEngLine)]

    if fullEngLine.startswith(b'NpcTalk'):
        engJoined = engParts[0] + b'\x00' + colorStr + b''.join(rebalance_linebreaks(engParts[1:], hasPortrait))
    elif fullEngLine.startswith(b'AnonymousTalk'):
        tmpJoined = b''.join(engParts)
        if b'   ' in tmpJoined or b'\x81@' * 3 in tmpJoined:  # don't rebalance lines
            tmpList = engParts
            print("norebalance!!!", engParts)
            for part in engParts:
                if len(part) > 59:
                    print("TOOLONG!!!", len(part), part)
                    # lengths = [len(part) > 48 for part in engParts]
                    # if True in lengths:
                    # print("TOOLONG!!!!",engParts)
        else:
            tmpList = rebalance_linebreaks(engParts, hasPortrait, True)
        # if len(tmpList) > 3:
        # 	tmpList[2] += tmpList[2].replace(b'\\x01', b'\\x02\\x03')
        # 	print('tmpList',tmpList)
        engJoined = colorStr + b''.join(tmpList)
    else:
        engJoined = colorStr + b''.join(rebalance_linebreaks(engParts, hasPortrait))

    # apply control codes

    # engLine = engJoined
    # print('engLine',engLine)
    engLine = re.sub(rb'\\x(.{2})', rpl, engJoined)
    engLine = engLine.replace(b'Zane', b'Zin')
    # print('bfeore',engLine)
    # print('after',engLine)

    eng_lines = engLine.split(b'\x02\x03')
    eng_lines = [item for sublist in [re.split(br'(?<![\x00-\x1f])\x00', line) for line in eng_lines] for item in
                 sublist]

    return eng_lines


def getJpnLines(fullJpnLine):
    trimmedJpnLine = fullJpnLine[:fullJpnLine.find(b'\x02\x00') + 1]

    jpnLines = trimmedJpnLine.split(b'\x02\x03')

    # print('trimmedJpn',trimmedJpnLine.decode(jpn_encode))

    jpnLines = [item for sublist in [re.split(br'(?<![\x00-\x1f])\x00', line) for line in jpnLines] for item in sublist]

    return jpnLines


def fixEngLines(eng_lines, jpnLines, fullEngLines, hasPortrait, i, hax):
    skipLine = False

    # engLine is empty
    if len(eng_lines) > 0 and re.search(br'[A-Za-z0-9.,!?\x81-\x9f\']', eng_lines[0]):
        # engLine has an extra leading character name; remove it
        print('fixEngLines', i, len(eng_lines), len(jpnLines), eng_lines)
        if fullEngLines[i].startswith(b'NpcTalk') and len(eng_lines) - 1 == len(jpnLines):
            print('charnamehax', eng_lines, [line.decode(jpn_encode) for line in jpnLines])
            eng_lines = eng_lines[1:]
            hax.append(b'charnamehax')

        # jpnLine is engLine + next engLine(s)
        # elif i < len(fullEngLines) - 1 and len(eng_lines) + len(getEngLines(fullEngLines[i+1])) == len(jpnLines):
        k = 1
        while i + k < len(fullEngLines) and len(eng_lines) < len(jpnLines):
            # print('nextlinehax',eng_lines,eng_lines[-1])
            eng_lines[-1] = eng_lines[-1][:-1]  # remove last char (\x02) from last line
            nextLines = getEngLines(fullEngLines[i + k], hasPortrait)
            # print("NEXTLIENS!@@!@!")
            # print(nextLines, nextLines[1:])
            if fullEngLines[i + k].startswith(b'NpcTalk'):
                eng_lines += nextLines[1:]
            # pass
            else:
                eng_lines += nextLines
            k += 1
            hax.append(b'nextlinehax')
            print('nextlinehax', eng_lines, [line.decode(jpn_encode) for line in jpnLines])
    else:
        # print('skipline!!!!!!!!!')
        skipLine = True

    # can't reconcile differences; log and skip this line
    # print('lens',len(eng_lines),len(jpnLines))
    if len(eng_lines) != len(jpnLines):
        skipLine = True

    return (eng_lines, skipLine)


allcodes = set()


def get_npc_index(allbytes_main, scena_num, func_num):
    npcs = [m for m in re.finditer(rb'DeclNpc', allbytes_main)]
    # print('npcs', npcs)
    # print('search',rb'TalkFunctionIndex\s+= %d,[\r\n]+\s+TalkScenaIndex\s+= %d' % (scena_num, func_num))
    npc = [m for m in re.finditer(rb'TalkFunctionIndex\s+= %d,[\r\n]+\s+TalkScenaIndex\s+= %d' % (scena_num, func_num),
                                  allbytes_main)][0]
    return [i for i in range(len(npcs)) if
            (npc.start() > npcs[i].start() and (i + 1 == len(npcs) or npc.start() < npcs[i + 1].start()))][0]


# if allbytes is all bytes from an included scenario, then allbytes_main
# is allbytes from the scenario that included it
def get_chr_name(op_name, full_lines, lines, names, name_strings, name_start_index,
                 fname, allbytes, allbytes_main, set_chr_names, set_chr_names2):
    eng_chr_name = ''
    # print('get_npc_index', op_name, lines)
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
                        print('InitialNpcIndexError', traceback.format_exc())

                        calls = [m for m in re.finditer(rb'Call\(%d, %d\)' % (scena_num, func_num), allbytes_main)]
                        # print('notalkbegins!!!', fname, lines, calls)
                        if len(calls) == 0:
                            print('nocalls!!!', fname, lines, rb'Call\(%d, %d\)' % (scena_num, func_num))
                        else:
                            call = calls[0]
                            main_funcs = [m for m in re.finditer(rb'def Function_(\d+)_', allbytes_main) if
                                          m.start() < call.start()]
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
            print('BadNpcIndexError', traceback.format_exc())
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


def insertCodes(eng_lines, jpnLines, fullEngLines):
    # print('insertCodes')
    for j in range(len(eng_lines)):
        # print(j,eng_lines[j])
        # print('before ...',eng_lines[j])

        # if not re.search (rb'((^|\s+)[\x00-\x1fa-zA-Z0-9]+\.\.\.)(?=[a-zA-Z0-9]+)', eng_lines[j]) and re.search(rb'([a-zA-Z0-9]+\.\.\.)(?=[a-zA-Z0-9]+)', eng_lines[j]):
        # 	print("REGEX!!",eng_lines[j])

        # fix "word...word" -> "word... word"
        engCodes = [m for m in re.finditer(rb'#\d+[A-Z]', eng_lines[j])]
        ellipses = [m for m in re.finditer(rb'([a-zA-Z0-9]+\.\.\.)(?=[a-zA-Z0-9]+)', eng_lines[j])]

        for m in ellipses:
            doReplace = True
            for code in engCodes:
                if m.start() >= code.start() and m.start() < code.end():  # ellipsis match is part of a code
                    print("dontreplace!", eng_lines[j])
                    doReplace = False
                    break

            if doReplace:
                eng_lines[j] = eng_lines[j].replace(m.group(0), m.group(0) + b' ', 1)

        # eng_lines[j] = re.sub(rb'((^|\s+)[\x00-\x1fa-zA-Z0-9]+\.\.\.)(?=[a-zA-Z0-9]+)', b'\\1 ', eng_lines[j]) # fix "word...word" -> "word... word"
        eng_lines[j] = re.sub(rb'([^. \]\x00-\x1f]+--)\s+([^. \]\x00-\x1f]+)', b'\\1\\2',
                              eng_lines[j])  # fix 'word-- word' -> 'word--word'

        # don't care about preserving #R codes used for furigana
        codes = [m for m in re.finditer(br'((?:#\d+[A-QS-Z])+?)', jpnLines[j])]
        scodes = 0

        iCodeIndex = 0
        sCodeIndex = 0

        # print('str',[code.group(1) for code in codes])

        lens = []

        if len(codes) > 0:
            lens = [0]

        for code in codes[:-1]:
            lens.append(lens[-1] + len(code.group(1)))

        jpnControlCodes = [m.start() for m in re.finditer(rb'\x01', jpnLines[j])]
        engControlCodes = [m.start() for m in re.finditer(rb'\x01', eng_lines[j])]

        for code in codes:

            insertIndex = code.start(1) - (
                    re.search(rb'[^\x00-\x1f\xfe-\xff]', jpnLines[j]).start() - re.search(rb'[^\x00-\x1f\xfe-\xff]',
                                                                                          eng_lines[j]).start())

            stuff = [code.start(1) < m for m in jpnControlCodes]

            # print('stuff',stuff, jpnControlCodes)

            # size code
            if b'S' in code.group(1):
                scodes += 1

                if scodes > 1:
                    print('continue...', eng_lines[j])
                    continue

            # icon code
            if b'I' in code.group(1):
                # print('icode=', code.group(1))
                try:
                    insertIndex = [m.start() + 2 for m in re.finditer(br'\x07\x02', eng_lines[j])][iCodeIndex]
                    iCodeIndex += 1
                except IndexError:
                    print('IndexErrorI:', code.group(1))
                    print(eng_lines, [line.decode(jpn_encode) for line in jpnLines], len(eng_lines), len(jpnLines))
                    insertIndex = -1
            elif False in stuff:
                if len(jpnControlCodes) != len(engControlCodes):
                    insertIndex = -1
                    print('nolencode!!!', code.group(1), jpnLines[j].decode(jpn_encode),
                          eng_lines[j].decode(jpn_encode))
                    pass
                else:
                    engControlCodes = [m for m in re.finditer(rb'\x01', eng_lines[j])]
                    insertIndex = engControlCodes[stuff.index(False)].start() + 1
                    # print(engControlCodes, insertIndex, eng_lines[j])

            if insertIndex != -1:
                eng_lines[j] = eng_lines[j][:insertIndex] + code.group(1) + eng_lines[j][insertIndex:]
                # scount = [x.group(1) for x in codes if b'S' in x.group(1)]
                # if len(scount) > 1:
                # print('SCOUNT!!!',len(scount),scount,eng_lines,[line.decode(jpn_encode) for line in jpnLines])

        # also copy color code: \x07\x##
        jpnColorMatches = [m for m in re.finditer(rb'\x07[\x00-\x1f]', jpnLines[j])]
        engColorMatches = [m for m in re.finditer(rb'\x07[\x00-\x1f]', eng_lines[j])]
        # print('colorMatch',colorMatch)
        # only get color from JPN line if Eng line has no colors already
        if len(jpnColorMatches) > 0 and len(engColorMatches) == 0:
            # print('colormatches!', len(jpnColorMatches), eng_lines[j], jpnLines[j].decode(jpn_encode))
            if fullEngLines.startswith(b'NpcTalk'):
                parts = eng_lines[j].split(b'\x01')
                eng_lines[j] = parts[0] + b'\x01' + jpnColorMatches[0].group(0) + b'\x01'.join(parts[1:])
            else:
                eng_lines[j] = jpnColorMatches[0].group(0) + eng_lines[j]

    return eng_lines


def replacenth(string, sub, wanted, n):
    # print('replacenth', string, sub, wanted, n)
    where = [m.start() for m in re.finditer(sub, string)][n - 1]
    before = string[:where]
    after = string[where:]
    after = after.replace(sub, wanted, 1)
    newString = before + after
    return newString


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
    '司会の声'.encode(jpn_encode): b'Chairman\'s voice',
    '占いマシーン'.encode(jpn_encode): b'Tester',
    '黒服の老人'.encode(jpn_encode): b'Old Man In Black',
    '乗組員の声'.encode(jpn_encode): b'Crew Member\'s Voice',
    '特務兵たち'.encode(jpn_encode): b'Special Ops Soldiers',
    '一同'.encode(jpn_encode): b'Royal Guardsmen',
    # 'ジン'.encode(jpn_encode): b'Zin',
    # 'タロット'.encode(jpn_encode): b'Tarot'
}

nameDict = {}
inverseNameDict = {}


def convertName(oldName):
    if oldName.encode(jpn_encode) in inverseNameDict:
        return inverseNameDict[oldName.encode(jpn_encode)].decode(jpn_encode)
    else:
        print('convert warning!!!!', oldName)

    return oldName


def getNames(path, fname):
    regex = r'(#\d+?F(#\d[A-Z])*)(.+?)\x02\x00'

    names = []

    with open(path + fname, 'rb') as f:
        allbytes = f.read()
        startIndex = allbytes.rindex(b'@FileName')
        nameStr = allbytes[startIndex:]
        names = nameStr.split(b'\x00')

    return names


def setupNameDict():
    # first pass: build name dict
    for fname in os.listdir(vita_jpn_path):
        # for fname in ['t0311.mbin']:

        try:
            fname = os.path.splitext(fname)[0]

            engNames = getNames(psp_eng_path, fname + '._SN')
            jpnNames = getNames("./FC-PC-JPN/ED6_DT01/", fname + '   ._SN')
            # jpnNames = getNames(vita_jpn_path, fname + '.bin')

            print(fname, len(engNames), len(jpnNames), str(len(engNames) == len(jpnNames)) + '!!!!!!')

            print([x.decode(jpn_encode) for x in jpnNames])

            for i in range(len(jpnNames)):
                if jpnNames[i] in nameDict and nameDict[jpnNames[i]] != engNames[i]:
                    print('dictfail! currJpn=%s; dictEng=%s; currEng=%s ' % (
                    jpnNames[i].decode(jpn_encode), nameDict[jpnNames[i]].decode(jpn_encode),
                    engNames[i].decode(jpn_encode)))
                    # dictFail[jpnNames[i]] = 1
                nameDict[jpnNames[i]] = engNames[i]

                # if '市長邸' in jpnNames[i].decode(jpn_encode):
                # 	print('yes!!!!!!',jpnNames[i].decode(jpn_encode), engNames[i])
                # print(i, jpnNames[i].decode(jpn_encode))
        except FileNotFoundError:
            print("NO!!!!", fname)
            pass

    for key in nameDictBase:
        nameDict[key] = nameDictBase[key]

    # return {v: k for k, v in nameDict.items()}
    for k, v in nameDict.items():
        if v in inverseNameDict and inverseNameDict[v] != k:
            print("inversedictfail!", [x.decode(jpn_encode) for x in [v, inverseNameDict[v], k]])
        else:
            inverseNameDict[v] = k


def OP_E5(one, two):
    return two * 0x100 + one


def get_jpn_op_names(all_jpn_bytes, splitbodybytes):
    lines = [
        m.group(0) for m in re.finditer(rb'[a-zA-Z]+Talk\(((.|\n)+?)    \)|OP_E5\(.+?\)', all_jpn_bytes)
    ]

    op_names = [None] * len(splitbodybytes)

    for i in range(len(lines)):

        if lines[i].startswith(b'OP_E5'):
            index = eval(lines[i])

            op_name = lines[i + 1][:lines[i + 1].index(b'(')].decode(jpn_encode)

            op_names[index] = op_name

    return op_names


def main():
    displaytbl = []
    displaytbl2 = {}
    footer = {}

    setupNameDict()

    # print(inverseNameDict)
    # print('begin inverseNameDict')
    # for k,v in inverseNameDict.items():
    #     print(k.decode(jpn_encode), v.decode(jpn_encode))
    # print('end inverseNameDict')

    eng_name_pointers = getnamepointers("./ED6_DT02/", "t_name._dt")
    eng_names = getnames("./ED6_DT02/", "t_name._dt", eng_name_pointers, 30)

    jpn_name_pointers = getnamepointers("./FC-VITA-JPN-SOURCE/PCSG00488.VPK/gamedata/data/text/", "t_name._dt")
    jpn_names = getnames("./FC-VITA-JPN-SOURCE/PCSG00488.VPK/gamedata/data/text/", "t_name._dt", jpn_name_pointers, 38)

    print('len names', len(eng_names))

    if len(sys.argv) > 1:
        fnames = sys.argv[1:]
    else:
        fnames = os.listdir(vita_jpn_path)

    for fname in fnames:
        # for fname in ['t1210','t1210_1']:
        # for fname in ['t0120']:

        fname = os.path.splitext(fname)[0]

        print('=' * len(fname))
        print(fname)
        print('=' * len(fname))

        pointers = getpointers(fname + '.mbin')
        splitbodybytes = []

        # if len(pointers) == 0:
        # continue

        displaytbl2[fname] = []
        footer[fname] = []

        try:
            if '_' not in fname:
                eng_name_strings, name_start_index = get_string_names(psp_eng_path, fname + ".py")
                jpn_name_strings, jpn_start_index = get_string_names(
                    "./FC-VITA-JPN-SOURCE/PCSG00488.VPK/gamedata/data/scenario/0/", fname + ".py")

            print('engnames', eng_name_strings)

            print('lesn!!!', len(eng_name_strings), len(jpn_name_strings))
            # get split body bytes from japanese vita script
            print('try open', vita_jpn_path + fname + '.mbin')
            with open(vita_jpn_path + fname + '.mbin', 'rb') as f:

                allbytes = f.read()

                if len(pointers) > 0:
                    body_offset = pointers[0][0] * 8 + 7

                    headerbytes = allbytes[:body_offset]
                    bodybytes = allbytes[body_offset:]

                    splitbodybytes = getsplitbodybytes(pointers, bodybytes)

                print('yes?')

            files = [i for i in os.listdir(psp_eng_path) if
                     os.path.isfile(os.path.join(psp_eng_path, i)) and i.startswith(fname.upper() + '.') and i.endswith(
                         '.py')]

            if len(files) != 1:
                print('no!!!!', len(files))
                if len(files) == 0:
                    continue

            print('try open', psp_eng_path + files[0])
            with open(psp_eng_path + files[0], 'rb') as f, open(
                    "./FC-VITA-JPN-SOURCE/PCSG00488.VPK/gamedata/data/scenario/0/" + fname + ".py",
                    'rb') as f_jpn:

                all_jpn_bytes = f_jpn.read()

                temp_full_jpn_lines = [
                    m for m in re.finditer(rb'[a-zA-Z]+Talk\(((.|\n)+?)    \)', all_jpn_bytes)
                ]

                full_jpn_lines = [
                    m.group(0) for m in re.finditer(rb'[a-zA-Z]+Talk\(((.|\n)+?)    \)', all_jpn_bytes)
                ]

                set_chr_names_jpn = [
                    m for m in re.finditer(rb'SetChrName\(((.|\n)+?)\)', all_jpn_bytes)
                ]

                funcs = [
                    m for m in re.finditer(rb'def Function_(\d+)_', all_jpn_bytes)
                ]

                print(set_chr_names_jpn)

                allbytes = f.read()

                if '_' not in fname:
                    allbytes_main = allbytes
                    all_jpn_bytes_main = all_jpn_bytes

                fullEngLines = [
                    m.group(0) for m in re.finditer(rb'[a-zA-Z]+Talk\(((.|\n)+?)    \)', allbytes)
                ]

                setChrNamesEng = [
                    m for m in re.finditer(rb'SetChrName\(((.|\n)+?)\)', allbytes)
                ]

                scene_nums = []
                for m_line in temp_full_jpn_lines:
                    temp_funcs = [m_func for m_func in funcs if m_func.start() < m_line.start()]
                    scene_nums.append(len(temp_funcs))

                print(setChrNamesEng)

                # displaytbl.append([str(len(fullEngLines) == len(splitbodybytes))+'!!!!!!!!', str(len(fullEngLines)), str(len(splitbodybytes)),''])
                print([str(len(fullEngLines) == len(splitbodybytes)) + '!!!!!!!!', str(len(fullEngLines)),
                       str(len(splitbodybytes)), ''])

                # for each jpn vita line
                jpn_op_names = get_jpn_op_names(all_jpn_bytes, splitbodybytes)
                scene_num = 1

                for i in range(len(splitbodybytes)):

                    # new scene
                    try:
                        if i > 0 and scene_nums[i - 1] != scene_nums[i]:
                            scene_num += 1
                    except IndexError:
                        print('INDEX ERROR scene')
                        continue

                    try:
                        op_name = fullEngLines[i][:fullEngLines[i].index(b'(')].decode(jpn_encode)
                        # op_name_jpn = full_jpn_lines[i][:full_jpn_lines[i].index(b'(')].decode(jpn_encode)
                        op_name_jpn = jpn_op_names[i]
                    except IndexError:
                        print("INDEX ERROR op name")
                        continue

                    eng_lines = []
                    jpnLines = getJpnLines(splitbodybytes[i])

                    hasPortrait = False

                    for m in [re.search(rb'#\d+F', jpnLine) for jpnLine in jpnLines]:
                        if m:
                            hasPortrait = True
                            break

                    try:
                        originalEngLines = getOriginalEngLines(fullEngLines[i], hasPortrait)

                        goodLine = True
                        lineLength = getLineLength(originalEngLines, hasPortrait)

                        # pgNum = 0
                        for row in originalEngLines:
                            # lnNum = 0
                            for p in row.split(b'\x02\x03'):

                                # if not re.search(br'[a-gi-ln-zA-GI-LN-Z0-9]',p):
                                # 	print('NOWORDS!!!', fname, i, pgNum,lnNum,p,re.sub(rb'(?:#\d+[A-Z])|\x01|\x02|\x03',b'',jpnLines[pgNum]).decode(jpn_encode))

                                for line in p.split(b'\x01'):
                                    line = line.replace(b'\x02', b'')
                                    # print('originalline',line)

                                    if len(line) > lineLength:
                                        goodLine = False  # line doesn't fit in text box; needs to be reformatted
                                        # print("badline", line)
                                        break
                                        # lnNum += 1
                                        # pgNum += 1

                        # print("goodLine=",goodLine, i)

                        if goodLine:
                            eng_lines = getOriginalEngLines(fullEngLines[i], hasPortrait)
                        else:
                            eng_lines = getEngLines(fullEngLines[i], hasPortrait)

                    except IndexError:
                        pass

                    hax = []

                    # test
                    # jpn_npc_name = None # test
                    eng_npc_name = None

                    if op_name == 'NpcTalk':
                        temp_eng_npc_name = eng_lines[0].decode(jpn_encode)
                        temp_jpn_npc_name = jpnLines[0].decode(jpn_encode)

                        if temp_eng_npc_name.encode(jpn_encode) in inverseNameDict or '#' not in temp_jpn_npc_name:
                            print('eng HandleNpcTalk GOOD:', fname, temp_eng_npc_name, temp_jpn_npc_name)

                            if splitbodybytes[i].startswith(jpnLines[0]):
                                splitbodybytes[i] = splitbodybytes[i][len(jpnLines[0]) + 1:]
                                print("eng HandleNpcTalk YES", jpnLines[0].decode(jpn_encode), eng_lines[0])
                                eng_npc_name = temp_eng_npc_name

                                del eng_lines[0]

                                if len(eng_lines) < len(jpnLines):
                                    jpn_npc_name = temp_jpn_npc_name
                                    del jpnLines[0]

                                # if len(jpnLines) != len(eng_lines):
                                #     print(fname, eng_lines, [ln.decode(jpn_encode) for ln in jpnLines])
                                #     raise RuntimeError('wtf')

                            else:
                                print(jpnLines[0].decode(jpn_encode), splitbodybytes[i].decode(jpn_encode))
                                raise RuntimeError("eng HandleNpcTalk NO!!!!!!!!!!")
                            eng_npc_name = temp_eng_npc_name
                        else:
                            print('eng HandleNpcTalk BAD:', fname, temp_eng_npc_name, eng_lines)
                    else:
                        jpn_npc_name = None
                        eng_npc_name = None

                    # if op_name_jpn == 'NpcTalk':
                    #     temp_jpn_npc_name = jpnLines[0].decode(jpn_encode)
                    #
                    #     if '#' not in temp_jpn_npc_name:
                    #         if splitbodybytes[i].startswith(jpnLines[0]):
                    #             splitbodybytes[i] = splitbodybytes[i][len(jpnLines[0]) + 1:]
                    #             print("jpn HandleNpcTalk YES", jpnLines[0].decode(jpn_encode), eng_lines[0])
                    #
                    #             jpn_npc_name = temp_jpn_npc_name
                    #             del jpnLines[0]
                    #
                    #         else:
                    #             print(jpnLines[0].decode(jpn_encode), splitbodybytes[i].decode(jpn_encode))
                    #             raise RuntimeError("jpn HandleNpcTalk NO!!!!!!!!!!")
                    #     else:
                    #         print('jpn HandleNpcTalk BAD:', fname, temp_eng_npc_name, eng_lines)

                    rubyJpnLines = [line for line in jpnLines]

                    for j in range(len(rubyJpnLines)):
                        rubyMatches = [m for m in re.finditer(br'#(\d+)R(.+?)(#)', rubyJpnLines[j])]
                        for m in reversed(rubyMatches):
                            end_index = m.start(1) - 1
                            start_index = end_index - int(m.group(1))
                            # rubyJpnLines[j][:start_index] + b'<ruby>' + rubyJpnLines[j][start_index:end_index] + b'</ruby>' + rubyJpnLines[j][end_index:]
                            main_text = rubyJpnLines[j][start_index:end_index]
                            extra_text = m.group(2)
                            # print('index', start_index, end_index)
                            # print('main', main_text.decode(jpn_encode), main_text)
                            # print('extra', extra_text.decode(jpn_encode))
                            rubyJpnLines[j] = rubyJpnLines[j][:start_index] + b'<ruby>%s<rt>%s</rt></ruby>' % (
                            main_text, extra_text) + rubyJpnLines[j][(m.start(3) + 1):]
                            print('ruby result', rubyJpnLines[j].decode(jpn_encode))

                    jpn_html_text = '<br/><br/>'.join(
                        [re.sub(rb'#\d+[A-Z]|[\x00-\x09]', b'', line.replace(b'\x01', b'<br/>')).decode(jpn_encode) for
                         line in rubyJpnLines])

                    jpn_search_text = ''.join([re.sub(rb'#\d*?R[^#]+?#|#\d+[A-Z]|[\x00-\x09]', b'',
                                                      line.replace(b'\x01', b'<br/>')).decode(jpn_encode) for
                                               line in jpnLines])

                    # line counts don't match

                    eng_lines2 = eng_lines

                    if len(eng_lines) != len(jpnLines) or not re.search(br'[^\x00-\x1f\xfe-\xff]', eng_lines[0]):
                        eng_lines, skipLine = fixEngLines(eng_lines, jpnLines, fullEngLines, hasPortrait, i, hax)
                        print('fixed', eng_lines)
                        # print(skipLine)
                        if skipLine:
                            # hax.append(b'[bad]')
                            print("skipLine!!!!!", fname, eng_lines, [line.decode(jpn_encode) for line in jpnLines])
                            # displaytbl.append([str(i) + str(hax), str(eng_lines), str([line.decode(jpn_encode) for line in jpnLines])])
                            continue

                    eng_lines = insertCodes(eng_lines, jpnLines, fullEngLines[i])

                    if fullEngLines[i].startswith(b'AnonymousTalk'):
                        for k in range(len(eng_lines)):
                            numLines = eng_lines[k].count(b'\x01') + 1
                            if numLines > 3:
                                print("OVER3LINES!!!!", fname, i, k, eng_lines[k])

                    # print(i,[line.decode(jpn_encode) for line in jpnLines],eng_lines)

                    # apply english lines to japanese script
                    for j in range(len(jpnLines)):

                        # print(j,eng_lines[j])

                        replaced = splitbodybytes[i].replace(jpnLines[j], eng_lines[j], 1)
                        # print(i, j, jpnLines[j].decode(jpn_encode), eng_lines[j])
                        # print('splitbodybytes',splitbodybytes[i].decode(jpn_encode))
                        # print(jpnLines[j], jpnLines[j] == eng_lines[j])
                        if splitbodybytes[i] == replaced and jpnLines[j] != eng_lines[j]:
                            print(i, j, jpnLines[j].decode(jpn_encode), eng_lines[j])
                            print("FAILURE!!!")
                            print(splitbodybytes[i])
                            print(jpnLines[j], jpnLines[j] == eng_lines[j])
                        splitbodybytes[i] = replaced

                    # if len(occurrences) != len(splitbodybytes):
                    # displaytbl.append([str(i) + str(hax), splitbodybytes[i], jpnLines])
                    voiceLinks = b'\n'.join([b'http://platonicfuzz.com/evo/fc/ch%s.ogg' % m.group(1) for m in
                                             re.finditer(rb'#(\d+)V', splitbodybytes[i])]).decode(jpn_encode)
                    eng_search_text = re.sub(rb'#\d+[A-Z]|[\x00-\x09]', b'',
                                          b'\n\n'.join(originalEngLines).replace(b'\x01', b' ')).decode(jpn_encode)
                    # formattedEng = b'\n'.join(originalEngLines).replace(b'\x01', b'\n').decode(jpn_encode)
                    # print('jpn line?', [line.decode(jpn_encode) for line in jpnLines])

                    # print([line.decode(jpn_encode) for line in jpnLines])

                    pages = splitbodybytes[i].split(b'\x02\x03')
                    # pages = eng_lines2
                    evo_icons = []
                    pc_icons = []

                    # print(i,full_eng_lines[i])
                    pc_icon = re.finditer(rb'#(\d+?)F', fullEngLines[i])

                    if pc_icon:
                        for m in pc_icon:
                            icon_index = int(m.group(1).decode(jpn_encode))
                            if len(str(icon_index)) <= 3:
                                icon_index = f'{icon_index:03}'
                                icon_str = '<img class="itp" src="itp/1/pc/H_KAO%s.webp"/> ' \
                                           % icon_index
                            else:
                                icon_str = '<img class="itp" src="itp/1/pc/H_KA%s.webp"/> ' \
                                           % icon_index
                            pc_icons.append(icon_str)

                    # print('pc icon???', pc_icons)

                    for j in range(len(pages)):
                        voice = re.search(rb'#(\d+?)V', pages[j])
                        evo_icon = re.search(rb'#(\d+?)F', pages[j])

                        if voice:
                            # print('a voice!!!')
                            pages[j] = b'<audio id="ch%s"><source src="talk/1/ch%s.ogg" ' \
                                       b'type="audio/ogg"></audio><a href="javascript:void(0)" ' \
                                       b'onclick="document.getElementById(\'ch%s\').play()">%s</a>' \
                                       % (voice.group(1), voice.group(1), voice.group(1), pages[j])
                            # print(pages[j])
                        if evo_icon:
                            icon_index = int(evo_icon.group(1).decode(jpn_encode))
                            if len(str(icon_index)) <= 3:
                                icon_index = f'{icon_index:03}'
                                icon_str = '<img class="itp" src="itp/1/evo/c_kao%s.webp"/> ' \
                                           % icon_index
                            else:
                                icon_str = '<img class="itp" src="itp/1/evo/c_ka%s.webp"/> ' \
                                           % icon_index
                            evo_icons.append(icon_str)

                    if eng_npc_name is not None:
                        eng_chr_name = eng_npc_name
                    else:
                        eng_chr_name = get_chr_name(op_name, fullEngLines[i], originalEngLines, eng_names,
                                                    eng_name_strings, name_start_index, fname, allbytes, allbytes_main,
                                                    setChrNamesEng, setChrNamesEng)
                        # jpn_chr_name = convertName(eng_chr_name)
                    if jpn_npc_name is not None:
                        jpn_chr_name = jpn_npc_name
                    else:
                        # if eng_chr_name != '' and jpn_chr_name == eng_chr_name and op_name == 'AnonymousTalk':

                        try:
                            jpn_chr_name = get_chr_name(op_name_jpn, fullEngLines[i], jpnLines, jpn_names,
                                                        jpn_name_strings, jpn_start_index, fname, allbytes,
                                                        allbytes_main, set_chr_names_jpn, set_chr_names_jpn)
                            if '#' in jpn_chr_name:
                                jpn_chr_name = convertName(eng_chr_name)
                        except ValueError:
                            print('VALUE ERROR', fname)
                            # if fname == 't0000':
                            jpn_chr_name = convertName(eng_chr_name)
                            # print('convert result', eng_chr_name, jpn_chr_name)
                            # else:
                            #     raise ValueError
                    if eng_chr_name != '' and jpn_chr_name == '':
                        jpn_chr_name = convertName(eng_chr_name)

                    print('jpn_chr_name RESULT', jpn_chr_name)

                    if eng_chr_name == '' and jpn_chr_name != '':
                        jpn_chr_name = ''

                    if not (eng_chr_name == '' and jpn_chr_name == '') and (eng_chr_name == '' or jpn_chr_name == '' or eng_chr_name == jpn_chr_name):
                        print('weird jpn chr name!!!!', fname, eng_chr_name, jpn_chr_name)

                    eng_html_text = re.sub(rb'#\d+[A-Z]|[\x00-\x09\xfe-\xff]', b'',
                                           b'<br/><br/>'.join(pages).replace(b'\x01', b'<br/>')).decode(
                        jpn_encode)

                    # if op_name == 'NpcTalk':

                    # print("??? npc???", pages)
                    # jpn_chr_name = jpnLines[0].decode(jpn_encode)
                    # print('npc jpn chr = ', jpn_chr_name)
                    # else:
                    #     eng_html_text = re.sub(rb'#\d+[A-Z]|[\x00-\x09\xfe-\xff]', b'',
                    #                                 b'<br/><br/>'.join(pages).replace(b'\x01', b'<br/>')).decode(
                    #         jpn_encode)
                    # jpn_chr_name = convertName(eng_chr_name)

                    # if len(jpnLines) > 1 and b'#' not in jpnLines[0]:
                    #     print('maybe jpn npc', jpnLines[0].decode(jpn_encode), jpn_search_text, eng_search_text, fname)
                    #     jpn_chr_name = jpnLines[0].decode(jpn_encode)
                    # else:
                    #     jpn_chr_name = convertName(eng_chr_name)

                    # eng_search_text = eng_html_text.replace('<br/>', ' ')

                    # print(op_name, eng_chr_name, eng_search_text, eng_lines)

                    displaytbl.append(
                        ['1', fname, str(i + 1), eng_chr_name, eng_search_text, eng_html_text,
                         jpn_chr_name, jpn_search_text, jpn_html_text, op_name, ''.join(pc_icons), ''.join(evo_icons)])

                    # displaytbl2[fname].append(
                    # ['<a id="%d">%d</a>' % (i + 1, i + 1), '<br/>'.join(icons), eng_chr_name, eng_html_text,
                    # jpn_chr_name, jpn_html_text])

                # exportPatchedMbin(splitbodybytes, headerbytes, fname)
                os.system("title " + fname)

        except FileNotFoundError:
            print('NOT FOUND', fname)
            pass
        # except IndexError:
        #     print('INDEX ERR', fname)
        #     pass

    print(allcodes)

    with open(r'snkfcevo.sql', 'w', encoding='utf-8') as sqlfile:
        sqlfile.write('delete from script where game_id = 1;\n')
        for row in displaytbl:
            newrow = []
            for cell in row:
                if type(cell) is list:
                    print('cell=', cell)
                    cell = str([line.decode(jpn_encode) for line in cell])
                elif type(cell) is bytes:
                    cell = str(cell)
                newrow.append(cell)
            # print("','".join([c.replace("'", "''") for c in newrow]))
            sqlfile.write(
                'insert into script (game_id, fname, row, eng_chr_name, eng_search_text, eng_html_text, jpn_chr_name, jpn_search_text, jpn_html_text, op_name, pc_icon_html, evo_icon_html) values\n')
            sqlfile.write("('%s');\n" % ("','".join([c.replace("'", "''").replace('\x1a', '\\Z') for c in newrow])))
        # csvwriter = csv.writer(csvfile, delimiter='\t', quotechar='`')
        # # write header
        # csvwriter.writerow(['game', 'fname', 'row', 'eng_chr_name', 'eng_search_text', 'eng_html_text', 'jpn_chr_name', 'jpn_search_text', 'jpn_html_text', 'op_name'])
        # for row in displaytbl:
        #     newrow = []
        #     for cell in row:
        #         if type(cell) is list:
        #             print('cell=', cell)
        #             cell = str([line.decode(jpn_encode) for line in cell])
        #         elif type(cell) is bytes:
        #             cell = str(cell)
        #         newrow.append(cell)
        #     csvwriter.writerow(newrow)

    # for fname in displaytbl2.keys():
    #     with open(r'\\WEJJ\projects\platonicfuzz\evo\fc\%s.html' % fname, 'w', newline='') as htmlfile:
    #         htmlfile.write(template_start % (fname, fname))

    #         for row in displaytbl2[fname]:
    #             htmlfile.write('<tr>' + ('<td>%s</td>' * len(row)) % tuple(row) + '</tr>'
    #                            )

    #         htmlfile.write(template_mid)

    #         for row in footer[fname]:
    #             htmlfile.write('<tr><td><a href="%s.html">%s</a></td></tr>' % (row, row))

    #         htmlfile.write(template_end)


if __name__ == "__main__":
    main()
