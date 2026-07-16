#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سازنده‌ی تمرین «جای خالی» از روی کتاب درسی (PDF).

این اسکریپت متن فارسی PDF را با مرتب‌سازی مختصاتی (راست‌به‌چپ) استخراج می‌کند،
جمله‌ها را جدا می‌کند و در هر جمله حداقل ۳ واژه‌ی کلیدی را به «جای خالی» تبدیل می‌کند.
خروجی یک فایل data.js است که سایت آن را می‌خواند.

اجرا:
    python3 build.py "../Zist 3.pdf"

نیازمندی: pip install pymupdf
"""

import sys, os, re, json, unicodedata
from collections import defaultdict, Counter

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF نصب نیست. اجرا کنید: pip install pymupdf")

MIN_BLANKS = 3            # هدفِ جای خالی در هر عبارت (اگر ممکن نبود، کمتر)
OUTPUT = "data.js"        # هیچ عبارتی حذف نمی‌شود؛ فقط خط‌های بدون حرف کنار می‌روند

# ------------------------------------------------------------------ #
#  ۱) پاکسازی نویسه‌ها
# ------------------------------------------------------------------ #
ZWNJ = "‌"

def normalize(s: str) -> str:
    # یکسان‌سازی عربی -> فارسی
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "هٔ")
    # حذف فاصله‌های نامرئی گوناگون، نگه‌داشتن نیم‌فاصله‌ی واقعی بعداً
    s = s.replace(" ", " ").replace("​", "").replace("﻿", "")
    s = s.replace("‫", "").replace("‬", "").replace("‪", "")
    s = s.replace("ـ", "")  # کشیده
    # حذف اعرابِ اضافه (نگه‌داشتنشان مشکلی ندارد ولی برای تطبیق پاسخ بهتر است حذف شوند)
    s = re.sub(r"[ً-ْٰ]", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

# ------------------------------------------------------------------ #
#  ۲) استخراج خط‌به‌خط با ترتیب درست
#     در این PDF هر خطِ راست‌به‌چپ با «فاصله‌ی مویی» (U+200A) به چند «قطعه»
#     شکسته شده و قطعه‌ها معکوس ذخیره شده‌اند. با معکوس‌کردنِ قطعه‌ها و
#     چسباندنشان با نیم‌فاصله، جمله‌ی درست و خوانا بازسازی می‌شود.
# ------------------------------------------------------------------ #
HAIR = " "
LEAD_PUNCT = re.compile(r"^([.!؟،؛:]+)(.+)$")
WORD_RE = re.compile(r"[ء-ی]+")

# نگاشتِ تصحیح لیگاتورِ «لا» که در این PDF برعکس ذخیره شده («اخالق»→«اخلاق»).
# به‌صورت خودکار از روی نشانه‌ی هندسی (حرف «ا»ی عرض‌صفر پیش از «ل») ساخته می‌شود.
LIG_MAP = {}

def build_ligature_map(doc):
    mapping = {}
    for pno in range(doc.page_count):
        d = doc[pno].get_text("rawdict")
        for b in d.get("blocks", []):
            for ln in b.get("lines", []):
                for s in ln.get("spans", []):
                    chars = s["chars"]
                    raw = [c["c"] for c in chars]
                    cor = raw[:]
                    changed = False
                    for i in range(len(chars) - 1):
                        w = chars[i]["bbox"][2] - chars[i]["bbox"][0]
                        if raw[i] == "ا" and w < 0.5 and raw[i + 1] == "ل":
                            cor[i], cor[i + 1] = cor[i + 1], cor[i]  # ال → لا
                            changed = True
                    if not changed:
                        continue
                    rw = WORD_RE.findall(normalize("".join(raw)))
                    cw = WORD_RE.findall(normalize("".join(cor)))
                    if len(rw) == len(cw):
                        for a, b2 in zip(rw, cw):
                            if a != b2:
                                mapping[a] = b2
    return mapping

def reconstruct_line(raw_line: str) -> str:
    runs = raw_line.split(HAIR)
    fixed = []
    for r in runs:
        r = normalize(r)
        if not r:
            continue
        # علامت پایانی که در RTL به ابتدای قطعه چسبیده را به انتهای همان قطعه ببر
        m = LEAD_PUNCT.match(r)
        if m:
            r = m.group(2).strip() + m.group(1)
        fixed.append(r)
    text = ZWNJ.join(reversed(fixed)).strip()
    if LIG_MAP:
        text = WORD_RE.sub(lambda mm: LIG_MAP.get(mm.group(), mm.group()), text)
    return text

def extract_lines(page):
    lines = []
    for rl in page.get_text().split("\n"):
        if not rl.strip():
            continue
        t = reconstruct_line(rl)
        if t:
            lines.append(t)
    return lines

# ------------------------------------------------------------------ #
#  ۳) تشخیص خطوط زائد (شماره صفحه، سربرگ، عنوان شکل و ...)
# ------------------------------------------------------------------ #
FIG_RE = re.compile(r"^\s*(شکل|جدول)\b")
NOISE_EXACT = {"بیشتر بدانید", "فعالیت", "خودارزیابی", "بخوانید و بیندیشید"}

def is_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if re.fullmatch(r"[\d\W_]+", s):     # فقط عدد/نماد
        return True
    if len(s) <= 2:
        return True
    if s in NOISE_EXACT:
        return True
    return False

# ------------------------------------------------------------------ #
#  ۴) جمله‌بندی
# ------------------------------------------------------------------ #
SENT_SPLIT = re.compile(r"(?<=[\.!؟])\s+")

def split_sentences(paragraph: str):
    # نقطه‌ی داخل اعداد اعشاری/شکل را نشکن
    parts = SENT_SPLIT.split(paragraph)
    res = []
    for p in parts:
        p = p.strip(" .•-–—")
        if p:
            res.append(p)
    return res

# ------------------------------------------------------------------ #
#  ۵) انتخاب جای خالی
# ------------------------------------------------------------------ #
# واژه‌های نقشی که هرگز نباید جای خالی شوند
HARD_STOP = set("""
و در به از که را این آن با یا هم اما ولی پس چون زیرا اگر تا یک بر نه بی هیچ
آنها اینها آنان ایشان او وی ما شما من تو خود خویش یکدیگر همدیگر آنچه آنکه کسی
هرگاه وقتی هنگامی چنانچه یعنی یا نیز فقط تنها حتی مگر بلکه خواه اینکه چنین چنان
همین همان دیگر دیگری هرچه هر چند برخی بعضی سایر همه تمام کل بیشتر کمتر
""".split())

# کلمات محتوایی ولی کم‌ارزش برای کنکور (جریمه می‌شوند، نه حذف)
SOFT_LOW = set("""
مانند مثل همانند مثلا مختلف گوناگون متفاوت معمولا اغلب اکثر همواره همیشه اکنون
سپس آنگاه دارای شامل وجود ایجاد انجام دچار طریق وسیله کمک همراه جهت مورد موارد
عنوان حدود قسمت بخش حالت زمان هنگام صورت طور طوری گونه امکان توجه نسبت ممکن لازم
بهتر زیاد بسیار خیلی نوعی طبق اساس روی زیر بالا پایین کنار میان بین بعد قبل درون بیرون
""".split())

# فعل‌های پرتکرار که ارزش جای‌خالی ندارند (جریمه می‌شوند)
VERB_SET = set("""
است هست هستند نیست نیستند بود بودند باشد باشند شد شدند شده شود می‌شود می‌شوند
شوند کرد کردند کند کنند کرده می‌کند می‌کنند دارد دارند داشت داشته می‌دهد دهد
دهند داده گیرد می‌گیرد گیرند گرفته آید می‌آید رود می‌رود یابد می‌یابد یافته
خواهد باید نامند می‌نامند گویند می‌گویند دیده شده‌اند می‌شد می‌توان می‌تواند
تواند توانند بردارد می‌ماند ماند رسد می‌رسد افتد می‌افتد آورد می‌آورد شویم
""".split())

PUNCT = "()[]{}،؛:«»\"'.؟!ـ-–—…"
TERM_FREQ = Counter()

def is_verb(tok: str) -> bool:
    if tok.startswith("می" + ZWNJ) or tok.startswith("نمی" + ZWNJ):
        return True
    plain = tok.strip(PUNCT)
    return plain in VERB_SET

def pick_blanks(tokens):
    """اندیسِ واژه‌هایی که جای خالی می‌شوند؛ با اولویتِ ارزشِ کنکوری."""
    scored = []
    for i, tok in enumerate(tokens):
        core = tok.strip(PUNCT)
        plain = core.replace(ZWNJ, "")
        if not plain or len(plain) < 3 or plain in HARD_STOP:
            continue
        score = float(len(plain))
        if re.search(r"[A-Za-z]", core):                 # اصطلاح/فرمول لاتین
            score += 8
        if re.search(r"[0-9۰-۹]", core):                 # عدد
            score += 7
        if ZWNJ in core:                                  # واژه‌ی مرکبِ تخصصی
            score += 3
        score += min(TERM_FREQ.get(plain, 0), 10) * 0.8   # مفهومِ پرتکرارِ کتاب
        if plain in SOFT_LOW:                             # کلمه‌ی عمومی
            score -= 6
        if is_verb(tok):                                  # فعل
            score -= 9
        scored.append((score, i))
    scored.sort(key=lambda x: (-x[0], x[1]))
    # تراکم مثل قبل: هدف ~۳۰٪ واژه‌ها، حداقل MIN_BLANKS، سقف ۸ (کم نمی‌شود)
    n = max(MIN_BLANKS, round(len(tokens) * 0.30))
    n = min(n, 8, len(scored))
    idx = [i for _, i in scored[:n]]
    if not idx:
        cand = [(len(t.replace(ZWNJ, "")), i) for i, t in enumerate(tokens)
                if len(t.replace(ZWNJ, "")) >= 2]
        if cand:
            idx = [max(cand)[1]]
    return sorted(idx)

def tokens_of(text: str):
    return [t for t in text.split(" ") if t]

def count_terms(tokens):
    """واژه‌های محتوایی هر جمله را برای شمارشِ سراسری برمی‌گرداند."""
    for tok in tokens:
        plain = tok.strip(PUNCT).replace(ZWNJ, "")
        if len(plain) >= 3 and plain not in HARD_STOP and not is_verb(tok):
            TERM_FREQ[plain] += 1

# ------------------------------------------------------------------ #
#  ۶) پردازش کل کتاب
# ------------------------------------------------------------------ #
HAS_LETTER = re.compile(r"[A-Za-z؀-ۿ]")

def build(pdf_path):
    global LIG_MAP
    doc = fitz.open(pdf_path)
    LIG_MAP = build_ligature_map(doc)
    print(f"  کلمات تصحیح‌شده‌ی لیگاتور «لا»: {len(LIG_MAP)}")

    # گذر اول: استخراج جمله‌ها و شمارشِ سراسریِ واژه‌ها (برای ارزش‌گذاری کنکوری)
    raw_pages = []
    skipped_no_letter = 0
    for pno in range(doc.page_count):
        kept = []
        for ln in extract_lines(doc[pno]):
            if HAS_LETTER.search(ln):
                kept.append(ln)
            else:
                skipped_no_letter += 1
        if not kept:
            continue
        paragraph = re.sub(r"\s+", " ", " ".join(kept)).strip()
        parts = split_sentences(paragraph) or [paragraph]
        items = [tokens_of(p) for p in parts]
        items = [t for t in items if t]
        if items:
            raw_pages.append((pno + 1, items))
            for toks in items:
                count_terms(toks)
    print(f"  خط‌های بدون حرف که کنار گذاشته شد (شماره صفحه و…): {skipped_no_letter}")
    print(f"  واژه‌های محتواییِ یکتا (برای ارزش‌گذاری): {len(TERM_FREQ)}")

    # گذر دوم: انتخاب جای خالی‌ها با ارزش کنکوری
    pages_out = []
    total_sent = 0
    for pno, items in raw_pages:
        sents = [{"t": toks, "b": pick_blanks(toks)} for toks in items]
        pages_out.append({"page": pno, "sentences": sents})
        total_sent += len(sents)
    data = {
        "title": "زیست‌شناسی ۳ — تمرین جای خالی",
        "pages": pages_out,
        "stats": {"pages": len(pages_out), "sentences": total_sent},
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("window.KETAB_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"✓ ساخته شد: {OUTPUT}")
    print(f"  صفحات دارای محتوا: {len(pages_out)}")
    print(f"  کل جمله‌ها: {total_sent}")

if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "../Zist 3.pdf"
    if not os.path.exists(pdf):
        sys.exit(f"فایل پیدا نشد: {pdf}")
    build(pdf)
