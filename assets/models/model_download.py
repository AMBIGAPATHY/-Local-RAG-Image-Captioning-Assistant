# assets/models/model_download.py
from sentence_transformers import SentenceTransformer
import os

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_DIR = "assets/models/all-MiniLM-L6-v2"


def main():
    os.makedirs("assets/models", exist_ok=True)
    print(f"Downloading model '{MODEL_NAME}' ...")
    model = SentenceTransformer(MODEL_NAME)

    print(f"Saving to local folder: {TARGET_DIR} ...")
    model.save(TARGET_DIR)

    print("✅ Done. You can now use this model offline.")


if __name__ == "__main__":
    main()
