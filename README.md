# song-wizard

[![CI](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml/badge.svg)](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml)

Herramienta de terminal para preparar temas para ensayar con la banda. Es un proyecto personal, hecho por hobby y sin fines comerciales.

- **download**: baja audio de YouTube en la mejor calidad disponible (Opus original, sin recomprimir).
- **key**: detecta la tonalidad.
- **bpm**: detecta el tempo y avisa si varía a lo largo del tema.
- **click**: genera una pista de click fija, con el tempo, el compás y la duración que quieras.
- **transpose**: sube o baja el tono sin cambiar el tempo.
- **speed**: hace un tema más lento (o más rápido) sin cambiar el tono, para sacarlo de a poco.
- **separate**: separa tu instrumento del resto del tema (voz, batería, bajo o guitarra).
- **convert**: convierte a MP3 (o M4A) para compartir, por ejemplo por WhatsApp.
- **ui**: todo lo anterior desde una página en el navegador, sin usar la terminal.

Todo menos `download` funciona con cualquier archivo de audio que tengas: grabaciones de ensayo, temas comprados, maquetas propias, etc.

Funciona en **Mac con chip M** (M1 a M5, con macOS 15 o más nuevo), **Linux** y **Windows con WSL**. No funciona en Mac con procesador Intel.

## Requerimientos

song-wizard está escrito en Python, pero usa algunos programas externos que hay que instalar aparte. Los comandos de [Instalación](#instalación) instalan todos; acá se explica para qué sirve cada uno. Todos son programas libres y de código abierto, y se instalan desde sus fuentes oficiales.

| Programa | Por qué hace falta | Cómo lo usa song-wizard |
|---|---|---|
| [**uv**](https://docs.astral.sh/uv/) | Instala song-wizard y sus librerías de Python en un entorno aislado, sin tocar el Python del sistema. Si hace falta, también baja Python 3.12. | `uv tool install` deja disponible el comando `song-wizard`, y `song-wizard upgrade` lo actualiza. |
| [**ffmpeg**](https://ffmpeg.org) | Lee y convierte cualquier formato de audio (Opus, MP3, M4A, WAV…). | Decodifica los temas antes de detectar la tonalidad, transponer o separar. En `download`, yt-dlp lo usa para extraer el audio del video (y para generar los `.wav` con `--wav`). |
| [**deno**](https://deno.com) | YouTube exige resolver un desafío en JavaScript antes de dejar descargar, y deno es el programa que ejecuta ese JavaScript. Node v20 o más nuevo también sirve. | yt-dlp, el motor de descarga, lo detecta y lo usa solo en `download`. |
| [**rubberband**](https://breakfastquay.com/rubberband/) | Cambia el tono sin cambiar el tempo, o el tempo sin cambiar el tono, con muy buena calidad. | `transpose` le pasa los semitonos y genera `Título (+2).wav`; `speed` le pasa la velocidad y genera `Título (80%).wav`. |

En Linux y WSL además se instalan `curl` (para bajar los instaladores oficiales de uv y deno) y `build-essential` + `python3-dev`, para compilar una librería de Python que no viene precompilada. En Mac no hace falta, porque el compilador ya lo instala Homebrew.

Las librerías de Python que hacen el trabajo pesado las instala uv automáticamente: [yt-dlp](https://github.com/yt-dlp/yt-dlp) para las descargas, [Essentia](https://essentia.upf.edu) para la tonalidad, y [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) y [PyTorch](https://pytorch.org) para separar instrumentos.

Todo se procesa en tu computadora: song-wizard no manda tus archivos a ningún servidor. Solo se conecta a internet para bajar temas de YouTube, bajar los modelos de separación la primera vez y actualizarse.

`song-wizard setup` revisa que estén todos instalados.

## Instalación

### Mac

1. Si no tenés Homebrew, instalalo siguiendo las instrucciones de [brew.sh](https://brew.sh).
2. Abrí la Terminal y corré:

   ```bash
   brew install ffmpeg deno rubberband uv
   uv tool install git+https://github.com/nicoarbio/song-wizard
   ```

### Linux o WSL (Ubuntu)

En Windows, si no tenés WSL: abrí PowerShell como administrador, corré `wsl --install`, reiniciá y abrí "Ubuntu" desde el menú Inicio. Después, en esa terminal:

```bash
sudo apt update && sudo apt install -y ffmpeg rubberband-cli curl build-essential python3-dev
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://deno.land/install.sh | sh
```

Cerrá y volvé a abrir la terminal, y después:

```bash
uv tool install git+https://github.com/nicoarbio/song-wizard
```

### Comprobar que quedó todo bien

```bash
song-wizard setup
```

Todo tiene que quedar en verde. También te dice si la separación va a usar la placa de video (mucho más rápido) o solo el procesador.

### Configuración

```bash
song-wizard config
```

Muestra dónde está el archivo de configuración y qué valores se están usando; si no existe, lo crea con todo comentado. Por ahora guarda la carpeta de descargas. Lo que pases en cada comando siempre gana sobre el archivo.

- Linux/WSL: `~/.config/song-wizard/config.toml`
- Mac: `~/Library/Application Support/song-wizard/config.toml`

```toml
[download]
music_dir = "~/Ensayos"
```

### Actualizar

```bash
song-wizard upgrade
```

Conviene hacerlo seguido: YouTube cambia a menudo y las descargas pueden dejar de andar hasta actualizar.

### Qué se guarda en tu computadora

| Qué | Dónde | Tamaño |
|---|---|---|
| song-wizard y sus librerías | `~/.local/share/uv/tools/song-wizard` | ~6 GB en Linux/WSL (incluye las librerías de NVIDIA para usar la placa de video); bastante menos en Mac |
| Modelos de separación | Linux/WSL: `~/.local/share/song-wizard/models`<br>Mac: `~/Library/Application Support/song-wizard/models` | ~1.3 GB si usás los cuatro instrumentos; se bajan la primera vez que se usa cada uno |
| Registro de temas ya bajados | Linux/WSL: `~/.local/share/song-wizard/archives`<br>Mac: `~/Library/Application Support/song-wizard/archives` | unos pocos KB |
| Tus temas | La carpeta Música (o la que elijas) | lo que bajes |

Los modelos se bajan de fuentes públicas: los de Demucs, de los servidores de Meta (que lo creó), y los demás, de los repositorios públicos en GitHub del proyecto [UVR](https://github.com/Anjok07/ultimatevocalremovergui) y de audio-separator.

### Desinstalar

```bash
uv tool uninstall song-wizard
rm -rf ~/.local/share/song-wizard                    # Linux/WSL
rm -rf ~/Library/Application\ Support/song-wizard    # Mac
```

Tus temas no se tocan. Si no usás ffmpeg, deno, rubberband ni uv para otra cosa, también podés desinstalarlos con `brew uninstall` (Mac) o `sudo apt remove` (Linux).

## Uso

### Interfaz en el navegador

```bash
song-wizard ui
```

Abre una página en el navegador (en WSL, el navegador de Windows) con todo lo que hace song-wizard, sin escribir comandos:

- **Biblioteca**: las carpetas de tu carpeta de música con sus temas, la tonalidad y el tempo de cada uno si ya los detectaste, y los archivos generados de cada tema (stems, versiones transpuestas o con otra velocidad, MP3). Con ▶ se escucha cualquiera.
- **Bajar**: pegás la URL de un video o una playlist arriba de todo.
- **Acciones** sobre los temas elegidos: tonalidad, tempo, separar instrumentos, transponer, cambiar la velocidad, convertir y generar un click.
- **Trabajos**: lo que está corriendo, con su avance en vivo; se puede cancelar. Corren de a uno.
- **Playlists bajadas**: las mismas de `song-wizard archives`, con la opción de olvidarlas.

La página solo funciona mientras la terminal donde la abriste siga abierta; Ctrl+C la cierra. Funciona solo en tu computadora: el servidor no acepta conexiones de afuera, y cada vez que se abre usa una clave nueva en el link, así que ni otras páginas abiertas en el navegador pueden usarla. Si el navegador no se abre solo, abrí el link que muestra la terminal.

Todo lo que hace la interfaz se puede hacer también con los comandos de abajo, que son los que la interfaz usa por detrás.

### Bajar temas

```bash
song-wizard download "https://www.youtube.com/playlist?list=..."
song-wizard download "https://www.youtube.com/watch?v=..."
```

- Las playlists se guardan en `Música/<nombre de la playlist>/001 - Título.opus`, numeradas en orden. Los videos sueltos van a `Música/Singles/`. En WSL, "Música" es la carpeta Música de Windows.
- Si volvés a correr la misma playlist, solo baja los temas nuevos.
- `--wav` además genera un `.wav` de cada tema (misma calidad, ocupa 10 veces más).
- Para playlists privadas: agregá `--cookies-from-browser chrome` (o `firefox`, `safari`) al final.
- Para guardar en otra carpeta: `SONG_WIZARD_DIR=~/Ensayos song-wizard download "URL"`.
- Para volver a bajar temas que ya están en el registro: agregá `--no-download-archive` al final. Si los archivos siguen en la carpeta, sumá también `--force-overwrites`, porque si no se saltean igual.

Para ver qué playlists bajaste y cuántos temas de cada una:

```bash
song-wizard archives
```

```
   #  Playlist                 Songs  Last download
   1  Ensayo diciembre            11  2026-10-31 18:44
   2  Singles (single videos)      1  2026-10-31 18:44
```

Para olvidar una playlist, de modo que la próxima vez se baje entera de nuevo: `song-wizard archives --delete 1` (o varios números, o `all` para todas). Pide confirmación y nunca borra los temas ya bajados.

### Detectar la tonalidad

```bash
song-wizard key "Música/Show"          # todos los temas de la carpeta
song-wizard key "tema.opus"
```

```
  A    A major   relative F#m   4/4  01 - Tema uno.opus
  Em   E minor   relative G     2/4  02 - Tema dos.opus  uncertain, also: G
```

Los resultados también quedan en `key.txt`, en la carpeta de los temas; si después analizás un solo tema, se actualiza solo su línea. En una carpeta se analizan solo los temas originales, no los stems ni las versiones generadas.

`4/4` significa que los cuatro métodos de detección coinciden. Con menos, conviene confirmarlo de oído: lo más común es confundir una tonalidad con su relativa (Em y G usan las mismas notas), por eso siempre se muestra. Detecta la tonalidad predominante; si el tema modula, no lo indica.

### Detectar el tempo

```bash
song-wizard bpm "Música/Show"
song-wizard bpm "tema.opus"
```

```
   103.1 BPM  01 - Tema uno.opus  steady
   123.1 BPM  02 - Tema dos.opus  varies 121-125, probably played without a click
   178.2 BPM  03 - Tema tres.opus  uncertain, check by ear (could be 89.1)
```

Los resultados también quedan en `bpm.txt`, en la carpeta de los temas, igual que con `key`.

- `steady`: el tempo se mantiene fijo, como cuando se graba con click.
- `varies`: el tempo cambia a lo largo del tema (muchos temas de los 80 y 90 se grabaron sin click). Se muestra el rango en el que se mueve; un click fijo se va a ir desfasando.
- `uncertain`: la detección no es confiable. Lo más común es que el detector marque el doble o la mitad del tempo real, por eso se sugiere la alternativa.

### Pista de click

Genera un click fijo, con el primer tiempo de cada compás acentuado:

```bash
song-wizard click 120                            # 120 BPM, 4/4, 1 minuto
song-wizard click 96 --meter 3/4 --bars 32       # 32 compases de 3/4
song-wizard click 123 --duration 4:30            # 4 minutos y medio
song-wizard click 105.6 --like "tema.opus"       # tan largo como un tema
song-wizard click 90 --subdivide 2               # con corcheas
```

- Genera `Click 120 BPM 4-4.wav` en la carpeta donde lo corrés; `-o` elige otro archivo o carpeta.
- Acepta tempos con decimales, así podés usar el número exacto que da `song-wizard bpm`.
- La duración se redondea hacia arriba a compases completos. Sin `--duration`, `--bars` ni `--like`, dura un minuto.
- `--subdivide` agrega clicks más suaves entre tiempo y tiempo: `2` = corcheas, `3` = tresillos, `4` = semicorcheas.
- El compás: el número de arriba es la cantidad de clicks por compás (`4/4` = 4, `3/4` = 3, `6/8` = 6).
- Es un click de tempo fijo: sirve para ensayar sin la grabación o a otro tempo. Si el tema original se grabó sin click (`bpm` dice `varies`), un click fijo se va a ir desfasando de la grabación.
- Para mandarlo por WhatsApp: `song-wizard convert "Click 120 BPM 4-4.wav"`.

### Cambiar el tono

```bash
song-wizard transpose +2 "tema.opus"      # un tono arriba
song-wizard transpose -1 "tema.opus"      # medio tono abajo
song-wizard transpose -1 "Música/Show"    # todos los temas de la carpeta
```

El número es en semitonos: `+1` = medio tono, `+2` = un tono. Acepta decimales (`-0.5`) por si un tema está desafinado respecto de La 440. Genera `Título (+2).wav` al lado del original sin tocarlo. El tempo y la duración no cambian, así que sigue alineado con el click.

### Cambiar la velocidad

```bash
song-wizard speed 80 "tema.opus"                   # al 80 %: más lento, mismo tono
song-wizard speed 70 "tema (no guitar).wav"        # el tema sin tu instrumento, más lento
song-wizard speed 90 --semitones -2 "tema.opus"    # más lento y un tono abajo, en un solo paso
```

El número es el porcentaje de la velocidad original, de 25 a 200: menos de 100 es más lento, más de 100 más rápido. El tono no cambia, salvo que agregues `--semitones` (igual que en `transpose`). Genera `Título (80%).wav` (o `Título (90%, -2).wav`) al lado del original sin tocarlo.

Sirve para sacar un tema de a poco: practicarlo al 70 %, después al 85 % y al final a velocidad normal. Para practicar con click, generá el click al tempo nuevo: si el tema va a 120 BPM, al 80 % va a 96. Cuanto más lento, más se nota que el audio está estirado, sobre todo en la batería.

### Separar instrumentos

Cada uno pide su instrumento y recibe dos archivos: **el instrumento solo** y **el resto del tema sin ese instrumento**.

```bash
song-wizard separate --stem vocals "tema.opus"    # cantante
song-wizard separate --stem drums  "tema.opus"    # batería
song-wizard separate --stem bass   "tema.opus"    # bajo
song-wizard separate --stem guitar "tema.opus"    # guitarra
```

Genera, por ejemplo, `Título (drums).wav` y `Título (no drums).wav` al lado del original. Se pueden pedir varios a la vez y procesar una carpeta entera:

```bash
song-wizard separate --stem drums --stem bass "Música/Show"
```

Para tener **todos los stems** (por ejemplo, para mezclar en REAPER):

```bash
song-wizard separate --stem all "tema.opus"
```

Genera `Título (vocals).wav`, `(drums)`, `(bass)`, `(guitar)` y `(other)`, donde "other" es todo lo demás: teclados, sintes, coros, efectos. Los cinco suman exactamente el tema original: con todos los faders a 0 dB suena igual que la grabación. No genera los "no X", porque se arman silenciando una pista. Como los stems salen de modelos distintos, "other" puede tener algún resto de los otros instrumentos.

- Cada instrumento se separa con el modelo que mejor lo hace: Mel-Band Roformer para la voz, Demucs `htdemucs_ft` para batería y bajo, Demucs `htdemucs_6s` para la guitarra.
- Instrumento + resto suman **exactamente** el tema original, y todo queda alineado.
- La primera vez descarga los modelos (unos 1.3 GB en total si usás todos).
- La guitarra es la separación menos precisa: suele mezclarse algo de teclados o de otras guitarras.

#### ¿Dónde corre la separación?

Separar es lo único pesado. song-wizard elige solo dónde correrlo, y anda en cualquier computadora; lo que cambia es cuánto tarda:

| Tu computadora | Dónde corre | Un tema de 5 minutos, por instrumento |
|---|---|---|
| NVIDIA serie GTX 16, RTX 20 o más nueva | Placa de video | menos de 1 minuto (medido con una RTX 4060) |
| Mac con chip M | Placa de video de Apple | rápido; varía según el modelo de Mac |
| NVIDIA GTX 10 o más vieja, AMD, Intel o sin placa | Procesador | unos 10 minutos (medido con un Ryzen 5 de 6 núcleos) |

- Si la placa no tiene memoria suficiente, song-wizard avisa y sigue con el procesador.
- Si la placa es NVIDIA pero no se usa, suele alcanzar con actualizar el driver de NVIDIA.
- `--cpu` fuerza el procesador, por si la placa da algún problema.
- `song-wizard setup` muestra dónde va a correr en tu computadora.
- Pedir batería y bajo juntos cuesta lo mismo que pedir uno solo: salen del mismo modelo.

Los archivos son WAV de 32 bits float a 44.1 kHz: no se recortan los picos y REAPER, Ableton, Logic o cualquier DAW los abre directo.

### Convertir para compartir (WhatsApp, mail…)

Los WAV de 32 bits que genera song-wizard son ideales para trabajar, pero pesan mucho (unos 20 MB por minuto). Para mandarlos por WhatsApp:

```bash
song-wizard convert "tema (no drums).wav"         # un archivo
song-wizard convert "Música/Show"                 # todos los WAV de la carpeta
song-wizard convert --format m4a "tema.wav"       # M4A (AAC) en lugar de MP3
```

- Genera `Título.mp3` al lado del original: MP3 a ~190 kbps, que cualquier teléfono reproduce. Un tema de 5 minutos queda en unos 7 MB. M4A ocupa lo mismo y suena apenas mejor; MP3 es el más compatible.
- Con una carpeta convierte solo los archivos sin pérdida (WAV, FLAC, AIFF), para no recomprimir los `.opus` bajados. Si nombrás un archivo, convierte cualquier formato.
- Si el archivo tiene picos por encima de 0 dB (pasa con los stems), baja el volumen lo justo para que no se recorten, y avisa cuánto.
- No pisa archivos que ya existen; `--overwrite` los reemplaza.
- Para trabajar en un DAW seguí usando los WAV: el MP3 pierde algo de calidad y agrega unos milisegundos de silencio al principio, así que no queda perfectamente alineado con el click ni con los otros stems.

## Aviso legal

song-wizard es un proyecto personal, hecho por hobby para preparar ensayos, **sin fines comerciales**: no se vende, no se cobra y no se monetiza de ninguna forma. Esto no es asesoramiento legal.

- **Sos responsable de lo que bajás y procesás.** Usalo solo con audio sobre el que tengas derechos o permiso de uso, y respetá los derechos de autor y los [Términos de servicio de YouTube](https://www.youtube.com/t/terms), que no permiten descargar contenido salvo con las funciones de la propia plataforma. No compartas ni publiques los temas, stems o pistas que generes a partir de material ajeno.
- **No apto para uso comercial.** Aunque el código de song-wizard es libre (ver [Licencia](#licencia)), algunas piezas que usa no lo permiten o no tienen una licencia clara: [diffq](https://github.com/facebookresearch/diffq) (una dependencia de audio-separator) tiene licencia CC BY-NC 4.0, que prohíbe el uso comercial; y los modelos de separación (Demucs, el Mel-Band Roformer de voz y los modelos de UVR) no indican la licencia de sus pesos entrenados. Cualquier uso comercial requiere revisar esas licencias por separado.
- **Sin afiliación.** song-wizard no está afiliado ni respaldado por YouTube, Google, Meta, UVR ni ninguno de los proyectos o servicios mencionados. Todas las marcas pertenecen a sus dueños.
- **Sin garantías.** Se ofrece tal cual, sin garantía de ningún tipo, como establece su licencia.

## Licencia

El código de song-wizard se distribuye bajo la [GNU Affero General Public License v3.0 o posterior](LICENSE) (AGPL-3.0-or-later): podés usarlo, estudiarlo, modificarlo y compartirlo, siempre que lo que compartas mantenga la misma licencia y su código fuente. Es la licencia que corresponde porque song-wizard usa [Essentia](https://essentia.upf.edu), que se distribuye bajo AGPL-3.0.

## Créditos

song-wizard es una capa fina sobre el trabajo de otros proyectos libres:

- [Ultimate Vocal Remover (UVR)](https://github.com/Anjok07/ultimatevocalremovergui), de Anjok07 y aufr33, y su colección de modelos de separación.
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator), que permite usar los modelos de UVR desde Python.
- [Demucs](https://github.com/facebookresearch/demucs), de Meta: los modelos `htdemucs_ft` y `htdemucs_6s`.
- [Mel-Band Roformer Vocal Model](https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model), de KimberleyJensen, entrenado con el código de ZFTurbo.
- [Essentia](https://essentia.upf.edu), del Music Technology Group de la Universitat Pompeu Fabra: tonalidad, tempo y pulsos.
- [Rubber Band](https://breakfastquay.com/rubberband/), de Breakfast Quay: cambio de tono y de velocidad.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): descargas.
- [ffmpeg](https://ffmpeg.org): lectura y conversión de audio.
- [PyTorch](https://pytorch.org) y [uv](https://docs.astral.sh/uv/).

## Anexo: pruebas

### Pruebas automáticas

En cada cambio que se sube a GitHub corren las pruebas automáticas, en Linux (Ubuntu) y en una Mac con chip M (macOS 15): el resultado se ve en el ícono de arriba de todo. Además de las pruebas, instalan song-wizard igual que en [Instalación](#instalación), para verificar que se instala bien en los dos sistemas.

Usan audio sintético generado en la misma prueba (tonos, acordes y una batería simple), nunca temas reales, y no se conectan a internet. Cubren:

- Que cada comando de la terminal llegue a lo que tiene que hacer.
- `key`: una progresión de acordes en Sol mayor, La menor, Mi bemol mayor y Fa sostenido menor da la tonalidad correcta con 4/4.
- `bpm`: una batería a 90, 120 y 137 BPM da el tempo exacto (±0.5) y "estable".
- `click`: cada golpe a menos de 0.1 ms de su posición teórica durante 10 minutos, también con tempos con decimales; acentos y subdivisiones en su lugar; la duración redondea a compases enteros.
- `transpose`: el tono cambia lo pedido (un La 440 sube a 880 con +12), la duración no cambia y los picos por encima de 0 dB quedan intactos; con 0 semitonos devuelve el original.
- `speed`: de 25 % a 200 %, la duración cambia exactamente lo pedido, el tono queda igual (y cambia lo pedido con `--semitones`) y los picos por encima de 0 dB quedan intactos; los golpes de un click caen en su lugar al tempo nuevo.
- `convert`: baja el volumen solo de lo que pasa de 0 dB; en una carpeta saltea los archivos comprimidos; no pisa archivos sin `--overwrite`.
- `key.txt` y `bpm.txt`, la configuración, la carpeta de música y los registros de `archives`.
- `ui`: la seguridad (clave, dominio, rutas fuera de la carpeta de música, acciones inválidas), la biblioteca agrupada por tema, la reproducción por partes y un trabajo de click de punta a punta.

`separate` no corre en las pruebas automáticas porque necesita bajar los modelos (1.3 GB); se puede probar a mano con `uv run pytest -m slow`, que verifica que instrumento + resto sumen el original. Para correr las pruebas en tu computadora, desde la carpeta del proyecto: `uv run pytest`.

### Pruebas a mano

Probado el 31/10/2026 con song-wizard 0.1.0, en este equipo:

- Windows con WSL2 (Ubuntu 24.04.5)
- AMD Ryzen 5 8500G (6 núcleos, 12 hilos), 11 GB de RAM disponibles en WSL
- NVIDIA GeForce RTX 4060 de 8 GB, driver 610.88
- Python 3.12.3, PyTorch 2.15.0 (CUDA 13.2), audio-separator 0.48.0, Essentia 2.1b6.dev1389, yt-dlp 2026.10.26, Rubber Band 3.3.0, ffmpeg 6.1.1

| Prueba | Tipo | Resultado |
|---|---|---|
| Instalar desde GitHub con `uv tool install` | Real | ✅ `setup` en verde |
| `download` de una playlist de 11 temas, y volver a correrla | Real | ✅ La segunda vez reconoce los 11 y no baja nada |
| `download` de un video suelto y con `SONG_WIZARD_DIR` | Real (sin descargar) | ✅ Rutas correctas |
| `key` sobre 11 temas | Real | ✅ 9 con 4/4; los 2 dudosos marcan la alternativa (en ambos, la relativa o una quinta) |
| `bpm` sobre 11 temas | Real | ✅ 8 estables, 2 con tempo variable (121-125 y 144-147) y 1 dudoso que sugiere la mitad |
| `key` y `bpm` guardan `key.txt` / `bpm.txt`; volver a analizar un tema solo cambia su línea | Real | ✅ |
| `download --no-download-archive` | Real (sin descargar) | ✅ Ignora el registro y no lo modifica |
| `download` + `archives` (2 temas de una playlist y un video suelto) | Real | ✅ Guarda el nombre de la playlist; la lista muestra la playlist con 2 temas y los sueltos con 1 |
| `archives` con un registro anterior, sin nombre guardado | Real | ✅ Busca el nombre en YouTube una vez y lo guarda |
| `archives --delete` con número inexistente, texto inválido o sin confirmar | Real | ✅ No borra nada y explica por qué |
| `archives --delete all --yes` | Real | ✅ Borra los registros; los temas bajados quedan intactos |
| `click` a 120 BPM 4/4, 96 BPM 3/4, 105.6 BPM durante 10 minutos, con tresillos y `--like` | Real | ✅ Cada golpe a 0.03 ms de su posición teórica (redondeo a la muestra), también a los 10 minutos; cantidad de golpes, acentos y subdivisiones correctos; `--like` cubre todo el tema |
| `ui`: seguridad | Real | ✅ Sin clave, con clave incorrecta o con otro dominio responde 403; rutas fuera de la carpeta de música, rechazadas; acciones que no existen, rechazadas |
| `ui`: todos los trabajos desde la API (tonalidad, tempo, transponer, separar, convertir, click, bajar, olvidar registros) | Real | ✅ Todos terminan bien; el avance de la separación se ve en vivo; cancelar a mitad de una separación la detiene |
| `ui`: página en Edge (escritorio y 400 px de ancho) | Real | ✅ Biblioteca agrupada por tema, nombres con HTML mostrados como texto, sin desbordes en pantallas angostas |
| `ui` en WSL: el navegador de Windows llega al servidor | Real | ✅ |
| `transpose +2` | Real | ✅ Un tema en La da Si; duración idéntica; picos por encima de 0 dB intactos |
| `transpose 0` | Real | ✅ Idéntico al original |
| `transpose` sobre un click sintético | Real | ✅ Los golpes se corren menos de 1 ms con ±2 y −3 semitonos, unos 2 ms con +7 |
| `speed` sobre un click de 5 minutos a 120 BPM | Real | ✅ Ningún golpe se acumula atrasado ni adelantado a lo largo del tema; al 90 % o más caen a menos de 2 ms de su lugar, al 75 % a menos de 4 ms y al 50 % a unos 10 ms (el ataque del golpe se estira) |
| `speed 80` y `speed 120 --semitones -2` sobre un tema de 4:33 | Real | ✅ 21 s cada uno; `key` da la misma tonalidad al 80 % y un tono abajo con −2; `bpm` da 103.1 → 82.5 y 123.6 (exacto); duración 5:41 y 3:47 |
| `speed` con `--semitones` y con archivos ilegibles | Real | ✅ Velocidad y tono en un paso; un archivo que no se puede leer se saltea con un aviso |
| `separate` de los 4 instrumentos en placa de video (tema de 5 min) | Real | ✅ 2 min 11 s en total |
| Instrumento + resto contra el original | Real | ✅ Diferencia de 0.0000001 (redondeo de float) |
| Batería contra la de UVR (`htdemucs`) | Real | ✅ Correlación 0.994, sin desfase |
| `separate --stem all` (tema de 5 min) | Real | ✅ 2 min 18 s; los 5 stems suman el original (diferencia de 0.0000002) |
| `convert` de un WAV float con picos por encima de 0 dB, un WAV de 16 bits y un `.opus` | Real | ✅ Baja el volumen solo donde hace falta (pico final −1.2 dB); en una carpeta saltea el `.opus`; no pisa archivos existentes salvo con `--overwrite` |
| `convert --format m4a` | Real | ✅ AAC a 192 kbps, mismo tamaño que el MP3 |
| `separate --cpu` (30 s, 2 instrumentos) | Real | ✅ 124 s, contra 24 s en placa; mismo resultado |
| Placa NVIDIA muy vieja (GTX 1080) | Simulada | ✅ Avisa y usa el procesador |
| Placa NVIDIA con driver viejo | Simulada | ✅ Avisa que actualice el driver y usa el procesador |
| Placa sin memoria suficiente | Simulada | ✅ Avisa, pasa al procesador y termina |
| Mac con chip M | Real (pruebas automáticas, macOS 15) | ✅ Se instala y pasan todas las pruebas automáticas. Falta probar en una Mac real la separación (con la placa de video del chip M) y la interfaz |
| Linux sin WSL | Real (pruebas automáticas, Ubuntu) | ✅ Se instala y pasan todas las pruebas automáticas |
