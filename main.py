import os
import zipfile
import requests
import openai
import mammoth
from bs4 import BeautifulSoup

# === CONFIGURATION ===
openai.api_key = os.getenv("OPENAI_API_KEY")
WP_SITE = "https://societederatisation.fr"
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
WP_API_POSTS = f"{WP_SITE}/wp-json/wp/v2/posts"
WP_API_MEDIA = f"{WP_SITE}/wp-json/wp/v2/media"
CATEGORIE_ID = 17

ZIP_URL = os.getenv("ZIP_URL")
ZIP_PATH = "articles.zip"
UPLOAD_FOLDER = "articles_docx"

# === 1. TÉLÉCHARGER LE ZIP ===
def download_zip():
    print("⬇️ Téléchargement du fichier ZIP...")
    try:
        r = requests.get(ZIP_URL)
        r.raise_for_status()
        with open(ZIP_PATH, "wb") as f:
            f.write(r.content)
        print("✅ ZIP téléchargé avec succès.")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement du ZIP : {e}")

# === 2. EXTRAIRE LE ZIP ===
def extract_zip():
    print("📦 Extraction des fichiers .docx...")
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(UPLOAD_FOLDER)
        print(f"✅ Extraction terminée. Fichiers extraits dans {UPLOAD_FOLDER}")
    except Exception as e:
        print(f"❌ Erreur extraction ZIP : {e}")

# === 3. EXTRAIRE ET NETTOYER LE CONTENU .DOCX ===
def extract_docx_content(path):
    try:
        with open(path, "rb") as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html = result.value
            messages = result.messages

        title = os.path.basename(path).replace(".docx", "")
        soup = BeautifulSoup(html, "html.parser")
        text_only = soup.get_text()
        words = text_only.split()
        meta_description = " ".join(words[:20]) + "..." if len(words) > 20 else text_only.strip()

        return title.strip(), html.strip(), meta_description.strip()
    except Exception as e:
        print(f"❌ Erreur lecture fichier {path} : {e}")
        return "Erreur", "", ""

# === 4. GÉNÉRER IMAGE IA ===
def generate_image(prompt):
    try:
        print("🎨 Génération image IA...")
        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        image_url = response.data[0].url
        print(f"✅ Image générée : {image_url}")
        image_data = requests.get(image_url).content
        return image_data
    except Exception as e:
        print(f"❌ Erreur génération image : {e}")
        return None

# === 5. UPLOADER UNE IMAGE SUR WORDPRESS ===
def upload_image(image_data, filename):
    try:
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "image/jpeg"
        }
        response = requests.post(
            WP_API_MEDIA,
            headers=headers,
            data=image_data,
            auth=(WP_USER, WP_APP_PASSWORD)
        )
        if response.status_code == 201:
            print(f"✅ Image uploadée : {filename}")
            return response.json()["id"]
        else:
            print(f"❌ Échec upload image : {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception upload image : {e}")
        return None

# === 6. PUBLIER UN ARTICLE ===
def publish_post(title, content, image_id, meta_description):
    try:
        data = {
            "title": title,
            "content": content,
            "status": "draft",
            "categories": [CATEGORIE_ID],
            "featured_media": image_id,
            "meta": {
                "yoast_wpseo_metadesc": meta_description
            }
        }
        response = requests.post(
            WP_API_POSTS,
            json=data,
            auth=(WP_USER, WP_APP_PASSWORD)
        )
        if response.status_code == 201:
            print(f"✅ Brouillon publié : {title}")
        else:
            print(f"❌ Échec publication : {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Erreur lors de la publication : {e}")

# === 7. MAIN ===
if __name__ == "__main__":
    download_zip()
    extract_zip()

    files = os.listdir(UPLOAD_FOLDER)
    docx_files = [f for f in files if f.endswith(".docx")]
    print(f"🗂️ {len(docx_files)} fichiers .docx trouvés.")

    for file in docx_files:
        path = os.path.join(UPLOAD_FOLDER, file)
        print(f"\n📄 Traitement : {file}")

        title, content, meta_desc = extract_docx_content(path)

        if not content:
            print(f"⚠️ Fichier ignoré (contenu vide ou erreur) : {file}")
            continue

        prompt = "Photo réaliste d'une boulangerie artisanale en France avec vitrine, croissants, baguettes et soleil"
        image_data = generate_image(prompt)

        if image_data:
            image_id = upload_image(image_data, f"{title.replace(' ', '_')}.jpg")
            if image_id:
                publish_post(title, content, image_id, meta_desc)
            else:
                print(f"⚠️ Image non uploadée pour {file}")
        else:
            print(f"⚠️ Image non générée pour {file}")
