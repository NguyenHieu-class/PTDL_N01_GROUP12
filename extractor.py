# extractor.py

from transformers import AutoTokenizer, AutoModelForQuestionAnswering
import torch

class ProductInfoExtractor:
    def __init__(self, model_name, token):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=token)
        self.model = AutoModelForQuestionAnswering.from_pretrained(model_name, use_auth_token=token).to(self.device)

    def extract_answer(self, context, question):
        inputs = self.tokenizer(question, context, return_tensors="pt", truncation=True).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        start = torch.argmax(outputs.start_logits)
        end = torch.argmax(outputs.end_logits) + 1
        answer = self.tokenizer.convert_tokens_to_string(
            self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0][start:end])
        )
        return answer.strip()
