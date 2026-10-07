"""Turn a pydantic model into a self-contained strict JSON schema
(no $ref, additionalProperties: false, every property required) - the
shape both vLLM guided decoding and Claude structured outputs accept."""

from __future__ import annotations

import copy

from pydantic import BaseModel

_DROP = {"title", "default", "description", "minimum", "maximum", "ge", "le"}


def strict_schema(model: type[BaseModel]) -> dict:
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            out = {k: walk(v) for k, v in node.items() if k not in _DROP}
            if out.get("type") == "object" and "properties" in out:
                out["additionalProperties"] = False
                out["required"] = list(out["properties"].keys())
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(raw)
