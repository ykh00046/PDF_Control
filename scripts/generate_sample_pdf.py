import fitz


def generate_sample_pdf(filename="sample.pdf"):
    doc = fitz.open()  # new PDF
    page = doc.new_page()  # new page

    # Add some text
    page.insert_text((50, 70), "This is a sample document for testing purposes.", fontsize=12)
    page.insert_text((50, 100), "The number 12345 should be replaced.", fontsize=12)
    page.insert_text((50, 130), "This sentence needs to be deleted.", fontsize=12)
    page.insert_text((50, 160), "Another line with some important text.", fontsize=12)
    page.insert_text((50, 190), "Date: 2023-11-25", fontsize=12)

    doc.save(filename)
    doc.close()
    print(f"Generated {filename}")


if __name__ == "__main__":
    generate_sample_pdf()
