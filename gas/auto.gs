// ============================================================
// auto.gs — 自律調査エンジン（単一ファイルで全自動・体系管理）
// ============================================================
// 3本柱を毎日 自律調査→分析→昇格起案→自己改善→週次レポート（無料・Claudeトークン0）。
//   ① 成功法則 : あらゆる成功の機序（シャローム5次元・偏らせない・大衆/関係も）
//   ② 経済     : 経済の成功と歴史（福音→改革→経済の論旨鎖）
//   ③ 技術     : 技術の成功と歴史 ＋ 新AIツールのレーダー（パイプライン用）
//
// 【セットアップ】setupAutoTrigger() を一度だけ手動実行（毎朝8時 runAll）。
// 旧 collector.gs / research.gs は本ファイルに統合・退役。
// 設計根拠: docs/research_system.md
// ============================================================

// ===== 設定（ここだけ見れば全体像が分かる）=====
const SPREADSHEET_ID = '1MBOHX1yRwUC3AaMKVtdUxfmirYpcFVM0jf_Tgvve5MA';
const GROQ_MODEL = 'llama-3.3-70b-versatile';   // 研究品質重視（RPD=1000で十分）

const SHEETS = {
  gap: '論旨ギャップ', draft: '昇格ドラフト', improve: '研究改善ログ',
  radar: '技術レーダー', report: 'レポート', market: '市況'
};

// 市況ウォッチリスト（インフラ最前線＝論旨鎖の現在地を映す銘柄）
// AI基盤/半導体・プラットフォーム・メディア。時系列で「今の勝者」を観測。
const WATCHLIST = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'AMD', 'TSM', 'AVGO', 'TSLA'];

// 3本柱（weight＝1日あたりの生成比率）
const PILLARS = [
  { key: 'success', label: '成功法則', weight: 2,
    focus: 'あらゆる成功(富/関係/健康/心の平和/霊性=シャローム5次元)の機序。' +
           'アニメ・音楽・人物・大衆現象も含め偏らせない(trend/everyday/relational/random)' },
  { key: 'economy', label: '経済', weight: 1,
    focus: '経済の成功と歴史(資本主義/市場/貨幣/産業/起業/金融)。福音→改革→経済の論旨鎖' },
  { key: 'tech', label: '技術', weight: 1,
    focus: '技術の成功と歴史(発明/AI/メディア)。福音インフラ→技術→ペイロードの論旨鎖' }
];

const THESIS =
  '作品「勝利の福音」: 福音→心の解放(Christus Victor)→宗教改革→科学/医療/経済→産業革命' +
  '→メディア革命→IT/AI。芸術は福音インフラ上のペイロード。' +
  '成功は富だけでない＝シャローム5次元(外の豊かさ/関係/健康/心の平和/神との和解)。' +
  '全ては繋がる—神が人間・脳・被造世界を作ったから。連関は捏造でなく発見する。';

// 列インデックス（論旨ギャップ・0始まり A..P）
const COL = {
  id: 0, domain: 1, phenom: 2, stype: 3, persp: 4, qMech: 5, qMacro: 6, qMicro: 7,
  hypo: 8, counter: 9, prio: 10, status: 11, insight: 12, target: 13, source: 14, updated: 15
};

// 成功次元 → 被造設計(ミクロ軸)を裏づける arxiv 認知科学クエリ
const COGNITIVE_QUERY = {
  '外的': 'status motivation reward brain dopamine',
  '関係的': 'social bonding attraction oxytocin attachment',
  '身体的': 'facial attractiveness perception evolution',
  '内面的': 'music emotion narrative engagement brain',
  '霊的': 'meaning purpose transcendence psychology religion'
};

// ============================================================
// 毎日のエントリ（全自動オーケストレーション）
// ============================================================
function runAll() {
  generateGaps_(4);          // ①②③ 3本柱の二軸ギャップ生成（自己点検反映）
  Utilities.sleep(2000);
  researchOpenGaps_(3);      // 多源調査(日英Wikipedia+arxiv脳科学)→洞察
  Utilities.sleep(2000);
  draftPromotions_(2);       // resolved→content_design草案+品質ゲート
  Utilities.sleep(1500);
  marketSnapshot_();         // ②経済: 市況スナップショット（今の勝者を時系列で観測）
  var dow = Number(Utilities.formatDate(new Date(), 'Asia/Tokyo', 'u')); // 1=月..7=日
  if (dow === 4) { Utilities.sleep(2000); techRadar_(6); }   // 木: ③技術レーダー
  if (dow === 1) {                                            // 月: 自己深化+週次レポート
    Utilities.sleep(2000); selfDeepen_();
    Utilities.sleep(2000); weeklyDigest_();
  }
}

// ============================================================
// ① 生成 — 3本柱・二軸・偏りなき・自己点検反映
// ============================================================
function generateGaps_(n) {
  var sheet = _sheet_(SHEETS.gap, GAP_HEADERS_());

  // 自己改善ループ: 直近の点検を生成へ反映
  var steer = '';
  var imp = _sheet_(SHEETS.improve, IMPROVE_HEADERS_());
  if (imp.getLastRow() > 1) {
    var r = imp.getRange(imp.getLastRow(), 1, 1, 4).getValues()[0];
    steer = '\n【前回の自己点検を必ず反映】偏り:' + r[1] + ' / 次に厚く:' + r[2] + ' / 新しい問いの型:' + r[3];
  }

  // 本柱ごとの生成数（weight比）
  var counts = _pillarCounts_(n);
  var pillarSpec = PILLARS.map(function (p) {
    return '【' + p.label + '】' + counts[p.key] + '個: ' + p.focus;
  }).join('\n');

  var prompt =
    'あなたは知的ドキュメンタリーの首席リサーチャー兼 認知/脳科学の素養を持つ分析者。\n' +
    THESIS + steer + '\n\n' +
    '3本柱それぞれ指定数の「知識ギャップを埋める問い」を作れ:\n' + pillarSpec + '\n\n' +
    '各事象を二軸で問う:\n' +
    '- マクロ相関: 歴史・インフラ・摂理(福音→改革→産業→メディア→ペイロード)との繋がり\n' +
    '- ミクロ相関(被造設計): なぜ人間の脳・心はそれに惹かれるよう作られているか\n' +
    '※domainは「柱ラベル/具体領域」形式(例「成功法則/アニメ」「経済/資本主義」「技術/AI」)。\n' +
    '※phenomenonは固有名詞で具体的に(総称でなく)。counterは論旨を本当に揺さぶる非自明な反証。\n\n' +
    '必ずJSONのみ: {"gaps":[{"domain":"","phenomenon":"","success_type":"外的|関係的|身体的|内面的|霊的",' +
    '"perspective":"trend|everyday|relational|random|elite","q_mechanism":"","q_macro":"","q_micro":"",' +
    '"hypothesis":"","counter":"","integration_target":"","priority":"high|medium|low"}]}';

  var res = callGroq_(prompt);
  if (!res) { Logger.log('generateGaps: 応答なし'); return; }
  var gaps;
  try { gaps = JSON.parse(_clean_(res)).gaps || []; }
  catch (e) { Logger.log('generateGaps JSONエラー: ' + e.message); return; }

  var today = _today_();
  var nextId = _maxGapNum_(sheet);
  gaps.forEach(function (g) {
    nextId++;
    var row = [];
    row[COL.id] = 'gap_' + ('000' + nextId).slice(-3);
    row[COL.domain] = toStr_(g.domain); row[COL.phenom] = toStr_(g.phenomenon);
    row[COL.stype] = toStr_(g.success_type); row[COL.persp] = toStr_(g.perspective);
    row[COL.qMech] = toStr_(g.q_mechanism); row[COL.qMacro] = toStr_(g.q_macro);
    row[COL.qMicro] = toStr_(g.q_micro); row[COL.hypo] = toStr_(g.hypothesis);
    row[COL.counter] = toStr_(g.counter); row[COL.prio] = toStr_(g.priority) || 'medium';
    row[COL.status] = 'open'; row[COL.insight] = '';
    row[COL.target] = toStr_(g.integration_target); row[COL.source] = ''; row[COL.updated] = today;
    sheet.appendRow(row);
  });
  Logger.log('generateGaps: ' + gaps.length + '件' + (steer ? '（自己点検反映）' : ''));
}

// ============================================================
// 多源調査 — 日英Wikipedia + arxiv認知科学
// ============================================================
function researchOpenGaps_(maxN) {
  var sheet = _sheet_(SHEETS.gap, GAP_HEADERS_());
  var data = sheet.getDataRange().getValues();
  var today = _today_(); var done = 0;

  for (var i = 1; i < data.length && done < maxN; i++) {
    if (data[i][COL.status] !== 'open') continue;
    var phenom = data[i][COL.phenom];
    if (!phenom) continue;

    var ev = gatherEvidence_(phenom, data[i][COL.stype], data[i][COL.domain]);
    var evidence = ev.length
      ? ev.map(function (h) { return '- [' + (h.source || '') + '] ' + h.title + ': ' + (h.snippet || ''); }).join('\n')
      : '(一次調査ヒットなし。一般知識で)';
    var srcUrls = ev.filter(function (h) { return h.url; }).map(function (h) { return h.url; }).slice(0, 3).join(' ');

    var prompt =
      THESIS + '\n\n事象「' + phenom + '」を分析し洞察を出す。\n' +
      '※事象は領域「' + data[i][COL.domain] + '」の文脈で解釈し、同名の別概念に逸れないこと。\n' +
      '機序: ' + data[i][COL.qMech] + '\nマクロ: ' + data[i][COL.qMacro] +
      '\n被造設計: ' + data[i][COL.qMicro] + '\n一次仮説: ' + data[i][COL.hypo] +
      '\n\n参考(多源・無関係は無視):\n' + evidence + '\n\n' +
      '二軸(マクロ=歴史/インフラ/摂理、ミクロ=脳/心の被造設計)で2〜4文に統合。' +
      '被造設計はarxiv知見を踏まえ、対抗仮説も一言。全フィールド文字列。' +
      '必ずJSONのみ: {"insight":"","source":"","integration_target":""}';

    var out = null; var res = callGroq_(prompt);
    if (res) { try { out = JSON.parse(_clean_(res)); } catch (e) {} }

    var r = i + 1;
    if (out && out.insight) {
      sheet.getRange(r, COL.insight + 1).setValue(toStr_(out.insight));
      sheet.getRange(r, COL.source + 1).setValue(toStr_(out.source) || srcUrls);
      if (out.integration_target) sheet.getRange(r, COL.target + 1).setValue(toStr_(out.integration_target));
      sheet.getRange(r, COL.status + 1).setValue('resolved');
    } else {
      sheet.getRange(r, COL.status + 1).setValue('researching');
    }
    sheet.getRange(r, COL.updated + 1).setValue(today);
    done++; Utilities.sleep(1500);
  }
  Logger.log('researchOpenGaps: ' + done + '件（多源）');
}

function gatherEvidence_(phenom, stype, domain) {
  var dom = String(domain || '').split('/').pop();  // 「柱/領域」→領域
  var q = phenom + (dom ? ' ' + dom : '');
  var ev = [];
  try { ev = ev.concat(searchWikiJa_(q)); } catch (e) {}
  try { ev = ev.concat(searchWikiEn_(q)); } catch (e) {}
  var cq = COGNITIVE_QUERY[stype] || 'human preference cognition brain';
  try { ev = ev.concat(searchArxiv_(cq).slice(0, 2)); } catch (e) {}
  return ev;
}

// ============================================================
// 昇格起案 — resolved を content_design草案化＋品質ゲート
// ============================================================
function draftPromotions_(maxN) {
  var sheet = _sheet_(SHEETS.gap, GAP_HEADERS_());
  var data = sheet.getDataRange().getValues();
  var dsheet = _sheet_(SHEETS.draft, DRAFT_HEADERS_());
  var today = _today_(); var done = 0;

  for (var i = 1; i < data.length && done < maxN; i++) {
    if (data[i][COL.status] !== 'resolved' || !data[i][COL.insight]) continue;
    var prompt =
      THESIS + '\n\n確定洞察を content_design.md に統合する草案を作る。\n' +
      '事象: ' + data[i][COL.phenom] + '\n成功次元: ' + data[i][COL.stype] +
      '\n洞察: ' + data[i][COL.insight] + '\n統合先候補: ' + data[i][COL.target] +
      '\n出典: ' + data[i][COL.source] + '\n\n' +
      '品質ゲート自己適用: ①出典 ②対抗仮説(世俗的説明で足りるか) ③どの章/節 ' +
      '④神学整合(繁栄の神学と混同しない/シャローム射程)。content_designの厳粛・知的な文体で' +
      '2〜4段落のmarkdown。全フィールド文字列。' +
      '必ずJSONのみ: {"draft_md":"","sources":"","counter_check":"","theology_check":"","section":"","gate_pass":true}';

    var out = null; var res = callGroq_(prompt);
    if (res) { try { out = JSON.parse(_clean_(res)); } catch (e) {} }
    if (out && out.draft_md) {
      dsheet.appendRow([today, data[i][COL.id], data[i][COL.phenom],
        toStr_(out.section || data[i][COL.target]), toStr_(out.draft_md),
        toStr_(out.sources) || data[i][COL.source], toStr_(out.counter_check),
        toStr_(out.theology_check), out.gate_pass ? 'pass' : 'check', '待承認']);
      sheet.getRange(i + 1, COL.status + 1).setValue('proposed');
      sheet.getRange(i + 1, COL.updated + 1).setValue(today);
      done++;
    }
    Utilities.sleep(1500);
  }
  Logger.log('draftPromotions: ' + done + '件起案');
}

// ============================================================
// ③ 技術レーダー — 新AIツールを追跡（パイプライン用）
// ============================================================
function techRadar_(n) {
  var sheet = _sheet_(SHEETS.radar, RADAR_HEADERS_());
  var queries = [
    'open source video generation model',
    'text to speech voice cloning japanese',
    'image generation diffusion model efficient',
    'depth estimation parallax video'
  ];
  var today = _today_(); var added = 0;
  queries.forEach(function (q) {
    var hits = [];
    try { hits = searchArxiv_(q).slice(0, 2); } catch (e) {}
    hits.forEach(function (h) {
      sheet.appendRow([today, q, h.title, (h.snippet || '').substring(0, 200), h.url, '', '新規']);
      added++;
    });
  });
  // Groqで「本パイプライン(FLUX/LTX/DepthFlow/SBV2)を超える候補は？」を要約
  var prompt = '本プロジェクトの動画/音声生成スタック(FLUX schnell/LTX-Video/DepthFlow/' +
    'Style-Bert-VITS2)を、より無料・高品質・T4で動くもので置換できる新OSSが2026年にあるか。' +
    '具体名と理由を簡潔に。必ずJSONのみ: {"candidates":[{"name":"","why":"","replaces":""}]}';
  var res = callGroq_(prompt);
  if (res) {
    try {
      var c = JSON.parse(_clean_(res)).candidates || [];
      c.forEach(function (x) {
        sheet.appendRow([today, 'スタック更新候補', x.name, x.why, '', x.replaces, '要検討']);
      });
    } catch (e) {}
  }
  Logger.log('techRadar: ' + added + '件追跡');
}

// ============================================================
// ② 市況スナップショット — 「今の勝者」を時系列で観測（Alpaca）
// ============================================================
// 時価総額/値動きの先頭＝インフラ最前線＝論旨鎖の現在地。Apple→Nvidiaの交代を捉える。
// 要: スクリプトプロパティ ALPACA_KEY / ALPACA_SECRET（無料データAPI）。無ければスキップ。
function marketSnapshot_() {
  var key = PropertiesService.getScriptProperties().getProperty('ALPACA_KEY');
  var sec = PropertiesService.getScriptProperties().getProperty('ALPACA_SECRET');
  if (!key || !sec) { Logger.log('marketSnapshot: ALPACAキー未設定→スキップ'); return; }
  var sheet = _sheet_(SHEETS.market, MARKET_HEADERS_());
  var today = _today_(); var n = 0;

  // ① 値動き上位（今ホットな勝者/敗者）
  try {
    var mv = alpacaGet_('https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=8', key, sec);
    (mv.gainers || []).slice(0, 6).forEach(function (g) {
      sheet.appendRow([today, 'gainer', g.symbol, g.price, g.percent_change, '']); n++;
    });
    (mv.losers || []).slice(0, 3).forEach(function (g) {
      sheet.appendRow([today, 'loser', g.symbol, g.price, g.percent_change, '']); n++;
    });
  } catch (e) { Logger.log('movers取得失敗: ' + e.message); }

  // ② ウォッチリスト（インフラ最前線銘柄の前日比）
  try {
    var snap = alpacaGet_('https://data.alpaca.markets/v2/stocks/snapshots?symbols='
      + WATCHLIST.join(','), key, sec);
    WATCHLIST.forEach(function (sym) {
      var s = snap[sym]; if (!s) return;
      var price = s.latestTrade && s.latestTrade.p;
      var prev = s.prevDailyBar && s.prevDailyBar.c;
      var chg = (price && prev) ? Math.round((price - prev) / prev * 10000) / 100 : '';
      sheet.appendRow([today, 'watch', sym, price || '', chg, '']); n++;
    });
  } catch (e) { Logger.log('snapshot取得失敗: ' + e.message); }

  Logger.log('marketSnapshot: ' + n + '件記録');
}

function alpacaGet_(url, key, sec) {
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true,
    headers: { 'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': sec } });
  return JSON.parse(res.getContentText());
}

// ============================================================
// 自己深化 — 偏り点検→次の攻め方（→翌日の生成へ還流）
// ============================================================
function selfDeepen_() {
  var sheet = _sheet_(SHEETS.gap, GAP_HEADERS_());
  var data = sheet.getDataRange().getValues();
  var stype = {}, persp = {}, pillar = {}, open = 0, resolved = 0, proposed = 0;
  for (var i = 1; i < data.length; i++) {
    _inc_(stype, data[i][COL.stype]); _inc_(persp, data[i][COL.persp]);
    _inc_(pillar, String(data[i][COL.domain]).split('/')[0]);
    var st = data[i][COL.status];
    if (st === 'open') open++; else if (st === 'resolved') resolved++; else if (st === 'proposed') proposed++;
  }
  var prompt = THESIS + '\n\n研究キューを点検しシステムを深化。\n' +
    '柱の分布: ' + JSON.stringify(pillar) + '\n成功次元: ' + JSON.stringify(stype) +
    '\n視点: ' + JSON.stringify(persp) + '\nopen=' + open + ' resolved=' + resolved + ' proposed=' + proposed + '\n\n' +
    '3本柱(成功法則/経済/技術)とシャローム5次元・視点の偏りを指摘し、' +
    '次に厚くすべき領域と、見落としている問いの型を3点。' +
    '必ずJSONのみ: {"bias":"","next_focus":["","",""],"new_question_types":["",""]}';
  var out = null; var res = callGroq_(prompt);
  if (res) { try { out = JSON.parse(_clean_(res)); } catch (e) {} }
  if (!out) { Logger.log('selfDeepen: 応答なし'); return; }
  var imp = _sheet_(SHEETS.improve, IMPROVE_HEADERS_());
  imp.appendRow([_today_(), toStr_(out.bias), toStr_(out.next_focus), toStr_(out.new_question_types),
                 JSON.stringify(stype), JSON.stringify(pillar)]);
  Logger.log('selfDeepen: 記録');
}

// ============================================================
// 週次レポート — 断片を1本の読める報告書に束ねる（最後のピース）
// ============================================================
function weeklyDigest_() {
  var gap = _sheet_(SHEETS.gap, GAP_HEADERS_()).getDataRange().getValues();
  var recentInsights = [];
  for (var i = 1; i < gap.length; i++) {
    if (gap[i][COL.insight]) {
      recentInsights.push('・[' + gap[i][COL.domain] + '] ' + gap[i][COL.phenom] + ': ' + gap[i][COL.insight]);
    }
  }
  recentInsights = recentInsights.slice(-15); // 直近15件

  var radar = _sheet_(SHEETS.radar, RADAR_HEADERS_()).getDataRange().getValues();
  var radarLines = radar.slice(-8).map(function (r) { return '・' + r[2] + ': ' + r[3]; });

  // 市況: 直近スナップショット（今の勝者＝インフラ最前線）
  var mkt = _sheet_(SHEETS.market, MARKET_HEADERS_()).getDataRange().getValues();
  var mktLines = mkt.slice(-30).map(function (r) {
    return '・' + r[0] + ' [' + r[1] + '] ' + r[2] + ' ' + r[3] + ' (' + r[4] + '%)';
  });

  var prompt = THESIS + '\n\n以下の今週の研究断片を、読める週次レポート(Markdown)に統合せよ。\n' +
    '構成: # 今週の発見 / ## 成功法則 / ## 経済・市況の今 / ## 技術動向 / ## 論旨への影響 / ## 次の問い。\n' +
    '【市況の読み方】時価総額/値動きの先頭＝インフラ最前線＝論旨鎖(福音→産業→メディア→IT→AI基盤)の現在地。' +
    '今の勝者は誰か・先週から何が変わったか・なぜか・本作の論旨とどう接続するか(例 NVDA=AI基盤=鎖の最前線)を分析せよ。\n\n' +
    '断片(洞察):\n' + recentInsights.join('\n') +
    '\n\n市況スナップショット:\n' + (mktLines.join('\n') || '(市況データなし=ALPACAキー未設定)') +
    '\n\n技術レーダー:\n' + radarLines.join('\n') + '\n\n' +
    '必ずJSONのみ: {"report_md":""}';
  var res = callGroq_(prompt);
  var md = '';
  if (res) { try { md = toStr_(JSON.parse(_clean_(res)).report_md); } catch (e) {} }
  if (!md) { Logger.log('weeklyDigest: 応答なし'); return; }
  _sheet_(SHEETS.report, REPORT_HEADERS_()).appendRow([_today_(), md]);
  Logger.log('weeklyDigest: 週次レポート生成');
}

// ============================================================
// Groq / 検索 / ユーティリティ（自己完結）
// ============================================================
function callGroq_(prompt) {
  var key = PropertiesService.getScriptProperties().getProperty('GROQ_API_KEY');
  if (!key) { Logger.log('GROQ_API_KEY未設定'); return null; }
  var payload = { model: GROQ_MODEL, messages: [{ role: 'user', content: prompt }],
    temperature: 0.85, max_tokens: 3500, response_format: { type: 'json_object' } };
  try {
    var res = UrlFetchApp.fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'post', contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + key },
      payload: JSON.stringify(payload), muteHttpExceptions: true });
    var j = JSON.parse(res.getContentText());
    if (j.error) { Logger.log('Groq error: ' + JSON.stringify(j.error)); return null; }
    return (j.choices && j.choices[0] && j.choices[0].message.content) || null;
  } catch (e) { Logger.log('Groq fetch error: ' + e.message); return null; }
}

function searchWikiJa_(query) { return _wiki_('ja', query); }
function searchWikiEn_(query) { return _wiki_('en', query); }
function _wiki_(lang, query) {
  var url = 'https://' + lang + '.wikipedia.org/w/api.php?action=query&list=search&srsearch='
    + encodeURIComponent(query) + '&format=json&srlimit=2&origin=*';
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true,
    headers: { 'User-Agent': 'documentary-gpu-research/1.0' } });
  var t = res.getContentText();
  if (t.charAt(0) !== '{') return [];
  var list = (JSON.parse(t).query || {}).search || [];
  return list.map(function (it) {
    return { title: it.title,
      url: 'https://' + lang + '.wikipedia.org/wiki/' + encodeURIComponent(it.title.replace(/ /g, '_')),
      snippet: it.snippet.replace(/<[^>]+>/g, '').substring(0, 200), source: lang + 'Wiki' };
  });
}

function searchArxiv_(query) {
  var url = 'https://export.arxiv.org/api/query?search_query=all:' + encodeURIComponent(query)
    + '&start=0&max_results=3';
  var text = UrlFetchApp.fetch(url, { muteHttpExceptions: true }).getContentText();
  var out = [];
  var entries = text.match(/<entry>([\s\S]*?)<\/entry>/g) || [];
  entries.forEach(function (e) {
    var title = (e.match(/<title>([\s\S]*?)<\/title>/) || [])[1] || '';
    var id = (e.match(/<id>([\s\S]*?)<\/id>/) || [])[1] || '';
    var sum = (e.match(/<summary>([\s\S]*?)<\/summary>/) || [])[1] || '';
    if (title) out.push({ title: title.trim(), url: id.trim(),
      snippet: sum.trim().replace(/\n/g, ' ').substring(0, 200), source: 'arXiv' });
  });
  return out;
}

function toStr_(v) {
  if (v == null) return '';
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}
function _clean_(s) { return s.replace(/```json\n?|\n?```/g, '').trim(); }
function _today_() { return Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd'); }
function _inc_(o, k) { o[k] = (o[k] || 0) + 1; }

function _pillarCounts_(n) {
  var c = { success: 0, economy: 0, tech: 0 };
  c.success = Math.max(1, Math.round(n / 2));
  c.economy = Math.max(0, Math.round(n / 4));
  c.tech = Math.max(0, n - c.success - c.economy);
  return c;
}

function _maxGapNum_(sheet) {
  if (sheet.getLastRow() < 2) return 0;
  var ids = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues(); var n = 0;
  ids.forEach(function (r) { var m = /gap_(\d+)/.exec(String(r[0])); if (m) n = Math.max(n, Number(m[1])); });
  return n;
}

function _sheet_(name, headers) {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var s = ss.getSheetByName(name);
  if (!s) { s = ss.insertSheet(name); s.appendRow(headers); }
  return s;
}
function GAP_HEADERS_() { return ['ID', '領域', '事象', '成功次元', '視点', '問い(機序)', '問い(マクロ相関)',
  '問い(被造設計)', '初期仮説', '対抗仮説', '優先度', '状態', '洞察・結論', '統合先', '出典', '更新日']; }
function DRAFT_HEADERS_() { return ['日付', 'gap_id', '事象', '統合先', 'content_design草案(markdown)',
  '出典', '対抗仮説チェック', '神学整合チェック', '品質ゲート', '承認状態']; }
function IMPROVE_HEADERS_() { return ['日付', '偏りの所見', '次に厚くする領域', '新しい問いの型', '成功次元分布', '柱分布']; }
function RADAR_HEADERS_() { return ['日付', 'クエリ', 'ツール/論文', '概要', 'URL', '置換対象', '状態']; }
function REPORT_HEADERS_() { return ['日付', '週次レポート(markdown)']; }
function MARKET_HEADERS_() { return ['日付', '区分', 'シンボル', '価格', '前日比%', 'メモ']; }

// ============================================================
// トリガー（初回のみ手動実行）
// ============================================================
function setupAutoTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var f = t.getHandlerFunction();
    if (f === 'runAll' || f === 'runResearchAll') ScriptApp.deleteTrigger(t); // 旧トリガーも掃除
  });
  ScriptApp.newTrigger('runAll').timeBased().everyDays(1).atHour(8).create();
  Logger.log('完了: 毎朝8時 runAll（成功法則/経済/技術の自律調査・統合）');
}
