import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Extracteur France VAE", page_icon="🇫🇷", layout="wide")

# --- VOS CLÉS CLICKUP (Intégrées directement) ---
CLICKUP_API_KEY = "pk_164681139_0EVG3A2732TCZ9GTV6WBEDI94N2JFJP7"
CLICKUP_LIST_ID = "901207888548"

# --- 1. FONCTION D'ANALYSE HTML ---
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

        # Nom et Prénom
        info_block = soup.find(attrs={"data-testid": "candidate-information"})
        if info_block:
            dd_tags = info_block.find_all('dd')
            full_name = dd_tags[0].get_text(strip=True) if dd_tags else "Nom inconnu"
            
            # Séparation Nom / Prénom
            name_parts = full_name.split(' ', 1)
            data['nom'] = name_parts[0] if name_parts else "Inconnu"
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
        st.error(f"Erreur d'analyse HTML: {e}")
        return None

# --- 2. RÉCUPÉRATION DES CHAMPS CLICKUP ---
def get_custom_fields(api_key, list_id):
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
    
    description = (
        f"👤 **Candidat:** {data['name']}\n"
        f"🎓 **Certification:** {data['certification']}\n"
        f"📧 **Email:** {data['email']}\n"
        f"📞 **Téléphone:** {data['phone']}\n"
    )

    # Récupération des champs dispos dans votre liste
    fields = get_custom_fields(api_key, list_id)
    custom_fields_payload = []
    
    # Données à mapper
    mapping_data = {
        "mail": data['email'],
        "email": data['email'],
        "téléphone": data['phone'],
        "telephone": data['phone'],
        "tel": data['phone'],
        "diplôme": data['certification'],
        "certification": data['certification'],
        "nom": data['nom'],
        "prénom": data['prenom'],
        "prenom": data['prenom']
    }
    
    # Algorithme de remplissage des champs
    for field in fields:
        field_name = field['name'].lower()
        field_type = field.get('type', '')
        f_id = field['id']
        
        for key, value in mapping_data.items():
            if field_name == key or (key != "nom" and key in field_name):
                final_value = value
                
                # Formatage téléphone (+33)
                if field_type == 'phone' and value:
                    digits = ''.join(filter(str.isdigit, value))
                    if digits.startswith('0') and len(digits) == 10:
                        final_value = '+33' + digits[1:]
                    elif not value.startswith('+'):
                        final_value = '+33' + digits
                
                custom_fields_payload.append({
                    "id": f_id,
                    "value": final_value
                })
                break 

    payload = {
        "name": f"{data['name']} - {data['certification']}",
        "description": description,
        # "status": "TO DO",  <-- LIGNE SUPPRIMÉE (Correction Erreur 400)
        "custom_fields": custom_fields_payload,
        "tags": ["francevae"]
    }

    return requests.post(url, json=payload, headers=headers)

# --- INTERFACE ---
st.title("🇫🇷 Extracteur VAE -> ClickUp")
st.markdown("Copiez le code source (Ctrl+U) et collez-le ci-dessous.")

# Zone de collage
html_input = st.text_area("Zone HTML", height=300, label_visibility="collapsed", placeholder="Collez le code HTML ici...")

if st.button("Analyser et Envoyer 🚀", type="primary"):
    if not html_input:
        st.warning("Veuillez coller du code HTML.")
    else:
        with st.spinner("Traitement en cours..."):
            extracted_data = parse_html_content(html_input)
            
            if extracted_data and extracted_data['name'] != "Nom inconnu":
                st.success(f"Candidat détecté : **{extracted_data['name']}**")
                
                # Appel ClickUp avec les clés intégrées en haut du fichier
                res = send_to_clickup(CLICKUP_API_KEY, CLICKUP_LIST_ID, extracted_data)
                
                if res.status_code in [200, 201]:
                    st.balloons()
                    st.success(f"✅ Tâche créée dans ClickUp ! (ID: {res.json().get('id')})")
                else:
                    st.error(f"❌ Erreur ClickUp ({res.status_code}) : {res.text}")
            else:
                st.error("Impossible de lire les données. Vérifiez le code source.")
