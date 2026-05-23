# 🛒 SuperAhorro GBA — App Familiar de Ofertas y Descuentos

App web para familia que vive en **José C. Paz, zona norte GBA**.  
Muestra las mejores ofertas scrapeadas de supermercados + descuentos por banco/billetera + mapa de sucursales.  
**Gratis, sin anuncios, sin datos en la nube.**

---

## ¿Cómo funciona?

```
GitHub Actions (gratis)
  └─ Corre scraper.py todos los días a las 7am Argentina
       └─ Actualiza data/ofertas.json en el repo
            └─ GitHub Pages sirve la web (index.html lee el JSON)
```

La web vive en tu celular como ícono, sin necesidad de app store.

---

## 🚀 GUÍA DE DEPLOY PASO A PASO

### PASO 1 — Crear el repositorio en GitHub

1. Entrá a **[github.com](https://github.com)** e iniciá sesión (o creá cuenta gratis).
2. Hacé clic en el botón verde **"New"** (arriba a la izquierda).
3. Llenás así:
   - **Repository name:** `superahorro-gba` (o el nombre que quieras)
   - **Description:** "App familiar de ahorro en supermercados"
   - Seleccioná **Public** ✅ (necesario para GitHub Pages gratis)
   - Tildá **"Add a README file"** ✅
4. Clic en **"Create repository"**.

---

### PASO 2 — Subir los archivos

La forma más fácil es **arrastrar y soltar** directamente en el navegador:

1. En tu repo recién creado, hacé clic en **"Add file" → "Upload files"**.
2. **Arrastrá todos los archivos** de este proyecto a la pantalla.
3. Para las carpetas (`data/`, `.github/`): GitHub permite subir carpetas arrastrándolas también.
4. Abajo donde dice "Commit changes", escribí algo como `"Sube proyecto inicial"`.
5. Clic en **"Commit changes"** (botón verde).

> ⚠️ **Ojo con la carpeta `.github/`**: en Windows puede estar oculta. Si no la ves, activá "Mostrar archivos ocultos" en el Explorador de archivos.

**Alternativa si hay problemas con `.github/`:**  
Podés crear el workflow a mano en GitHub:
- En el repo, hacé clic en la pestaña **"Actions"**
- Clic en **"set up a workflow yourself"**
- Borrá todo el contenido y pegá el contenido del archivo `.github/workflows/scrape.yml`
- Guardá con "Commit changes"

---

### PASO 3 — Activar GitHub Pages

1. En tu repo, andá a **Settings** (pestaña con ícono de engranaje).
2. En el menú lateral izquierdo, clic en **"Pages"**.
3. En "Branch", seleccioná **`main`** y carpeta **`/ (root)`**.
4. Clic en **"Save"**.
5. Esperá 2-3 minutos. Después vas a ver la URL de tu app, algo como:
   ```
   https://TU_USUARIO.github.io/superahorro-gba/
   ```

> 📱 Guardá esa URL — es la dirección de tu app.

---

### PASO 4 — Activar el scraping automático

El scraper corre en GitHub Actions. Solo necesitás que esté habilitado:

1. En tu repo, andá a la pestaña **"Actions"**.
2. Si aparece un cartel amarillo diciendo que los workflows están desactivados, hacé clic en **"I understand my workflows, go ahead and enable them"**.
3. En la lista de workflows vas a ver **"Scraper Diario de Ofertas"**.
4. Para correrlo manualmente la primera vez:
   - Clic en el workflow
   - Clic en **"Run workflow"** → **"Run workflow"** (botón verde)
5. Esperá que termine (ícono verde ✅ = todo bien, rojo ❌ = hubo error).

Después de la primera corrida manual, corre **solo todos los días a las 7am** hora Argentina sin que hagas nada.

---

### PASO 5 — Agregar la app al celular

**Android (cualquier navegador):**
1. Abrí la URL de tu GitHub Pages en Chrome.
2. Tocá el menú (los 3 puntitos arriba a la derecha).
3. Tocá **"Agregar a pantalla de inicio"**.
4. Poné un nombre → **"Agregar"**.

**iPhone / iPad (Safari):**
1. Abrí la URL en **Safari** (tiene que ser Safari, no Chrome).
2. Tocá el ícono de **compartir** (cuadrado con flechita hacia arriba).
3. Bajá hasta **"Añadir a pantalla de inicio"**.
4. Poné un nombre → **"Añadir"**.

La app va a aparecer como ícono en tu pantalla, como si fuera una app descargada.

---

## ⚠️ CUÁNDO Y CÓMO SE ROMPE ESTO

Esta es la sección honesta. Las partes frágiles son:

### 🟡 Scrapers de supermercados (se rompen cada 1-3 meses)
Los supermercados cambian su HTML o bloquean bots periódicamente.  
**Señales de que se rompió:** la app muestra "Sin ofertas" o la fecha no se actualiza.

**Cómo darse cuenta:**
1. En GitHub, andá a **Actions** → última corrida del scraper.
2. Si hay un ❌ rojo → hacé clic → buscá el error en rojo.

### 🔴 Scrapers de redes sociales (frágiles siempre)
Facebook e Instagram bloquean activamente el scraping. Esta parte puede fallar sin previo aviso y no hay mucho que hacer más que esperar a que se actualicen las librerías.

### 🟢 Datos de bancos (estables)
Los descuentos bancarios se actualizan manualmente. Son los más confiables.

### 🟢 El mapa y las sucursales (estables)
Son datos fijos, no se rompen.

---

## 🔧 CÓMO ARREGLAR CUANDO SE ROMPE

### Si el scraper falla:
1. Andá a **Actions** → clic en la corrida fallida → copiá el mensaje de error.
2. Abrí **Claude** (claude.ai).
3. Pegá este mensaje:
   ```
   Mi scraper de supermercados falló. Este es el error de GitHub Actions:
   [PEGÁ EL ERROR ACÁ]
   
   El archivo scraper.py tiene este código para ese supermercado:
   [PEGÁ LA FUNCIÓN CORRESPONDIENTE]
   
   ¿Cómo lo arreglo?
   ```
4. Claude te va a dar el código corregido. Reemplazá en `scraper.py` y commiteá.

### Si la web no carga:
- Verificá que GitHub Pages siga activo (Settings → Pages).
- Abrí la URL con `?v=2` al final para forzar recarga sin caché.

---

## 📁 ESTRUCTURA DEL PROYECTO

```
superahorro-gba/
├── index.html              ← La app web completa
├── manifest.json           ← Configuración PWA
├── service-worker.js       ← Cache offline
├── scraper.py              ← Script de scraping
├── requirements.txt        ← Dependencias Python
├── README.md               ← Esta guía
├── data/
│   ├── ofertas.json        ← Actualizado cada día por el scraper
│   ├── descuentos_bancos.json  ← Editable a mano
│   └── sucursales.json     ← Sucursales de tu zona
└── .github/
    └── workflows/
        └── scrape.yml      ← Automatización diaria
```

---

## ✏️ ACTUALIZAR DESCUENTOS BANCARIOS A MANO

Cuando cambian las promociones de tu banco:
1. En GitHub, abrí `data/descuentos_bancos.json`.
2. Hacé clic en el ícono del **lápiz** (editar).
3. Modificá los datos.
4. Guardá con "Commit changes".

La app lo va a leer automáticamente la próxima vez que se abra.

---

## 📝 NOTAS LEGALES

- Esta app es **uso personal / familiar**, no comercial.
- Las ofertas son obtenidas de páginas públicas. **Siempre verificá disponibilidad en la sucursal antes de viajar.**
- Los precios pueden variar. Esta app es una guía, no un contrato.
- Sin afiliación con ningún supermercado ni banco.
