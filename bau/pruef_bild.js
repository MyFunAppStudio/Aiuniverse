// Rendert alle drei Reiter mit erfundenen Daten und meldet jeden JS-Fehler.
const { chromium } = require('playwright');
const fs = require('fs');

const ECHT = JSON.parse(fs.readFileSync('/tmp/testdaten.json', 'utf8'));

const ANTWORT = {
  '/api/stand': {
    kanaele: [{ key: 'test', name: 'AiUniverse Test', thema: 'Archäologie' }],
    apis: { text: 1, bilder: 1, stimme: 1, ref: 0, animation: 0, avatar: 0 },
    laeuft: false, fortschritt: 0, meldung: ''
  },
  '/api/kanal': {
    modus: 'szenen', sprachen: ['de'], format: '9_16', stimme_an: true, musik_an: true,
    tempo: 'normal', nachlauf: 0.9, musik_leise: 12, musik_laut: 75, musik_ein: 1, musik_aus: 1.5,
    prompt: '', kling_anteil: 0, kling_prompt: ''
  },
  '/api/modelle': {
    slots: ['ref', 'text', 'bilder', 'stimme', 'video', 'musik', 'sound', 'avatar'],
    apis: {
      ref: [], text: [{ name: 'Claude', url: 'claude-opus', preis: '0.02', key: true, aktiv: true }],
      bilder: [], stimme: [], video: [], musik: [], sound: [], avatar: []
    }
  },
  '/api/figuren': { figuren: [], plaetze: [['a', 'Platz 1'], ['b', 'Platz 2']] },
  '/api/telegram': { bereit: false, token: '', chat: '', adresse: '' },
  '/api/videos': [{ name: 'pompeji_folge1.mp4', zeit: '2026-11-08 20:14', groesse: 18400000, dauer: 63 }],
  '/api/preis': { modus: 'szenen', szenen: 2, gesprochen: 2, stimme: 0.1, animiert: 0, je_clip: 0, gesamt: 0.1, sekunden: 13 },
  '/api/themen': { offen: [], erledigt: [] },
  '/api/arten': { arten: [] },
  '/api/vorlagen': { vorlagen: {} },
  '/api/schluessel': { schluessel: { anthropic: true, fal: true } },
  '/api/schriften': { schriften: [] },
  '/api/guthaben': { ok: true, betrag: 12.5, waehrung: 'USD' },
  '/api/geschichte': { eintraege: [] },
  '/api/clip_stand': { laeuft: false },
  '/api/kanal': {
    modus: 'szenen', sprachen: ['de'], format: '9_16', stimme_an: true, musik_an: true,
    tempo: 'normal', nachlauf: 0.9, musik_leise: 12, musik_laut: 75, musik_ein: 1, musik_aus: 1.5,
    prompt: '', kling_anteil: 0, kling_prompt: ''
  },
  '/api/szenen': ECHT['/api/szenen'],
  '/api/darsteller': ECHT['/api/darsteller'],
  '/api/abspann': ECHT['/api/abspann']
};

(async () => {
  const html = fs.readFileSync('/home/claude/aiuniverse/dashboard2.html', 'utf8');
  const browser = await chromium.launch();
  const seite = await browser.newPage({ viewport: { width: 390, height: 844 } });

  const fehler = [];
  seite.on('pageerror', e => fehler.push('JS: ' + e.message));
  seite.on('console', m => { if (m.type() === 'error') fehler.push('Konsole: ' + m.text()); });

  await seite.route('**/*', async route => {
    const u = new URL(route.request().url());
    if (u.pathname === '/') return route.fulfill({ contentType: 'text/html', body: html });
    for (const p in ANTWORT) {
      if (u.pathname === p) return route.fulfill({ contentType: 'application/json', body: JSON.stringify(ANTWORT[p]) });
    }
    if (u.pathname.startsWith('/api/')) return route.fulfill({ contentType: 'application/json', body: '{"ok":true}' });
    return route.fulfill({ status: 200, body: '' });
  });

  await seite.goto('http://pruef.ungueltig/', { waitUntil: 'networkidle' });
  await seite.waitForTimeout(700);

  for (const [id, name] of [['machen', 'Video machen'], ['darsteller', 'Darsteller'], ['einst', 'Einstellungen']]) {
    await seite.evaluate(t => { S.tab = t; zeichne(); }, id);
    await seite.waitForTimeout(600);
    const z = await seite.evaluate(() => ({
      karten: document.querySelectorAll('.karte').length,
      regler: document.querySelectorAll('input[type=range]').length,
      mehr: document.querySelectorAll('details.mehr').length,
      falt: document.querySelectorAll('details.falt').length,
      leer: document.body.innerText.trim().length
    }));
    console.log(`  ${name.padEnd(14)} Karten ${String(z.karten).padStart(2)} · Text ${String(z.leer).padStart(5)} Zeichen · mehr-Falten ${z.mehr} · Abschnitte ${z.falt} · Regler ${z.regler}`);
    await seite.screenshot({ path: `/tmp/schau_${id}.png`, fullPage: true });
  }

  // Szenenkarte: was ist ohne Aufklappen sichtbar?
  await seite.evaluate(() => { S.tab = 'machen'; zeichne(); });
  await seite.waitForTimeout(400);
  const sicht = await seite.evaluate(() => {
    const k = document.querySelector('.szn');
    if (!k) return null;
    const d = k.querySelector('details.mehr');
    const offen = [];
    k.querySelectorAll('.szz, textarea, img, video, button').forEach(n => {
      if (d && d.contains(n)) return;
      const t = (n.innerText || n.placeholder || n.tagName).trim().slice(0, 34);
      if (t) offen.push(t.replace(/\s+/g, ' '));
    });
    return offen;
  });
  console.log('\n  Ohne Aufklappen sichtbar je Szene:');
  (sicht || []).forEach(x => console.log('    · ' + x));

  // mit Alte Funktionen an
  await seite.evaluate(() => { S.alt = true; S.tab = 'machen'; zeichne(); });
  await seite.waitForTimeout(400);
  const alt = await seite.evaluate(() => document.querySelectorAll('.szn .p89').length);
  console.log(`\n  Alte Funktionen an: KI-Animation-Haken je Szene wieder da = ${alt}`);

  // Bleiben die Laden offen, wenn neu gezeichnet wird?
  await seite.evaluate(() => { S.tab = 'einst'; S.offen = {}; zeichne(); });
  await seite.waitForTimeout(300);
  const falttest = await seite.evaluate(async () => {
    const auf = () => [...document.querySelectorAll('details.falt')]
      .filter(d => d.open).map(d => d.querySelector('summary').innerText.trim());
    const d = [...document.querySelectorAll('details.falt')][2];
    const name = d.querySelector('summary').innerText.trim();
    d.open = true; d.dispatchEvent(new Event('toggle'));
    const vorher = auf();
    zeichne();
    await new Promise(r => setTimeout(r, 120));
    return { geoeffnet: name, vorher, nachher: auf() };
  });
  console.log(`\n  Lade "${falttest.geoeffnet}" geoeffnet, dann neu gezeichnet:`);
  console.log(`    vorher offen:  ${JSON.stringify(falttest.vorher)}`);
  console.log(`    nachher offen: ${JSON.stringify(falttest.nachher)}`);

  // Szenen-Lade "mehr einstellen"
  await seite.evaluate(() => { S.tab = 'machen'; zeichne(); });
  await seite.waitForTimeout(300);
  const mehrtest = await seite.evaluate(async () => {
    const d = document.querySelector('details.mehr');
    if (!d) return 'keine mehr-Lade da';
    d.open = true; d.dispatchEvent(new Event('toggle'));
    zeichne();
    await new Promise(r => setTimeout(r, 120));
    return document.querySelector('details.mehr').open ? 'bleibt offen' : 'KLAPPT ZU';
  });
  console.log(`  Szenen-Lade "mehr einstellen" nach dem Neuzeichnen: ${mehrtest}`);

  await browser.close();
  if (fehler.length) { console.log('\nFEHLER:'); fehler.forEach(f => console.log('  ' + f)); process.exit(1); }
  console.log('\nOK  keine JS-Fehler in allen drei Reitern');
})();
