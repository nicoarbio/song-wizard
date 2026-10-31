# song-wizard

Herramienta de terminal para preparar temas para ensayar con la banda. Es un proyecto personal, hecho por hobby y sin fines comerciales (ver [Aviso legal](#aviso-legal)).

- **download**: baja audio de YouTube en la mejor calidad disponible (Opus original, sin recomprimir).
- **key**: detecta la tonalidad.
- **bpm**: detecta el tempo y avisa si varía a lo largo del tema.
- **click** *(experimental)*: genera una pista de click con count-in, alineada al tema.
- **transpose**: sube o baja el tono sin cambiar el tempo.
- **separate**: separa tu instrumento del resto del tema (voz, batería, bajo o guitarra).

Todo menos `download` funciona con cualquier archivo de audio que tengas: grabaciones de ensayo, temas comprados, maquetas propias, etc.

Funciona en **Mac con chip M** (M1 a M5, con macOS 15 o más nuevo), **Linux** y **Windows con WSL**. No funciona en Mac con procesador Intel.

## Requerimientos

song-wizard está escrito en Python, pero usa algunos programas externos que hay que instalar aparte. Los comandos de [Instalación](#instalación) instalan todos; acá se explica para qué sirve cada uno. Todos son programas libres y de código abierto, y se instalan desde sus fuentes oficiales.

| Programa | Por qué hace falta | Cómo lo usa song-wizard |
|---|---|---|
| [**uv**](https://docs.astral.sh/uv/) | Instala song-wizard y sus librerías de Python en un entorno aislado, sin tocar el Python del sistema. Si hace falta, también baja Python 3.12. | `uv tool install` deja disponible el comando `song-wizard`, y `song-wizard upgrade` lo actualiza. |
| [**ffmpeg**](https://ffmpeg.org) | Lee y convierte cualquier formato de audio (Opus, MP3, M4A, WAV…). | Decodifica los temas antes de detectar la tonalidad, transponer o separar. En `download`, yt-dlp lo usa para extraer el audio del video (y para generar los `.wav` con `--wav`). |
| [**deno**](https://deno.com) | YouTube exige resolver un desafío en JavaScript antes de dejar descargar, y deno es el programa que ejecuta ese JavaScript. Node v20 o más nuevo también sirve. | yt-dlp, el motor de descarga, lo detecta y lo usa solo en `download`. |
| [**rubberband**](https://breakfastquay.com/rubberband/) | Cambia el tono sin cambiar el tempo y con muy buena calidad. | `transpose` le pasa los semitonos y genera el archivo `Título (+2).wav`. |

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

Muestra dónde está el archivo de configuración y qué valores se están usando; si no existe, lo crea con todo comentado. Ahí se pueden guardar valores por defecto propios: la carpeta de descargas y el compás y count-in del click. Lo que pases en cada comando siempre gana sobre el archivo.

- Linux/WSL: `~/.config/song-wizard/config.toml`
- Mac: `~/Library/Application Support/song-wizard/config.toml`

```toml
[download]
music_dir = "~/Ensayos"

[click]
meter = "4/4"
count_in = 2
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

Los resultados también quedan en `key.txt`, en la carpeta de los temas; si después analizás un solo tema, se actualiza solo su línea. En una carpeta se analizan solo los temas originales, no los stems ni los clicks generados.

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

### Pista de click *(experimental)*

```bash
song-wizard click "tema.opus"                    # 4/4, 1 compás de count-in
song-wizard click --count-in 2 "Música/Show"     # 2 compases, toda la carpeta
song-wizard click --meter 3/4 "vals.opus"
```

Genera dos archivos que arrancan juntos:

- `Título (click).wav`: el click, con el count-in antes del compás 1 y el primer tiempo de cada compás acentuado.
- `Título (count-in).wav`: el tema con el silencio necesario al principio para que entre la cuenta. Si al lado del tema hay stems generados con `separate`, también se genera la versión con count-in de cada uno: `Título (drums) (count-in).wav`, etc.

Por defecto **el click sigue al tema**: si la banda original aceleraba o frenaba, el click también, así queda alineado con la grabación. `--steady` genera un click de tempo fijo; en temas grabados sin click se va a ir desfasando (avisa cuando pasa).

Es **experimental** porque hay algo que conviene revisar de oído:

- **Dónde cae el "1".** Lo estima con el bombo, el bajo y los cambios de acorde, pero en temas reales puede quedar en otro tiempo del compás. Si el acento cae, por ejemplo, en el 2, corregilo con `--shift`: `--shift 1` lo corre un tiempo más tarde, `--shift -1` uno antes.
- **Las intros sin batería** (sintes, colchones) tienen pocos golpes claros para guiarse, así que ahí el click es una estimación a partir del tempo del resto del tema.

El compás: el número de arriba es la cantidad de clicks por compás (`4/4` = 4, `3/4` = 3, `6/8` = 6). Para un 6/8 que se cuenta en 2, usá `2/4`.

### Cambiar el tono

```bash
song-wizard transpose +2 "tema.opus"      # un tono arriba
song-wizard transpose -1 "tema.opus"      # medio tono abajo
song-wizard transpose -1 "Música/Show"    # todos los temas de la carpeta
```

El número es en semitonos: `+1` = medio tono, `+2` = un tono. Acepta decimales (`-0.5`) por si un tema está desafinado respecto de La 440. Genera `Título (+2).wav` al lado del original sin tocarlo. El tempo y la duración no cambian, así que sigue alineado con el click.

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
- [Rubber Band](https://breakfastquay.com/rubberband/), de Breakfast Quay: cambio de tono.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): descargas.
- [ffmpeg](https://ffmpeg.org): lectura y conversión de audio.
- [PyTorch](https://pytorch.org) y [uv](https://docs.astral.sh/uv/).

## Anexo: pruebas

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
| `click` sobre 3 temas sintéticos (120 estable, 118 a 126 acelerando, vals en 3/4) | Real, con los tiempos exactos conocidos | ✅ Clicks a 3 ms en promedio y 5 ms como máximo del golpe real; el "1" en el lugar correcto en el 100% de los compases; count-in y relleno exactos |
| `click` sobre 4 temas reales | Real | ✅ Entre el 92% y el 99% de los clicks a menos de 10 ms de un golpe del tema. El lugar del "1" no se verificó de oído |
| `click --steady` sobre el tema que acelera | Real | ✅ Avisa que el click se va a desfasar |
| `click --count-in 2` con stems al lado | Real | ✅ Click, tema y stems con count-in del mismo largo exacto |
| `download --no-download-archive` | Real (sin descargar) | ✅ Ignora el registro y no lo modifica |
| `download` + `archives` (2 temas de una playlist y un video suelto) | Real | ✅ Guarda el nombre de la playlist; la lista muestra la playlist con 2 temas y los sueltos con 1 |
| `archives` con un registro anterior, sin nombre guardado | Real | ✅ Busca el nombre en YouTube una vez y lo guarda |
| `archives --delete` con número inexistente, texto inválido o sin confirmar | Real | ✅ No borra nada y explica por qué |
| `archives --delete all --yes` | Real | ✅ Borra los registros; los temas bajados quedan intactos |
| `transpose +2` | Real | ✅ Un tema en La da Si; duración idéntica; picos por encima de 0 dB intactos |
| `transpose 0` | Real | ✅ Idéntico al original |
| `transpose` sobre un click sintético | Real | ✅ Los golpes se corren menos de 1 ms con ±2 y −3 semitonos, unos 2 ms con +7 |
| `separate` de los 4 instrumentos en placa de video (tema de 5 min) | Real | ✅ 2 min 11 s en total |
| Instrumento + resto contra el original | Real | ✅ Diferencia de 0.0000001 (redondeo de float) |
| Batería contra la de UVR (`htdemucs`) | Real | ✅ Correlación 0.994, sin desfase |
| `separate --stem all` (tema de 5 min) | Real | ✅ 2 min 18 s; los 5 stems suman el original (diferencia de 0.0000002) |
| `separate --cpu` (30 s, 2 instrumentos) | Real | ✅ 124 s, contra 24 s en placa; mismo resultado |
| Placa NVIDIA muy vieja (GTX 1080) | Simulada | ✅ Avisa y usa el procesador |
| Placa NVIDIA con driver viejo | Simulada | ✅ Avisa que actualice el driver y usa el procesador |
| Placa sin memoria suficiente | Simulada | ✅ Avisa, pasa al procesador y termina |
| Mac con chip M | **No probado** | uv verifica que existan paquetes de todas las librerías para Mac con chip M; falta probarlo en una Mac real |
| Linux sin WSL | **No probado** aparte | WSL corre el mismo Ubuntu, así que se espera que funcione igual |
