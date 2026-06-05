// ============================================================
// research.gs — 論旨補完エンジン（自律研究・自己深化・自己改善ループ）
// ============================================================
// 日々の研究・分析・自己深化・昇格起案を全自動で回す（無料・Claudeトークン0）。
// collector.gs の callGemini(Groq) / SPREADSHEET_ID / searchWikipedia / searchArxiv を再利用。
//
// 【セットアップ】setupResearchTrigger() を一度だけ手動実行（毎朝8時 runResearchAll）。
// 設計根拠: docs/research_system.md
//
// 全体ループ（A調査多源 / B昇格起案 / C自己改善フィードバック）:
//   selfDeepen_ → 研究改善ログ → generateGaps_ が読んで次の生成を是正（Cで閉じる）
// ============================================================

const GAP_SHEET = '論旨ギャップ';
const IMPROVE_SHEET = '研究改善ログ';
const DRAFT_SHEET = '昇格ドラフト';

// 列インデックス（0始まり）: A..P = 16列
const COL = {
  id: 0, domain: 1, phenom: 2, stype: 3, persp: 4,
  qMech: 5, qMacro: 6, qMicro: 7, hypo: 8, counter: 9,
  prio: 10, status: 11, insight: 12, target: 13, source: 14, updated: 15
};

const THESIS_GAS =
  '作品「勝利の福音」: 福音→心の解放(Christus Victor)→宗教改革→科学/医療/経済→産業革命' +
  '→メディア革命→IT/AI。芸術は福音インフラ上のペイロード。' +
  '成功は富だけでない＝シャローム5次元(外の豊かさ/関係/健康/心の平和/神との和解)。' +
  '全ては繋がる—神が人間・脳・被造世界を作ったから。連関は捏造でなく発見する。';

// 成功次元 → 被造設計(ミクロ軸)を裏づける arxiv 認知科学クエリ（英語）
const COGNITIVE_QUERY = {
  '外的':   'status motivation reward brain dopamine',
  '関係的': 'social bonding attraction oxytocin attachment',
  '身体的': 'facial attractiveness perception evolution',
  '内面的': 'music emotion narrative engagement brain',
  '霊的':   'meaning purpose transcendence psychology religion'
};

// ─────────────────────────────────────────────
// 毎日のエントリ
// ─────────────────────────────────────────────
function runResearchAll() {
  generateGaps_(4);          // C: 前回の自己点検を反映して生成
  Utilities.sleep(2000);
  researchOpenGaps_(3);      // A: 多源調査(日英Wikipedia+arxiv脳科学)+Groq合成
  Utilities.sleep(2000);
  draftPromotions_(2);       // B: resolved→content_design草案+品質ゲート
  var dow = Number(Utilities.formatDate(new Date(), 'Asia/Tokyo', 'u')); // 1=月
  if (dow === 1) { Utilities.sleep(2000); selfDeepen_(); } // 週1 自己深化
}

// ─────────────────────────────────────────────
// A+C. 生成 — 自己点検を反映した偏りなき二軸ギャップ
// ─────────────────────────────────────────────
function generateGaps_(n) {
  var sheet = _gapSheet_();

  // C: 直近の自己点検（研究改善ログ）を生成プロンプトへ反映
  var steer = '';
  var imp = _improveSheet_();
  if (imp.getLastRow() > 1) {
    var r = imp.getRange(imp.getLastRow(), 1, 1, 4).getValues()[0];
    steer = '\n【前回の自己点検を必ず反映】偏り所見:' + r[1] +
            ' / 次に厚くすべき領域:' + r[2] + ' / 新しい問いの型:' + r[3];
  }

  var prompt =
    'あなたは知的ドキュメンタリーの首席リサーチャー兼 認知/脳科学の素養を持つ分析者。\n' +
    THESIS_GAS + steer + '\n\n' +
    '知識ギャップを埋める問いを' + n + '個。対象を偏らせるな（富/エリートに寄せない。' +
    'trend/everyday/relational/randomを混ぜ、成功次元も分散）。各事象を二軸で問う:\n' +
    '- マクロ相関: 歴史・インフラ・摂理(福音→改革→産業→メディア→ペイロード)との繋がり\n' +
    '- ミクロ相関(被造設計): なぜ人間の脳・心はそれに惹かれるよう作られているか\n\n' +
    '必ずJSONのみ: {"gaps":[{"domain":"","phenomenon":"","success_type":"外的|関係的|身体的|内面的|霊的",' +
    '"perspective":"trend|everyday|relational|random|elite","q_mechanism":"","q_macro":"","q_micro":"",' +
    '"hypothesis":"","counter":"","integration_target":"","priority":"high|medium|low"}]}';

  var res = callGroq_(prompt);
  if (!res) { Logger.log('generateGaps: Groq応答なし'); return; }
  var gaps;
  try {
    gaps = JSON.parse(res.replace(/```json\n?|\n?```/g, '').trim()).gaps || [];
  } catch (e) { Logger.log('generateGaps JSONエラー: ' + e.message); return; }

  var today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  var nextId = _maxGapNum_(sheet);
  gaps.forEach(function (g) {
    nextId++;
    var row = [];
    row[COL.id] = 'gap_' + ('000' + nextId).slice(-3);
    row[COL.domain] = g.domain || '';
    row[COL.phenom] = g.phenomenon || '';
    row[COL.stype] = g.success_type || '';
    row[COL.persp] = g.perspective || '';
    row[COL.qMech] = g.q_mechanism || '';
    row[COL.qMacro] = g.q_macro || '';
    row[COL.qMicro] = g.q_micro || '';
    row[COL.hypo] = g.hypothesis || '';
    row[COL.counter] = g.counter || '';
    row[COL.prio] = g.priority || 'medium';
    row[COL.status] = 'open';
    row[COL.insight] = '';
    row[COL.target] = g.integration_target || '';
    row[COL.source] = '';
    row[COL.updated] = today;
    sheet.appendRow(row);
  });
  Logger.log('generateGaps: ' + gaps.length + '件 追加' + (steer ? '（自己点検反映）' : ''));
}

// ─────────────────────────────────────────────
// A. 調査+合成 — 多源(日英Wikipedia+arxiv脳科学)で open を洞察化
// ─────────────────────────────────────────────
function researchOpenGaps_(maxN) {
  var sheet = _gapSheet_();
  var data = sheet.getDataRange().getValues();
  var today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  var done = 0;

  for (var i = 1; i < data.length && done < maxN; i++) {
    if (data[i][COL.status] !== 'open') continue;
    var phenom = data[i][COL.phenom];
    if (!phenom) continue;

    var ev = gatherEvidence_(phenom, data[i][COL.stype]);
    var evidence = ev.length
      ? ev.map(function (h) { return '- [' + (h.source || '') + '] ' + h.title + ': ' + (h.snippet || ''); }).join('\n')
      : '(一次調査ヒットなし。一般知識で)';
    var srcUrls = ev.filter(function (h) { return h.url; }).map(function (h) { return h.url; }).slice(0, 3).join(' ');

    var prompt =
      THESIS_GAS + '\n\n事象「' + phenom + '」を分析し洞察を出す。\n' +
      '機序: ' + data[i][COL.qMech] + '\nマクロ: ' + data[i][COL.qMacro] +
      '\n被造設計: ' + data[i][COL.qMicro] + '\n一次仮説: ' + data[i][COL.hypo] +
      '\n\n参考(多源一次調査):\n' + evidence + '\n\n' +
      '二軸(マクロ=歴史/インフラ/摂理、ミクロ=脳/心の被造設計)で2〜4文に統合。' +
      '被造設計はarxiv知見を踏まえること。対抗仮説も一言。' +
      '必ずJSONのみ: {"insight":"","source":"","integration_target":""}';

    var res = callGroq_(prompt);
    var out = null;
    if (res) { try { out = JSON.parse(res.replace(/```json\n?|\n?```/g, '').trim()); } catch (e) {} }

    var r = i + 1;
    if (out && out.insight) {
      sheet.getRange(r, COL.insight + 1).setValue(out.insight);
      sheet.getRange(r, COL.source + 1).setValue(out.source || srcUrls);
      if (out.integration_target) sheet.getRange(r, COL.target + 1).setValue(out.integration_target);
      sheet.getRange(r, COL.status + 1).setValue('resolved');
    } else {
      sheet.getRange(r, COL.status + 1).setValue('researching');
    }
    sheet.getRange(r, COL.updated + 1).setValue(today);
    done++;
    Utilities.sleep(1500);
  }
  Logger.log('researchOpenGaps: ' + done + '件 処理（多源）');
}

// 多源証拠収集（日Wikipedia + 英Wikipedia + arxiv認知科学）
function gatherEvidence_(phenom, stype) {
  var ev = [];
  try { ev = ev.concat(searchWikipediaJa_(phenom)); } catch (e) {}
  try { ev = ev.concat(searchWikipedia(phenom)); } catch (e) {}   // collector.gs(en)
  var cq = COGNITIVE_QUERY[stype] || 'human preference cognition brain';
  try { ev = ev.concat((searchArxiv(cq) || []).slice(0, 2)); } catch (e) {} // collector.gs
  return ev;
}

function searchWikipediaJa_(query) {
  var url = 'https://ja.wikipedia.org/w/api.php?action=query&list=search&srsearch='
    + encodeURIComponent(query) + '&format=json&srlimit=2&origin=*';
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true,
    headers: { 'User-Agent': 'documentary-gpu-research/1.0' } });
  var t = res.getContentText();
  if (t.charAt(0) !== '{') return [];
  var j = JSON.parse(t);
  var list = (j.query && j.query.search) || [];
  return list.map(function (it) {
    return { title: it.title,
             url: 'https://ja.wikipedia.org/wiki/' + encodeURIComponent(it.title.replace(/ /g, '_')),
             snippet: it.snippet.replace(/<[^>]+>/g, '').substring(0, 200),
             source: 'jaWiki' };
  });
}

// ─────────────────────────────────────────────
// B. 昇格起案 — resolved を content_design 草案化＋品質ゲート
// ─────────────────────────────────────────────
function draftPromotions_(maxN) {
  var sheet = _gapSheet_();
  var data = sheet.getDataRange().getValues();
  var draftSheet = _draftSheet_();
  var today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  var done = 0;

  for (var i = 1; i < data.length && done < maxN; i++) {
    if (data[i][COL.status] !== 'resolved') continue;
    if (!data[i][COL.insight]) continue;

    var prompt =
      THESIS_GAS + '\n\n以下の確定洞察を content_design.md に統合する草案を作る。\n' +
      '事象: ' + data[i][COL.phenom] + '\n成功次元: ' + data[i][COL.stype] +
      '\n洞察: ' + data[i][COL.insight] + '\n統合先(候補): ' + data[i][COL.target] +
      '\n出典: ' + data[i][COL.source] + '\n\n' +
      '品質ゲートを自己適用: ①出典 ②対抗仮説の検討(世俗的説明で足りるか) ' +
      '③どの章/節に効くか ④神学的整合(繁栄の神学と混同しない/シャローム射程)。\n' +
      'content_designの厳粛・知的な文体で2〜4段落のmarkdown草案。' +
      '必ずJSONのみ: {"draft_md":"","sources":"","counter_check":"","theology_check":"",' +
      '"section":"","gate_pass":true}';

    var res = callGroq_(prompt);
    var out = null;
    if (res) { try { out = JSON.parse(res.replace(/```json\n?|\n?```/g, '').trim()); } catch (e) {} }

    if (out && out.draft_md) {
      draftSheet.appendRow([today, data[i][COL.id], data[i][COL.phenom],
        out.section || data[i][COL.target], out.draft_md, out.sources || data[i][COL.source],
        out.counter_check || '', out.theology_check || '',
        out.gate_pass ? 'pass' : 'check', '待承認']);
      sheet.getRange(i + 1, COL.status + 1).setValue('proposed');
      sheet.getRange(i + 1, COL.updated + 1).setValue(today);
      done++;
    }
    Utilities.sleep(1500);
  }
  Logger.log('draftPromotions: ' + done + '件 起案');
}

// ─────────────────────────────────────────────
// C. 自己深化 — 偏り点検→次の攻め方を起案（→generateGapsが翌日反映）
// ─────────────────────────────────────────────
function selfDeepen_() {
  var sheet = _gapSheet_();
  var data = sheet.getDataRange().getValues();
  var stype = {}, persp = {}, open = 0, resolved = 0, proposed = 0;
  for (var i = 1; i < data.length; i++) {
    stype[data[i][COL.stype]] = (stype[data[i][COL.stype]] || 0) + 1;
    persp[data[i][COL.persp]] = (persp[data[i][COL.persp]] || 0) + 1;
    var st = data[i][COL.status];
    if (st === 'open') open++; else if (st === 'resolved') resolved++; else if (st === 'proposed') proposed++;
  }
  var prompt =
    THESIS_GAS + '\n\n研究キューの現状を点検し、システムを深化させる。\n' +
    '成功次元の分布: ' + JSON.stringify(stype) + '\n視点の分布: ' + JSON.stringify(persp) +
    '\nopen=' + open + ' resolved=' + resolved + ' proposed=' + proposed + '\n\n' +
    'シャローム5次元・視点の偏りを指摘し、次に厚くすべき領域/モードと、' +
    '見落としている問いの型を3点提案。必ずJSONのみ: ' +
    '{"bias":"","next_focus":["","",""],"new_question_types":["",""]}';

  var res = callGroq_(prompt);
  var out = null;
  if (res) { try { out = JSON.parse(res.replace(/```json\n?|\n?```/g, '').trim()); } catch (e) {} }
  if (!out) { Logger.log('selfDeepen: 応答なし'); return; }

  var imp = _improveSheet_();
  var today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  imp.appendRow([today, out.bias || '',
                 (out.next_focus || []).join(' / '),
                 (out.new_question_types || []).join(' / '),
                 JSON.stringify(stype), JSON.stringify(persp)]);
  Logger.log('selfDeepen: 改善提案を記録（次のgenerateGapsが反映）');
}

// ─────────────────────────────────────────────
// Groq呼び出し（研究用は70b・JSON強制。collectorの8bより高品質）
// ─────────────────────────────────────────────
function callGroq_(prompt) {
  var key = PropertiesService.getScriptProperties().getProperty('GROQ_API_KEY');
  if (!key) { Logger.log('GROQ_API_KEY未設定'); return null; }
  var payload = {
    model: 'llama-3.3-70b-versatile',
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.85, max_tokens: 3500,
    response_format: { type: 'json_object' }
  };
  try {
    var res = UrlFetchApp.fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'post', contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + key },
      payload: JSON.stringify(payload), muteHttpExceptions: true
    });
    var j = JSON.parse(res.getContentText());
    if (j.error) { Logger.log('Groq error: ' + JSON.stringify(j.error)); return null; }
    return (j.choices && j.choices[0] && j.choices[0].message.content) || null;
  } catch (e) { Logger.log('Groq fetch error: ' + e.message); return null; }
}

// ─────────────────────────────────────────────
// ヘルパ
// ─────────────────────────────────────────────
function _maxGapNum_(sheet) {
  var n = 0;
  if (sheet.getLastRow() < 2) return 0;
  var ids = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues();
  ids.forEach(function (r) {
    var m = /gap_(\d+)/.exec(String(r[0]));
    if (m) n = Math.max(n, Number(m[1]));
  });
  return n;
}

function _gapSheet_() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var s = ss.getSheetByName(GAP_SHEET);
  if (!s) {
    s = ss.insertSheet(GAP_SHEET);
    s.appendRow(['ID', '領域', '事象', '成功次元', '視点', '問い(機序)', '問い(マクロ相関)',
                 '問い(被造設計)', '初期仮説', '対抗仮説', '優先度', '状態', '洞察・結論',
                 '統合先', '出典', '更新日']);
  }
  return s;
}

function _improveSheet_() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var s = ss.getSheetByName(IMPROVE_SHEET);
  if (!s) {
    s = ss.insertSheet(IMPROVE_SHEET);
    s.appendRow(['日付', '偏りの所見', '次に厚くする領域', '新しい問いの型', '成功次元分布', '視点分布']);
  }
  return s;
}

function _draftSheet_() {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var s = ss.getSheetByName(DRAFT_SHEET);
  if (!s) {
    s = ss.insertSheet(DRAFT_SHEET);
    s.appendRow(['日付', 'gap_id', '事象', '統合先', 'content_design草案(markdown)',
                 '出典', '対抗仮説チェック', '神学整合チェック', '品質ゲート', '承認状態']);
  }
  return s;
}

// ─────────────────────────────────────────────
// トリガー（初回のみ手動実行）
// ─────────────────────────────────────────────
function setupResearchTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'runResearchAll') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('runResearchAll').timeBased().everyDays(1).atHour(8).create();
  Logger.log('完了: 毎朝8時 runResearchAll（自律研究 A調査多源/B昇格起案/C自己改善）');
}
