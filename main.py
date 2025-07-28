import os
import zipfile
import requests
import openai
from docx import Document
from io import BytesIO

# === CONFIGURATION ===
openai.api_key = os.getenv("OPENAI_API_KEY")
WP_SITE = "https://societederatisation.fr"
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")
WP_API_POSTS = f"{WP_SITE}/wp-json/wp/v2/posts"
WP_API_MEDIA = f"{WP_SITE}/wp-json/wp/v2/media"
CATEGORIE_ID = 17

ZIP_URL = os.getenv("ZIP_URL")  # Ex: "https://tonsite.com/uploads/articles.zip"
ZIP_PATH = "articles.zip"
UPLOAD_FOLDER = "articles_docx"

# === 1. TÉLÉCHARGER LE ZIP ===
def download_zip():
    print("⬇️ Téléchargement du fichier ZIP...")
    r = requests.get(ZIP_URL)
    with open(ZIP_PATH, "wb") as f:
        f.write(r.content)

# === 2. EXTRAIRE LE ZIP ===
def extract_zip():
    print("📦 Extraction des fichiers .docx...")
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(UPLOAD_FOLDER)

# === 3. EXTRAIRE LE CONTENU D'UN DOCX ===
def extract_docx_content(path):
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    title = paragraphs[0] if paragraphs else "Sans titre"
    full_text = " ".join(paragraphs[1:]) if len(paragraphs) > 1 else "Pas de contenu"
    content_html = "<br>".join(paragraphs[1:]) if len(paragraphs) > 1 else full_text

    words = full_text.split()
    meta_description = " ".join(words[:20]) + "..." if len(words) > 20 else full_text

    return title.strip(), content_html.strip(), meta_description.strip()

# === 4. GÉNÉRER UNE IMAGE AVEC DALL·E ===
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
        image_data = requests.get(image_url).content
        return image_data
    except Exception as e:
        print(f"❌ Erreur DALL·E : {e}")
        return None

# === 5. UPLOADER UNE IMAGE SUR WORDPRESS ===
def upload_image(image_data, filename):
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
        return response.json()["id"]
    else:
        print(f"❌ Erreur upload image : {response.status_code} - {response.text}")
        return None

# === 6. PUBLIER UN ARTICLE ===
def publish_post(title, content, image_id, meta_description):
    data = {
        "title": title,
        "content": content,
        "status": "draft",  # ← en brouillon
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
        print(f"✅ Brouillon créé : {title}")
    else:
        print(f"❌ Erreur publication : {response.status_code} - {response.text}")

# === 7. MAIN ===
if __name__ == "__main__":
    download_zip()
    extract_zip()

    for file in os.listdir(UPLOAD_FOLDER):
        if file.endswith(".docx"):
            path = os.path.join(UPLOAD_FOLDER, file)
            print(f"📄 Traitement : {file}")
            title, content, meta_desc = extract_docx_content(path)

            prompt = f"Photo réaliste d'une boulangerie artisanale en France avec vitrine, croissants, baguettes et soleil"
            image_data = generate_image(prompt)

            if image_data:
                image_id = upload_image(image_data, f"{title.replace(' ', '_')}.jpg")
                if image_id:
                    publish_post(title, content, image_id, meta_desc)
