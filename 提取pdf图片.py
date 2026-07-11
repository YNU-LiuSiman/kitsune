import fitz
from pathlib import Path

pdf_path = "input.pdf"
output_dir = Path("extracted_images")
output_dir.mkdir(exist_ok=True)

document = fitz.open(pdf_path)

image_number = 0

for page_index in range(len(document)):
    page = document[page_index]
    images = page.get_images(full=True)

    for image_index, image_info in enumerate(images):
        xref = image_info[0]

        image_data = document.extract_image(xref)
        image_bytes = image_data["image"]
        image_extension = image_data["ext"]

        output_path = output_dir / (
            f"page_{page_index + 1}_image_{image_index + 1}."
            f"{image_extension}"
        )

        output_path.write_bytes(image_bytes)
        image_number += 1

print(f"提取完成，共提取 {image_number} 张图片。")