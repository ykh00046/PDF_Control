import inspect

import fitz

try:
    # Get the signature of add_redact_annot method
    signature = inspect.signature(fitz.Page.add_redact_annot)
    print("Signature of fitz.Page.add_redact_annot:")
    print(signature)

    # Check for 'fontfile' parameter
    if 'fontfile' in signature.parameters:
        print("\n'fontfile' parameter IS supported in fitz.Page.add_redact_annot.")
    else:
        print("\n'fontfile' parameter IS NOT supported in fitz.Page.add_redact_annot.")

except AttributeError:
    print("fitz.Page.add_redact_annot method not found or inspect failed.")
except Exception as e:
    print(f"An error occurred: {e}")

