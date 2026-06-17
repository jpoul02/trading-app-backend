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
