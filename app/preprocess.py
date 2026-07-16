from __future__ import annotations

import json

from app.core.config import Settings
from app.services.data_loader import DataLoader


def main() -> None:
    """Preprocesa la fuente configurada y muestra el manifiesto verificable."""

    manifest = DataLoader(Settings()).prepare()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
