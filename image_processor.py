
import os
import base64
from openai import OpenAI
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    print("⚠️ pytesseract not installed — OCR will use GPT-4o Vision as fallback")
from dotenv import load_dotenv
from PIL import Image
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize your OpenAI Client
print(" clinet", client)

def extract_image_text_tesseract(image_path: str) -> str:
    """Attempt local OCR using Tesseract"""
    if not HAS_TESSERACT:
        return ""
    try:
        # Optional: Add path if not in your Environment Variables
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        image = Image.open(image_path)
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""

def analyze_image_gpt4o(image_path: str) -> str:
    """Escalated Vision analysis for complex images"""
    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode('utf-8')

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract all text and describe this document in detail for a RAG database."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }]
    )
    return response.choices[0].message.content

def process_single_image(image_path: str) -> dict:
    """The Smart Logic: Tesseract first, then GPT-4o if needed"""
    filename = os.path.basename(image_path)
    
    # 1. Try Tesseract first (Free)
    ocr_text = extract_image_text_tesseract(image_path)
    
    # 2. Logic: If text is shorter than 20 characters, it's likely a failure/logo
    if len(ocr_text) < 20:
        print(f"🔍 Tesseract failed or found little text. Escalating '{filename}' to GPT-4o...")
        final_content = analyze_image_gpt4o(image_path)
        source_method = "GPT-4o Vision"
    else:
        print(f"✅ Tesseract succeeded on '{filename}'.")
        final_content = f"Local OCR Extraction:\n{ocr_text}"
        source_method = "Tesseract OCR"

    return {
        "file": filename,
        "combined_text": f"Source: {source_method}\n\n{final_content}",
        "modality": "image"
    }




# from PIL import Image
# import torch
# from transformers import CLIPProcessor, CLIPModel
# import pytesseract
# from typing import List, Tuple
# import os
# import numpy as np
# #import pytesseract pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# # Initialize CLIP model for image embeddings
# device = "cuda" if torch.cuda.is_available() else "cpu"
# print(f"🖼️  Image Processor using device: {device}")

# try:
#     model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
#     processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
#     print("✅ CLIP model loaded successfully")
# except Exception as e:
#     print(f"⚠️  Warning loading CLIP model: {e}")
#     model = None
#     processor = None


# def extract_image_text(image_path: str) -> str:
#     """Extract text from image using OCR"""
#     try:
#         image = Image.open(image_path)
#         text = pytesseract.image_to_string(image)
#         return text if text.strip() else ""
#     except Exception as e:
#         print(f"❌ OCR Error for {image_path}: {e}")
#         return ""


# def generate_image_caption(image_path: str) -> str:
#     """Generate caption for image"""
#     try:
#         filename = os.path.basename(image_path)
#         image = Image.open(image_path)
        
#         # Get image dimensions for context
#         width, height = image.size
        
#         # Generate basic caption
#         caption = f"Image: {filename} (dimensions: {width}x{height}px)"
#         return caption
#     except Exception as e:
#         print(f"❌ Caption Error for {image_path}: {e}")
#         return f"Image: {os.path.basename(image_path)}"


# def get_image_embedding(image_path: str) -> Tuple[List[float], str]:
#     """Get CLIP embedding for image"""
#     try:
#         if model is None or processor is None:
#             print(f"⚠️  CLIP model not available, using fallback for {image_path}")
#             caption = generate_image_caption(image_path)
#             # Return dummy embedding of CLIP size (512 dim)
#             embedding = np.random.randn(512).tolist()
#             return embedding, caption
        
#         image = Image.open(image_path)
#         inputs = processor(images=image, return_tensors="pt", padding=True).to(device)
        
#         with torch.no_grad():
#             image_features = model.get_image_features(**inputs)
        
#         # Normalize embedding
#         embedding = image_features[0].cpu().numpy().tolist()
#         caption = generate_image_caption(image_path)
        
#         print(f"✅ Embedded image: {os.path.basename(image_path)}")
#         return embedding, caption
#     except Exception as e:
#         print(f"❌ Embedding Error for {image_path}: {e}")
#         return [], ""


# def process_single_image(image_path: str) -> dict:
#     """Process a single image file"""
#     try:
#         if not os.path.exists(image_path):
#             raise FileNotFoundError(f"Image not found: {image_path}")
        
#         print(f"\n🖼️  Processing image: {os.path.basename(image_path)}")
        
#         # Get embedding
#         embedding, caption = get_image_embedding(image_path)
        
#         # Extract OCR text
#         ocr_text = extract_image_text(image_path)
        
#         # Combine texts
#         combined_text = f"{caption}\n{ocr_text}" if ocr_text else caption
        
#         result = {
#             "file": os.path.basename(image_path),
#             "file_path": image_path,
#             "embedding": embedding,
#             "caption": caption,
#             "ocr_text": ocr_text,
#             "combined_text": combined_text,
#             "modality": "image"
#         }
        
#         print(f"✅ Image processed: {len(embedding)} dim embedding, {len(combined_text)} chars text")
#         return result
#     except Exception as e:
#         print(f"❌ Image Processing Error: {e}")
#         return {}


# def process_images_in_directory(dir_path: str) -> List[dict]:
#     """Process all images in directory"""
#     results = []
#     image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
#     if not os.path.exists(dir_path):
#         print(f"❌ Directory not found: {dir_path}")
#         return results
    
#     print(f"\n📂 Processing images in: {dir_path}")
    
#     for file in os.listdir(dir_path):
#         if os.path.splitext(file)[1].lower() in image_extensions:
#             file_path = os.path.join(dir_path, file)
#             try:
#                 result = process_single_image(file_path)
#                 if result:
#                     results.append(result)
#             except Exception as e:
#                 print(f"❌ Error processing {file}: {e}")
    
#     print(f"✅ Processed {len(results)} images from directory")
#     return results


# if __name__ == "__main__":
#     # Test with a sample image
#     print("Testing image processor...")
    
#     # Create test image if not exists
#     test_image_path = "./resources/test_image.png"
#     if not os.path.exists(test_image_path):
#         # Create a simple test image
#         os.makedirs("./resources", exist_ok=True)
#         img = Image.new('RGB', (100, 100), color='red')
#         img.save(test_image_path)
#         print(f"Created test image: {test_image_path}")
    
#     result = process_single_image(test_image_path)
#     print(f"Result: {result}")
