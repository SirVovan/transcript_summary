#!/usr/bin/env python3
"""
widget_generator.py — генератор HTML-виджета конспекта.

Читает JSON-файл с контентом, выдаёт готовый HTML-виджет.
JS-экранирование полностью выполняет Python (json.dumps) —
кириллические lookalike-символы в \\u-эскейпах исключены.

Использование:
    python widget_generator.py <content.json>

Формат input JSON — см. widget.md раздел «Формат JSON».
"""

import sys
import os
import json
import subprocess

# ──────────────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────────────

CSS = """\
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --ff: 'Manrope', system-ui, sans-serif;
  --fm: 'JetBrains Mono', 'Courier New', monospace;
  --bg-page:  #EDEADE;
  --bg-noise: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
  --surface:  #FFFFFF;
  --surface2: #F8F6F1;
  --border:   rgba(60,52,36,.1);
  --border2:  rgba(60,52,36,.18);
  --tx1: #1C1915;
  --tx2: #4A4438;
  --tx3: #8C8278;
  --tx4: #B8B0A6;
  --sh1: 0 2px 8px rgba(28,25,21,.06), 0 1px 2px rgba(28,25,21,.04);
  --sh2: 0 6px 20px rgba(28,25,21,.09), 0 2px 6px rgba(28,25,21,.05);
  --sh3: 0 16px 48px rgba(28,25,21,.12), 0 4px 12px rgba(28,25,21,.06);
  --c-concept:#2562B0; --c-concept-bg:#ECF2FB; --c-concept-mid:#B8D0EF; --c-concept-pale:#F4F8FE;
  --c-method: #2E6E2E; --c-method-bg: #EBF5EB; --c-method-mid: #B0D4B0; --c-method-pale: #F3FAF3;
  --c-demo:   #96580F; --c-demo-bg:   #FAF0E4; --c-demo-mid:   #DEB882; --c-demo-pale:   #FDF8F0;
  --c-final:  #4C3FA0; --c-final-bg:  #EDEAFA; --c-final-mid:  #BEB6E6; --c-final-pale:  #F5F4FC;
  --tab-bg: var(--c-concept-bg);
  --tab-c:  var(--c-concept);
  --tab-mid:var(--c-concept-mid);
}

@keyframes slideIn   { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
@keyframes stripePulse{ 0%,100%{opacity:1} 50%{opacity:.7} }
@keyframes tooltipIn { from{opacity:0;transform:translateX(-4px)} to{opacity:1;transform:translateX(0)} }

body { font-family:var(--ff); background-color:var(--bg-page); background-image:var(--bg-noise); color:var(--tx1); font-size:13.5px; line-height:1.6; overflow:hidden; height:100vh; display:flex; align-items:center; justify-content:center; padding:16px; }

.shell { display:flex; flex-direction:column; width:100%; max-width:1380px; height:92vh; min-height:520px; max-height:840px; background:var(--surface); border-radius:18px; box-shadow:var(--sh3),0 0 0 1px var(--border); overflow:hidden; animation:slideIn .3s ease both; }

.topbar { display:flex; align-items:center; justify-content:space-between; padding:10px 20px 9px; background:var(--surface); border-bottom:1px solid var(--border); flex-shrink:0; gap:16px; }
.topbar-left { display:flex; align-items:center; gap:10px; min-width:0; }
.course-badge { font-size:10px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--tx3); background:var(--surface2); border:1px solid var(--border2); border-radius:6px; padding:3px 9px; white-space:nowrap; flex-shrink:0; }
.course-title { font-size:13.5px; font-weight:700; color:var(--tx1); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

.tabs { display:flex; gap:3px; flex-shrink:0; position:relative; z-index:100; }
.tab-wrap { position:relative; }
.tab { width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; font-family:var(--ff); color:var(--tx4); background:transparent; border:1.5px solid transparent; border-radius:9px; cursor:pointer; transition:color .15s,background .15s,border-color .15s,transform .1s; position:relative; z-index:1; }
.tab:hover { background:var(--surface2); color:var(--tx2); transform:scale(1.08); }
.tab.on { background:var(--tab-bg); color:var(--tab-c); border-color:var(--tab-mid); }

.stripe { height:3px; flex-shrink:0; transition:background .35s ease; animation:stripePulse 4s ease infinite; }

.body { flex:1; display:grid; grid-template-columns:1fr 1fr; overflow:hidden; min-height:0; }

.lcol { padding:20px 24px 14px; border-right:1px solid var(--border); display:flex; flex-direction:column; overflow:hidden; min-height:0; background:var(--surface); }
.seg-pill { display:inline-flex; align-items:center; gap:5px; font-size:10px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; border-radius:20px; padding:3px 10px 3px 8px; margin-bottom:9px; flex-shrink:0; width:fit-content; box-shadow:var(--sh1); }
.seg-dot { width:5px; height:5px; border-radius:50%; flex-shrink:0; }
.seg-title { font-size:16px; font-weight:800; color:var(--tx1); line-height:1.28; margin-bottom:4px; flex-shrink:0; letter-spacing:-.01em; }
.seg-timing { font-size:11px; font-weight:500; color:var(--tx4); margin-bottom:13px; font-family:var(--fm); flex-shrink:0; }
.seg-body { flex:1; overflow-y:auto; overflow-x:hidden; min-height:0; padding-right:8px; color:var(--tx2); font-size:13.5px; line-height:1.7; animation:slideIn .25s ease both; }
.seg-body::-webkit-scrollbar{width:3px} .seg-body::-webkit-scrollbar-track{background:transparent} .seg-body::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
.seg-body p{margin-bottom:8px} .seg-body p:last-child{margin-bottom:0} .seg-body strong{color:var(--tx1);font-weight:700} .seg-body h3{font-size:13px;font-weight:700;color:var(--tx1);margin:11px 0 5px;letter-spacing:-.01em} .seg-body ul{margin:4px 0 9px 18px} .seg-body li{margin-bottom:4px} .seg-body li::marker{color:var(--tx4)} .seg-body li strong{color:var(--tx1);font-weight:700}

.rcol { display:flex; flex-direction:column; overflow:hidden; min-height:0; transition:background .35s ease; position:relative; }
.rcol::before { content:''; position:absolute; inset:0; background:var(--bg-noise); opacity:.6; pointer-events:none; }
.rcol-inner { padding:18px 20px 14px; display:flex; flex-direction:column; gap:10px; height:100%; overflow-y:auto; min-height:0; position:relative; z-index:1; animation:slideIn .3s ease both; }
.rcol-inner::-webkit-scrollbar{width:3px} .rcol-inner::-webkit-scrollbar-track{background:transparent} .rcol-inner::-webkit-scrollbar-thumb{background:rgba(60,52,36,.15);border-radius:3px}

.stats3 { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; flex-shrink:0; }
.stat-card { background:rgba(255,255,255,.85); border:1px solid var(--border); border-radius:13px; padding:12px 13px; box-shadow:var(--sh1); backdrop-filter:blur(4px); transition:box-shadow .2s,transform .15s; }
.stat-card:hover{box-shadow:var(--sh2);transform:translateY(-1px)}
.stat-n { font-size:24px; font-weight:800; line-height:1; margin-bottom:4px; letter-spacing:-.02em; }
.stat-l { font-size:11px; color:var(--tx3); line-height:1.35; font-weight:500; }

.cmp2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; flex-shrink:0; }
.cmp-card { border-radius:13px; padding:12px 14px; box-shadow:var(--sh1); border:1px solid transparent; transition:box-shadow .2s,transform .15s; }
.cmp-card:hover{box-shadow:var(--sh2);transform:translateY(-1px)}
.cmp-h { font-size:12px; font-weight:700; margin-bottom:5px; }
.cmp-b { font-size:12px; line-height:1.55; font-weight:500; }
.cmp-m { font-size:11px; margin-top:6px; font-weight:600; font-style:italic; opacity:.8; }

.cycle { display:flex; align-items:stretch; flex-shrink:0; background:rgba(255,255,255,.85); border:1px solid var(--border); border-radius:13px; overflow:hidden; box-shadow:var(--sh1); }
.cs { flex:1; text-align:center; padding:9px 4px; font-size:11px; color:var(--tx3); line-height:1.35; font-weight:600; border-right:1px solid var(--border); }
.cs:last-child{border-right:none}
.cs-n { font-size:17px; font-weight:800; margin-bottom:2px; color:#2562B0; letter-spacing:-.02em; }

.insights { display:flex; flex-direction:column; gap:7px; }
.insight { background:rgba(255,255,255,.8); border:1px solid var(--border); border-radius:0 11px 11px 0; border-left:3px solid; padding:8px 12px 8px 13px; font-size:12px; color:var(--tx2); line-height:1.55; box-shadow:var(--sh1); font-weight:500; transition:box-shadow .15s; }
.insight:hover{box-shadow:var(--sh2)}
.insight strong{color:var(--tx1);font-weight:700}

.pr-block { background:rgba(250,248,243,.9); border:1px solid var(--border2); border-radius:13px; overflow:hidden; flex-shrink:0; box-shadow:var(--sh1); }
.pr-head { display:flex; align-items:center; justify-content:space-between; padding:7px 12px; border-bottom:1px solid var(--border); background:rgba(237,233,222,.5); }
.pr-label { font-size:10px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--tx4); }
.pr-copy { font-size:10.5px; font-weight:600; color:var(--tx3); background:rgba(255,255,255,.8); border:1px solid var(--border2); border-radius:5px; padding:2px 8px; cursor:pointer; font-family:var(--ff); transition:background .15s,color .15s; }
.pr-copy:hover{background:#fff;color:var(--tx1)}
.pr-text { font-family:var(--fm); font-size:11.5px; color:var(--tx1); line-height:1.65; white-space:pre-wrap; padding:10px 13px; }

.quote-block { border-radius:13px; padding:14px 16px; flex-shrink:0; box-shadow:var(--sh1); border-left:4px solid; }
.quote-text { font-size:13.5px; font-weight:600; line-height:1.55; font-style:italic; color:var(--tx1); letter-spacing:-.01em; }
.quote-auth { font-size:11px; color:var(--tx3); margin-top:6px; font-weight:600; }

.final-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; flex-shrink:0; }
.final-card { border-radius:13px; padding:12px 13px; border:1px solid var(--border); box-shadow:var(--sh1); transition:box-shadow .2s,transform .15s; }
.final-card:hover{box-shadow:var(--sh2);transform:translateY(-1px)}
.final-n { font-size:22px; font-weight:800; margin-bottom:3px; letter-spacing:-.02em; }
.final-t { font-size:12px; font-weight:700; color:var(--tx1); margin-bottom:4px; }
.final-d { font-size:11.5px; color:var(--tx2); line-height:1.45; font-weight:500; }

.fn-tag { font-family:var(--fm); font-size:11.5px; background:rgba(60,52,36,.06); border:1px solid var(--border2); border-radius:5px; padding:1px 6px; color:var(--tx1); font-weight:500; }
.kw-tag { font-weight:700; border-radius:4px; padding:0 5px; border:1px solid transparent; }

.svg-wrap { flex-shrink:0; border-radius:12px; overflow:hidden; box-shadow:var(--sh2); border:1px solid var(--border); }

.footer { display:flex; align-items:center; justify-content:space-between; padding:8px 20px; border-top:1px solid var(--border); background:var(--surface); flex-shrink:0; }
.f-info { font-size:11px; color:var(--tx4); font-family:var(--fm); font-weight:500; }
.pw { flex:1; max-width:140px; margin:0 16px; }
.pt { height:3px; background:var(--border); border-radius:3px; overflow:hidden; }
.pf { height:100%; border-radius:3px; transition:width .35s cubic-bezier(.4,0,.2,1),background .35s; }
.nav { display:flex; gap:6px; }
.btn { padding:6px 16px; font-size:12px; font-weight:700; font-family:var(--ff); border-radius:9px; border:1.5px solid var(--border2); background:var(--surface2); color:var(--tx2); cursor:pointer; transition:all .15s; box-shadow:var(--sh1); letter-spacing:-.01em; }
.btn:hover{background:#fff;box-shadow:var(--sh2);transform:translateY(-1px)}
.btn:active{transform:scale(.97);box-shadow:var(--sh1)}
.btn:disabled{opacity:.3;pointer-events:none;box-shadow:none}
.btn.primary { background:var(--tab-bg); color:var(--tab-c); border-color:var(--tab-mid); }
.btn.primary:hover{filter:brightness(.97)}

.toc-panel { position:absolute; top:calc(100% + 6px); right:0; width:320px; max-height:340px; background:var(--tx1); border-radius:13px; box-shadow:0 8px 32px rgba(28,25,21,.22),0 2px 8px rgba(28,25,21,.12); overflow:hidden; display:flex; flex-direction:column; z-index:200; opacity:0; pointer-events:none; transform:translateY(-4px); transition:opacity .18s ease,transform .18s ease; }
.toc-panel.visible{opacity:1;pointer-events:auto;transform:translateY(0)}
.toc-scroll { overflow-y:auto; padding:8px 6px; flex:1; }
.toc-scroll::-webkit-scrollbar{width:3px} .toc-scroll::-webkit-scrollbar-thumb{background:rgba(255,255,255,.2);border-radius:3px}
.toc-item { display:flex; align-items:flex-start; gap:10px; padding:7px 10px; border-radius:8px; cursor:pointer; transition:background .12s; }
.toc-item:hover{background:rgba(255,255,255,.08)}
.toc-item.active{background:rgba(255,255,255,.12)}
.toc-num { font-size:11px; font-weight:700; font-family:var(--fm); flex-shrink:0; width:20px; padding-top:1px; transition:color .12s; }
.toc-text { font-size:12px; font-weight:500; font-family:var(--ff); line-height:1.45; transition:color .12s; }
.toc-item.active .toc-num, .toc-item.active .toc-text{color:#ffffff}
.toc-item:not(.active) .toc-num{color:rgba(255,255,255,.35)}
.toc-item:not(.active) .toc-text{color:rgba(255,255,255,.45)}
.toc-item:not(.active):hover .toc-num{color:rgba(255,255,255,.65)}
.toc-item:not(.active):hover .toc-text{color:rgba(255,255,255,.75)}"""

# ──────────────────────────────────────────────────────────────────────
# JS ENGINE (неизменная часть — движок виджета)
# ──────────────────────────────────────────────────────────────────────

JS_T = """\
var T={
  concept:{lbl:'Концепция',   c:'#2562B0',bg:'#ECF2FB',mid:'#B8D0EF',pale:'#F4F8FE',stripe:'#2562B0'},
  method: {lbl:'Методология', c:'#2E6E2E',bg:'#EBF5EB',mid:'#B0D4B0',pale:'#F3FAF3',stripe:'#2E6E2E'},
  demo:   {lbl:'Демонстрация',c:'#96580F',bg:'#FAF0E4',mid:'#DEB882',pale:'#FDF8F0',stripe:'#96580F'},
  final:  {lbl:'Итоги',       c:'#4C3FA0',bg:'#EDEAFA',mid:'#BEB6E6',pale:'#F5F4FC',stripe:'#4C3FA0'}
};"""

JS_ENGINE = """\
function cp(id){
  var btn=document.getElementById('cpb'+id);
  if(!btn)return;
  var textEl=btn.closest('.pr-block').querySelector('.pr-text');
  var text=textEl?textEl.textContent:'';
  navigator.clipboard.writeText(text).then(function(){
    btn.textContent='скопировано';
    setTimeout(function(){btn.textContent='копировать';},1800);
  }).catch(function(){});
}

var cur=0;

function setTypeVars(t){
  document.documentElement.style.setProperty('--tab-bg',t.bg);
  document.documentElement.style.setProperty('--tab-c',t.c);
  document.documentElement.style.setProperty('--tab-mid',t.mid);
}

function render(){
  var s=SEG[cur];
  var t=T[s.type];
  var total=SEG.length<10?'0'+SEG.length:''+SEG.length;
  var pct=Math.round((cur+1)/SEG.length*100)+'%';
  document.getElementById('stripe').style.background=t.stripe;
  document.getElementById('pf').style.width=pct;
  document.getElementById('pf').style.background=t.stripe;
  setTypeVars(t);
  document.querySelectorAll('.tab').forEach(function(el,i){el.classList.toggle('on',i===cur);});
  document.getElementById('pb').disabled=cur===0;
  document.getElementById('nb').textContent=cur===SEG.length-1?'В начало \u2192':'Далее \u2192';
  document.getElementById('finfo').textContent='Сегмент '+s.id+' из '+total+' \u00b7 '+s.timing;
  document.getElementById('body').innerHTML=
    '<div class="lcol">'
      +'<span class="seg-pill" style="color:'+t.c+';background:'+t.bg+';border:1px solid '+t.mid+';box-shadow:0 1px 4px '+t.mid+'60">'
        +'<span class="seg-dot" style="background:'+t.c+'"></span>'
        +t.lbl
      +'</span>'
      +'<div class="seg-title">'+s.title+'</div>'
      +'<div class="seg-timing">'+s.timing+'</div>'
      +'<div class="seg-body">'+BODY[s.id]+'</div>'
    +'</div>'
    +'<div class="rcol" style="background:'+t.pale+'">'
      +'<div class="rcol-inner">'+RIGHT[s.id]+'</div>'
    +'</div>';
}

function go(d){
  if(d===1&&cur===SEG.length-1)cur=0;
  else if(d===-1&&cur===0)return;
  else cur+=d;
  render();
}

var tocPanel=document.createElement('div');
tocPanel.className='toc-panel';
var tocScroll=document.createElement('div');
tocScroll.className='toc-scroll';
tocPanel.appendChild(tocScroll);
var te=document.getElementById('tabs');
te.style.position='relative';
te.appendChild(tocPanel);

function buildToc(hoverIdx){
  var hi=(hoverIdx!==undefined)?hoverIdx:cur;
  tocScroll.innerHTML='';
  SEG.forEach(function(s,i){
    var item=document.createElement('div');
    item.className='toc-item'+(i===hi?' active':'');
    item.innerHTML='<span class="toc-num">'+s.id+'</span><span class="toc-text">'+s.title+'</span>';
    item.addEventListener('mousedown',function(e){e.preventDefault();cur=i;render();hideToc();});
    tocScroll.appendChild(item);
  });
}

var tocVisible=false;
var hideTimer=null;

function showToc(hoverIdx){clearTimeout(hideTimer);buildToc(hoverIdx);tocPanel.classList.add('visible');tocVisible=true;var ae=tocScroll.querySelector('.active');if(ae)ae.scrollIntoView({block:'nearest'});}
function hideToc(){clearTimeout(hideTimer);hideTimer=setTimeout(function(){tocPanel.classList.remove('visible');tocVisible=false;},120);}

SEG.forEach(function(s,i){
  var wrap=document.createElement('div');
  wrap.className='tab-wrap';
  var btn=document.createElement('button');
  btn.className='tab'+(i===0?' on':'');
  btn.textContent=s.id;
  btn.onclick=function(){cur=i;render();hideToc();};
  btn.addEventListener('mouseenter',(function(idx){return function(){showToc(idx);};})(i));
  wrap.appendChild(btn);
  te.insertBefore(wrap,tocPanel);
});

tocPanel.addEventListener('mouseenter',function(){clearTimeout(hideTimer);});
tocPanel.addEventListener('mouseleave',hideToc);
te.addEventListener('mouseleave',function(e){if(!tocPanel.contains(e.relatedTarget))hideToc();});

render();"""

# ──────────────────────────────────────────────────────────────────────
# HTML-сборка
# ──────────────────────────────────────────────────────────────────────

def js_obj(d):
    """Строит JS-объект из dict. Все строки экранирует через json.dumps."""
    if not d:
        return '{}'
    lines = [
        '  ' + json.dumps(k, ensure_ascii=False) + ': ' + json.dumps(v, ensure_ascii=False)
        for k, v in d.items()
    ]
    return '{\n' + ',\n'.join(lines) + '\n}'


def js_arr(segments):
    """Строит JS-массив метаданных сегментов."""
    items = []
    for s in segments:
        items.append('  ' + json.dumps(
            {'id': s['id'], 'type': s['type'], 'title': s['title'], 'timing': s['timing']},
            ensure_ascii=False
        ))
    return '[\n' + ',\n'.join(items) + '\n]'


def build_reconstruction_html(recon):
    if not recon:
        return ''
    prose = recon.get('prose', '')
    table_rows = recon.get('table', [])
    parts = [f'<p>{prose}</p>']
    if table_rows:
        cell = 'style="color:#4A4438;padding:3px 14px 3px 0;vertical-align:top;font-size:12px"'
        th   = 'style="font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#8C8278;text-align:left;padding:2px 14px 4px 0;border-bottom:1px solid rgba(60,52,36,.15)"'
        parts += [
            '<table style="width:100%;border-collapse:collapse;margin-top:10px">',
            f'<thead><tr><th {th}>#</th><th {th}>Риторическая роль</th><th {th}>Ключевой ход автора</th></tr></thead>',
            '<tbody>',
        ]
        for row in table_rows:
            parts.append(
                f'<tr>'
                f'<td {cell}>{row.get("segment","")}</td>'
                f'<td {cell}>{row.get("role","")}</td>'
                f'<td {cell}>{row.get("move","")}</td>'
                f'</tr>'
            )
        parts += ['</tbody></table>']
    return '\n'.join(parts)


def build_html(data):
    meta     = data['meta']
    prompts  = data.get('prompts', {})
    segments = data['segments']

    badge = meta['badge']
    title = meta['title']

    body_dict  = {s['id']: s['body']  for s in segments}
    right_dict = {s['id']: s['right'] for s in segments}

    recon = data.get('reconstruction')
    if recon:
        body_dict  = {'00': build_reconstruction_html(recon), **body_dict}
        right_dict = {'00': '<div class="insights"></div>', **right_dict}
        segments   = [{'id': '00', 'type': 'concept', 'title': 'Логическая реконструкция', 'timing': ''}] + list(segments)

    pr_js    = 'var PR = ' + js_obj(prompts) + ';'
    body_js  = 'var BODY = ' + js_obj(body_dict) + ';'
    right_js = 'var RIGHT = ' + js_obj(right_dict) + ';'
    seg_js   = 'var SEG = ' + js_arr(segments) + ';'

    return '\n'.join([
        '<!DOCTYPE html>',
        '<html lang="ru">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">',
        f'<title>{title}</title>',
        '<style>',
        CSS,
        '</style>',
        '</head>',
        '<body>',
        '',
        '<div class="shell">',
        '  <div class="topbar">',
        '    <div class="topbar-left">',
        f'      <span class="course-badge">{badge}</span>',
        f'      <span class="course-title">{title}</span>',
        '    </div>',
        '    <div class="tabs" id="tabs"></div>',
        '  </div>',
        '  <div class="stripe" id="stripe"></div>',
        '  <div class="body" id="body"></div>',
        '  <div class="footer">',
        '    <span class="f-info" id="finfo"></span>',
        '    <div class="pw"><div class="pt"><div class="pf" id="pf" style="width:6%"></div></div></div>',
        '    <div class="nav">',
        '      <button class="btn" id="pb" onclick="go(-1)" disabled>\u2190 \u041d\u0430\u0437\u0430\u0434</button>',
        '      <button class="btn primary" id="nb" onclick="go(1)">\u0414\u0430\u043b\u0435\u0435 \u2192</button>',
        '    </div>',
        '  </div>',
        '</div>',
        '',
        '<script>',
        JS_T,
        '',
        pr_js,
        '',
        body_js,
        '',
        right_js,
        '',
        seg_js,
        '',
        JS_ENGINE,
        '</script>',
        '</body>',
        '</html>',
    ])


# ──────────────────────────────────────────────────────────────────────
# Валидация JS
# ──────────────────────────────────────────────────────────────────────

def validate_js(html_path):
    import re
    with open(html_path, encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    if not m:
        return True, ''
    js = m.group(1)
    tmp = html_path + '.__check__.js'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(js)
        r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
        ok = r.returncode == 0
        err = r.stderr.replace(tmp, html_path) if not ok else ''
        return ok, err
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f'Файл не найден: {json_path}', file=sys.stderr)
        sys.exit(1)

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    html = build_html(data)

    # Путь к выходному файлу
    out_name = data['meta'].get('out', 'widget_output.html')
    out_dir  = os.path.dirname(os.path.abspath(json_path))
    out_path = os.path.join(out_dir, out_name)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'Виджет создан: {out_path}')

    # Валидация JS
    ok, err = validate_js(out_path)
    if ok:
        print('✅ JS syntax OK')
    else:
        print(f'❌ JS syntax ERROR:\n{err}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
