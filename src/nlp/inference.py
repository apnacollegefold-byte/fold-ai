import json
import os
import re
import torch
import torch.nn as nn
import spacy
from transformers import AutoTokenizer, AutoModel
import sys

MODEL_DIR = os.path.join(os.path.dirname(__file__), "my_finetuned_distilbert")
NER_MODEL_DIR = os.path.join(os.path.dirname(__file__), "amount_ner_model")

VALID_CATEGORIES = {
    "education", "emi", "entertainment", "food", "friends",
    "healthcare", "investment", "shopping", "travel", "utilities",
}

FALLBACK_CATEGORY= "shopping"

INDIAN_BANKS = [
    "hdfc", "sbi", "icici", "axis", "kotak", "pnb",
    "bob", "yes bank", "idfc", "indusind", "canara",
    "union bank", "federal bank", "rbl", "bandhan",
    "slice", "jupiter", "fi", "niyo",
]

class TransactionExtractor:

    def __init__(self):
        """Load all models and data into memory."""

        # ── Load DistilBERT multi-head model ──
        self.label_maps: dict = {}
        heads_path = os.path.join(MODEL_DIR, "heads.pt")
        maps_path = os.path.join(MODEL_DIR, "label_maps.json")

        if os.path.isdir(MODEL_DIR) and os.path.isfile(heads_path) and os.path.isfile(maps_path):
            print("[NLP] Loading multi-head DistilBERT model...")
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
            self.encoder = AutoModel.from_pretrained(MODEL_DIR)
            hidden = self.encoder.config.hidden_size

            with open(maps_path, "r", encoding="utf-8") as f:
                self.label_maps = json.load(f)

            head_state = torch.load(heads_path, map_location="cpu", weights_only=True)
            self.head_cat = nn.Linear(hidden, head_state["num_cat"])
            self.head_method = nn.Linear(hidden, head_state["num_method"])
            self.head_bank = nn.Linear(hidden, head_state["num_bank"])
            self.head_provider = nn.Linear(hidden, head_state["num_provider"])
            self.head_cat.load_state_dict(head_state["head_cat"])
            self.head_method.load_state_dict(head_state["head_method"])
            self.head_bank.load_state_dict(head_state["head_bank"])
            self.head_provider.load_state_dict(head_state["head_provider"])
            self.encoder.eval()
            self.head_cat.eval()
            self.head_method.eval()
            self.head_bank.eval()
            self.head_provider.eval()
            print("[NLP] DistilBERT model loaded successfully.")
        else:
            raise FileNotFoundError(
                f"DistilBERT model not found at {MODEL_DIR}. "
                "Please train it first using model.ipynb."
            )

        # ── Load spaCy NER model for amount extraction ──
        if os.path.isdir(NER_MODEL_DIR):
            print("[NLP] Loading spaCy NER model for amount extraction...")
            self.ner_model = spacy.load(NER_MODEL_DIR)
            print("[NLP] NER model loaded successfully.")
        else:
            print(f"[NLP] WARNING: NER model not found at {NER_MODEL_DIR}.")
            print("[NLP] Amount extraction will be unavailable. Train it with: python -m src.nlp.train_ner")
            self.ner_model = None

    def _predict_all(self, text: str) -> dict:

        # Tokenize the input text
        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=128, padding=True
        )

        with torch.no_grad():
            outputs = self.encoder(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"])
            cls_output = outputs.last_hidden_state[:, 0] #[1, 768]
            logits_cat = self.head_cat(cls_output)
            logits_method = self.head_method(cls_output)
            logits_bank = self.head_bank(cls_output)
            logits_provider = self.head_provider(cls_output)

        # Get the label maps for each head
        cat_map = self.label_maps.get("category", {})
        method_map = self.label_maps.get("payment_method", {})
        bank_map = self.label_maps.get("bank_account", {})
        provider_map = self.label_maps.get("payment_provider", {})

        # Pick the class with the highest score (argmax)
        cat_id = logits_cat.argmax(dim=1).item()
        method_id = logits_method.argmax(dim=1).item()
        bank_id = logits_bank.argmax(dim=1).item()
        provider_id = logits_provider.argmax(dim=1).item()

        # Convert numeric IDs back to human-readable labels
        category = cat_map.get(str(cat_id), FALLBACK_CATEGORY)
        method = method_map.get(str(method_id), "unknown")
        bank = bank_map.get(str(bank_id), "unknown")
        provider = provider_map.get(str(provider_id), "none")

        # Validate the category
        if category not in VALID_CATEGORIES:
            category = FALLBACK_CATEGORY

        # Treat "unknown"/"none" as None (meaning the model couldn't determine it)
        if method == "unknown":
            method = None
        if bank == "unknown":
            bank = None
        if provider == "none":
            provider = None

        return {"category": category, "payment_method": method, "bank_account": bank, "payment_provider": provider}

    def _extract_amount(self, text: str) -> float | None:

        # If NER model isn't available, we can't extract amounts
        if self.ner_model is None:
            return None

        # Run the NER model on the text
        doc = self.ner_model(text)

        # Look for entities tagged as "AMOUNT"
        for ent in doc.ents:
            if ent.label_ == "AMOUNT":
                try:
                    amount = float(ent.text.strip())

                    # Only return positive, reasonable amounts
                    if amount > 0:
                        return amount
                except (ValueError, TypeError):
                    # If conversion fails, try next entity
                    continue

        return None

    def extract(self, text: str) -> dict:

        # Step 1: Run DistilBERT for classification
        predictions = self._predict_all(text)

        # Step 2: Run NER for amount extraction
        amount = self._extract_amount(text)

        payment_provider = predictions["payment_provider"]

        # Step 3: Fallback — scan text for bank names the model might have missed
        lower = text.lower()
        bank_account = predictions["bank_account"]
        if not bank_account:
            for bank in INDIAN_BANKS:
                if re.search(r"\b" + re.escape(bank) + r"\b", lower):
                    bank_account = bank
                    break

        # If payment method is cash but no bank detected, set bank to "cash"
        # so the backend can match it to the Cash Wallet account
        payment_method = predictions["payment_method"]
        if payment_method == "cash" and not bank_account:
            bank_account = "cash"

        category= predictions["category"]

        return {
            "amount": amount,
            "category": category,
            "payment_method": payment_method,
            "payment_provider": payment_provider,
            "bank_account": bank_account,
        }

if __name__ == "__main__":
    

    extractor = TransactionExtractor()

    test_sentences = [
        "Bhai Swiggy se pizza mangwaya 450 rupaye ka, UPI se pay kiya",
        "Amazon pe 2000 ka shopping kiya hdfc card se",
        "Ola cab liya 357.96 rupaye cash diye",
        "Netflix subscription 199.00 rupaye renew kiya",
        "Electricity bill 1200 rupaye card 1915 waale se pay kiya",
    ]

    if len(sys.argv) > 1:
        test_sentences = [" ".join(sys.argv[1:])]

    for sentence in test_sentences:
        print(f"\n{'='*60}")
        print(f"INPUT: {sentence}")
        result = extractor.extract(sentence)
        print(f"OUTPUT: {json.dumps(result, indent=2)}")
