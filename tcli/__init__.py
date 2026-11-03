"""tcli — CLI для Tinkoff Invest API (только песочница)."""

from .ssl import ensure_ssl

# Подложить корень НУЦ Минцифры до инициализации gRPC-канала SDK.
ensure_ssl()

__version__ = "0.1.0"
