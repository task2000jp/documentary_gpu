// ============================================================
// documentary_gpu_db — 情報収集GASスクリプト
// ============================================================
// 【初回セットアップ】
//   1. スクリプトエディタ → プロジェクトの設定 → スクリプトプロパティ
//      GEMINI_API_KEY = (Google AI Studioのキー)
//   2. setupTriggers() を一度だけ手動実行
// ============================================================

const SPREADSHEET_ID = '1MBOHX1yRwUC3AaMKVtdUxfmirYpcFVM0jf_Tgvve5MA';

// ─────────────────────────────────────────────
// メインエントリー（毎朝7時に自動実行）
// ─────────────────────────────────────────────

function runAll() {
  runSearchStrategyLoop();
  Utilities.sleep(2000);
  runSearchExecutionLoop();
}

// ─────────────────────────────────────────────
// 1. 模索ループ — Geminiが「今日何を調べるか」を生成
// ─────────────────────────────────────────────

function runSearchStrategyLoop() {
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');

  const prompt = `
あなたは「勝利の福音 ── なぜ蒸気機関はスコットランドで生まれたか」という神学ドキュメンタリーの
リサーチャーです。今日（${today}）調べるべき内容を生成してください。

ドキュメンタリーの主要テーマ:
- Christus Victor神学 / 宗教改革 / スコットランド教育革命
- ジェームズ・ワット / ルター / カルヴァン / ジョン・ノックス
- 産業革命と福音の関係 / 文化的使命論
- AI動画生成技術（DepthFlow, FLUX.1, LTX-Video, Style-Bert-VITS2等）
- フリー素材・パブリックドメイン画像・BGM

以下のカテゴリで合計10個の検索クエリをJSON形式で生成:
- 神学歴史: 3個（学術的事実・聖書学・宗教改革史）
- 技術情報: 4個（AI/OSS最新情報・動画処理・音声合成）
- 素材候補: 3個（フリー画像・BGM・映像素材）

【重要1】sourceは必ず以下の3種類のみ使うこと（他は使用禁止）:
- "wikipedia" : 歴史・神学・人物の事実調査
- "arxiv"     : AI・機械学習・技術論文の検索
- "rss"       : 最新OSS・素材サイトのフィード

【重要2】queryは必ず英語で書くこと（wikipedia・arxivは英語クエリのみヒットする）

必ずこのJSON形式のみで返す（説明文・コードブロック不要）:
{"date":"${today}","queries":[{"category":"神学歴史","query":"Christus Victor atonement theology history","source":"wikipedia"},{"category":"技術情報","query":"DepthFlow video parallax generation neural network","source":"arxiv"},{"category":"素材候補","query":"public domain historical images free","source":"rss"}]}
`;

  const result = callGemini(prompt);
  if (!result) return;

  try {
    const cleaned = result.replace(/```json\n?|\n?```/g, '').trim();
    const data = JSON.parse(cleaned);
    saveStrategiesToSheet(data);
    Logger.log('模索ループ完了: ' + data.queries.length + '件のクエリを生成');
  } catch (e) {
    Logger.log('模索ループ JSONパースエラー: ' + e.message + '\nRaw: ' + result.substring(0, 300));
  }
}

function saveStrategiesToSheet(data) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName('技術情報');
  if (!sheet) return;

  // ヘッダー有無をA1セルの値で判定（空行バグ回避）
  const a1 = sheet.getRange('A1').getValue();
  if (a1 !== '日付') {
    sheet.clearContents();
    sheet.appendRow(['日付', 'カテゴリ', '検索クエリ', 'ソース', 'ステータス', '実行日時']);
    sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
  }

  data.queries.forEach(q => {
    sheet.appendRow([data.date, q.category, q.query, q.source, '未実行', '']);
  });
}

// ─────────────────────────────────────────────
// 2. 実行&保存ループ — 検索を実行してDBに保存
// ─────────────────────────────────────────────

function runSearchExecutionLoop() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const stratSheet = ss.getSheetByName('技術情報');
  if (!stratSheet || stratSheet.getLastRow() < 2) return;

  const data = stratSheet.getDataRange().getValues();
  const headers = data[0];
  const colStatus   = headers.indexOf('ステータス');
  const colQuery    = headers.indexOf('検索クエリ');
  const colCategory = headers.indexOf('カテゴリ');
  const colSource   = headers.indexOf('ソース');
  const colExecTime = headers.indexOf('実行日時');

  let executed = 0;
  const MAX_PER_RUN = 5; // レート制限対策

  for (let i = 1; i < data.length; i++) {
    if (data[i][colStatus] !== '未実行') continue;
    if (executed >= MAX_PER_RUN) break;

    const query    = data[i][colQuery];
    const category = data[i][colCategory];
    const source   = data[i][colSource];

    let results = [];
    if (source === 'arxiv') {
      results = searchArxiv(query);
    } else if (source === 'rss') {
      results = searchRSS(query);
    } else {
      results = searchWikipedia(query);
    }

    const now = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm');
    if (results.length > 0) {
      saveResultsToSheet(ss, category, query, results);
      stratSheet.getRange(i + 1, colStatus + 1).setValue('完了');
    } else {
      stratSheet.getRange(i + 1, colStatus + 1).setValue('結果なし');
    }
    stratSheet.getRange(i + 1, colExecTime + 1).setValue(now);

    executed++;
    Utilities.sleep(1500);
  }

  Logger.log('実行&保存ループ完了: ' + executed + '件実行');
}

// ─────────────────────────────────────────────
// 検索ソース（全て無料・APIキー不要）
// ─────────────────────────────────────────────

function searchWikipedia(query) {
  try {
    const url = 'https://en.wikipedia.org/w/api.php?action=query&list=search'
      + '&srsearch=' + encodeURIComponent(query)
      + '&format=json&srlimit=3&origin=*';
    const res = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      headers: { 'User-Agent': 'documentary-gpu-research/1.0' }
    });
    const text = res.getContentText();
    if (!text.startsWith('{')) {
      Logger.log('Wikipedia non-JSON: ' + text.substring(0, 80));
      return [];
    }
    const json = JSON.parse(text);
    return (json.query?.search || []).map(item => ({
      title: item.title,
      url: 'https://en.wikipedia.org/wiki/' + encodeURIComponent(item.title.replace(/ /g, '_')),
      snippet: item.snippet.replace(/<[^>]+>/g, '').substring(0, 300),
      source: 'Wikipedia'
    }));
  } catch (e) {
    Logger.log('Wikipedia error: ' + e.message);
    return [];
  }
}

function searchArxiv(query) {
  try {
    const url = 'https://export.arxiv.org/api/query?search_query=all:'
      + encodeURIComponent(query) + '&start=0&max_results=3';
    const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    const text = res.getContentText();
    const results = [];
    const entries = text.match(/<entry>([\s\S]*?)<\/entry>/g) || [];
    entries.slice(0, 3).forEach(entry => {
      const title   = (entry.match(/<title>([\s\S]*?)<\/title>/) || [])[1] || '';
      const id      = (entry.match(/<id>([\s\S]*?)<\/id>/)       || [])[1] || '';
      const summary = (entry.match(/<summary>([\s\S]*?)<\/summary>/) || [])[1] || '';
      if (title) results.push({
        title: title.trim(),
        url: id.trim(),
        snippet: summary.trim().replace(/\n/g, ' ').substring(0, 300),
        source: 'arXiv'
      });
    });
    return results;
  } catch (e) {
    Logger.log('arXiv error: ' + e.message);
    return [];
  }
}

function searchRSS(query) {
  const feeds = [
    'https://huggingface.co/blog/feed.xml',
    'https://github.blog/feed/',
    'https://paperswithcode.com/rss.xml'
  ];
  const results = [];
  const keyword = query.toLowerCase().split(' ')[0];

  feeds.forEach(feedUrl => {
    try {
      const res = UrlFetchApp.fetch(feedUrl, { muteHttpExceptions: true });
      const text = res.getContentText();
      const items = text.match(/<item>([\s\S]*?)<\/item>/g) || [];
      items.slice(0, 5).forEach(item => {
        const title = ((item.match(/<title><!\[CDATA\[([\s\S]*?)\]\]>/) ||
                        item.match(/<title>([\s\S]*?)<\/title>/) || [])[1] || '').trim();
        const link  = ((item.match(/<link>([\s\S]*?)<\/link>/) || [])[1] || '').trim();
        if (title && title.toLowerCase().includes(keyword)) {
          results.push({ title, url: link, snippet: '', source: 'RSS:' + feedUrl.split('/')[2] });
        }
      });
    } catch (e) {
      Logger.log('RSS error: ' + feedUrl.split('/')[2] + ' - ' + e.message);
    }
  });

  return results.slice(0, 3);
}

// ─────────────────────────────────────────────
// Groq API（無料枠：6000リクエスト/日・クレカ不要）
// スクリプトプロパティ: GROQ_API_KEY
// ─────────────────────────────────────────────

function callGemini(prompt) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('GROQ_API_KEY');
  if (!apiKey) {
    Logger.log('ERROR: GROQ_API_KEY がスクリプトプロパティに未設定');
    return null;
  }

  const url = 'https://api.groq.com/openai/v1/chat/completions';
  const payload = {
    model: 'llama-3.1-8b-instant',
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.7,
    max_tokens: 2048
  };

  try {
    const res = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + apiKey },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    const json = JSON.parse(res.getContentText());
    if (json.error) {
      Logger.log('Groq API error: ' + JSON.stringify(json.error));
      return null;
    }
    return json.choices?.[0]?.message?.content || null;
  } catch (e) {
    Logger.log('Groq fetch error: ' + e.message);
    return null;
  }
}

// ─────────────────────────────────────────────
// 結果をカテゴリ別シートに保存
// ─────────────────────────────────────────────

function saveResultsToSheet(ss, category, query, results) {
  const sheetMap = { '神学歴史': '神学歴史', '技術情報': '技術情報', '素材候補': '素材候補' };
  const sheetName = sheetMap[category] || '技術情報';
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) return;

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['日付', '検索クエリ', 'タイトル', 'URL', '概要', 'ソース']);
    sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
  }

  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  results.forEach(r => {
    sheet.appendRow([today, query, r.title, r.url, r.snippet, r.source]);
  });
}

// ─────────────────────────────────────────────
// トリガー設定（初回のみ手動実行）
// ─────────────────────────────────────────────

function setupTriggers() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('runAll')
    .timeBased()
    .everyDays(1)
    .atHour(7)
    .create();
  Logger.log('完了: 毎朝7時に runAll() が自動実行されます');
}
