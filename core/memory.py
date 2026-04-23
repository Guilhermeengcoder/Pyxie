import json
import os
import datetime


class Memory:

    def __init__(self, filename="memory.json"):
        self.filename = filename
        self.data = self.load_memory()

    def load_memory(self):
        if not os.path.exists(self.filename):
            return {}
        try:
            with open(self.filename, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save_memory(self):
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump(self.data, file, indent=4, ensure_ascii=False)

    def remember(self, category, content):

        timestamp = datetime.datetime.now().isoformat()

        if category not in self.data:
            self.data[category] = {
                "current": content,
                "history": [],
                "created_at": timestamp,
                "last_updated": timestamp
            }
        else:
            old = self.data[category]["current"]

            self.data[category]["history"].append({
                "value": old,
                "timestamp": self.data[category].get("last_updated", "")
            })

            if "last_updated" not in self.data[category]:
                self.data[category]["last_updated"] = timestamp

            self.data[category]["current"] = content
            self.data[category]["last_updated"] = timestamp

        self.save_memory()

    def recall(self, category):
        if category in self.data:
            return self.data[category]["current"]
        return None

    def search(self, keyword):
        results = []
        keyword = keyword.lower()

        for category in self.data:
            current = self.data[category]["current"]
            if keyword in current.lower():
                results.append({
                    "category": category,
                    "value": current
                })

        return results

    def get_history(self, category):
        if category in self.data:
            return self.data[category]["history"]
        return [] 