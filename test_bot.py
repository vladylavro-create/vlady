import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import bot


class Filters(unittest.TestCase):
    def test_audiences(self):
        cases = [
            ('Permessi permanenti entrate uscite', 'Circ 046\nProt. A22/1\nAi docenti\nAgli studenti\nAlle famiglie\nOGGETTO: Permessi', 'include'),
            ('Coordinatori di classe 26-27 corsi diurni', 'Ai docenti OGGETTO: Nomine', 'exclude'),
            ('Consigli di classe per 1^ e 3^ diurno', '', 'exclude'),
            ('Docenti in ingresso - incontro', 'Ai docenti\nAlle famiglie\nAgli studenti\nAl personale ata\nOGGETTO: Incontro docenti', 'exclude'),
            ('Orario definitivo diurno', 'Ai docenti\nAlle famiglie\nAgli studenti\nAl personale ata\nOGGETTO: Orario', 'include'),
            ('Primo giorno di scuola', 'Oggetto: Inizio. 1AE 1BE ore 8. Classi 2° - 3° - 4° - 5° ore 9.', 'include'),
            ('Progetto studenti atleti', 'Oggetto: Requisiti sportivi. 4x e 4-; 2o o 3° posto; vela 2.4 MR.', 'include'),
            ('Laboratorio', 'Oggetto: 5AEN e 4BEN', 'exclude'),
            ('Uscita didattica 5FI', 'Agli studenti della classe 5FI Oggetto: Uscita', 'exclude'),
            ('Orientamento classi quinte', 'Agli studenti Oggetto: Orientamento', 'exclude'),
            ('Orientamento classi terze, quarte e quinte', '', 'exclude'),
            ('Attività classi prime e seconde', '', 'include'),
            ('Attività classi 1 e 2', '', 'include'),
            ('Uscita 2 FI', '', 'include'),
            ('Uscita 2 F I e 5FI', '', 'include'),
            ('Uscita 2AI', 'Destinata alla 2AI', 'exclude'),
            ('Uscita 12FI', '', 'review'),
            ('Progetto', 'Agli studenti delle classi seconde Oggetto: Progetto', 'include'),
            ('Incontro biennio', '', 'include'),
            ('Incontro triennio', '', 'exclude'),
            ('Calendario scolastico', 'Agli studenti e alle famiglie Oggetto: Calendario. Le quinte finiscono prima.', 'include'),
            ('Collegio docenti', 'Ai docenti Oggetto: Riunione', 'exclude'),
            ('Assicurazione', 'Ai docenti e al personale ATA Oggetto: Polizza', 'exclude'),
            ('Sciopero', 'Al personale docente Oggetto: possibili disagi alle lezioni', 'include'),
            ('Comunicazione', 'Ai genitori e agli alunni Oggetto: Assemblea', 'include'),
            ('Progetto corso serale', '', 'exclude'),
            ('Progetto nuovo', 'Non contiene destinatari identificabili.', 'review'),
        ]
        for title, body, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(bot.decide(title, body)[0], expected)

    def test_index_validates_and_encodes(self):
        html = '<table><tr><td></td><td><a href="Documents/circolari/CIRC 001.pdf">CIRC 001.pdf</a></td><td>03 settembre 2026</td></tr></table>'
        result = bot.parse_index(html)
        self.assertIn('CIRC%20001.pdf', result[0]['url'])
        self.assertTrue(result[0]['date'].startswith('2026-09-03'))
        with self.assertRaises(RuntimeError):
            bot.parse_index('<html>Manutenzione</html>')

    def test_atomic_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            bot.save({'documents': {}}, path)
            self.assertEqual(json.loads(path.read_text()), {'documents': {}})

    def test_failed_delivery_retried_and_success_not_duplicated(self):
        row = {'url': 'https://www.iiscastelli.edu.it/Documents/circolari/test.pdf',
               'title': 'Calendario scolastico', 'date': bot.datetime.now(bot.timezone.utc).isoformat()}
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'ROOT', Path(folder)), \
             patch.object(bot, 'parse_index', return_value=[row]), \
             patch.object(bot, 'fetch', return_value=b'%PDF test'), \
             patch.object(bot, 'read_pdf', return_value='Agli studenti e alle famiglie Oggetto: Calendario scolastico. ' * 3), \
             patch.object(bot, 'telegram'), patch.object(bot.time, 'sleep'), \
             patch.dict(bot.os.environ, {'TELEGRAM_CHAT_ID': '123'}):
            bot.save({'documents': {}, 'initialized': True}, Path(folder) / 'state.json')
            with patch.object(bot, 'send', side_effect=RuntimeError('failed')):
                with self.assertRaises(RuntimeError):
                    bot.run()
            self.assertEqual(json.loads((Path(folder) / 'state.json').read_text())['documents'], {})
            with patch.object(bot, 'send') as sender:
                bot.run()
                bot.run()
                self.assertEqual(sender.call_count, 1)


if __name__ == '__main__':
    unittest.main()
