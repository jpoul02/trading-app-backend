from fastapi import APIRouter, HTTPException

router = APIRouter()

LESSONS = [
    {"id": 1, "title": "¿Qué es invertir?", "description": "Conceptos básicos de inversión y por qué es importante.", "level": "Principiante", "duration_min": 5, "icon": "📈"},
    {"id": 2, "title": "Acciones vs ETFs", "description": "Diferencias clave y cuándo usar cada uno.", "level": "Principiante", "duration_min": 7, "icon": "⚖️"},
    {"id": 3, "title": "¿Qué es DCA?", "description": "Dollar Cost Averaging: la estrategia pasiva más poderosa.", "level": "Principiante", "duration_min": 6, "icon": "📅"},
    {"id": 4, "title": "Riesgo y diversificación", "description": "Cómo reducir el riesgo distribuyendo tu portafolio.", "level": "Principiante", "duration_min": 8, "icon": "🛡️"},
    {"id": 5, "title": "Introducción a las criptomonedas", "description": "Bitcoin, Ethereum y el ecosistema crypto.", "level": "Principiante", "duration_min": 10, "icon": "₿"},
    {"id": 6, "title": "Staking y rendimientos pasivos", "description": "Gana intereses con tus criptos sin venderlas.", "level": "Intermedio", "duration_min": 8, "icon": "🔒"},
    {"id": 7, "title": "Análisis técnico básico", "description": "RSI, MACD, soportes y resistencias.", "level": "Intermedio", "duration_min": 12, "icon": "📊"},
    {"id": 8, "title": "Gestión de riesgo", "description": "Stop-loss, position sizing y control emocional.", "level": "Intermedio", "duration_min": 10, "icon": "🎯"},
    {"id": 9, "title": "Dividendos e ingresos pasivos", "description": "ETFs de dividendos y acciones que pagan rendimiento.", "level": "Intermedio", "duration_min": 9, "icon": "💰"},
    {"id": 10, "title": "Psicología del inversor", "description": "FOMO, FUD y cómo tomar decisiones racionales.", "level": "Intermedio", "duration_min": 7, "icon": "🧠"},
]

LESSON_CONTENT = {
    1: """**¿Qué es invertir?**

Invertir es destinar dinero hoy esperando obtener más dinero en el futuro. A diferencia de ahorrar (guardar dinero sin que crezca), invertir pone tu dinero a trabajar.

**¿Por qué invertir?**
La inflación reduce el poder adquisitivo de tu dinero con el tiempo. Si guardas $1,000 debajo del colchón, en 10 años esos $1,000 comprarán menos cosas. Invertir te permite superar la inflación y construir riqueza.

**Tipos de inversiones:**
- **Acciones**: participación en una empresa. Si la empresa crece, tu inversión crece.
- **Bonos**: préstamos a empresas o gobiernos a cambio de interés fijo.
- **ETFs**: fondos que agrupan múltiples activos, comprando diversificación fácilmente.
- **Criptomonedas**: activos digitales descentralizados con alta volatilidad y potencial.
- **Bienes raíces**: propiedad física que genera alquiler o apreciación.

**El poder del interés compuesto:**
Si inviertes $200/mes durante 30 años con un retorno anual del 10%, terminarás con más de $450,000, habiendo invertido solo $72,000. El tiempo es tu mejor aliado.""",

    2: """**Acciones vs ETFs**

**Acciones (Stocks):**
Comprar una acción significa ser dueño de una pequeña parte de una empresa. Si Apple sube 20%, tu inversión en Apple sube 20%. Pero si Apple cae 50%, también pierdes 50%.

*Ventajas*: potencial de altos retornos, dividendos, control total sobre qué empresas elegir.
*Desventajas*: requiere investigación, riesgo concentrado, más volatilidad.

**ETFs (Exchange Traded Funds):**
Un ETF agrupa decenas o miles de acciones en un solo instrumento. El SPY replica las 500 empresas más grandes de EE.UU. Al comprar 1 acción de SPY, tienes exposición a todas ellas.

*Ventajas*: diversificación instantánea, bajo costo, menos riesgo, ideal para inversión pasiva.
*Desventajas*: no superarás al mercado (eres el mercado), menor emoción para algunos inversores.

**¿Cuál elegir?**
Para la mayoría de inversores, especialmente principiantes, los ETFs de índice como SPY, VTI o QQQ son la opción superior por su simplicidad, costo bajo y retornos históricamente sólidos.

La regla de oro: si no puedes dedicar tiempo a investigar empresas individuales, los ETFs son tu mejor opción.""",

    3: """**Dollar Cost Averaging (DCA)**

DCA es la estrategia de invertir una cantidad fija de dinero en intervalos regulares, independientemente del precio del activo.

**¿Cómo funciona?**
En lugar de intentar comprar en el "momento perfecto" (lo cual es imposible incluso para profesionales), inviertes $200 cada mes sin importar si el mercado está alto o bajo.

**Ejemplo práctico:**
- Enero: precio $100, compras 2 unidades → $200
- Febrero: precio $80 (baja), compras 2.5 unidades → $200
- Marzo: precio $120 (sube), compras 1.67 unidades → $200
- Precio promedio de compra: ~$97 (mejor que si hubieras comprado todo en enero)

**¿Por qué funciona?**
Cuando el precio baja, compras más unidades. Cuando sube, compras menos. Automáticamente "compras más cuando está barato". Elimina el estrés de "timing" el mercado y el impacto emocional de la volatilidad.

**Automatización:**
La clave del DCA exitoso es la automatización. Configura transferencias automáticas mensuales a tu cuenta de inversión el día de tu pago. "Págate a ti mismo primero."

Históricamente, quien aplicó DCA consistente en SPY durante cualquier período de 20+ años obtuvo retornos positivos.""",

    4: """**Riesgo y Diversificación**

**¿Qué es el riesgo en inversiones?**
Riesgo es la posibilidad de perder parte o todo tu dinero. No existe inversión sin riesgo, pero puedes gestionarlo inteligentemente.

**Tipos de riesgo:**
- **Riesgo de mercado**: todo el mercado cae (crisis 2008, COVID 2020)
- **Riesgo específico**: una empresa individual quiebra (Enron, Lehman Brothers)
- **Riesgo de liquidez**: no puedes vender cuando quieres
- **Riesgo de inflación**: tus retornos no superan la inflación

**Diversificación:**
"No pongas todos los huevos en la misma canasta." Distribuir tu dinero entre múltiples activos reduce el riesgo específico.

*Diversificación por activo*: acciones + bonos + crypto + real estate
*Diversificación geográfica*: EE.UU. + Europa + Asia + mercados emergentes
*Diversificación temporal*: DCA a lo largo del tiempo

**Correlación:**
Los bonos tienden a subir cuando las acciones bajan. Tener ambos reduce la volatilidad total de tu portafolio.

**Regla general por edad:**
Una guía simple: 100 menos tu edad en acciones. A los 30 años: 70% acciones, 30% bonos. Esto se vuelve más conservador con la edad.""",

    5: """**Introducción a las Criptomonedas**

**¿Qué es una criptomoneda?**
Es dinero digital descentralizado que funciona en una red blockchain sin necesidad de bancos o gobiernos que lo controlen.

**Bitcoin (BTC):**
La primera y más importante. Creado en 2009 por Satoshi Nakamoto (anónimo). Supply máximo de 21 millones de monedas. Considerado "oro digital" y reserva de valor. Volatilidad alta pero históricamente el activo de mejor rendimiento en la última década.

**Ethereum (ETH):**
Plataforma de contratos inteligentes. Más allá de ser dinero, es infraestructura para aplicaciones descentralizadas (DeFi, NFTs, DAOs). El "sistema operativo" de Web3.

**Altcoins:**
Todas las criptos que no son Bitcoin. Miles existen, mayoría fallará. Solo invertir en proyectos con fundamentos sólidos.

**Stablecoins:**
Criptos ancladas al dólar (USDT, USDC). No suben ni bajan con el mercado. Útiles para guardar valor en crypto sin exposición a volatilidad.

**Wallets:**
- *Custodial* (exchange como Binance/Coinbase): la empresa guarda tus claves. Fácil pero riesgo de hackeo del exchange.
- *Non-custodial* (MetaMask, Ledger): tú controlas tus claves. "Not your keys, not your coins."

**Regla de oro**: nunca inviertas en crypto más de lo que estás dispuesto a perder completamente.""",

    6: """**Staking y Rendimientos Pasivos**

**¿Qué es el staking?**
Bloquear tus criptomonedas en una red blockchain para ayudar a validar transacciones (Proof of Stake) y recibir recompensas en forma de más criptomonedas.

**¿Cómo funciona?**
Las redes PoS (Ethereum, Solana, Cardano) necesitan "validadores" que pongan en garantía sus monedas para verificar transacciones. A cambio, reciben una parte de las comisiones de la red.

**APY típicos:**
- ETH: ~4% anual (más seguro, red más establecida)
- SOL: ~6.5% anual (mayor riesgo, mayor recompensa)
- DOT: ~12% anual (alta volatilidad del activo base)
- ATOM: ~15% anual (ecosistema Cosmos)

**Riesgos del staking:**
1. *Volatilidad del activo*: si DOT baja 50%, tu 12% de APY no compensa la pérdida
2. *Slashing*: penalización si el validador se porta mal
3. *Período de lock*: algunas redes te bloquean el dinero por semanas
4. *Smart contract risk*: bugs en protocolos DeFi

**Opciones:**
- Staking en exchange (fácil, menor yield, riesgo contraparte)
- Staking nativo (más complejo, mayor yield, más seguro)
- Liquid staking (stETH, mSOL): haces staking y recibes un token que puedes usar en DeFi""",

    7: """**Análisis Técnico Básico**

El análisis técnico estudia gráficos de precios para predecir movimientos futuros basándose en patrones históricos.

**RSI (Relative Strength Index):**
Indicador de 0 a 100 que mide velocidad y cambio de movimientos de precio.
- RSI > 70: sobrecomprado (posible bajada)
- RSI < 30: sobrevendido (posible subida)
- RSI 50: zona neutral

**MACD (Moving Average Convergence Divergence):**
Diferencia entre dos medias móviles. Cuando la línea MACD cruza por arriba la línea de señal: posible compra. Por abajo: posible venta.

**Soportes y Resistencias:**
- *Soporte*: nivel de precio donde el activo históricamente ha rebotado hacia arriba. Zona de compra.
- *Resistencia*: nivel donde históricamente ha caído. Zona de venta.
Cuando una resistencia se rompe, se convierte en soporte.

**Medias Móviles:**
- MA50 y MA200 son las más usadas
- Golden Cross: MA50 cruza MA200 hacia arriba → señal alcista
- Death Cross: MA50 cruza MA200 hacia abajo → señal bajista

**Importante:**
El análisis técnico no predice el futuro, solo indica probabilidades. Nunca operar solo con AT sin gestión de riesgo. Funciona mejor en mercados líquidos y trending.""",

    8: """**Gestión de Riesgo**

La gestión de riesgo es la habilidad más importante del trader/inversor. Puedes tener una estrategia con solo 40% de operaciones ganadoras y aún ser rentable si gestionas bien el riesgo.

**Stop-Loss:**
Orden automática que cierra tu posición si el precio cae a cierto nivel, limitando tu pérdida máxima.
Ejemplo: compras BTC a $50,000, pones stop-loss en $47,500 → máximo pierdes 5%.

**Position Sizing:**
¿Cuánto de tu capital arriesgar por operación?
Regla del 1-2%: nunca arriesgar más del 1-2% de tu capital total en una sola operación.
Con $10,000: máximo en riesgo por trade = $100-200.

**Risk/Reward Ratio:**
Buscar operaciones donde la ganancia potencial sea al menos 2x la pérdida potencial.
Si arriesgas $100, solo entra si puedes ganar $200+.

**Diversificación temporal:**
No poner todo el capital de golpe. Entrar en fases reduce el riesgo de timing.

**Control emocional:**
- Nunca promediar pérdidas ("double down") por ego
- Respetar siempre el stop-loss sin moverlo
- No operar cuando estás estresado o emocional
- Llevar un diario de operaciones para aprender de errores

**El objetivo es sobrevivir para operar otro día.** Un trader que pierde 50% necesita ganar 100% solo para recuperarse.""",

    9: """**Dividendos e Ingresos Pasivos en Bolsa**

Los dividendos son pagos que empresas estables hacen a sus accionistas, típicamente cada trimestre.

**¿Cómo funcionan?**
Si posees 100 acciones de Coca-Cola (KO) con dividendo de $1.84/año → recibes $184 anuales sin vender nada.

**ETFs de Dividendos:**
- **SCHD**: Schwab US Dividend Equity. Yield ~3.5%, alta calidad crediticia, crecimiento de dividendo consistente.
- **VYM**: Vanguard High Dividend Yield. Yield ~3%, diversificado, bajo costo.
- **O** (Realty Income): REIT que paga dividendo MENSUAL. Yield ~5-6%, más de 600 aumentos consecutivos de dividendo.

**DRIP (Dividend Reinvestment Plan):**
Reinvertir automáticamente los dividendos en más acciones. Potencia enormemente el interés compuesto a largo plazo.

**Dividend Yield vs Dividend Growth:**
- Yield alto hoy (8%+): puede ser trampa, investigar si es sostenible
- Yield moderado + crecimiento anual (3% + 8% crecimiento/año): superior a largo plazo

**Aristocratas del dividendo:**
Empresas que han aumentado su dividendo por 25+ años consecutivos. Coca-Cola, Johnson & Johnson, Procter & Gamble, etc.

**Estrategia:**
A mayor horizonte de tiempo, más valioso es el crecimiento del dividendo sobre el yield inicial.""",

    10: """**Psicología del Inversor**

El mayor enemigo del inversor no es el mercado, es su propio cerebro.

**FOMO (Fear Of Missing Out):**
Comprar en máximos por miedo a perderse la subida. Clásico en bull markets: todos hablan de las ganancias, tú entras tarde y eres el que termina comprando caro.
*Solución*: DCA sistemático elimina el FOMO porque siempre estás comprando.

**FUD (Fear, Uncertainty, Doubt):**
Vender en pánico durante caídas por miedo a perder todo. Quien vendió en marzo 2020 (COVID crash) se perdió el rally de 100%+ que siguió.
*Solución*: invierte solo lo que no necesitas en 5+ años.

**Sesgo de confirmación:**
Solo leer noticias que confirman lo que ya crees. Si compraste Bitcoin, solo ves las noticias positivas.
*Solución*: buscar activamente puntos de vista opuestos.

**Anclaje:**
"Ya bajó de $60k a $30k, tiene que volver a $60k." El mercado no debe nada.
*Solución*: evaluar activos por fundamentos actuales, no por precios pasados.

**El inversor más exitoso de todos los tiempos (Warren Buffett) dice:**
"El mercado es un mecanismo para transferir dinero del impaciente al paciente."

**Reglas mentales:**
1. El corto plazo es impredecible; el largo plazo favorece al inversor disciplinado
2. Nunca tomes decisiones de inversión bajo estrés emocional
3. Tener un plan escrito y seguirlo reduce las decisiones emocionales""",
}

GLOSSARY = [
    {"term": "ETF", "definition": "Exchange Traded Fund. Fondo de inversión que cotiza en bolsa y agrupa múltiples activos (acciones, bonos) en un solo instrumento."},
    {"term": "DCA", "definition": "Dollar Cost Averaging. Estrategia de invertir una cantidad fija periódicamente sin importar el precio del activo."},
    {"term": "Bull Market", "definition": "Mercado alcista. Período prolongado donde los precios suben, generalmente +20% desde mínimos recientes."},
    {"term": "Bear Market", "definition": "Mercado bajista. Período prolongado donde los precios caen, generalmente -20% desde máximos recientes."},
    {"term": "HODL", "definition": "Término cripto que significa mantener el activo a largo plazo sin vender, independientemente de la volatilidad."},
    {"term": "Staking", "definition": "Bloquear criptomonedas en una red blockchain para validar transacciones y recibir recompensas (APY)."},
    {"term": "Wallet", "definition": "Billetera digital que almacena claves privadas para acceder a criptomonedas. Puede ser custodial (exchange) o non-custodial."},
    {"term": "Dividendo", "definition": "Pago que una empresa hace a sus accionistas, generalmente trimestral, como distribución de ganancias."},
    {"term": "Yield", "definition": "Rendimiento o tasa de retorno de una inversión, expresada como porcentaje anual (APY o APR)."},
    {"term": "P&L", "definition": "Profit & Loss. Ganancia y pérdida. Diferencia entre el valor actual de una posición y su costo de adquisición."},
    {"term": "Portfolio", "definition": "Portafolio o cartera de inversiones. Conjunto de todos los activos financieros que posee un inversor."},
    {"term": "Market Cap", "definition": "Capitalización de mercado. Precio actual × número total de unidades en circulación. Mide el tamaño de un activo."},
    {"term": "Volatilidad", "definition": "Medida de cuánto fluctúa el precio de un activo. Alta volatilidad = mayor riesgo y mayor potencial de ganancia/pérdida."},
    {"term": "Diversificación", "definition": "Distribuir inversiones entre múltiples activos para reducir el riesgo. 'No poner todos los huevos en la misma canasta.'"},
    {"term": "FOMO", "definition": "Fear Of Missing Out. Miedo a perderse una oportunidad que lleva a tomar decisiones impulsivas de compra en máximos."},
    {"term": "FUD", "definition": "Fear, Uncertainty, Doubt. Miedo, incertidumbre y duda. Información negativa que puede causar ventas en pánico."},
    {"term": "Liquidez", "definition": "Facilidad con que un activo puede comprarse o venderse sin afectar significativamente su precio."},
    {"term": "Orden Market", "definition": "Orden de compra/venta que se ejecuta inmediatamente al precio actual del mercado."},
    {"term": "Orden Limit", "definition": "Orden que solo se ejecuta si el precio alcanza un nivel específico determinado por el usuario."},
    {"term": "Stop-Loss", "definition": "Orden automática que vende un activo cuando cae a cierto precio, limitando la pérdida máxima en una posición."},
    {"term": "RSI", "definition": "Relative Strength Index. Indicador de 0-100 que mide si un activo está sobrecomprado (>70) o sobrevendido (<30)."},
    {"term": "MACD", "definition": "Moving Average Convergence Divergence. Indicador que muestra la relación entre dos medias móviles para identificar tendencias."},
    {"term": "Soporte", "definition": "Nivel de precio donde históricamente el activo ha dejado de caer y ha rebotado hacia arriba. Zona de posible compra."},
    {"term": "Resistencia", "definition": "Nivel de precio donde históricamente el activo ha dejado de subir y ha caído. Zona de posible venta o toma de ganancias."},
    {"term": "Altcoin", "definition": "Cualquier criptomoneda que no sea Bitcoin. Incluye Ethereum, Solana, Cardano y miles más."},
    {"term": "Stablecoin", "definition": "Criptomoneda cuyo valor está anclado a una moneda fiat (generalmente el dólar). Ejemplos: USDT, USDC, DAI."},
]


@router.get("/lessons")
def get_lessons():
    return LESSONS


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: int):
    meta = next((l for l in LESSONS if l["id"] == lesson_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Lesson not found")
    content = LESSON_CONTENT.get(lesson_id, "Contenido no disponible.")
    return {**meta, "content": content}


@router.get("/glossary")
def get_glossary():
    return GLOSSARY
