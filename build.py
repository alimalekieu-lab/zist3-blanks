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
from collections import defaultdict

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
    return ZWNJ.join(reversed(fixed)).strip()

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
STOPWORDS = set("""
و در به از که را این آن با یا است بود شد شده می نمی برای هر تا یک دو سه چهار
هم اما ولی پس چون زیرا اگر نیز باید تواند توانند دارد دارند داشت داشته کرد کند
کنند کردن شود شوند های ها یک را بر نه بی هیچ آنها اینها همه چند وقتی هنگامی
مانند مثل مثلاً یعنی همچنین بنابراین درون بیرون روی زیر بالا پایین کنار میان
بین طور طوری گونه انواع نوع دیگر دیگری خود آنچه چه کدام کجا چگونه بعد قبل هنگام
""".split())

def pick_blanks(tokens):
    """اندیس واژه‌هایی که باید جای خالی شوند را برمی‌گرداند (حداقل MIN_BLANKS)."""
    scored = []
    for i, tok in enumerate(tokens):
        core = tok.strip("()[]،؛:«»\"'.")
        core_plain = core.replace(ZWNJ, "")
        if not core_plain:
            continue
        if core_plain in STOPWORDS:
            continue
        if len(core_plain) < 3:
            continue
        score = len(core_plain)
        if re.search(r"[A-Za-z]", core):      # اصطلاح لاتین/فرمول
            score += 5
        if re.search(r"\d", core):            # عدد مهم
            score += 4
        if ZWNJ in core:                       # واژه‌ی مرکب
            score += 2
        scored.append((score, i))
    scored.sort(reverse=True)
    # هدف: حداقل MIN_BLANKS؛ برای عبارت‌های بلند تا ۳۰٪ واژه‌ها با سقف ۸.
    # اگر واژه‌ی مناسب کمتر بود، هرچه هست جای خالی می‌شود (چیزی رد نمی‌شود).
    n = max(MIN_BLANKS, round(len(tokens) * 0.30))
    n = min(n, 8, len(scored))
    idx = [i for _, i in scored[:n]]
    if not idx:
        # هیچ واژه‌ی «کلیدی» نبود: بلندترین واژه (>=۲ حرف) را جای خالی کن
        cand = [(len(t.replace(ZWNJ, "")), i) for i, t in enumerate(tokens)
                if len(t.replace(ZWNJ, "")) >= 2]
        if cand:
            idx = [max(cand)[1]]
    return sorted(idx)

def make_item(text: str):
    tokens = [t for t in text.split(" ") if t]
    if not tokens:
        return None
    return {"t": tokens, "b": pick_blanks(tokens)}

# ------------------------------------------------------------------ #
#  ۶) پردازش کل کتاب
# ------------------------------------------------------------------ #
HAS_LETTER = re.compile(r"[A-Za-z؀-ۿ]")

def build(pdf_path):
    doc = fitz.open(pdf_path)
    pages_out = []
    total_sent = 0
    skipped_no_letter = 0
    for pno in range(doc.page_count):
        lines = extract_lines(doc[pno])
        # خط‌های دارای حرف را نگه می‌داریم (خط بدون حرف = شماره صفحه و… کنار می‌رود)
        kept = []
        for ln in lines:
            if HAS_LETTER.search(ln):
                kept.append(ln)
            else:
                skipped_no_letter += 1
        if not kept:
            continue
        # خط‌ها را به هم می‌چسبانیم تا جمله‌های شکسته‌شده روی چند خط، کامل بازخوانده شوند،
        # سپس بر اساس نقطه/علامت پایان به جمله می‌شکنیم. هیچ جمله‌ای حذف نمی‌شود.
        paragraph = re.sub(r"\s+", " ", " ".join(kept)).strip()
        parts = split_sentences(paragraph) or [paragraph]
        objs = []
        for p in parts:
            o = make_item(p)
            if o:
                objs.append(o)
        if objs:
            pages_out.append({"page": pno + 1, "sentences": objs})
            total_sent += len(objs)
    print(f"  خط‌های بدون حرف که کنار گذاشته شد (شماره صفحه و…): {skipped_no_letter}")
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
