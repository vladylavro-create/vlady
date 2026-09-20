# Bot Telegram — Circolari Castelli 2FI

Il programma è pronto. **Non è ancora online**: occorre creare il bot Telegram e collegarlo al proprio account GitHub.

## Cosa fa

- Controlla l'archivio pubblico ufficiale dell'IIS Benedetto Castelli di Brescia ogni 15 minuti, giorno e notte, con il PC spento dopo l'attivazione su GitHub.
- Legge titolo, destinatari e testo dei PDF, senza abbonamenti ad AI.
- Include 2FI (anche scritta 2 FI o 2 F I), classi seconde, biennio e comunicazioni generali per studenti/famiglie.
- Esclude altre classi specifiche, altri anni, triennio, esami finali, corsi serali e avvisi solo per il personale quando sono riconoscibili.
- Invia titolo, motivo della selezione e link al PDF. Nei casi incerti manda un avviso **DA VERIFICARE**.
- Memorizza i documenti elaborati; ricontrolla giornalmente i PDF degli ultimi 60 giorni per rilevare modifiche anche allo stesso indirizzo.
- Primo avvio: al massimo 10 avvisi pertinenti degli ultimi 7 giorni. I più vecchi entrano nella memoria senza intasare Telegram.

Il filtro è euristico, non un'AI a pagamento: può sbagliare, specialmente con destinatari impliciti, tabelle o scansioni. Non accede al registro riservato. La scuola rimane la fonte ufficiale. La classe resta 2FI finché non si modifica il programma, anche al cambio di anno.

## Attivazione gratuita

1. Su Telegram apri **[@BotFather](https://t.me/BotFather)**, invia `/newbot`, scegli nome e username terminante in `bot`. Conserva il token; non pubblicarlo e non inviarlo in chat ad altre persone.
2. Apri il bot che hai creato e premi **Avvia**.
3. Sul PC fai doppio clic su **TROVA_CHAT_TELEGRAM.bat**. Inserisci il token nella finestra (non viene mostrato né salvato), poi invia al tuo bot il codice indicato. Il programma restituisce il tuo `TELEGRAM_CHAT_ID`. Richiede Python 3.11, presente sul PC usato per preparare il progetto.
4. Su [GitHub](https://github.com/new) crea un repository **pubblico** chiamato `castelli-2fi-bot`. Per mantenere il funzionamento gratuito usa i runner standard già configurati, senza attivare servizi a pagamento.
5. Carica nella radice del repository `bot.py`, `requirements.txt`, `test_bot.py` e `LEGGIMI.md`.
6. Il file nascosto `.github/workflows/circolari.yml` è indispensabile. Se non compare durante il caricamento, su GitHub scegli **Add file → Create new file**, usa esattamente `.github/workflows/circolari.yml` come nome e copia il contenuto del file locale. Conferma con **Commit changes** sul branch predefinito.
7. Nel repository vai in **Settings → Secrets and variables → Actions → New repository secret**. Crea:
   - `TELEGRAM_BOT_TOKEN`: il token di BotFather.
   - `TELEGRAM_CHAT_ID`: il numero ottenuto al punto 3.
8. Vai in **Actions → Circolari 2FI → Run workflow → Run workflow**. Se richiesto, abilita Actions. Dopo il primo controllo completato riceverai il messaggio di attivazione. Da allora la pianificazione ripete i controlli automaticamente.
9. Verifica che il controllo sia verde e che `state.json` sia stato creato nel repository. Se il salvataggio viene negato, abilita **Settings → Actions → General → Workflow permissions → Read and write permissions**.

**Non caricare token, chat ID, `.env`, altri progetti o file personali.** `state.json` contiene soltanto metadati delle circolari pubbliche e le decisioni del filtro. Non contiene credenziali o dati della chat.

## Costi e continuità: limiti reali

Telegram Bot API e le librerie utilizzate non richiedono un abbonamento. GitHub Actions con runner standard in repository pubblici è gratuito secondo le condizioni attuali. Il workflow non usa servizi AI, runner maggiorati, cache o artifact a pagamento.

La pianificazione gira ai minuti 07, 22, 37 e 52 di ogni ora. GitHub può ritardare o saltare esecuzioni; il successivo controllo recupera le circolari ancora presenti nell'archivio. Non è un servizio con disponibilità garantita. Nei repository pubblici GitHub disabilita le pianificazioni dopo 60 giorni senza attività: il bot salva lo stato dei controlli, ma controlla comunque Actions durante le lunghe pause e riabilita il workflow se disattivato. Nessun servizio gratuito può essere promesso invariato per sempre.

In caso di errore del sito/PDF, il documento non viene segnato come elaborato e viene riprovato. Gli errori rendono rosso il workflow: abilita le notifiche GitHub per le esecuzioni fallite. Telegram non può notificare un arresto totale del servizio che lo esegue. Una rara interruzione dopo l'invio ma prima del salvataggio può causare una notifica duplicata; l'API Telegram non offre una transazione unica con GitHub.

Non avviare copie contemporanee del bot su PC e GitHub: ciascuna avrebbe la sua memoria. Non cancellare `state.json` per evitare una nuova inizializzazione.

## Verifica locale senza Telegram

Con Python 3.11 o successivo, nella cartella del progetto:

```text
python -m pip install -r requirements.txt
python -m unittest discover -s . -v
python bot.py --dry-run
```

L'anteprima scrive `preview.json`, non manda messaggi e non modifica la memoria. `--dry-run --limit 10` limita la prova ai 10 documenti più recenti. Per l'esecuzione reale servono le variabili d'ambiente `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`; su GitHub sono già fornite tramite secrets.

## Fonti

- [Archivio ufficiale Castelli](https://www.iiscastelli.edu.it/pager.aspx?order=name&page=circolari)
- [Creazione bot Telegram](https://core.telegram.org/bots/tutorial)
- [Gratuità di GitHub Actions per repository pubblici](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Limiti della pianificazione GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
