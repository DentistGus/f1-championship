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

# --- FUNZIONI BACKEND (Adattate per il Web) ---

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
    pilota = row['Pilota']
    scuderia = row['Scuderia']
    if pilota == 'Utente':
        if scuderia == 'Mercedes-AMG Petronas': return 'Chiumms'
        elif scuderia == 'Scuderia Ferrari HP': return 'Frolla'
    if pilota == 'Dentist_Gus' or pilota == 'Dentist Gus' or ('Dentist' in pilota and 'Gus' in pilota):
        return 'DentistGus'
    return pilota

def process_uploaded_file(uploaded_file):
    # Salva temporaneamente il file per leggerlo
    content = uploaded_file.getvalue().decode("utf-8")
    lines = content.splitlines()
    
    db = load_db()
    
    # Check duplicati (basato sul nome file)
    if uploaded_file.name in db['processed_files']:
        return False, f"Il file '{uploaded_file.name}' è già stato caricato!"

    # Parsing (trova lo split)
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

    # Logica Punti
    df['Pilota'] = df.apply(resolve_names, axis=1)
    db['race_count'] += 1
    current_race_num = db['race_count']
    drivers_in_race = df['Pilota'].unique()
    standings = db['standings']
    
    # Aggiorna storici mancanti
    for driver in standings:
        if 'history' not in standings[driver]: standings[driver]['history'] = []
        while len(standings[driver]['history']) < current_race_num - 1:
            standings[driver]['history'].append(0)
        if driver not in drivers_in_race:
            standings[driver]['history'].append(0)
            standings[driver]['points'] = sum(standings[driver]['history'])
            
    # Aggiorna presenti
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

# --- INTERFACCIA WEB ---

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
    st.info("Sistema sviluppato per F1 25 League")

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
    
    # 1. TABELLA
    st.subheader("📊 Classifica Piloti")
    # Style per evidenziare i primi 3
    st.dataframe(
        df_display,
        use_container_width=True,
        height=500
    )

    # 2. GRAFICO
    st.subheader("📈 Andamento Punti")
    
    # Preparazione Plot Matplotlib
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('#0e1117') # Colore sfondo Streamlit Dark
    ax.set_facecolor('#0e1117')
    
    races = range(1, db['race_count'] + 1)
    top_10 = df.index[:10].tolist()
    
    color_map = {
        'DentistGus': '#1E90FF', # Blu
        'Chiumms': '#40E0D0',    # Turchese
        'Frolla': '#DC0000'      # Rosso
    }
    friends = list(color_map.keys())

    for driver, data in df.iterrows():
        name = driver
        # Filtra solo Top 10 e Amici
        if name not in top_10 and name not in friends: continue
        
        hist = db['standings'][name].get('history', [])
        # Padding history se necessario
        if len(hist) < db['race_count']: hist += [0]*(db['race_count']-len(hist))
        cum_pts = np.cumsum(hist)
        
        if name in color_map:
            ax.plot(races, cum_pts, label=name, color=color_map[name], linewidth=3, marker='o')
        else:
            ax.plot(races, cum_pts, label=name, color='#555555', linewidth=1, alpha=0.5, linestyle='--')

    ax.set_xlabel("Gara", color='white')
    ax.set_ylabel("Punti Totali", color='white')
    ax.set_xticks(list(races))
    ax.set_xlim(left=0.8, right=db['race_count'] + 0.2)
    ax.grid(True, linestyle=':', alpha=0.3)
    ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', facecolor='#0e1117', edgecolor='white')
    
    st.pyplot(fig)

else:
    st.warning("Nessuna gara caricata nel database. Usa la sidebar a sinistra per iniziare.")