import os

VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\Datasys2\Documents\TradingBot-Vault")


def _format_timestamp(opened_at: str) -> str:
    # opened_at is an ISO string like "2026-08-11T14:32:00" (from datetime.isoformat())
    date_part, time_part = opened_at.split("T")
    return f"{date_part.replace('-', '')}-{time_part[:8].replace(':', '')}"


def write_trade_opened(trade: dict, vault_path: str = VAULT_PATH) -> str:
    trades_dir = os.path.join(vault_path, "Trades")
    os.makedirs(trades_dir, exist_ok=True)

    stamp = _format_timestamp(trade["opened_at"])
    filename = f"{trade['symbol']}-{stamp}.md"
    path = os.path.join(trades_dir, filename)

    content = f"""---
symbol: {trade['symbol']}
mode: {trade['mode']}
action: {trade['action']}
volume: {trade['volume']}
entry_price: {trade['price']}
sl: {trade['sl']}
tp: {trade['tp']}
status: open
opened_at: {trade['opened_at']}
---

# {trade['symbol']} — {trade['action'].upper()}

**Razón de entrada:** {trade['signal_reason']}

Abierta automáticamente por el bot.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def write_trade_closed(path: str, profit: float, closed_at: str) -> None:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    content = content.replace("status: open", "status: closed", 1)
    content = content.replace(
        "opened_at:",
        f"profit: {profit}\nclosed_at: {closed_at}\nopened_at:",
        1,
    )

    sign = "+" if profit >= 0 else ""
    outcome = "Ganó" if profit >= 0 else "Perdió"
    content += f"\n## Resultado\n\n{outcome} {sign}{profit}\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
