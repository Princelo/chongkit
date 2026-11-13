const express = require('express');
const { ClassicLevel } = require('classic-level');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = 3000;

// Rime 資料目錄
const RIME_DIR = path.join(__dirname, '..');

// 當前資料庫狀態
let db;
let dbMode = 'unknown'; // 'original' | 'copy'
let originalLocked = false;
let currentDbName = '';

// 取得所有 .userdb 資料庫
function listDatabases() {
  const dirs = fs.readdirSync(RIME_DIR).filter(f => {
    const full = path.join(RIME_DIR, f);
    return f.endsWith('.userdb') && fs.statSync(full).isDirectory();
  });
  return dirs.sort();
}

// 取得資料庫路徑
function getDbPath(dbName) {
  return path.join(RIME_DIR, dbName);
}

// 取得工作副本路徑
function getWorkDir(dbName) {
  return path.join(__dirname, 'workdb', dbName);
}

// 中介軟體
app.use(express.json({ limit: '50mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// 複製資料庫檔案
function copyDatabase(src, dest) {
  if (fs.existsSync(dest)) {
    fs.rmSync(dest, { recursive: true, force: true });
  }
  fs.mkdirSync(dest, { recursive: true });

  const files = fs.readdirSync(src);
  for (const file of files) {
    // 跳過隱藏檔案和目錄
    if (file.startsWith('.') || file === 'lost') continue;
    const srcFile = path.join(src, file);
    const destFile = path.join(dest, file);
    const stat = fs.statSync(srcFile);
    if (stat.isFile()) {
      fs.copyFileSync(srcFile, destFile);
    }
  }
}

// 解析值的 c/d/t 標量（支援科學記號如 1.5e-10、2E5）
function parseMetrics(buffer) {
  if (!Buffer.isBuffer(buffer)) buffer = Buffer.from(buffer);
  const text = buffer.toString('utf8');
  const metrics = {};
  const numRe = /\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/;
  const cMatch = text.match(new RegExp('c=(' + numRe.source + ')'));
  const dMatch = text.match(new RegExp('d=(' + numRe.source + ')'));
  const tMatch = text.match(new RegExp('t=(' + numRe.source + ')'));
  if (cMatch) metrics.c = parseFloat(cMatch[1]);
  if (dMatch) metrics.d = parseFloat(dMatch[1]);
  if (tMatch) metrics.t = parseFloat(tMatch[1]);
  return metrics;
}

// 判斷鍵是否為 enc 條目（鍵以 \x7fenc\x1f 開頭）
function isEncKey(key) {
  return key.startsWith('\x7fenc\x1f');
}

// 格式化值為可顯示的字串
function formatValue(buffer) {
  if (!Buffer.isBuffer(buffer)) {
    buffer = Buffer.from(buffer);
  }
  const text = buffer.toString('utf8');
  const isPrintable = /^[\x09\x0A\x0D\x20-\x7E\u0080-\uFFFF]*$/.test(text);
  if (isPrintable) {
    return { type: 'text', value: text, hex: buffer.toString('hex') };
  }
  return { type: 'hex', value: buffer.toString('hex'), text: text.substring(0, 100) };
}

// 初始化/切換資料庫連接
async function initDB(dbName) {
  // 關閉現有連接
  if (db) {
    try { await db.close(); } catch (e) { /* 忽略 */ }
  }

  currentDbName = dbName;
  const dbPath = getDbPath(dbName);
  const workDir = getWorkDir(dbName);

  try {
    db = new ClassicLevel(dbPath, { keyEncoding: 'utf8', valueEncoding: 'buffer' });
    await db.open();
    dbMode = 'original';
    originalLocked = false;
    console.log('直接連接原始資料庫成功:', dbPath);
  } catch (err) {
    console.log('原始資料庫被鎖定（Rime 正在使用），建立工作副本...');
    originalLocked = true;

    try {
      copyDatabase(dbPath, workDir);

      const lockFile = path.join(workDir, 'LOCK');
      if (fs.existsSync(lockFile)) {
        fs.unlinkSync(lockFile);
      }

      db = new ClassicLevel(workDir, { keyEncoding: 'utf8', valueEncoding: 'buffer', createIfMissing: false });
      await db.open();
      dbMode = 'copy';
      console.log('工作副本建立成功:', workDir);
    } catch (err2) {
      console.error('資料庫初始化失敗:', err2.message);
      throw err2;
    }
  }
}

// API: 取得可用資料庫列表
app.get('/api/databases', (req, res) => {
  try {
    const databases = listDatabases();
    res.json({ databases, current: currentDbName });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 切換資料庫
app.post('/api/switch-db', async (req, res) => {
  try {
    const { name } = req.body;
    if (!name) return res.status(400).json({ error: '缺少資料庫名稱' });
    const databases = listDatabases();
    if (!databases.includes(name)) return res.status(404).json({ error: `找不到資料庫: ${name}` });

    await initDB(name);
    res.json({ success: true, current: currentDbName, mode: dbMode, originalLocked });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 取得資料庫狀態
app.get('/api/stats', async (req, res) => {
  try {
    let count = 0;
    for await (const _ of db.iterator()) {
      count++;
    }
    res.json({
      totalEntries: count,
      dbPath: getDbPath(currentDbName),
      workPath: getWorkDir(currentDbName),
      dbName: currentDbName,
      mode: dbMode,
      originalLocked: originalLocked,
      status: 'connected'
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 取得所有條目（分頁 + 篩選 + 排序）
app.get('/api/entries', async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 50;
    const offset = (page - 1) * limit;
    const type = req.query.type || 'all'; // all | enc | user
    const minC = req.query.minC !== undefined ? parseFloat(req.query.minC) : undefined;
    const maxC = req.query.maxC !== undefined ? parseFloat(req.query.maxC) : undefined;
    const minD = req.query.minD !== undefined ? parseFloat(req.query.minD) : undefined;
    const maxD = req.query.maxD !== undefined ? parseFloat(req.query.maxD) : undefined;
    const minT = req.query.minT !== undefined ? parseFloat(req.query.minT) : undefined;
    const maxT = req.query.maxT !== undefined ? parseFloat(req.query.maxT) : undefined;
    const hasScalarFilter = [minC, maxC, minD, maxD, minT, maxT].some(v => v !== undefined);
    const sortBy = req.query.sortBy || ''; // key | value | c | d | t
    const sortOrder = req.query.sortOrder || 'asc'; // asc | desc
    const needCollect = type !== 'all' || hasScalarFilter || sortBy;

    // 需要篩選或排序時，先收集全部匹配項
    if (needCollect) {
      const allMatches = [];
      for await (const [key, value] of db.iterator()) {
        const keyStr = key.toString();
        // 類型篩選
        if (type === 'enc' && !isEncKey(keyStr)) continue;
        if (type === 'user' && isEncKey(keyStr)) continue;
        // 解析標量（篩選與排序共用，避免重複解析）
        const m = (hasScalarFilter || (sortBy && ['c','d','t'].includes(sortBy))) ? parseMetrics(value) : {};
        // 標量值篩選
        if (hasScalarFilter) {
          if (minC !== undefined && (m.c === undefined || m.c < minC)) continue;
          if (maxC !== undefined && (m.c === undefined || m.c > maxC)) continue;
          if (minD !== undefined && (m.d === undefined || m.d < minD)) continue;
          if (maxD !== undefined && (m.d === undefined || m.d > maxD)) continue;
          if (minT !== undefined && (m.t === undefined || m.t < minT)) continue;
          if (maxT !== undefined && (m.t === undefined || m.t > maxT)) continue;
        }
        allMatches.push({ key: keyStr, value, metrics: m });
      }
      // 排序
      if (sortBy) {
        const dir = sortOrder === 'desc' ? -1 : 1;
        allMatches.sort((a, b) => {
          let va, vb;
          if (sortBy === 'key') { va = a.key; vb = b.key; }
          else if (sortBy === 'value') { va = a.value.toString('utf8'); vb = b.value.toString('utf8'); }
          else if (sortBy === 'c') { va = a.metrics.c; vb = b.metrics.c; }
          else if (sortBy === 'd') { va = a.metrics.d; vb = b.metrics.d; }
          else if (sortBy === 't') { va = a.metrics.t; vb = b.metrics.t; }
          // 缺少標量值的條目一律排到最後
          const aMiss = va === undefined, bMiss = vb === undefined;
          if (aMiss && bMiss) return 0;
          if (aMiss) return 1;
          if (bMiss) return -1;
          if (va < vb) return -1 * dir;
          if (va > vb) return 1 * dir;
          return 0;
        });
      }
      const total = allMatches.length;
      const totalPages = Math.ceil(total / limit);
      const entries = allMatches.slice(offset, offset + limit).map(item => {
        const formatted = formatValue(item.value);
        return {
          key: item.key,
          value: formatted.type === 'text' ? formatted.value : formatted.value,
          valueType: formatted.type,
          hex: formatted.hex
        };
      });
      return res.json({ entries, page, limit, total, totalPages });
    }

    // 無篩選無排序時，使用高效的串流分頁
    const entries = [];
    let total = 0;
    let skipped = 0;

    for await (const [key, value] of db.iterator()) {
      total++;
      if (skipped < offset) {
        skipped++;
        continue;
      }
      if (entries.length < limit) {
        const formatted = formatValue(value);
        entries.push({
          key,
          value: formatted.type === 'text' ? formatted.value : formatted.value,
          valueType: formatted.type,
          hex: formatted.hex
        });
      }
    }

    res.json({ entries, page, limit, total, totalPages: Math.ceil(total / limit) });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 搜尋條目（支援篩選 + 排序）
app.get('/api/search', async (req, res) => {
  try {
    const query = req.query.q || '';
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 50;
    const offset = (page - 1) * limit;
    const type = req.query.type || 'all'; // all | enc | user
    const minC = req.query.minC !== undefined ? parseFloat(req.query.minC) : undefined;
    const maxC = req.query.maxC !== undefined ? parseFloat(req.query.maxC) : undefined;
    const minD = req.query.minD !== undefined ? parseFloat(req.query.minD) : undefined;
    const maxD = req.query.maxD !== undefined ? parseFloat(req.query.maxD) : undefined;
    const minT = req.query.minT !== undefined ? parseFloat(req.query.minT) : undefined;
    const maxT = req.query.maxT !== undefined ? parseFloat(req.query.maxT) : undefined;
    const hasScalarFilter = [minC, maxC, minD, maxD, minT, maxT].some(v => v !== undefined);
    const sortBy = req.query.sortBy || ''; // key | value | c | d | t
    const sortOrder = req.query.sortOrder || 'asc'; // asc | desc

    if (!query && type === 'all' && !hasScalarFilter && !sortBy) {
      return res.json({ entries: [], total: 0, page, totalPages: 0 });
    }

    // 收集所有匹配項，再排序分頁
    const allMatches = [];
    for await (const [key, value] of db.iterator()) {
      const keyStr = key.toString();
      const valueStr = value.toString('utf8');
      const valueHex = value.toString('hex');

      // 文字搜尋篩選
      if (query && !keyStr.includes(query) && !valueStr.includes(query) && !valueHex.includes(query)) continue;
      // 類型篩選
      if (type === 'enc' && !isEncKey(keyStr)) continue;
      if (type === 'user' && isEncKey(keyStr)) continue;
      // 解析標量（篩選與排序共用，避免重複解析）
      const m = (hasScalarFilter || (sortBy && ['c','d','t'].includes(sortBy))) ? parseMetrics(value) : {};
      // 標量值篩選
      if (hasScalarFilter) {
        if (minC !== undefined && (m.c === undefined || m.c < minC)) continue;
        if (maxC !== undefined && (m.c === undefined || m.c > maxC)) continue;
        if (minD !== undefined && (m.d === undefined || m.d < minD)) continue;
        if (maxD !== undefined && (m.d === undefined || m.d > maxD)) continue;
        if (minT !== undefined && (m.t === undefined || m.t < minT)) continue;
        if (maxT !== undefined && (m.t === undefined || m.t > maxT)) continue;
      }

      allMatches.push({ key: keyStr, value, metrics: m });
    }

    // 排序
    if (sortBy) {
      const dir = sortOrder === 'desc' ? -1 : 1;
      allMatches.sort((a, b) => {
        let va, vb;
        if (sortBy === 'key') { va = a.key; vb = b.key; }
        else if (sortBy === 'value') { va = a.value.toString('utf8'); vb = b.value.toString('utf8'); }
        else if (sortBy === 'c') { va = a.metrics.c; vb = b.metrics.c; }
        else if (sortBy === 'd') { va = a.metrics.d; vb = b.metrics.d; }
        else if (sortBy === 't') { va = a.metrics.t; vb = b.metrics.t; }
        // 缺少標量值的條目一律排到最後
        const aMiss = va === undefined, bMiss = vb === undefined;
        if (aMiss && bMiss) return 0;
        if (aMiss) return 1;
        if (bMiss) return -1;
        if (va < vb) return -1 * dir;
        if (va > vb) return 1 * dir;
        return 0;
      });
    }

    const total = allMatches.length;
    const totalPages = Math.ceil(total / limit);
    const entries = allMatches.slice(offset, offset + limit).map(item => {
      const formatted = formatValue(item.value);
      return {
        key: item.key,
        value: formatted.type === 'text' ? formatted.value : formatted.value,
        valueType: formatted.type,
        hex: formatted.hex
      };
    });

    res.json({ entries, total, page, totalPages });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 取得單個條目
app.get('/api/entries/:key', async (req, res) => {
  try {
    const key = decodeURIComponent(req.params.key);
    const value = await db.get(key);
    const formatted = formatValue(value);
    res.json({
      key,
      value: formatted.type === 'text' ? formatted.value : formatted.value,
      valueType: formatted.type,
      hex: formatted.hex
    });
  } catch (err) {
    if (err.code === 'LEVEL_NOT_FOUND') {
      return res.status(404).json({ error: '條目未找到' });
    }
    res.status(500).json({ error: err.message });
  }
});

// API: 更新/建立條目
app.put('/api/entries/:key', async (req, res) => {
  try {
    const key = decodeURIComponent(req.params.key);
    const { value, hex } = req.body;

    let valueBuffer;
    if (hex) {
      valueBuffer = Buffer.from(hex, 'hex');
    } else if (value !== undefined) {
      valueBuffer = Buffer.from(value, 'utf8');
    } else {
      return res.status(400).json({ error: '缺少 value 或 hex 欄位' });
    }

    await db.put(key, valueBuffer);
    const formatted = formatValue(valueBuffer);
    res.json({
      key,
      value: formatted.type === 'text' ? formatted.value : formatted.value,
      valueType: formatted.type,
      hex: formatted.hex,
      message: '更新成功'
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 刪除條目
app.delete('/api/entries/:key', async (req, res) => {
  try {
    const key = decodeURIComponent(req.params.key);
    await db.del(key);
    res.json({ key: req.params.key, message: '刪除成功' });
  } catch (err) {
    if (err.code === 'LEVEL_NOT_FOUND') {
      return res.status(404).json({ error: '條目未找到' });
    }
    res.status(500).json({ error: err.message });
  }
});

// API: 批次刪除
app.post('/api/batch-delete', async (req, res) => {
  try {
    const { keys } = req.body;
    if (!Array.isArray(keys)) {
      return res.status(400).json({ error: 'keys 必須是陣列' });
    }
    const batch = db.batch();
    for (const key of keys) {
      batch.del(key);
    }
    await batch.write();
    res.json({ deleted: keys.length, message: '批次刪除成功' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 匯出資料庫為 JSON（支援搜尋/篩選）
app.get('/api/export', async (req, res) => {
  try {
    const query = req.query.q || '';
    const type = req.query.type || 'all';
    const minC = req.query.minC !== undefined ? parseFloat(req.query.minC) : undefined;
    const maxC = req.query.maxC !== undefined ? parseFloat(req.query.maxC) : undefined;
    const minD = req.query.minD !== undefined ? parseFloat(req.query.minD) : undefined;
    const maxD = req.query.maxD !== undefined ? parseFloat(req.query.maxD) : undefined;
    const minT = req.query.minT !== undefined ? parseFloat(req.query.minT) : undefined;
    const maxT = req.query.maxT !== undefined ? parseFloat(req.query.maxT) : undefined;
    const hasScalarFilter = [minC, maxC, minD, maxD, minT, maxT].some(v => v !== undefined);
    const hasFilter = query || type !== 'all' || hasScalarFilter;

    const entries = [];
    for await (const [key, value] of db.iterator()) {
      const keyStr = key.toString();

      if (hasFilter) {
        // 文字搜尋篩選
        if (query) {
          const valueStr = value.toString('utf8');
          const valueHex = value.toString('hex');
          if (!keyStr.includes(query) && !valueStr.includes(query) && !valueHex.includes(query)) continue;
        }
        // 類型篩選
        if (type === 'enc' && !isEncKey(keyStr)) continue;
        if (type === 'user' && isEncKey(keyStr)) continue;
        // 標量值篩選
        if (hasScalarFilter) {
          const m = parseMetrics(value);
          if (minC !== undefined && (m.c === undefined || m.c < minC)) continue;
          if (maxC !== undefined && (m.c === undefined || m.c > maxC)) continue;
          if (minD !== undefined && (m.d === undefined || m.d < minD)) continue;
          if (maxD !== undefined && (m.d === undefined || m.d > maxD)) continue;
          if (minT !== undefined && (m.t === undefined || m.t < minT)) continue;
          if (maxT !== undefined && (m.t === undefined || m.t > maxT)) continue;
        }
      }

      const formatted = formatValue(value);
      entries.push({
        key: keyStr,
        value: formatted.type === 'text' ? formatted.value : undefined,
        hex: formatted.hex,
        type: formatted.type
      });
    }

    res.setHeader('Content-Disposition', 'attachment; filename=chongkit-export.json');
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.json({ entries, exportTime: new Date().toISOString(), totalEntries: entries.length, filtered: hasFilter });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 匯入 JSON 資料
app.post('/api/import', async (req, res) => {
  try {
    const { entries } = req.body;
    if (!Array.isArray(entries)) {
      return res.status(400).json({ error: 'entries 必須是陣列' });
    }
    const batch = db.batch();
    let imported = 0;
    for (const entry of entries) {
      if (!entry.key) continue;

      let valueBuffer;
      if (entry.hex) {
        valueBuffer = Buffer.from(entry.hex, 'hex');
      } else if (entry.value !== undefined) {
        valueBuffer = Buffer.from(entry.value, 'utf8');
      } else {
        continue;
      }

      batch.put(entry.key, valueBuffer);
      imported++;
    }
    await batch.write();
    res.json({ imported, message: `成功匯入 ${imported} 筆資料` });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API: 同步工作副本回原始資料庫
app.post('/api/sync', async (req, res) => {
  try {
    if (dbMode !== 'copy') {
      return res.json({ success: true, message: '目前已是直接存取模式，無需同步' });
    }

    const dbPath = getDbPath(currentDbName);
    const workDir = getWorkDir(currentDbName);

    // 1. 關閉工作副本
    await db.close();
    console.log('工作副本已關閉，準備同步...');

    // 2. 嘗試開啟原始資料庫以偵測是否仍被鎖定
    try {
      const testDb = new ClassicLevel(dbPath, { keyEncoding: 'utf8', valueEncoding: 'buffer' });
      await testDb.open();
      await testDb.close();
    } catch (testErr) {
      // 仍被鎖定，重新開啟工作副本
      db = new ClassicLevel(workDir, { keyEncoding: 'utf8', valueEncoding: 'buffer', createIfMissing: false });
      await db.open();
      return res.status(409).json({
        success: false,
        message: '原始資料庫仍被 Rime 鎖定，請先關閉 Rime 輸入法後再同步'
      });
    }

    // 3. 將工作副本覆蓋回原始資料庫
    const origFiles = fs.readdirSync(dbPath);
    for (const file of origFiles) {
      if (file.startsWith('.') || file === 'lost') continue;
      fs.unlinkSync(path.join(dbPath, file));
    }
    const workFiles = fs.readdirSync(workDir);
    for (const file of workFiles) {
      if (file.startsWith('.') || file === 'lost' || file === 'LOCK') continue;
      fs.copyFileSync(path.join(workDir, file), path.join(dbPath, file));
    }
    console.log('工作副本已同步到原始資料庫');

    // 4. 直接連接原始資料庫
    db = new ClassicLevel(dbPath, { keyEncoding: 'utf8', valueEncoding: 'buffer' });
    await db.open();
    dbMode = 'original';
    originalLocked = false;

    res.json({ success: true, message: '同步成功！已切換為直接存取原始資料庫' });
  } catch (err) {
    if (!db || !db.status || db.status === 'closed') {
      try {
        db = new ClassicLevel(getWorkDir(currentDbName), { keyEncoding: 'utf8', valueEncoding: 'buffer', createIfMissing: false });
        await db.open();
      } catch (e) { /* 忽略 */ }
    }
    res.status(500).json({ success: false, message: '同步失敗: ' + err.message });
  }
});

// API: 重新整理工作副本（從原始資料庫重新複製）
app.post('/api/refresh-copy', async (req, res) => {
  try {
    if (dbMode !== 'copy') {
      return res.json({ success: true, message: '目前已是直接存取模式' });
    }

    const dbPath = getDbPath(currentDbName);
    const workDir = getWorkDir(currentDbName);

    await db.close();
    copyDatabase(dbPath, workDir);
    const lockFile = path.join(workDir, 'LOCK');
    if (fs.existsSync(lockFile)) fs.unlinkSync(lockFile);

    db = new ClassicLevel(workDir, { keyEncoding: 'utf8', valueEncoding: 'buffer', createIfMissing: false });
    await db.open();

    res.json({ success: true, message: '工作副本已從原始資料庫重新整理' });
  } catch (err) {
    res.status(500).json({ success: false, message: '重新整理失敗: ' + err.message });
  }
});

// 啟動伺服器
const databases = listDatabases();
const defaultDb = databases.includes('chongkit.userdb') ? 'chongkit.userdb' : databases[0];

initDB(defaultDb).then(() => {
  app.listen(PORT, () => {
    console.log(`\n========================================`);
    console.log(`  Rime 用戶詞典管理器已啟動`);
    console.log(`========================================`);
    console.log(`  存取位址: http://localhost:${PORT}`);
    console.log(`  可用資料庫: ${databases.join(', ')}`);
    console.log(`  當前資料庫: ${currentDbName} (${dbMode === 'original' ? '直接存取' : '工作副本'})`);
    if (dbMode === 'copy') {
      console.log(`  注意: 目前操作的是資料庫副本，修改不會自動同步到原始資料庫`);
      console.log(`  如需同步，請先關閉 Rime 輸入法，然後使用同步功能`);
    }
    console.log(`========================================\n`);
  });
}).catch(err => {
  console.error('啟動失敗:', err.message);
  process.exit(1);
});

// 優雅關閉
process.on('SIGINT', async () => {
  console.log('\n正在關閉資料庫...');
  if (db) await db.close();
  console.log('資料庫已關閉，再見！');
  process.exit(0);
});