import google.generativeai as genai
import json
import os
try:
    from gtts import gTTS
    from playsound import playsound
    TTS_ENABLED = True
except ImportError:
    TTS_ENABLED = False
    print("ATTENZIONE: Librerie gTTS o playsound non trovate. Il Text-to-Speech non sarà disponibile.")
    print("Per abilitare il TTS, installale con: pip install gTTS playsound")


# --- CONFIGURAZIONE DEL BOT --
BOT_NAME = "Branza" # Scegli il nome del tuo bot
BOT_PERSONA_INSTRUCTION = f"Ti chiami {BOT_NAME}. Sei un assistente sarcastico, estremamente intelligente, kawaii ma un po' impaziente. Rispondi in modo conciso e con un tocco di umorismo secco."
# Esempio alternativo di personalità:
# BOT_PERSONA_INSTRUCTION = f"Ti chiami {BOT_NAME}. Sei un assistente virtuale amichevole, empatico e molto paziente. Ti piace aiutare gli utenti e spiegare le cose in modo semplice."

# Configuration for Gemini API
# Considera di usare variabili d'ambiente per la chiave API per maggiore sicurezza
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDcafgm71EwWOEewFnQWgrCnGcLjTNgpeg") # Sostituisci con la tua chiave se non usi var d'ambiente
if API_KEY == "AIzaSyDcafgm71EwWOEewFnQWgrCnGcLjTNgpeg" and not os.getenv("GEMINI_API_KEY"):
    print("ATTENZIONE: Stai usando una chiave API di esempio. Sostituiscila con la tua vera chiave API o impostala come variabile d'ambiente GEMINI_API_KEY.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest') # Aggiornato a un modello più recente

HISTORY_FILE = "conversation_history.json"
TTS_TEMP_FILE = "temp_response.mp3" # File temporaneo per l'audio TTS

def speak_text(text, lang='it', tld='com'): # Aggiunto tld, default 'com'
    """Converte il testo in parlato e lo riproduce, se TTS è abilitato."""
    if not TTS_ENABLED or not text or not text.strip():
        return # Non fare nulla se TTS non è abilitato o il testo è vuoto

    try:
        # Usa il parametro tld
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        tts.save(TTS_TEMP_FILE)
        playsound(TTS_TEMP_FILE)
    except Exception as e:
        print(f"Errore durante la riproduzione dell'audio TTS: {e}")
    finally:
        # Rimuovi il file audio temporaneo se esiste
        if os.path.exists(TTS_TEMP_FILE):
            try:
                os.remove(TTS_TEMP_FILE)
            except Exception as e:
                # Non critico se non si riesce a rimuovere, ma è bene saperlo
                print(f"Avviso: errore durante la rimozione del file audio temporaneo '{TTS_TEMP_FILE}': {e}")

def load_conversation_history(filename=HISTORY_FILE):
    """Carica la cronologia della conversazione da un file JSON."""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
                # Verifica se il formato è quello vecchio (lista di tuple/liste)
                # o quello nuovo (dizionario con 'persona' e 'chat_log')
                if isinstance(history_data, list):
                     # Converti dal vecchio formato se necessario, ma idealmente la nuova cronologia sarà già corretta
                    if all(isinstance(item, list) and len(item) == 2 for item in history_data):
                        print(f"Avviso: Rilevato vecchio formato di cronologia. La personalità potrebbe non essere mantenuta correttamente dalle sessioni precedenti.")
                        return [tuple(item) for item in history_data]
                    else:
                        print(f"Avviso: il formato della cronologia (lista) in {filename} non è valido. Inizio con una nuova cronologia.")
                        return []
                elif isinstance(history_data, dict) and "chat_log" in history_data:
                    # Nuovo formato: carica la chat_log
                    # Potresti voler confrontare history_data.get("persona_instruction") con BOT_PERSONA_INSTRUCTION
                    # e avvisare l'utente se sono diverse, o decidere come gestirlo.
                    # Per ora, carichiamo solo la chat_log. La personalità corrente verrà applicata.
                    if history_data.get("persona_instruction") != BOT_PERSONA_INSTRUCTION:
                        print(f"Avviso: La personalità salvata in {filename} è diversa da quella corrente. Verrà usata la personalità corrente.")
                    chat_log = history_data["chat_log"]
                    if isinstance(chat_log, list) and all(isinstance(item, list) and len(item) == 2 for item in chat_log):
                        return [tuple(item) for item in chat_log]
                    else:
                        print(f"Avviso: il formato di chat_log in {filename} non è valido. Inizio con una nuova cronologia.")
                        return []
                else:
                    print(f"Avviso: il formato della cronologia in {filename} non è riconosciuto. Inizio con una nuova cronologia.")
                    return []
        except json.JSONDecodeError:
            print(f"Avviso: errore nel decodificare {filename}. Inizio con una nuova cronologia.")
            return []
        except Exception as e:
            print(f"Errore durante il caricamento della cronologia: {e}. Inizio con una nuova cronologia.")
            return []
    return []

def save_conversation_history(history, persona_instr, filename=HISTORY_FILE):
    """Salva la cronologia della conversazione e l'istruzione di personalità su un file JSON."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            # Salva sia la cronologia che l'istruzione di personalità
            data_to_save = {
                "persona_instruction": persona_instr,
                "chat_log": history
            }
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Errore durante il salvataggio della cronologia: {e}")

# Carica la cronologia all'avvio
# Nota: la personalità caricata dal file (se presente) non viene usata per sovrascrivere
# BOT_PERSONA_INSTRUCTION definito nello script. Lo script usa sempre la sua definizione corrente.
conversation_history = load_conversation_history()

def get_gemini_response(prompt):
    global conversation_history
    global BOT_PERSONA_INSTRUCTION # Assicurati di avere accesso all'istruzione

    messages = []

    # 1. Aggiungi l'istruzione sulla personalità come primo messaggio "user"
    # Questo aiuta a "impostare la scena" per il modello ad ogni turno.
    # Per modelli che supportano un ruolo "system", quello sarebbe preferibile.
    # Con l'API attuale di google.generativeai, un messaggio "user" iniziale funziona bene.
    messages.append({"role": "user", "parts": [BOT_PERSONA_INSTRUCTION]})
    # Aggiungiamo una finta risposta "model" per mantenere la struttura alternata user/model
    # Questo è un trucco comune quando si usano istruzioni di sistema come messaggi utente.
    messages.append({"role": "model", "parts": ["Ok, ho capito. Procediamo."]})


    # 2. Aggiungi la cronologia della conversazione esistente
    for user_message, model_message in conversation_history:
        messages.append({"role": "user", "parts": [user_message]})
        messages.append({"role": "model", "parts": [model_message]})

    # 3. Aggiungi la nuova domanda dell'utente
    messages.append({"role": "user", "parts": [prompt]})

    try:
        # Alcuni modelli/API preferiscono che la chat venga iniziata con `start_chat`
        # e poi si usi `chat.send_message`. Per `generate_content` con una lista
        # completa di messaggi, l'approccio attuale è corretto.
        # Se si volesse usare `start_chat` per mantenere lo stato lato server (se supportato per questo caso d'uso):
        # chat = model.start_chat(history=messages[:-1]) # Escludi l'ultimo prompt utente
        # response = chat.send_message(messages[-1]['parts'])

        response = model.generate_content(messages)
        return response.text
    except Exception as e:
        # Potrebbe essere utile loggare l'eccezione completa per il debug
        # import traceback
        # print(traceback.format_exc())
        print(f"Errore durante la generazione della risposta da Gemini: {e}")
        return "Mi dispiace, ho riscontrato un errore e non posso rispondere ora."

# --- Ciclo Principale della Chat ---
print(f"Stai chattando con {BOT_NAME}. Digita 'exit' per uscire.")
if BOT_PERSONA_INSTRUCTION:
    print(f"({BOT_NAME} cercherà di comportarsi come: {BOT_PERSONA_INSTRUCTION[:100]}...)") # Mostra un'anteprima della personalità

while True:
    user_input = input("Tu: ")
    if user_input.lower() == 'exit':
        print(f"Arrivederci da {BOT_NAME}!")
        break
    if not user_input.strip(): # Ignora input vuoti
        continue

    gemini_response = get_gemini_response(user_input)
    print(f"{BOT_NAME}: {gemini_response}")

    # Leggi la risposta ad alta voce
    speak_text(gemini_response)

    # Aggiungi alla cronologia effettiva (senza l'istruzione di sistema)
    conversation_history.append((user_input, gemini_response))
    save_conversation_history(conversation_history, BOT_PERSONA_INSTRUCTION)