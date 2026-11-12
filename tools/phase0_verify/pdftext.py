"""Minimal stdlib-only PDF text extractor (enough to read a LaTeX/Word-generated document).

Usage: python -I pdftext.py <input.pdf> <output.txt>
Handles: classic xref objects, object streams (ObjStm), FlateDecode, page tree order,
ToUnicode CMaps (bfchar/bfrange), Tj/TJ/'/" operators, Form XObjects (one level of recursion).
"""
import re
import sys
import zlib

data = open(sys.argv[1], "rb").read()
objs = {}  # num -> bytes (object body, without 'obj'/'endobj')

for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", data, re.S):
    objs[int(m.group(1))] = m.group(3)


def stream_of(body):
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    raw = body[m.end():]
    end = raw.rfind(b"endstream")
    raw = raw[:end] if end >= 0 else raw
    head = body[:m.start()]
    if b"/FlateDecode" in head:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:
                return zlib.decompressobj().decompress(raw)
            except zlib.error:
                return b""
    return raw


def dict_of(body):
    m = re.search(rb"stream\r?\n", body)
    return body[:m.start()] if m else body


# Expand object streams
for num, body in list(objs.items()):
    if b"/ObjStm" in dict_of(body):
        s = stream_of(body)
        if not s:
            continue
        n = int(re.search(rb"/N\s+(\d+)", body).group(1))
        first = int(re.search(rb"/First\s+(\d+)", body).group(1))
        nums = list(map(int, s[:first].split()))
        pairs = [(nums[i], nums[i + 1]) for i in range(0, 2 * n, 2)]
        for k, (onum, off) in enumerate(pairs):
            end = pairs[k + 1][1] if k + 1 < len(pairs) else len(s) - first
            objs.setdefault(onum, s[first + off:first + end])


def ref(body, key):
    m = re.search(rb"/" + key + rb"\s+(\d+)\s+0\s+R", body)
    return int(m.group(1)) if m else None


def resolve_dict(body, key):
    """Return inline dict text for /key << ... >> or the referenced object's body."""
    r = ref(body, key)
    if r is not None:
        return objs.get(r, b"")
    i = body.find(b"/" + key)
    if i < 0:
        return b""
    j = body.find(b"<<", i)
    depth, k = 0, j
    while k < len(body):
        if body[k:k + 2] == b"<<":
            depth += 1
            k += 2
            continue
        if body[k:k + 2] == b">>":
            depth -= 1
            k += 2
            if depth == 0:
                return body[j:k]
            continue
        k += 1
    return b""


cmap_cache = {}


def parse_cmap(num):
    if num in cmap_cache:
        return cmap_cache[num]
    s = stream_of(objs.get(num, b"")) or b""
    mp, width = {}, 1
    cs = re.search(rb"begincodespacerange\s*<([0-9A-Fa-f]+)>", s)
    if cs:
        width = len(cs.group(1)) // 2
    for blk in re.findall(rb"beginbfchar(.*?)endbfchar", s, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", blk):
            try:
                mp[int(a, 16)] = bytes.fromhex(b.decode()).decode("utf-16-be", "replace")
            except ValueError:
                pass
    for blk in re.findall(rb"beginbfrange(.*?)endbfrange", s, re.S):
        for a, b, rest in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)", blk):
            lo, hi = int(a, 16), int(b, 16)
            if rest.startswith(b"["):
                vals = re.findall(rb"<([0-9A-Fa-f]*)>", rest)
                for i, v in enumerate(vals):
                    mp[lo + i] = bytes.fromhex(v.decode()).decode("utf-16-be", "replace")
            else:
                base = int(rest[1:-1] or b"0", 16)
                nbytes = max(2, len(rest[1:-1]) // 2)
                for c in range(lo, min(hi, lo + 5000) + 1):
                    try:
                        mp[c] = (base + c - lo).to_bytes(nbytes, "big").decode("utf-16-be", "replace")
                    except (OverflowError, ValueError):
                        pass
    cmap_cache[num] = (mp, width)
    return cmap_cache[num]


def fonts_for(res_body):
    fd = resolve_dict(res_body, b"Font")
    out = {}
    for name, num in re.findall(rb"/([A-Za-z0-9_.+-]+)\s+(\d+)\s+0\s+R", fd):
        fb = objs.get(int(num), b"")
        tu = ref(fb, b"ToUnicode")
        out[name] = parse_cmap(tu) if tu else ({}, 1)
    return out


def xobjects_for(res_body):
    xd = resolve_dict(res_body, b"XObject")
    return {n: int(r) for n, r in re.findall(rb"/([A-Za-z0-9_.+-]+)\s+(\d+)\s+0\s+R", xd)}


TOK = re.compile(rb"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>]+|[^\s/\[\]()<>]+", re.S)


def lit(b):
    out, i = bytearray(), 1
    depth = 0
    while i < len(b) - 1:
        c = b[i]
        if c == 0x5C:
            i += 1
            n = b[i:i + 1]
            esc = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
            if n in esc:
                out += esc[n]
            elif n.isdigit():
                o = re.match(rb"[0-7]{1,3}", b[i:i + 3]).group(0)
                out.append(int(o, 8) & 0xFF)
                i += len(o) - 1
            elif n in (b"\r", b"\n"):
                pass
            else:
                out += n
        else:
            out.append(c)
        i += 1
    return bytes(out)


def decode(raw, font):
    mp, width = font
    if not mp:
        return raw.decode("latin-1")
    s = []
    for i in range(0, len(raw) - width + 1, width):
        code = int.from_bytes(raw[i:i + width], "big")
        s.append(mp.get(code, ""))
    return "".join(s)


def run_content(stream, res_body, out, depth=0):
    fonts = fonts_for(res_body)
    xobjs = xobjects_for(res_body)
    font = ({}, 1)
    stack = []
    for t in TOK.findall(stream):
        if t.startswith(b"(") or t.startswith(b"<") or t.startswith(b"/") or t in (b"[", b"]") or \
                re.fullmatch(rb"[-+]?\d*\.?\d+", t):
            stack.append(t)
            continue
        op = t
        if op == b"Tf" and len(stack) >= 2:
            font = fonts.get(stack[-2][1:], ({}, 1))
        elif op in (b"Tj", b"'", b'"') and stack:
            s = stack[-1]
            raw = lit(s) if s.startswith(b"(") else bytes.fromhex(re.sub(rb"\s", b"", s[1:-1]).decode() or "")
            if op != b"Tj":
                out.append("\n")
            out.append(decode(raw, font))
        elif op == b"TJ":
            try:
                i = len(stack) - 1 - stack[::-1].index(b"[")
            except ValueError:
                i = len(stack)
            for s in stack[i + 1:]:
                if s.startswith(b"("):
                    out.append(decode(lit(s), font))
                elif s.startswith(b"<"):
                    out.append(decode(bytes.fromhex(re.sub(rb"\s", b"", s[1:-1]).decode() or ""), font))
                elif s != b"]":
                    try:
                        if float(s) < -180:
                            out.append(" ")
                    except ValueError:
                        pass
        elif op in (b"Td", b"TD") and len(stack) >= 2:
            try:
                if abs(float(stack[-1])) > 0.1:
                    out.append("\n")
                elif float(stack[-2]) > 1:
                    out.append(" ")
            except ValueError:
                pass
        elif op in (b"T*", b"ET"):
            out.append("\n")
        elif op == b"Tm":
            out.append("\n")
        elif op == b"Do" and stack and depth < 2:
            xn = xobjs.get(stack[-1][1:])
            if xn is not None:
                xb = objs.get(xn, b"")
                if b"/Form" in dict_of(xb):
                    xres = resolve_dict(dict_of(xb), b"Resources") or res_body
                    run_content(stream_of(xb) or b"", xres, out, depth + 1)
        stack = []


# Page order via page tree
root_num = None
for num, body in objs.items():
    if re.search(rb"/Type\s*/Catalog", dict_of(body)):
        root_num = num
        break
pages = []


def walk(num, inherited_res):
    body = dict_of(objs.get(num, b""))
    res = resolve_dict(body, b"Resources") or inherited_res
    if re.search(rb"/Type\s*/Pages", body):
        kids = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
        for k in re.findall(rb"(\d+)\s+0\s+R", kids.group(1)):
            walk(int(k), res)
    elif re.search(rb"/Type\s*/Page\b", body):
        pages.append((num, res))


walk(ref(dict_of(objs[root_num]), b"Pages"), b"")
with open(sys.argv[2], "w", encoding="utf-8") as f:
    for pno, (num, res) in enumerate(pages, 1):
        body = dict_of(objs[num])
        m = re.search(rb"/Contents\s*(\[(.*?)\]|(\d+)\s+0\s+R)", body, re.S)
        nums = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", m.group(1))] if m else []
        content = b"\n".join(stream_of(objs.get(n, b"")) or b"" for n in nums)
        out = []
        run_content(content, res, out)
        text = re.sub(r"[ \t]+", " ", "".join(out))
        text = re.sub(r"\n\s*\n+", "\n", text)
        f.write(f"\n\n======== PAGE {pno} ========\n{text}")
print("objects", len(objs), "pages", len(pages))
