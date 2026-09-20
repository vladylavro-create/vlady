"""Circolari pubbliche Castelli -> Telegram. Solo libreria standard + pypdf."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pypdf import PdfReader

SOURCE = 'https://www.iiscastelli.edu.it/pager.aspx?order=name&page=circolari'
ROOT = Path(__file__).resolve().parent
MONTHS = 'gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split()


def normalized(value):
    value = re.sub(r'(?im)^\s*prot\.?[^\n]*', '', value)
    value = unicodedata.normalize('NFKD', value.lower())
    return re.sub(r'\s+', ' ', ''.join(c for c in value if not unicodedata.combining(c))).strip()


class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cells, self.cell, self.link = [], [], None, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self.cells, self.link = [], None
        if tag == 'td':
            self.cell = ''
        if tag == 'a':
            href = attrs.get('href', '')
            path = unquote(urlsplit(urljoin(SOURCE, href)).path).lower()
            if '/documents/circolari/' in path and path.endswith('.pdf'):
                url = urljoin(SOURCE, href)
                if urlsplit(url).hostname == 'www.iiscastelli.edu.it':
                    self.link = quote(unquote(url), safe=':/?=&')

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.cells.append(self.cell.strip())
            self.cell = None
        if tag == 'tr' and self.link and len(self.cells) >= 3:
            day, month, year = self.cells[-1].split()
            date = datetime(int(year), MONTHS.index(month.lower()) + 1, int(day), tzinfo=timezone.utc)
            self.rows.append(dict(url=self.link, title=self.cells[-2], date=date.isoformat()))


def parse_index(html):
    parser = IndexParser()
    parser.feed(html)
    rows = {r['url']: r for r in parser.rows}
    if not rows:
        raise RuntimeError('Nessuna circolare trovata: sito non disponibile o formato cambiato.')
    return sorted(rows.values(), key=lambda r: (r['date'], r['title']), reverse=True)


def fetch(url):
    # No cookie, registro elettronico o credenziali scolastiche.
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'CastelliCircolari/1.0 (public school notices)'}), timeout=35) as response:
                data = response.read(20_000_001)
                if len(data) > 20_000_000:
                    raise RuntimeError('Documento troppo grande (oltre 20 MB).')
                return data
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError('Download non riuscito dopo tre tentativi.') from None
            time.sleep(2 ** attempt)


def read_pdf(data):
    if not data.startswith(b'%PDF'):
        raise RuntimeError('Il sito non ha restituito un PDF valido.')
    return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages)


CLASS = r'\b([1-5])\s*[°^ª]?\s*([a-l])\s*(en|el|tl|mm|ch|[icmeab])\b(?!\s+(?:docenti|studenti|genitori|famiglie|alunni)\b)'
YEARS = {'prime': 1, 'prima': 1, 'seconde': 2, 'seconda': 2, 'terze': 3, 'terza': 3,
         'quarte': 4, 'quarta': 4, 'quinte': 5, 'quinta': 5}


def scope(text):
    classes = {''.join(m) for m in re.findall(CLASS, text)}
    years = set()
    for match in re.finditer(r'class[ei]\s+(?:per\s+)?((?:(?:prime|seconde|terze|quarte|quinte|prima|seconda|terza|quarta|quinta|[1-5][°^ªa]?)(?![a-z0-9])\s*[,/e-]?\s*)+)', text):
        for word in re.findall(r'prime|seconde|terze|quarte|quinte|prima|seconda|terza|quarta|quinta|[1-5]', match[1]):
            years.add(YEARS[word] if word in YEARS else int(word))
    return classes, years


def decide(title, body):
    """Return include/review/exclude plus an explainable Italian reason."""
    title, body = normalized(title), normalized(body)
    # Destinatari prima dell'oggetto: il corpo può citare classi non destinatarie.
    header = body.split('oggetto', 1)[0] if 'oggetto' in body else ''
    header = header[-2400:]
    audience = title + ' ' + header
    classes, years = scope(audience)
    if '2fi' in classes:
        return 'include', 'La circolare nomina la 2FI tra i destinatari o nel titolo.'
    if classes and '2fi' not in classes and not years:
        return 'exclude', 'Destinata ad altre classi specifiche.'
    if 2 in years:
        return 'include', 'Riguarda le classi seconde.'
    if years:
        return 'exclude', 'Destinata ad anni diversi dalla seconda.'
    if re.search(r'\btriennio\b|esam[ei] di stato|maturita', audience):
        return 'exclude', 'Riguarda il triennio o gli esami finali.'
    if re.search(r'\bbiennio\b', audience):
        return 'include', 'Riguarda il biennio, quindi anche la seconda.'
    students = bool(re.search(r'student|alunn|famigli|genitor', header))
    # Il modello Castelli elenca spesso TUTTE le categorie nell'intestazione,
    # anche negli avvisi rivolti soltanto ai docenti: non basta quell'elenco.
    template_header = all(re.search(p, header) for p in (r'docenti', r'famigli', r'student|alunn', r'personale\s+ata'))
    if template_header:
        students = False
    if re.search(r'\bseral[ei]\b|secondo livello', audience) and not re.search(r'diurn|tutt[ei] (?:le classi|gli studenti)', audience):
        return 'exclude', 'Destinata ai corsi serali.'
    staff_topic = r'collegio docenti|dipartiment|nomina|nomine|collaboratori dirigente|funzioni strumentali|docenti in ingresso|segretari consigli|coordinatori di classe|materiali per docenti|disponibilita docenti|ore a disposizione|comunicazione supplenze|codici isa|comunicazione ora di colloquio|comunicazione orario attivita progettuali|adesione.*personale|polizza.*personale|spese sanitarie.*personale'
    if re.search(staff_topic, title) and not students:
        return 'exclude', 'Comunicazione organizzativa per il personale.'
    if header and not template_header and re.search(r'docenti|personale|\bata\b', header) and not students:
        if not re.search(r'sciopero|chiusur|sospensione.*lezioni', title):
            return 'exclude', 'Destinatari: personale della scuola.'
    # Se titolo e destinatari non delimitano la platea, controlla il contenuto.
    if not students:
        content = body.split('oggetto', 1)[-1]
        body_classes, body_years = scope(content)
        if '2fi' in body_classes:
            return 'include', 'La 2FI è citata nel contenuto.'
        if 2 in body_years or 'biennio' in body:
            return 'include', 'Il contenuto comprende le classi seconde o il biennio.'
        if body_classes and '2fi' not in body_classes:
            return 'exclude', 'Il contenuto riguarda altre classi specifiche.'
        if body_years:
            return 'exclude', 'Il contenuto riguarda altri anni di corso.'
    if students:
        return 'include', 'Avviso agli studenti o alle famiglie senza restrizioni ad altre classi.'
    if re.search(r'calendario scolastico|orario.*(?:lezion|diurno)|primo giorno|informazioni generali|sciopero|chiusur|evacuaz|assemblea.*istituto|libri di testo|permessi.*entrat|colloqui.*famigli|divieto di fumo|pause didattiche|studenti atleti|studenti non avvalentesi|ingressi posticipati|uscite anticipate', title):
        return 'include', 'Avviso di interesse generale per la vita scolastica.'
    return 'review', 'Possibile interesse: i destinatari non sono chiari; verifica il PDF.'


def telegram(method, data):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Manca TELEGRAM_BOT_TOKEN nei secrets.')
    request = Request(f'https://api.telegram.org/bot{token}/{method}',
                      data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError):
        # Non stampare mai l'URL: contiene il token.
        raise RuntimeError('Telegram non raggiungibile o credenziali/chat non valide.') from None
    if not result.get('ok'):
        raise RuntimeError('Telegram ha rifiutato la richiesta.')
    return result['result']


def send(text):
    chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not re.fullmatch(r'-?\d+', chat):
        raise RuntimeError('Manca TELEGRAM_CHAT_ID numerico nei secrets.')
    telegram('sendMessage', {'chat_id': chat, 'text': text[:4000], 'link_preview_options': {'is_disabled': True}})


def save(state, path):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def run(dry_run=False, limit=0):
    now = datetime.now(timezone.utc)
    path = ROOT / 'state.json'
    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'documents': {}}
    first = not state.get('initialized')
    rows = parse_index(fetch(SOURCE).decode('utf-8-sig'))
    if not dry_run:
        # Valida la destinazione prima di segnare documenti come elaborati.
        if not os.environ.get('TELEGRAM_CHAT_ID'):
            raise RuntimeError('Configura TELEGRAM_CHAT_ID prima dell’avvio.')
        telegram('getMe', {})
    failures, report, sent = 0, [], 0
    for row in rows[:limit or None]:
        key = hashlib.sha256(row['url'].encode()).hexdigest()
        old = state['documents'].get(key, {})
        age = (now - datetime.fromisoformat(row['date'])).days
        # Ogni quarto d'ora le novità, una volta al giorno revisioni degli ultimi 60 giorni.
        if not dry_run and old and (old.get('checked') == now.date().isoformat() or age > 60):
            continue
        try:
            data = fetch(row['url'])
            digest = hashlib.sha256(data).hexdigest()
            if old.get('sha256') == digest:
                old['checked'] = now.date().isoformat()
                continue
            body = read_pdf(data)
            decision, reason = decide(row['title'], body)
            if len(normalized(body)) < 80:
                title_decision, title_reason = decide(row['title'], '')
                if title_decision == 'exclude':
                    decision, reason = title_decision, title_reason
                else:
                    decision, reason = 'review', 'PDF non leggibile automaticamente: verifica i destinatari.'
            item = {**row, 'sha256': digest, 'checked': now.date().isoformat(), 'decision': decision, 'reason': reason}
            report.append(item)
            if dry_run:
                continue
            # Al primo avvio solo ultimi 7 giorni, massimo 10 notifiche; il resto è baseline.
            notify = decision != 'exclude' and (not first or (age <= 7 and sent < 10))
            if notify:
                label = 'DA VERIFICARE' if decision == 'review' else 'CIRCOLARE PER TE'
                if old:
                    label = 'AGGIORNAMENTO · ' + label
                send(f'{label} · 2FI Castelli\n\n{row["title"]}\n\n{reason}\n\n{row["url"]}')
                sent += 1
                time.sleep(1.1)
            state['documents'][key] = item
            save(state, path)
        except Exception as exc:
            failures += 1
            # Non registrare il documento: sarà riprovato al prossimo controllo.
            print(f'ERRORE documento {key[:10]}: {type(exc).__name__}', file=sys.stderr)
    if dry_run:
        (ROOT / 'preview.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        for item in report:
            print(f'{item["decision"]:7} | {item["title"]} | {item["reason"]}')
    else:
        if first and not failures:
            send('Bot 2FI Castelli attivato. Controlli previsti ogni 15 minuti, giorno e notte. '
                 'Riceverai circolari pertinenti e avvisi da verificare se i destinatari non sono chiari. '
                 'Al primo avvio mostro al massimo 10 avvisi degli ultimi 7 giorni. '
                 'Non sono un servizio ufficiale: il filtro può sbagliare.')
            state['initialized'] = True
        if not failures:
            # Aggiornamento giornaliero: prova dell'ultimo controllo riuscito.
            state['last_success_date'] = now.date().isoformat()
        save(state, path)
    print(f'Controllo completato: {len(report)} analizzate, {sent} inviate, {failures} errori.')
    if failures:
        raise RuntimeError('Controllo incompleto: i documenti falliti verranno riprovati.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Anteprima senza Telegram e senza modificare lo stato')
    parser.add_argument('--limit', type=int, default=0, help='Solo anteprima: limita il numero di PDF')
    args = parser.parse_args()
    if args.limit and not args.dry_run:
        parser.error('--limit richiede --dry-run')
    try:
        run(args.dry_run, args.limit)
    except Exception as exc:
        print(f'Controllo fallito: {type(exc).__name__}. Verifica sito, connessione e secrets.', file=sys.stderr)
        sys.exit(1)
