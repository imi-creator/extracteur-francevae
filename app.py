import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Extracteur France VAE", page_icon="🇫🇷", layout="wide")

# --- SÉCURITÉ (Mot de passe) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True
    
    # Mot de passe défini dans les Secrets Streamlit (ou admin123 par défaut)
    pwd = st.secrets.get("APP_PASSWORD", "admin123")
    
    st.title("🔒 Connexion")
    password = st.text_input("Mot de passe", type="password")
    if st.button("Valider"):
        if password == pwd:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect")
    return False

if not check_password():
    st.stop()

# --- 1. FONCTION D'ANALYSE HTML (VERSION WEB) ---
def parse_html_content(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {}

    try:
        # Email
        email_tag = soup.find(attrs={"data-testid": "candidate-contact-details-email"})
        data['email'] = email_tag.get_text(strip=True) if email_tag else ""

        # Téléphone
        phone_tag = soup.find(attrs={"data-testid": "candidate-contact-details-phone"})
        data['phone'] = phone_tag.get_text(strip=True) if phone_tag else ""

        # Nom / Prénom / Nom complet
        info_block = soup.find(attrs={"data-testid": "candidate-information"})
        if info_block:
            dd_tags = info_block.find_all('dd')
            full_name = dd_tags[0].get_text(strip=True) if dd_tags else "Nom inconnu"
            
            # Votre logique de séparation Nom/Prénom
            name_parts = full_name.split(' ', 1)
            data['nom'] = name_parts[0]
            data['prenom'] = name_parts[1] if len(name_parts) > 1 else ""
            data['name'] = full_name
        else:
            data['name'] = "Nom inconnu"
            data['nom'] = ""
            data['prenom'] = ""

        # Certification
        certif_tag = soup.find('h3', class_='fr-card__title')
        data['certification'] = certif_tag.get_text(strip=True) if certif_tag else "Non spécifié"

        return data

    except Exception as e:
        st.error(f"Erreur d'analyse : {e}")
        return None

# --- 2. RÉCUPÉRATION DES CHAMPS CLICKUP ---
def get_clickup_fields(api_key, list_id):
    url = f"https://api.clickup.com/api/v2/list/{list_id}/field"
    headers = {"Authorization": api_key}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json().get('fields', [])
        return []
    except:
        return []

# --- 3. ENVOI VERS CLICKUP ---
def send_to_clickup(api_key, list_id, data):
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    
    # Description standard
    description = (
        f"👤 **Candidat:** {data['name']}\n"
        f"🎓 **Diplôme:** {data['certification']}\n"
        f"📧 **Email:** {data['email']}\n"
        f"📞 **Tel:** {data['phone']}"
    )

    # Récupération et Mapping des champs Custom
    available_fields = get_clickup_fields(api_key, list_id)
    custom_fields_payload = []

    # Vos données à mapper
    mapping_data = {
        "email": data['email'],
        "mail": data['email'],
        "téléphone": data['phone'],
        "telephone": data['phone'],
        "tel": data['phone'],
        "diplôme": data['certification'],
        "certification": data['certification'],
        "nom": data['nom'],
        "prénom": data['prenom'],
        "prenom": data['prenom']
    }

    # Algorithme de correspondance intelligent
    for field in available_fields:
        f_name = field['name'].lower()
        f_id = field['id']
        f_type = field.get('type', '')

        # On cherche si un mot clé est dans le nom du champ ClickUp
        for key, value in mapping_data.items():
            if key in f_name and value:
                
                # Gestion spécifique des numéros de téléphone (+33)
                final_val = value
                if f_type == 'phone':
                    digits = ''.join(filter(str.isdigit, value))
                    if len(digits) == 10 and digits.startswith('0'):
                        final_val = '+33' + digits[1:]
                    elif not value.startswith('+'):
                        final_val = '+33' + digits

                custom_fields_payload.append({"id": f_id, "value": final_val})
                break # On passe au champ suivant une fois trouvé

    payload = {
        "name": f"{data['name']} - {data['certification']}",
        "description": description,
        "status": "TO DO",
        "custom_fields": custom_fields_payload
    }
    
    return requests.post(url, json=payload, headers=headers)

# --- INTERFACE ---
st.title("🇫🇷 Extracteur VAE pour ClickUp")

# Récupération sécurisée des clés (depuis les Secrets Streamlit)
default_api = st.secrets.get("CLICKUP_API_KEY", "")
default_list = st.secrets.get("CLICKUP_LIST_ID", "")

with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Clé API ClickUp", value=default_api, type="password")
    list_id = st.text_input("ID Liste ClickUp", value=default_list)
    
st.info("ℹ️ Mode d'emploi : Allez sur la page candidat > Clic Droit > Code Source (Ctrl+U) > Copier tout > Coller ici.")
html_input = st.text_area("Collez le Code Source HTML ici", height=300)

if st.button("EXTRAIRE ET ENVOYER 🚀", type="primary"):
    if not html_input:
        st.warning("Merci de coller le code HTML d'abord.")
    elif not api_key or not list_id:
        st.error("Clés API manquantes.")
    else:
        with st.spinner("Analyse en cours..."):
            extracted = parse_html_content(html_input)
            
            if extracted and extracted['name'] != "Nom inconnu":
                st.success(f"Candidat trouvé : {extracted['name']}")
                
                # Envoi
                resp = send_to_clickup(api_key, list_id, extracted)
                
                if resp.status_code in [200, 201]:
                    st.balloons()
                    st.success(f"✅ Tâche créée dans ClickUp ! (ID: {resp.json().get('id')})")
                    # On affiche les données pour vérif
                    st.json(extracted)
                else:
                    st.error(f"Erreur ClickUp ({resp.status_code}) : {resp.text}")
            else:
                st.error("Impossible de trouver les infos du candidat dans ce HTML.")
