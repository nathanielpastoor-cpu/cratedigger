"""
build_swipe.py  —  Build the "Tinder for crate-digging" page: swipe.html

Decks:
  * "Surprise me" = your personalized deck: LABEL releases (bandcamp_fresh.py) +
    DISCOVERIES (recommend.py), learned ranking.
  * a GENRE = a fresh deck of that genre from Audius (genres.py), all streamable.

Navigation is separate from judgment:
  ‹ ›  (on the art) or ← →  = move back / forward through the deck.
  ♥ / ↑ = save (keeps playing; tap again to un-save).
  ✕ / ↓ = not for me (trains the ranker against it, then moves on).

Genre dropdown switches the deck. AUTO-PLAY mode (⚙) filters "Surprise me" to
streaming cards; genre decks are all streaming so they auto-play either way.

State (likes/seen/prefs/settings) is in localStorage.
Refresh: bandcamp_fresh.py + recommend.py + genres.py, then this. Stdlib only.
"""

import json
import random
import webbrowser

import os
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "taste_profile.json")
OUT = os.path.join(HERE, "swipe.html")
INDEX = os.path.join(HERE, "index.html")


def load_tracks(profile):
    tracks, seen = [], set()
    for label, rels in profile.get("label_releases", {}).items():
        for r in rels:
            rid = r.get("id")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            tracks.append({
                "artist": r.get("artist", ""), "title": r.get("title", ""),
                "url": r.get("url", ""), "buy": r.get("url", ""),
                "art": r.get("art", ""), "id": rid, "type": r.get("type", "album"),
                "label": label, "source": "bandcamp", "kind": "label",
            })
    for d in profile.get("discovered", []):
        did = d.get("id")
        if not did or did in seen:
            continue
        seen.add(did)
        tracks.append({
            "artist": d.get("artist", ""), "title": d.get("title", ""),
            "url": d.get("url", ""), "buy": d.get("buy") or d.get("url", ""),
            "art": d.get("art", ""), "id": did, "type": d.get("type", "track"),
            "label": "", "source": d.get("source", "audius"),
            "kind": "discovery", "stream": d.get("stream", ""),
        })
    random.shuffle(tracks)
    return tracks


PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crate Swipe</title>
<style>
 :root{color-scheme:dark}
 *{box-sizing:border-box}
 :root{--artrgb:80,90,110}
 body{margin:0;background-color:#0d0d0f;color:#eee;font:15px/1.5 system-ui,sans-serif;transition:background-color .7s ease;
      min-height:100vh;display:flex;flex-direction:column;align-items:center}
 header{width:100%;max-width:520px;display:flex;justify-content:space-between;
        align-items:center;padding:14px 16px 6px;position:sticky;top:0;background:transparent;z-index:5}
 h1{font-size:18px;margin:0;color:#7df}
 .counts{font-size:13px;color:#999;margin-right:10px}
 button{font:inherit;cursor:pointer;border:0;border-radius:8px}
 .btn{background:#1c1c22;color:#cde;padding:6px 12px;font-size:13px;margin-left:6px}
 .btn:hover{background:#2a2a33}
 .genrebar{width:100%;max-width:520px;padding:0 16px 10px}
 .gsel{width:100%;background:#16161a;color:#eee;border:1px solid #2a2a33;border-radius:10px;
       padding:9px 12px;font-size:14px;cursor:pointer}
 #stage{width:100%;max-width:520px;padding:0 16px 24px;flex:1}
 .card{background:#16161a;border:1px solid #26262e;border-radius:16px;overflow:hidden;
       box-shadow:0 14px 44px rgba(var(--artrgb),.32);transition:box-shadow .7s ease}
 .art{position:relative}
 .artlink{display:block}
 .artlink img,.noart{width:100%;aspect-ratio:1/1;object-fit:cover;display:block;background:#222}
 .chip{position:absolute;top:10px;left:10px;background:rgba(0,0,0,.62);
       color:#9df;font-size:12px;padding:3px 9px;border-radius:20px;text-decoration:none}
 .navarrow{position:absolute;top:50%;transform:translateY(-50%);width:46px;height:46px;border-radius:50%;
   background:rgba(0,0,0,.55);color:#fff;font-size:30px;line-height:0;display:flex;align-items:center;
   justify-content:center;padding-bottom:4px}
 .navarrow:hover{background:rgba(0,0,0,.82)}
 .navarrow:disabled{opacity:.25;cursor:default}
 .navarrow.left{left:10px}.navarrow.right{right:10px}
 .meta{padding:12px 16px 4px}
 .title{font-size:19px;font-weight:700;color:#fff;line-height:1.25;word-break:break-word}
 .artist{font-size:14px;color:#9aa;margin-top:2px}
 .player{width:100%;height:120px;border:0;display:block;background:#181818}
 audio.player{height:54px;padding:10px 12px}
 .actions{display:flex;gap:18px;justify-content:center;padding:16px}
 .act{width:60px;height:60px;border-radius:50%;font-size:25px;transition:background .12s,box-shadow .12s}
 .no{background:#2a1416;color:#ff6b6b}.no:hover{background:#3a1a1d}
 .yes{background:#102a18;color:#4ade80}.yes:hover{background:#163a22}
 .own{background:#11212e;color:#5cc8ff;font-size:23px}.own:hover{background:#173043}
 .act.liked{background:#4ade80;color:#06210f;box-shadow:0 0 0 4px rgba(74,222,128,.25)}
 .hint{text-align:center;color:#777;font-size:12px;padding-bottom:14px}
 .empty{text-align:center;color:#aaa;padding:64px 16px;line-height:1.7}
 .empty code{color:#7df;background:#1c1c22;padding:1px 6px;border-radius:5px}
 #buylist{display:none;width:100%;max-width:520px;padding:0 16px 48px}
 #buylist.show{display:block}
 .bhead{display:flex;justify-content:space-between;align-items:center;margin:8px 0 4px}
 .buy{display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid #222}
 .buy img{width:50px;height:50px;border-radius:6px;object-fit:cover;background:#222}
 .buy .bt{flex:1;font-size:13px;color:#ccc}.buy .bt b{color:#fff}
 .buy a{color:#7df;font-size:12px;text-decoration:none;border:1px solid #2a4;border-radius:6px;padding:3px 9px;white-space:nowrap}
 .buy .rm{background:none;color:#a55;font-size:18px;padding:0 6px}
 a{color:#7df}
 .modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:20;
        align-items:center;justify-content:center;padding:16px}
 .modal.show{display:flex}
 .sheet{background:#16161a;border:1px solid #2a2a33;border-radius:14px;padding:18px 20px;max-width:400px;width:100%}
 .sheet h2{margin:0 0 14px;color:#7df;font-size:17px}
 .sheet .row{display:flex;align-items:center;gap:10px;font-size:15px;cursor:pointer;margin-top:12px}
 .sheet input[type=checkbox]{width:18px;height:18px;accent-color:#4ade80}
 .sheet .note{color:#888;font-size:12px;margin:6px 0 0}
 .sheet hr{border:0;border-top:1px solid #26262e;margin:16px 0}
 .btn.danger{color:#ff8a8a}
</style></head><body>
<header>
 <h1>🎧 Crate Swipe</h1>
 <div><span class="counts" id="counts"></span>
 <button class="btn" id="toggleBuy">♥ <span id="likeCount">0</span></button>
 <button class="btn" id="openSettings" title="Settings">⚙</button></div>
</header>
<div class="genrebar"><select id="genreSel" class="gsel"></select></div>
<div id="stage"></div>
<section id="buylist"></section>
<div id="settings" class="modal"><div class="sheet">
  <h2>Settings</h2>
  <label class="row"><input type="checkbox" id="setAutoplay"> Auto-play radio (streaming cards only)</label>
  <p class="note">Applies to "Surprise me": ON filters it to streaming cards that auto-play; OFF shows your
   full crate (Bandcamp, tap to play). Genre decks stream either way.</p>
  <label class="row"><input type="checkbox" id="setAdvance"> Auto-advance after I like a track</label>
  <p class="note">OFF (default) = ♥ saves and keeps playing; use › for the next. ON = a like jumps forward.</p>
  <hr>
  <p class="note">Moving to a new address? Likes and learning live in this browser, so back them up here
   and restore the file on the new page.</p>
  <button class="btn" id="setBackup">⬇ Back up my likes</button>
  <button class="btn" id="setRestore">⬆ Restore a backup</button>
  <input type="file" id="restoreFile" accept=".json,application/json" hidden>
  <hr>
  <button class="btn danger" id="setReset">↺ Reset all likes &amp; learning</button>
  <button class="btn" id="closeSettings">Close</button>
</div></div>
<script>
const TRACKS = __TRACKS_JSON__;
const GENRE_DECKS = __GENRES_JSON__;     // { "Dubstep": [tracks], ... }
const LS_LIKES='cd_likes', LS_SEEN='cd_seen', LS_PREFS='cd_prefs', LS_SET='cd_settings';
let likes = JSON.parse(localStorage.getItem(LS_LIKES) || '[]');
let seen  = new Set(JSON.parse(localStorage.getItem(LS_SEEN) || '[]'));
let prefs = JSON.parse(localStorage.getItem(LS_PREFS) || 'null');
let settings = JSON.parse(localStorage.getItem(LS_SET) || '{"autoplay":true,"advanceAfterLike":false}');
let selectedGenre = '';                  // '' = Surprise me
const stage = document.getElementById('stage');
const buyEl = document.getElementById('buylist');
const settingsEl = document.getElementById('settings');

// History-based navigation (back/forward through tracks you've seen).
let history = [], pos = -1, exhausted = false, cur = null;

function esc(s){ return (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function who(t){ return (!t.artist || t.artist.toUpperCase()==='VA') ? 'Various Artists' : t.artist; }
function feats(t){ return [['label', t.label], ['artist', who(t)]]; }
function isLiked(t){ return !!t && likes.some(x => x.id === t.id); }
function inMode(t){ return selectedGenre !== '' || !settings.autoplay || t.source === 'audius'; }
function activeBase(){ return (selectedGenre && GENRE_DECKS[selectedGenre]) ? GENRE_DECKS[selectedGenre] : TRACKS; }

function bump(t, key, delta){
  delta = (delta === undefined) ? 1 : delta;
  feats(t).forEach(([kind, val]) => {
    if(!val) return;
    const o = prefs[kind][val] || {l:0, d:0};
    o[key] = Math.max(0, o[key] + delta);
    prefs[kind][val] = o;
  });
}
function affinity(kind, val){
  const s = prefs[kind][val];
  if(!s) return 0;
  return (s.l - s.d) / (s.l + s.d + 2);
}
function score(t){
  return 1.6 * affinity('label', t.label)
       + 2.2 * affinity('artist', who(t))
       + (t.kind === 'discovery' ? 0.15 : 0)
       + (Math.random() - 0.5) * 0.4;
}
function freshPick(){
  let best = null, bs = -1e9;
  for(const t of activeBase()){
    if(seen.has(t.id) || !inMode(t)) continue;
    const s = score(t);
    if(s > bs){ bs = s; best = t; }
  }
  return best;
}
function remainingCount(){
  let n = 0;
  for(const t of activeBase()){ if(!seen.has(t.id) && inMode(t)) n++; }
  return n;
}
function reason(t){
  if(t.kind === 'soundcloud') return (t.free ? 'free download · ' : 'deep cut · ') + (t.plays || 0) + ' plays';
  if(t.kind === 'genre') return 'trending in ' + t.label;
  const a = prefs.artist[who(t)], l = prefs.label[t.label];
  if(t.kind === 'discovery' && !(a && a.l > 0)) return 'new artist, similar to ones you like';
  if(a && a.l > 0 && a.l >= a.d) return 'more from ' + who(t) + ' (liked ' + a.l + ')';
  if(l && l.l > 0 && l.l > l.d) return 'matches ' + l.l + ' you liked on ' + t.label;
  if((l && l.d > l.l) || (a && a.d > a.l)) return 'wildcard, outside your usual';
  return 'exploring your labels';
}

if(!prefs){ prefs = {label:{}, artist:{}}; likes.forEach(t => bump(t, 'l')); }
function save(){
  localStorage.setItem(LS_LIKES, JSON.stringify(likes));
  localStorage.setItem(LS_SEEN, JSON.stringify([...seen]));
  localStorage.setItem(LS_PREFS, JSON.stringify(prefs));
}
function saveSettings(){ localStorage.setItem(LS_SET, JSON.stringify(settings)); }

function tryAutoplay(){
  if(!settings.autoplay) return;
  const au = stage.querySelector('audio');
  if(au) au.play().catch(() => {});
}

// ---- art color -> page background (each track tints the whole page) ----
const BASE_ARTRGB = '80,90,110';
function setArt(r, g, b){
  document.documentElement.style.setProperty('--artrgb', r + ',' + g + ',' + b);
  document.body.style.backgroundColor = 'rgb(' + ((r*0.3)|0) + ',' + ((g*0.3)|0) + ',' + ((b*0.3)|0) + ')';
}
function resetArt(){
  document.documentElement.style.setProperty('--artrgb', BASE_ARTRGB);
  document.body.style.backgroundColor = '#0d0d0f';
}
function colorSrc(t){
  if(!t.art) return null;
  // bcbits sends no CORS, so canvas-reading it taints -> proxy + shrink to read color.
  if(t.source === 'bandcamp')
    return 'https://images.weserv.nl/?url=' + encodeURIComponent(t.art) + '&w=32&output=jpg';
  return t.art;                       // audius + soundcloud allow CORS directly
}
function applyArtColor(t){
  const src = colorSrc(t);
  if(!src){ resetArt(); return; }
  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.onload = () => {
    try{
      const n = 24, cv = document.createElement('canvas'); cv.width = cv.height = n;
      const ctx = cv.getContext('2d'); ctx.drawImage(img, 0, 0, n, n);
      const d = ctx.getImageData(0, 0, n, n).data;
      let r = 0, g = 0, b = 0, k = 0;
      for(let i = 0; i < d.length; i += 4){ if(d[i+3] < 100) continue; r += d[i]; g += d[i+1]; b += d[i+2]; k++; }
      if(k) setArt(Math.round(r/k), Math.round(g/k), Math.round(b/k));
    }catch(e){ resetArt(); }           // tainted canvas -> neutral
  };
  img.onerror = resetArt;
  img.src = src;
}
function hintText(t){
  return esc(reason(t)) + ' &nbsp;·&nbsp; ♥ save &nbsp;·&nbsp; 💿 own &nbsp;·&nbsp; ✕ pass';
}
function syncLikeUI(){
  document.getElementById('likeCount').textContent = likes.length;
  const yes = document.getElementById('byes');
  if(yes && cur) yes.classList.toggle('liked', isLiked(cur));
  const hint = document.querySelector('.hint');
  if(hint && cur) hint.innerHTML = isLiked(cur) ? 'saved ✓ &nbsp;·&nbsp; › for the next track' : hintText(cur);
}

function goNext(){
  if(pos < history.length - 1){ pos++; exhausted = false; render(); return; }
  const t = freshPick();
  if(!t){ exhausted = true; render(); return; }
  seen.add(t.id); save();
  history.push(t); pos = history.length - 1; exhausted = false;
  render();
}
function goPrev(){ if(pos > 0){ pos--; exhausted = false; render(); } }
function restart(){ history = []; pos = -1; exhausted = false; goNext(); }

function render(){
  const where = selectedGenre ? (' in ' + selectedGenre) : (settings.autoplay ? ' streaming' : ' left');
  document.getElementById('counts').textContent = remainingCount() + where;
  document.getElementById('likeCount').textContent = likes.length;
  cur = (pos >= 0 && pos < history.length) ? history[pos] : null;
  if(exhausted || !cur){
    const msg = selectedGenre
      ? ('That is the ' + esc(selectedGenre) + ' deck for now. 🎧<br>Pick another genre, or "✨ Surprise me" for your crate.')
      : (settings.autoplay
        ? 'No more streaming tracks. 🎧<br>Turn off Auto-play in ⚙ for your full crate, or pick a genre above.'
        : 'End of the crate &mdash; ' + likes.length + ' liked. 🎉<br>Re-run the scripts for more, or tap ♥ for your buy list.');
    stage.innerHTML = '<div class="empty">' + msg + '</div>';
    resetArt();
    return;
  }
  const t = cur;
  const player = t.source === 'audius'
    ? '<audio class="player" controls preload="none" src="' + esc(t.stream) + '"></audio>'
    : t.source === 'soundcloud'
    ? '<iframe class="player" scrolling="no" frameborder="no" src="https://w.soundcloud.com/player/?url='
      + encodeURIComponent(t.url) + '&color=%234dd2ff&auto_play=false&hide_related=true'
      + '&show_comments=false&show_user=true&show_reposts=false&download=false&buying=false&visual=false"></iframe>'
    : '<iframe class="player" src="https://bandcamp.com/EmbeddedPlayer/' + t.type + '=' + t.id
      + '/size=large/bgcol=181818/linkcol=4dd2ff/tracklist=false/artwork=none/transparent=true/" seamless></iframe>';
  const chip = t.kind === 'label' ? ('▸ ' + esc(t.label))
             : t.kind === 'genre' ? ('🎚 ' + esc(t.label))
             : t.kind === 'soundcloud' ? ('🔊 ' + (t.free ? 'free download' : (t.plays + ' plays')))
             : '🔎 discovery';
  stage.innerHTML =
    '<div class="card"><div class="art">'
    + '<a class="artlink" href="' + esc(t.url) + '" target="_blank" rel="noopener">'
    +   (t.art ? '<img src="' + esc(t.art) + '" alt="">' : '<div class="noart"></div>') + '</a>'
    + '<span class="chip">' + chip + '</span>'
    + '<button class="navarrow left" id="bprev" title="Back (←)">‹</button>'
    + '<button class="navarrow right" id="bnext" title="Next (→)">›</button>'
    + '</div>'
    + '<div class="meta"><div class="title">' + esc(t.title) + '</div>'
    +   '<div class="artist">' + esc(who(t)) + '</div></div>'
    + player
    + '<div class="actions">'
    +   '<button class="act no"   id="bno"  title="Not for me (↓)">✕</button>'
    +   '<button class="act own"  id="bown" title="I own this — counts toward your taste, skips the buy-list (O)">💿</button>'
    +   '<button class="act yes"  id="byes" title="Save — keeps playing (↑)">♥</button>'
    + '</div>'
    + '<div class="hint">' + hintText(t) + '</div>'
    + '</div>';
  document.getElementById('bprev').onclick = goPrev;
  document.getElementById('bprev').disabled = (pos <= 0);
  document.getElementById('bnext').onclick = goNext;
  document.getElementById('bno').onclick = dislike;
  document.getElementById('bown').onclick = own;
  document.getElementById('byes').onclick = like;
  document.getElementById('byes').classList.toggle('liked', isLiked(t));
  tryAutoplay();
  applyArtColor(t);
}

function like(){
  if(!cur) return;
  const t = cur;
  if(isLiked(t)){ likes = likes.filter(x => x.id !== t.id); bump(t, 'l', -1); }
  else { likes.push(t); bump(t, 'l', 1); }
  save();
  if(settings.advanceAfterLike) goNext();
  else syncLikeUI();
  if(buyEl.classList.contains('show')) renderBuy();
}

function dislike(){
  if(!cur) return;
  const t = cur;
  if(isLiked(t)){ likes = likes.filter(x => x.id !== t.id); }
  bump(t, 'd');
  save();
  goNext();
  if(buyEl.classList.contains('show')) renderBuy();
}

function own(){                 // 💿 : already own it — trains the ranker like a like, but no buy-list
  if(!cur) return;
  bump(cur, 'l', 1);
  seen.add(cur.id);
  save();
  goNext();
}

function renderBuy(){
  document.getElementById('likeCount').textContent = likes.length;
  if(!likes.length){ buyEl.innerHTML = '<div class="empty">No likes yet — tap ♥ on something.</div>'; return; }
  let h = '<div class="bhead"><b>Buy list — ' + likes.length + '</b>'
        + '<button class="btn" id="exp">⬇ Export</button></div>';
  likes.forEach((t, idx) => {
    h += '<div class="buy">' + (t.art ? '<img src="' + esc(t.art) + '">' : '')
      + '<div class="bt"><b>' + esc(t.title) + '</b><br>' + esc(who(t)) + ' · ' + esc(t.label || 'discovery') + '</div>'
      + '<a href="' + esc(t.buy || t.url) + '" target="_blank" rel="noopener">Buy ▸</a>'
      + '<button class="rm" data-i="' + idx + '" title="remove">×</button></div>';
  });
  buyEl.innerHTML = h;
  document.getElementById('exp').onclick = exportList;
  buyEl.querySelectorAll('.rm').forEach(b => b.onclick = () => {
    likes.splice(+b.dataset.i, 1); save(); renderBuy(); syncLikeUI();
  });
}

function exportList(){
  const rows = likes.map(t =>
    '<li><a href="' + esc(t.buy || t.url) + '">' + esc(who(t)) + ' — ' + esc(t.title) + '</a> <small>(' + esc(t.label || t.source) + ')</small></li>'
  ).join('');
  const doc = '<!doctype html><meta charset=utf-8><title>Crate buy list</title>'
    + '<body style="font:15px system-ui;background:#111;color:#eee;max-width:700px;margin:24px auto">'
    + '<h1>🎧 Buy list (' + likes.length + ')</h1><ol>' + rows + '</ol>';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([doc], {type:'text/html'}));
  a.download = 'crate-buy-list.html'; a.click();
}

// ---- genre dropdown ----
const gsel = document.getElementById('genreSel');
gsel.innerHTML = '<option value="">✨ Surprise me</option>'
  + Object.keys(GENRE_DECKS).map(g => '<option value="' + esc(g) + '">' + esc(g) + '</option>').join('');
gsel.onchange = () => { selectedGenre = gsel.value; restart(); };

// ---- settings ----
const cbAutoplay = document.getElementById('setAutoplay');
const cbAdvance = document.getElementById('setAdvance');
cbAutoplay.checked = !!settings.autoplay;
cbAdvance.checked = !!settings.advanceAfterLike;
cbAutoplay.onchange = () => { settings.autoplay = cbAutoplay.checked; saveSettings(); restart(); };
cbAdvance.onchange = () => { settings.advanceAfterLike = cbAdvance.checked; saveSettings(); syncLikeUI(); };
document.getElementById('openSettings').onclick  = () => settingsEl.classList.add('show');
document.getElementById('closeSettings').onclick = () => settingsEl.classList.remove('show');
settingsEl.onclick = e => { if(e.target === settingsEl) settingsEl.classList.remove('show'); };
document.getElementById('setReset').onclick = () => {
  if(confirm('Clear all likes, dislikes, and learning?')){
    [LS_LIKES, LS_SEEN, LS_PREFS].forEach(k => localStorage.removeItem(k));
    location.reload();
  }
};

document.getElementById('setBackup').onclick = () => {
  const dump = {cratedigger: 1, savedAt: new Date().toISOString(), likes, seen: [...seen], prefs, settings};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(dump)], {type: 'application/json'}));
  a.download = 'cratedigger-backup.json'; a.click();
};
const restoreFile = document.getElementById('restoreFile');
document.getElementById('setRestore').onclick = () => restoreFile.click();
restoreFile.onchange = async () => {
  const f = restoreFile.files[0]; if(!f) return;
  let d;
  try { d = JSON.parse(await f.text()); } catch(e) { d = null; }
  if(!d || d.cratedigger !== 1 || !Array.isArray(d.likes)){ alert('That file is not a CrateDigger backup.'); return; }
  // merge, never wipe: keep anything already liked here, add the backup's
  const ids = new Set(likes.map(t => t.id));
  d.likes.forEach(t => { if(t && !ids.has(t.id)){ likes.push(t); ids.add(t.id); } });
  (d.seen || []).forEach(id => seen.add(id));
  ['label', 'artist'].forEach(kind => {
    Object.entries((d.prefs && d.prefs[kind]) || {}).forEach(([k, v]) => {
      const o = prefs[kind][k] || {l:0, d:0};
      prefs[kind][k] = {l: Math.max(o.l, v.l || 0), d: Math.max(o.d, v.d || 0)};
    });
  });
  if(d.settings) settings = {...settings, ...d.settings};
  save(); saveSettings();
  alert('Restored ' + d.likes.length + ' likes from your backup.');
  location.reload();
};

document.getElementById('toggleBuy').onclick = () => {
  buyEl.classList.toggle('show'); renderBuy();
  if(buyEl.classList.contains('show')) buyEl.scrollIntoView({behavior:'smooth'});
};
document.addEventListener('keydown', e => {
  if(settingsEl.classList.contains('show') || document.activeElement === gsel) return;
  if(e.key === 'ArrowLeft') goPrev();
  else if(e.key === 'ArrowRight') goNext();
  else if(e.key === 'ArrowUp'){ e.preventDefault(); like(); }
  else if(e.key === 'ArrowDown'){ e.preventDefault(); dislike(); }
  else if(e.key === 'o' || e.key === 'O'){ own(); }
});
document.addEventListener('pointerdown', () => tryAutoplay(), {once:true});

restart();
</script></body></html>'''


def main():
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)
    tracks = load_tracks(profile)
    genre_decks = {**profile.get("genre_decks", {}), **profile.get("soundcloud", {})}
    n_disc = sum(1 for t in tracks if t["kind"] == "discovery")
    data = json.dumps(tracks, ensure_ascii=False).replace("</", "<\\/")
    gdata = json.dumps(genre_decks, ensure_ascii=False).replace("</", "<\\/")
    page = PAGE.replace("__TRACKS_JSON__", data).replace("__GENRES_JSON__", gdata)
    for path in (OUT, INDEX):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(page)
    print(f"Wrote swipe.html + index.html: {len(tracks)} deck tracks ({n_disc} discoveries) + "
          f"{sum(len(v) for v in genre_decks.values())} genre tracks across {len(genre_decks)} genres")
    if not os.environ.get("CI"):          # no browser on the CI runner
        webbrowser.open(OUT)


if __name__ == "__main__":
    main()
