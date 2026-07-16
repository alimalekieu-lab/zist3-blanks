/* تمرین جای خالی — تجربه‌ی دولینگویی (بدون سرور) */
(function () {
  "use strict";
  var DATA = window.KETAB_DATA;
  var app = document.getElementById("app");
  var ZWNJ = "‌";

  if (!DATA || !DATA.pages) {
    app.innerHTML = '<p style="padding:24px">داده‌ای نیست. ابتدا build.py را اجرا کنید.</p>';
    return;
  }

  /* ---------- ذخیره‌سازی ---------- */
  var store = {
    get: function (k, d) { try { return JSON.parse(localStorage.getItem("z3_" + k)) ?? d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem("z3_" + k, JSON.stringify(v)); } catch (e) {} }
  };
  var XP = store.get("xp", 0);
  var STREAK = store.get("streak", 0);            // روزهای/برد پیاپی نیست؛ زنجیره‌ی پاسخ درست کلی
  var DONE = store.get("done", {});               // {pageNo: bestAccuracy}
  var MODE = store.get("mode", "bank");           // bank | type
  var THEME = store.get("theme", "light");
  applyTheme(THEME);

  /* ---------- آماده‌سازی درس‌ها و مخزن گزینه‌ها ---------- */
  var LESSONS = [];         // [{page, items:[{t,b}]}]
  var POOL = [];            // مخزن کلمات برای گزینه‌های انحرافی
  var poolSet = {};
  DATA.pages.forEach(function (p) {
    var items = p.sentences.filter(function (s) { return s.b && s.b.length; });
    if (items.length) LESSONS.push({ page: p.page, items: items });
    p.sentences.forEach(function (s) {
      (s.b || []).forEach(function (i) {
        var w = clean(s.t[i]);
        if (w && !poolSet[norm(w)]) { poolSet[norm(w)] = 1; POOL.push(w); }
      });
    });
  });

  function clean(t) { return (t || "").replace(/^[()[\]{}،؛:«»"'.؟!ـ\-–—…]+|[()[\]{}،؛:«»"'.؟!ـ\-–—…]+$/g, ""); }
  function norm(s) {
    return (s || "").replace(/‌/g, "").replace(/[يﻱ]/g, "ی").replace(/[كﻙ]/g, "ک")
      .replace(/[ًٌٍَُِّْٰ]/g, "").replace(/[.،؛:!؟«»"'()\[\]\-–—…]/g, "")
      .replace(/\s+/g, "").trim().toLowerCase();
  }
  function shuffle(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }

  /* ---------- صدا (WebAudio، بدون فایل) ---------- */
  var AC = null;
  function beep(ok) {
    try {
      AC = AC || new (window.AudioContext || window.webkitAudioContext)();
      var o = AC.createOscillator(), g = AC.createGain();
      o.connect(g); g.connect(AC.destination);
      if (ok) { o.frequency.value = 660; o.frequency.setValueAtTime(880, AC.currentTime + 0.08); }
      else { o.type = "square"; o.frequency.value = 160; }
      g.gain.value = 0.05; o.start();
      g.gain.exponentialRampToValueAtTime(0.0001, AC.currentTime + 0.25);
      o.stop(AC.currentTime + 0.26);
    } catch (e) {}
  }

  /* ============================================================ */
  /*  صفحه‌ی خانه                                                  */
  /* ============================================================ */
  function renderHome() {
    var done = Object.keys(DONE).length;
    var h = '<div class="home">';
    h += '<div class="home-top">' +
      '<div class="title"><span class="logo">🧬</span><div><h1>زیست‌شناسی ۳</h1><p class="sub">تمرین جای خالی</p></div></div>' +
      '<div class="stats-row">' +
        '<span class="stat fire" title="زنجیره">🔥 ' + STREAK + '</span>' +
        '<span class="stat xp" title="امتیاز">⭐ ' + XP + '</span>' +
        '<button class="icon-btn" id="themeBtn">' + (THEME === "dark" ? "☀️" : "🌙") + '</button>' +
      '</div></div>';
    h += '<div class="home-hero"><h2>سلام! 👋</h2><p>یک درس انتخاب کن و شروع کن</p></div>';
    h += '<div class="section-label"><span>درس‌ها</span><span>' + done + ' / ' + LESSONS.length + ' کامل</span></div>';
    h += '<div class="lessons">';
    LESSONS.forEach(function (L, i) {
      var acc = DONE[L.page];
      var cls = acc != null ? "lesson done" : "lesson";
      h += '<button class="' + cls + '" data-idx="' + i + '">' +
        (acc != null ? '<span class="crown">👑</span>' : '') +
        '<span>' + (i + 1) + '</span><small>ص ' + L.page + '</small>' +
        (acc != null ? '<small>' + acc + '٪</small>' : '<small>' + L.items.length + ' سؤال</small>') +
      '</button>';
    });
    h += '</div></div>';
    app.innerHTML = h;
    document.getElementById("themeBtn").onclick = function () {
      THEME = THEME === "dark" ? "light" : "dark"; store.set("theme", THEME); applyTheme(THEME); renderHome();
    };
    [].forEach.call(document.querySelectorAll(".lesson"), function (b) {
      b.onclick = function () { startLesson(parseInt(b.dataset.idx, 10)); };
    });
  }

  /* ============================================================ */
  /*  اجرای یک درس                                                */
  /* ============================================================ */
  var L;  // وضعیت درس جاری
  function startLesson(idx) {
    var lesson = LESSONS[idx];
    L = {
      idx: idx, page: lesson.page, items: lesson.items,
      pos: 0, hearts: 5, correct: 0, total: lesson.items.length,
      earned: 0, answered: false, slots: [], selSlot: null
    };
    renderExercise();
  }

  function currentAnswers() {
    var it = L.items[L.pos];
    return it.b.slice().sort(function (a, b) { return a - b; }).map(function (i) {
      return { idx: i, word: clean(it.t[i]) };
    });
  }

  function renderExercise() {
    L.answered = false; L.selSlot = null; L.slots = [];
    var it = L.items[L.pos];
    var answers = currentAnswers();
    var pct = (L.pos / L.total) * 100;

    var h = '<div class="lesson-view">';
    h += '<div class="lesson-head">' +
      '<button class="close-btn" id="closeBtn">✕</button>' +
      '<div class="pbar"><div style="width:' + pct.toFixed(1) + '%"></div></div>' +
      '<span class="hearts">❤️ ' + L.hearts + '</span></div>';

    h += '<div class="exercise">';
    h += '<div class="ex-title">جای خالی‌ها را کامل کن</div>';
    h += '<div class="ex-sub">صفحه ' + L.page + ' — سؤال ' + (L.pos + 1) + ' از ' + L.total + '</div>';

    // جمله با جای خالی‌ها
    var blankSet = {}; answers.forEach(function (a, k) { blankSet[a.idx] = k; });
    h += '<div class="sentence-box" id="sbox">';
    it.t.forEach(function (tok, i) {
      if (blankSet[i] != null) {
        var k = blankSet[i];
        if (MODE === "type") {
          var w = Math.max(78, clean(tok).length * 15);
          h += '<input class="slot" data-k="' + k + '" style="width:' + w + 'px" autocomplete="off" spellcheck="false" inputmode="text">';
        } else {
          h += '<span class="slot" data-k="' + k + '"></span>';
        }
      } else {
        h += '<span class="tok">' + esc(tok) + '</span>';
      }
      h += " ";
    });
    h += '</div>';

    // بانک کلمات
    if (MODE === "bank") {
      var chips = answers.map(function (a) { return a.word; });
      var need = Math.min(6, Math.max(2, Math.round(answers.length * 0.6)));
      var pool = shuffle(POOL.slice());
      for (var i = 0; i < pool.length && chips.length < answers.length + need; i++) {
        if (chips.indexOf(pool[i]) === -1 && norm(pool[i]) && answers.every(function (a) { return norm(a.word) !== norm(pool[i]); }))
          chips.push(pool[i]);
      }
      shuffle(chips);
      h += '<div class="bank" id="bank">';
      chips.forEach(function (c, ci) { h += '<button class="chip" data-w="' + esc(c) + '" data-ci="' + ci + '">' + esc(c) + '</button>'; });
      h += '</div>';
    }

    h += '<div class="mode-toggle"><button id="modeBtn">' +
      (MODE === "bank" ? "✏️ حالت تایپ" : "🔤 حالت بانک کلمات") + '</button></div>';
    h += '</div>'; // exercise

    // فوتر بازخورد
    h += '<div class="footer" id="footer"><div class="feedback" id="feedback"></div>' +
      '<div class="row"><button class="btn wide" id="checkBtn" disabled>بررسی</button></div></div>';
    h += '</div>';
    app.innerHTML = h;

    document.getElementById("closeBtn").onclick = function () { if (confirm("از درس خارج می‌شوی؟")) renderHome(); };
    document.getElementById("modeBtn").onclick = function () { MODE = MODE === "bank" ? "type" : "bank"; store.set("mode", MODE); renderExercise(); };
    document.getElementById("checkBtn").onclick = onCheck;

    // اتصال جای خالی‌ها
    L.slots = [].map.call(document.querySelectorAll(".slot"), function (el) {
      return { el: el, word: "", chip: null, answer: answers[+el.dataset.k].word };
    });

    if (MODE === "type") {
      L.slots.forEach(function (s) {
        s.el.addEventListener("input", function () { s.word = s.el.value; refreshCheck(); });
        s.el.addEventListener("keydown", function (e) {
          if (e.key === "Enter") { e.preventDefault(); var d = document.getElementById("checkBtn"); if (!d.disabled) onCheck(); }
        });
      });
      var f = document.querySelector(".slot"); if (f) f.focus();
    } else {
      L.slots.forEach(function (s, si) { s.el.onclick = function () { selectSlot(si); }; });
      [].forEach.call(document.querySelectorAll(".chip"), function (c) { c.onclick = function () { tapChip(c); }; });
    }
    refreshCheck();
  }

  /* ---------- تعامل بانک کلمات ---------- */
  function selectSlot(si) {
    var s = L.slots[si];
    if (s.word) { // خالی کردن
      if (s.chip) s.chip.classList.remove("used");
      s.word = ""; s.chip = null; s.el.textContent = ""; s.el.classList.remove("filled");
    }
    L.selSlot = si;
    L.slots.forEach(function (x, k) { x.el.classList.toggle("sel", k === si); });
    refreshCheck();
  }
  function tapChip(c) {
    if (c.classList.contains("used")) return;
    var si = L.selSlot;
    if (si == null || L.slots[si].word) { // اولین خالی
      si = -1; for (var k = 0; k < L.slots.length; k++) if (!L.slots[k].word) { si = k; break; }
    }
    if (si < 0) return;
    var s = L.slots[si];
    s.word = c.dataset.w; s.chip = c; s.el.textContent = c.dataset.w; s.el.classList.add("filled");
    c.classList.add("used");
    L.selSlot = null; L.slots.forEach(function (x) { x.el.classList.remove("sel"); });
    refreshCheck();
  }
  function refreshCheck() {
    var all = L.slots.every(function (s) { return s.word && s.word.trim(); });
    document.getElementById("checkBtn").disabled = !all || L.answered;
  }

  /* ---------- بررسی پاسخ ---------- */
  function onCheck() {
    if (L.answered) return; L.answered = true;
    var allOk = true;
    L.slots.forEach(function (s) {
      var ok = norm(s.word) === norm(s.answer);
      if (!ok) allOk = false;
      if (MODE === "type") { s.el.readOnly = true; }
      s.el.classList.remove("sel");
      s.el.classList.add(ok ? "correct" : "wrong");
    });

    var footer = document.getElementById("footer");
    var fb = document.getElementById("feedback");
    fb.style.display = "block";
    if (allOk) {
      L.correct++; L.earned += 10; XP += 10; STREAK++;
      var combo = STREAK >= 3 ? ' <span style="color:#ff9600">🔥 ' + STREAK + 'تایی!</span>' : '';
      footer.className = "footer correct";
      fb.innerHTML = '<div class="head">✅ ' + praise() + combo + '</div>';
      beep(true);
    } else {
      L.hearts = Math.max(0, L.hearts - 1); STREAK = 0;
      var hd = document.querySelector(".hearts"); if (hd) hd.innerHTML = "❤️ " + L.hearts;
      var ans = currentAnswers().map(function (a) { return '<b>' + esc(a.word) + '</b>'; }).join("،‌ ");
      footer.className = "footer wrong";
      fb.innerHTML = '<div class="head">❌ درست‌ها:</div><div class="ans">' + ans + '</div>';
      beep(false);
    }
    store.set("xp", XP); store.set("streak", STREAK);

    var btn = document.getElementById("checkBtn");
    btn.disabled = false;
    btn.className = "btn wide " + (allOk ? "" : "red");
    btn.textContent = "ادامه";
    btn.onclick = next;
  }
  function praise() { var a = ["آفرین!", "عالی بود!", "درسته!", "ایول!", "کارت خوبه!"]; return a[Math.floor(Math.random() * a.length)]; }

  function next() {
    L.pos++;
    if (L.pos >= L.total) return finishLesson();
    renderExercise();
  }

  /* ---------- پایان درس ---------- */
  function finishLesson() {
    var acc = Math.round((L.correct / L.total) * 100);
    var prev = DONE[L.page];
    if (prev == null || acc > prev) { DONE[L.page] = acc; store.set("done", DONE); }
    var h = '<div class="lesson-view"><div class="complete">';
    h += '<div class="big">' + (acc >= 80 ? "🎉" : acc >= 50 ? "💪" : "📚") + '</div>';
    h += '<h2>درس کامل شد!</h2>';
    h += '<div class="cards">' +
      '<div class="rcard xp"><div class="inner"><div class="k">امتیاز</div><div class="v">+' + L.earned + '</div></div></div>' +
      '<div class="rcard acc"><div class="inner"><div class="k">دقت</div><div class="v">' + acc + '٪</div></div></div>' +
      '<div class="rcard"><div class="inner"><div class="k">درست</div><div class="v">' + L.correct + '/' + L.total + '</div></div></div>' +
      '</div>';
    h += '<div class="center-wrap">';
    h += '<button class="btn wide" id="againBtn" style="margin-bottom:12px">🔁 دوباره همین درس</button>';
    if (L.idx + 1 < LESSONS.length)
      h += '<button class="btn wide blue" id="nextLessonBtn" style="margin-bottom:12px">درس بعدی ←</button>';
    h += '<button class="btn wide ghost" id="homeBtn">خانه</button>';
    h += '</div></div></div>';
    app.innerHTML = h;
    document.getElementById("againBtn").onclick = function () { startLesson(L.idx); };
    document.getElementById("homeBtn").onclick = renderHome;
    var nb = document.getElementById("nextLessonBtn");
    if (nb) nb.onclick = function () { startLesson(L.idx + 1); };
  }

  function esc(s) { return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function applyTheme(t) { document.documentElement.setAttribute("data-theme", t); }

  renderHome();
})();
