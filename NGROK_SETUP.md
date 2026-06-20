# Exponer el backend con ngrok

El frontend corre en Railway. El backend corre en tu Windows local (para que MT5 funcione).
ngrok crea un túnel HTTPS público que apunta a tu `localhost:8000`.

## Pasos

1. Descargá ngrok: https://ngrok.com/download
2. Creá cuenta gratis en https://ngrok.com
3. Autenticá tu instalación (una sola vez):
   ```
   ngrok config add-authtoken TU_TOKEN
   ```
4. Levantá el backend primero (doble clic en `backend/START.bat`)
5. En una terminal separada, ejecutá:
   ```
   ngrok http 8000
   ```
6. ngrok te muestra una URL como:
   ```
   Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
   ```
7. Copiá esa URL (`https://abc123.ngrok-free.app`)
8. En Railway → tu servicio frontend → Variables → agregá o actualizá:
   ```
   NEXT_PUBLIC_API_URL=https://abc123.ngrok-free.app
   ```
9. Railway redespliega automáticamente con la nueva URL.

## Notas

- La URL de ngrok cambia cada vez que reiniciás ngrok (plan gratis).
  Con plan pago podés fijar un dominio estático.
- Dejá ngrok corriendo mientras usás la app desde Railway.
- Si reiniciás ngrok, actualizá `NEXT_PUBLIC_API_URL` en Railway y redesplegá.
- MT5 solo funciona en Windows. Cuando el frontend llama a `/api/mt5/*` y
  el backend está corriendo local con MT5 abierto, todo funciona.
  Si el backend está apagado, el frontend muestra "MT5 no disponible".

---

## WebSockets — datos en tiempo real

El backend expone dos endpoints WebSocket sobre el mismo puerto 8000.
ngrok los tunnela automáticamente — no requiere configuración adicional.

### Endpoints

| Endpoint | Frecuencia | Datos |
|----------|-----------|-------|
| `GET /api/mt5/ws/account` | cada 1 s | cuenta (balance, equity, profit, margin) + posiciones abiertas |
| `GET /api/mt5/ws/prices?symbols=EURUSD,XAUUSD` | cada 500 ms | bid, ask, spread, digits por símbolo |

### Cómo funciona la URL

El frontend lee `NEXT_PUBLIC_API_URL` y convierte el protocolo:

```
https://abc123.ngrok-free.app  →  wss://abc123.ngrok-free.app
http://localhost:8000           →  ws://localhost:8000
```

Esto lo hace `frontend/lib/ws.ts`. No hay que configurar nada extra.

### Hooks disponibles

**`useAccountWs()`** — `frontend/app/hooks/use-account-ws.ts`

Retorna `{ ready, connected, error, account, positions }`. Se reconecta automáticamente si el WS cae.

```typescript
const { ready, connected, account, positions } = useAccountWs();
```

**`usePricesWs(symbols)`** — `frontend/app/hooks/use-prices-ws.ts`

Recibe array de símbolos. Reconnecta si el array cambia.

```typescript
const { ready, prices } = usePricesWs(["EURUSD", "XAUUSD"]);
// prices["EURUSD"] → { bid, ask, spread, digits, time }
```

### Qué reemplazó a qué

| Antes | Ahora | Mejora |
|-------|-------|--------|
| `setInterval(fetchStatus, 10s)` | `useAccountWs()` | 10s → 1s |
| `setInterval(fetchPositions, 5s)` | `useAccountWs()` | 5s → 1s |
| `fetchOrderPrice()` on symbol change | `usePricesWs([orderSymbol])` | manual → 500ms live |

El historial de operaciones sigue en REST con polling cada 30s (no necesita ser más rápido).

### Desarrollo local

Para dev local sin Railway, creá `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Los WS usan `ws://localhost:8000/api/mt5/ws/...` automáticamente.
