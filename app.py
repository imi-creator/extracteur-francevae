import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Extracteur France VAE", page_icon="🇫🇷", layout="wide")

# --- SÉCURITÉ (Mot de passe) ---
def check_password():
    """Protège l'accès à l'application."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    # Le mot de passe est lu dans les Secrets. Défaut: "admin123"
    pwd_secret = st.secrets.get("APP_PASSWORD", "admin123") 

    st.title("🔒 Connexion")
    password_input = st.text_input("Mot de passe d'accès", type="password")
    
    if st.button("Se connecter"):
        if password_input == pwd_secret:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect")
    return False

if not check_password():
    st.stop()

# --- 1. FONCTION D'ANALYSE HTML (Mode Web) ---
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

        # Nom et Prénom (Logique de séparation)
        info_block = soup.find(attrs={"data-testid": "candidate-information"})
        if info_block:
            dd_tags = info_block.find_all('dd')
            full_name = dd_tags[0].get_text(strip=True) if dd_tags else "Nom inconnu"
            
            # Séparer nom et prénom (comme dans votre script)
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

    # Récupérer les champs personnalisés dynamiquement
    fields = get_custom_fields(api_key, list_id)
    custom_fields_payload = []
    
    # Mapping des données (Clés minuscules pour la recherche)
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
    
    for field in fields:
        field_name = field['name'].lower()
        field_type = field.get('type', '')
        f_id = field['id']
        
        # On cherche si un mot clé est dans le nom du champ ClickUp
        for key, value in mapping_data.items():
            # Matching intelligent : si "nom" est dans le champ, ou égal
            if field_name == key or (key != "nom" and key in field_name):
                
                # Formatage spécial pour le téléphone (+33)
                final_value = value
                if field_type == 'phone' and value:
                    digits = ''.join(filter(str.isdigit, value))
                    # Si c'est un 06/07..., on remplace le 0 par +33
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
        # "status": "TO DO",  <-- LIGNE SUPPRIMÉE POUR ÉVITER L'ERREUR 400
        "custom_fields": custom_fields_payload,
        "tags": ["francevae"]
    }

    return requests.post(url, json=payload, headers=headers)

# --- INTERFACE PRINCIPALE ---
st.title("🇫🇷 Extracteur VAE -> ClickUp")
st.markdown("""
**Mode d'emploi :**
1. Allez sur la page du candidat (connecté).
2. Faites `Clic Droit` > `Afficher le Code Source` (ou `Ctrl+U`).
3. Tout sélectionner (`Ctrl+A`) et Copier (`Ctrl+C`).
4. Collez le code ci-dessous.
""")

# Configuration automatique depuis les SECRETS (Sécurité)
api_key = st.secrets.get("CLICKUP_API_KEY", "pk_164681139_0EVG3A2732TCZ9GTV6WBEDI94N2JFJP7")
list_id = st.secrets.get("CLICKUP_LIST_ID", "901207888548")

# Vérification que les secrets sont bien là
if not api_key or not list_id:
    st.error("⚠️ La configuration ClickUp (API Key ou List ID) est manquante dans les Secrets.")
else:
    html_input = st.text_area("Collez le Code Source HTML ici", height=300)

    if st.button("Analyser et Envoyer 🚀", type="primary"):
        if not html_input:
            st.warning("Veuillez coller du code HTML.")
        else:
            with st.spinner("Analyse et envoi en cours..."):
                extracted_data = parse_html_content(html_input)
                
                if extracted_data and extracted_data['name'] != "Nom inconnu":
                    st.success(f"Candidat identifié : **{extracted_data['name']}**")
                    
                    # Envoi ClickUp
                    res = send_to_clickup(api_key, list_id, extracted_data)
                    
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success(f"✅ Tâche créée dans ClickUp ! (ID: {res.json().get('id')})")
                        with st.expander("Voir les données extraites"):
                            st.json(extracted_data)
                    else:
                        st.error(f"❌ Erreur ClickUp ({res.status_code}) : {res.text}")
                else:
                    st.error("Impossible de lire les données. Vérifiez que vous avez copié le bon code source.")
