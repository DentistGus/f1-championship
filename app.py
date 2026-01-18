import streamlit as st
import pandas as pd
import json
import os
import io
import matplotlib.pyplot as plt
import numpy as np

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="F1 25 Championship", layout="wide", page_icon="🏎️")

# --- COSTANTI ---
DB_FILE = 'f1_championship.json'

# --- FUNZIONI BACKEND ---

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            db = json.load(f)
            if 'race_count' not in db: db['race_count'] = 0
            return db
    else:
        return {"processed_files": [], "standings": {}, "race_count": 0}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

def resolve_names(row):
    """
    Mappa i nickname e gli utenti generici sui Nomi Reali.
    """
    pilota = row['Pilota']
    scuderia = row['Scuderia']
    
    # Gestione Utente generico
    if pilota == 'Utente':
        if scuderia == 'Mercedes-AMG Petronas': 
            return 'Matteo APERUTA'
        elif scuderia == 'Scuderia Ferrari HP': 
            return 'Giovanni LIGUORI'
            
    # Gestione Dentist Gus (varie formattazioni)
    if pilota == 'Dentist_Gus' or pilota == 'Dentist Gus' or ('Dentist' in pilota and 'Gus' in pilota):
        return 'Benito CERVONE'
        
    return pilota

def process_uploaded_file(uploaded_file):
    # Salva temporaneamente il file per leggerlo
    content = uploaded_file.getvalue().decode("utf-8")
    lines = content.splitlines()
    
    db = load_db()
    
    # Check duplicati (basato sul nome file)
    if uploaded_file.name in db['processed_files']:
        return False, f"Il file '{uploaded_file.name}' è già stato caricato!"

    # Parsing (trova lo split tra classifica e incidenti)
    split_index = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "" or "Tempo\",\"Giro" in line:
            split_index = i
            break
            
    csv_data = "\n".join(lines[:split_index])
    try:
        df = pd.read_csv(io.StringIO(csv_data))
    except Exception:
        return False, "Errore nel formato del CSV."

    # Applicazione Nomi Reali
    df['Pilota'] = df.apply(resolve_names, axis=1)
    
    db['race_count'] += 1
    current_race_num = db['race_count']
    drivers_in_race = df['Pilota'].unique()
    standings = db['standings']
    
    # Aggiorna storici mancanti per chi non ha corso
    for driver in standings:
        if 'history' not in standings[driver]: standings[driver]['history'] = []
        while len(standings[driver]['history']) < current_race_num - 1:
            standings[driver]['history'].append(0)
        if driver not in drivers_in_race:
            standings[driver]['history'].append(0)
            standings[driver]['points'] = sum(standings[driver]['history'])
            
    # Aggiorna punteggi presenti
    for index, row in df.iterrows():
        driver = row['Pilota']
        team = row['Scuderia']
        try: points = int(row['Pti.'])
        except: points = 0
        
        if driver not in standings:
            standings[driver] = {"points": 0,"team": team,"races": 0,"wins": 0,"history": [0] * (current_race_num - 1)}
        
        standings[driver]['history'].append(points)
        standings[driver]['points'] = sum(standings[driver]['history'])
        standings[driver]['team'] = team
        standings[driver]['races'] += 1
        if str(row['Pos.']) == "1": standings[driver]['wins'] += 1
        
    db['processed_files'].append(uploaded_file.name)
    save_db(db)
    return True, f"Gara {current_race_num} elaborata con successo!"

# --- INTERFACCIA WEB (Streamlit) ---

st.title("🏆 F1 25 Championship Standings")
st.markdown("### Pannello di Controllo Ufficiale")

# Sidebar per caricamento
with st.sidebar:
    st.header("Gestione Gare")
    uploaded_file = st.file_uploader("Carica CSV Gara", type=['csv'])
    if uploaded_file is not None:
        if st.button("Elabora Gara"):
            success, msg = process_uploaded_file(uploaded_file)
            if success:
                st.success(msg)
            else:
                st.error(msg)
    
    st.markdown("---")
    st.info("Sistema sviluppato per il Campionato F1 25")

# Caricamento Dati
db = load_db()

if db['standings']:
    # Creazione DataFrame Classifica
    df = pd.DataFrame.from_dict(db['standings'], orient='index')
    df = df.sort_values(by=['points', 'wins'], ascending=False)
    
    # Aggiungi colonna posizione
    df['Posizione'] = range(1, len(df) + 1)
    
    # Rinomina colonne per display
    df_display = df[['points', 'wins', 'races', 'team']].copy()
    df_display.columns = ['Punti', 'Vittorie', 'Gare Disputate', 'Scuderia']
    
    # 1. TABELLA CLASSIFICA
    st.subheader("📊 Classifica Piloti")
    st.dataframe(
        df_display,
        use_container_width=True,
        height=500
    )

    # 2. GRAFICO ANDAMENTO
    st.subheader("📈 Andamento Punti")
    
    # Preparazione Plot Matplotlib (Dark Mode)
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('#0e1117') # Sfondo integrato con Streamlit Dark
    ax.set_facecolor('#0e1117')
    
    races = range(1, db['race_count'] + 1)
    top_10 = df.index[:10].tolist()
    
    # Mappa Colori Aggiornata con i Nomi Reali
    color_map = {
        'Benito CERVONE': '#1E90FF',   # Blu
        'Matteo APERUTA': '#40E0D0',   # Turchese
        'Giovanni LIGUORI': '#DC0000'  # Rosso
    }
    friends = list(color_map.keys())

    # Disegna Linee
    for driver, data in df.iterrows():
        name = driver
        # Filtra: mostra solo Top 10 e i Nostri Amici
        if name not in top_10 and name not in friends: continue
        
        hist = db['standings'][name].get('history', [])
        # Padding history se necessario
        if len(hist) < db['race_count']: hist += [0]*(db['race_count']-len(hist))
        cum_pts = np.cumsum(hist)
        
        if name in color_map:
            # Linea Evidenziata per gli Amici
            ax.plot(races, cum_pts, label=name, color=color_map[name], linewidth=3, marker='o')
        else:
            # Linea Standard per IA
            ax.plot(races, cum_pts, label=name, color='#555555', linewidth=1, alpha=0.5, linestyle='--')

    # Configurazione Assi Grafico
    ax.set_xlabel("Gara", color='white')
    ax.set_ylabel("Punti Totali", color='white')
    
    # Forza asse X con numeri interi
    ax.set_xticks(list(races))
    ax.set_xlim(left=0.8, right=db['race_count'] + 0.2)
    
    ax.grid(True, linestyle=':', alpha=0.3)
    
    # Legenda Esterna
    ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', facecolor='#0e1117', edgecolor='white')
    
    st.pyplot(fig)

else:
    st.warning("Nessuna gara caricata nel database. Usa la sidebar a sinistra per iniziare.")