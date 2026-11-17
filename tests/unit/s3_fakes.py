"""Disposable S3 dependencies; no native imports or real account access."""
import copy

CONFIG = {"model": {"default": "gpt-6.1-sol", "provider": "openai-codex"}, "agent": {"reasoning_effort": "high"},
          "delegation": {"backends": {"model_map": {"options": [
              {"name": "general", "provider": "openai-codex", "model": "gpt-6.1-sol", "reasoning_effort": "medium",
               "description": "synthetic", "fallbacks": ["synthetic"]},
              {"name": "untouched", "model": "gpt-6.1-terra", "custom": "preserved"}]}}}, "cron": {"model": "", "model_provider": ""}}
TARGET = {"provider": "anthropic", "model": "claude-opus-5-5", "effort": "high"}


def qualified():
    return {"ok": True, "host": "synthetic", "reasons": []}


class Backend:
    def __init__(self):
        self.document = copy.deepcopy(CONFIG)
        self.writes = []

    def read(self):
        return copy.deepcopy(self.document)

    def write(self, updates, unset):
        self.writes.append((copy.deepcopy(updates), tuple(unset)))
        for path in [*updates, *unset]:
            parts = path.split('.')
            node = self.document
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            if path in unset:
                node.pop(parts[-1], None)
            else:
                node[parts[-1]] = copy.deepcopy(updates[path])
