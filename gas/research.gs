// ============================================================
// research.gs — 論旨補完エンジン（自律研究・自己深化）
// ============================================================
// 日々の研究・分析・自己深化を全自動で回す（無料・Claudeトークン0）。
// collector.gs の callGemini(Groq) / SPREADSHEET_ID / searchWikipedia を再利用。
//
// 【セットアップ】setupResearchTrigger() を一度だけ手動実行（毎朝8時 runResearchAll）。
// 設計根拠: docs/research_system.md
// ============================================================

const GAP_SHEET = '論旨ギャップ';
const IMPROVE_SHEET = '研究改善ログ';

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

// ─────────────────────────────────────────────
// 毎日のエントリ
// ─────────────────────────────────────────────
function runResearchAll() {
  generateGaps_(4);
  Utilities.sleep(2000);
  researchOpenGaps_(3);
  // 自己深化は週1（月曜）だけ
  var dow = Number(Utilities.formatDate(new Date(), 'Asia/Tokyo', 'u')); // 1=月
  if (dow === 1) { Utilities.sleep(2000); selfDeepen_(); }
}

// ─────────────────────────────────────────────
// A. 生成 — 偏りなき二軸ギャップを Groq で
// ─────────────────────────────────────────────
function generateGaps_(n) {
  var sheet = _gapSheet_();
  var prompt =
    'あなたは知的ドキュメンタリーの首席リサーチャー兼 認知/脳科学の素養を持つ分析者。\n' +
    THESIS_GAS + '\n\n' +
    '知識ギャップを埋める問いを' + n + '個。対象を偏らせるな（富/エリートに寄せない。' +
    'trend/everyday/relational/randomを混ぜ、成功次元も分散）。各事象を二軸で問う:\n' +
    '- マクロ相関: 歴史・インフラ・摂理(福音→改革→産業→メディア→ペイロード)との繋がり\n' +
    '- ミクロ相関(被造設計): なぜ人間の脳・心はそれに惹かれるよう作られているか\n\n' +
    '必ずJSONのみ: {"gaps":[{"domain":"","phenomenon":"","success_type":"外的|関係的|身体的|内面的|霊的",' +
    '"perspective":"trend|everyday|relational|random|elite","q_mechanism":"","q_macro":"","q_micro":"",' +
    '"hypothesis":"","counter":"","integration_target":"","priority":"high|medium|low"}]}';

  var res = callGemini(prompt); // collector.gs の Groq 呼び出し
  if (!res) { Logger.log('generateGaps: Groq応答なし'); return; }
  var gaps;
  try {
    gaps = JSON.parse(res.replace(/```json\n?|\n?```/g, '').trim()).gaps || [];
  } catch (e) { Logger.log('generateGaps JSONエラー: ' + e.message); return; }

  var today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  var nextId = sheet.getLastRow(); // ヘッダ込みの行数 ≒ 次の連番
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
  Logger.log('generateGaps: ' + gaps.length + '件 追加');
}

// ─────────────────────────────────────────────
// B. 調査+合成 — open を一次調査して Groq で洞察化
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

    // 一次調査（collector.gs の Wikipedia 検索を再利用）
    var hits = [];
    try { hits = searchWikipedia(phenom); } catch (e) {}
    var evidence = hits.map(function (h) { return '- ' + h.title + ': ' + h.snippet; }).join('\n')
                  || '(一次調査ヒットなし。一般知識で)';

    var prompt =
      THESIS_GAS + '\n\n事象「' + phenom + '」を分析し洞察を出す。\n' +
      '機序: ' + data[i][COL.qMech] + '\nマクロ: ' + data[i][COL.qMacro] +
      '\n被造設計: ' + data[i][COL.qMicro] + '\n一次仮説: ' + data[i][COL.hypo] +
      '\n\n参考(一次調査):\n' + evidence + '\n\n' +
      '二軸(マクロ=歴史/インフラ/摂理、ミクロ=脳/心の被造設計)で2〜4文に統合。' +
      '対抗仮説も一言。必ずJSONのみ: {"insight":"","source":"","integration_target":""}';

    var res = callGemini(prompt);
    var out = null;
    if (res) { try { out = JSON.parse(res.replace(/```json\n?|\n?```/g, '').trim()); } catch (e) {} }

    var r = i + 1;
    if (out && out.insight) {
      sheet.getRange(r, COL.insight + 1).setValue(out.insight);
      if (out.source) sheet.getRange(r, COL.source + 1).setValue(out.source);
      if (out.integration_target) sheet.getRange(r, COL.target + 1).setValue(out.integration_target);
      sheet.getRange(r, COL.status + 1).setValue('resolved');
    } else {
      sheet.getRange(r, COL.status + 1).setValue('researching');
    }
    sheet.getRange(r, COL.updated + 1).setValue(today);
    done++;
    Utilities.sleep(1500);
  }
  Logger.log('researchOpenGaps: ' + done + '件 処理');
}

// ─────────────────────────────────────────────
// C. 自己深化 — キューの偏りを点検し次の攻め方を起案（週1）
// ─────────────────────────────────────────────
function selfDeepen_() {
  var sheet = _gapSheet_();
  var data = sheet.getDataRange().getValues();
  var stype = {}, persp = {}, open = 0, resolved = 0;
  for (var i = 1; i < data.length; i++) {
    stype[data[i][COL.stype]] = (stype[data[i][COL.stype]] || 0) + 1;
    persp[data[i][COL.persp]] = (persp[data[i][COL.persp]] || 0) + 1;
    if (data[i][COL.status] === 'open') open++;
    if (data[i][COL.status] === 'resolved') resolved++;
  }
  var prompt =
    THESIS_GAS + '\n\n研究キューの現状を点検し、システムを深化させる。\n' +
    '成功次元の分布: ' + JSON.stringify(stype) + '\n視点の分布: ' + JSON.stringify(persp) +
    '\nopen=' + open + ' resolved=' + resolved + '\n\n' +
    'シャローム5次元・視点の偏りを指摘し、次に厚くすべき領域/モードと、' +
    '見落としている問いの型を3点提案。必ずJSONのみ: ' +
    '{"bias":"","next_focus":["","",""],"new_question_types":["",""]}';

  var res = callGemini(prompt);
  var out = null;
  if (res) { try { out = JSON.parse(res.replace(/```json\n?|\n?```/g, '').trim()); } catch (e) {} }
  if (!out) { Logger.log('selfDeepen: 応答なし'); return; }

  var imp = _improveSheet_();
  var today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  imp.appendRow([today, out.bias || '',
                 (out.next_focus || []).join(' / '),
                 (out.new_question_types || []).join(' / '),
                 JSON.stringify(stype), JSON.stringify(persp)]);
  Logger.log('selfDeepen: 改善提案を記録');
}

// ─────────────────────────────────────────────
// ヘルパ
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
// トリガー（初回のみ手動実行）
// ─────────────────────────────────────────────
function setupResearchTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'runResearchAll') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('runResearchAll').timeBased().everyDays(1).atHour(8).create();
  Logger.log('完了: 毎朝8時 runResearchAll（自律研究）');
}
