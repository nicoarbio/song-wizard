# song-wizard

Herramienta de terminal para preparar temas para ensayar con la banda:

- **download**: baja temas o playlists de YouTube en la mejor calidad disponible (Opus original, sin recomprimir).
- **key**: detecta la tonalidad.
- **transpose**: sube o baja el tono sin cambiar el tempo.
- **separate**: separa tu instrumento del resto del tema (voz, batería, bajo o guitarra).

Funciona en **Mac con chip M** (M1 a M5, con macOS 15 o más nuevo), **Linux** y **Windows con WSL**.
No funciona en Mac con procesador Intel.

## Requerimientos

song-wizard está escrito en Python, pero usa algunos programas externos que hay que instalar aparte.
Los comandos de [Instalación](#instalación) instalan todos; acá se explica para qué sirve cada uno.
Todos son programas libres y de código abierto, y se instalan desde sus fuentes oficiales.

| Programa | Por qué hace falta | Cómo lo usa song-wizard |
|---|---|---|
| [**uv**](https://docs.astral.sh/uv/) | Instala song-wizard y sus librerías de Python en un entorno aislado, sin tocar el Python del sistema. Si hace falta, también baja Python 3.12. | `uv tool install` deja disponible el comando `song-wizard`, y `song-wizard upgrade` lo actualiza. |
| [**ffmpeg**](https://ffmpeg.org) | Lee y convierte cualquier formato de audio (Opus, MP3, M4A, WAV…). | Decodifica los temas antes de detectar la tonalidad, transponer o separar. En `download`, yt-dlp lo usa para extraer el audio del video (y para generar los `.wav` con `--wav`). |
| [**deno**](https://deno.com) | YouTube exige resolver un desafío en JavaScript antes de dejar descargar, y deno es el programa que ejecuta ese JavaScript. Node v20 o más nuevo también sirve. | yt-dlp, el motor de descarga, lo detecta y lo usa solo en `download`. |
| [**rubberband**](https://breakfastquay.com/rubberband/) | Cambia el tono sin cambiar el tempo y con muy buena calidad. | `transpose` le pasa los semitonos y genera el archivo `Título (+2).wav`. |

En Linux y WSL además se instalan `curl` (para bajar los instaladores oficiales de uv y deno) y
`build-essential` + `python3-dev`, para compilar una librería de Python que no viene precompilada.
En Mac no hace falta, porque el compilador ya lo instala Homebrew.

Las librerías de Python que hacen el trabajo pesado las instala uv automáticamente:
[yt-dlp](https://github.com/yt-dlp/yt-dlp) para las descargas,
[Essentia](https://essentia.upf.edu) para la tonalidad, y
[audio-separator](https://github.com/nomadkaraoke/python-audio-separator) y
[PyTorch](https://pytorch.org) para separar instrumentos.

Todo se procesa en tu computadora: song-wizard no manda tus archivos a ningún servidor. Solo se
conecta a internet para bajar temas de YouTube, bajar los modelos de separación la primera vez y
actualizarse.

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

En Windows, si no tenés WSL: abrí PowerShell como administrador, corré `wsl --install`, reiniciá
y abrí "Ubuntu" desde el menú Inicio. Después, en esa terminal:

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

Todo tiene que quedar en verde. También te dice si la separación va a usar la placa de video
(mucho más rápido) o solo el procesador.

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

Los modelos se bajan de fuentes públicas: los de Demucs, de los servidores de Meta (que lo creó),
y los demás, de los repositorios públicos en GitHub del proyecto
[UVR](https://github.com/Anjok07/ultimatevocalremovergui) y de audio-separator.

### Desinstalar

```bash
uv tool uninstall song-wizard
rm -rf ~/.local/share/song-wizard                    # Linux/WSL
rm -rf ~/Library/Application\ Support/song-wizard    # Mac
```

Tus temas no se tocan. Si no usás ffmpeg, deno, rubberband ni uv para otra cosa, también podés
desinstalarlos con `brew uninstall` (Mac) o `sudo apt remove` (Linux).

## Uso

### Bajar temas

```bash
song-wizard download "https://www.youtube.com/playlist?list=..."
song-wizard download "https://www.youtube.com/watch?v=..."
```

- Las playlists se guardan en `Música/<nombre de la playlist>/001 - Título.opus`, numeradas en orden.
  Los videos sueltos van a `Música/Singles/`. En WSL, "Música" es la carpeta Música de Windows.
- Si volvés a correr la misma playlist, solo baja los temas nuevos.
- `--wav` además genera un `.wav` de cada tema (misma calidad, ocupa 10 veces más).
- Para playlists privadas: agregá `--cookies-from-browser chrome` (o `firefox`, `safari`) al final.
- Para guardar en otra carpeta: `SONG_WIZARD_DIR=~/Ensayos song-wizard download "URL"`.

### Detectar la tonalidad

```bash
song-wizard key "Música/Show"          # todos los temas de la carpeta
song-wizard key "tema.opus"
```

```
  A    A major   relative F#m   4/4  001 - Aerosmith - Cryin' (HQ).opus
  Em   E minor   relative G     2/4  004 - Bon Jovi - Livin' On A Prayer.opus  uncertain, also: G
```

`4/4` significa que los cuatro métodos de detección coinciden. Con menos, conviene confirmarlo de
oído: lo más común es confundir una tonalidad con su relativa (Em y G usan las mismas notas), por
eso siempre se muestra. Detecta la tonalidad predominante; si el tema modula, no lo indica.

### Cambiar el tono

```bash
song-wizard transpose +2 "tema.opus"      # un tono arriba
song-wizard transpose -1 "tema.opus"      # medio tono abajo
song-wizard transpose -1 "Música/Show"    # todos los temas de la carpeta
```

El número es en semitonos: `+1` = medio tono, `+2` = un tono. Acepta decimales (`-0.5`) por si un
tema está desafinado respecto de La 440. Genera `Título (+2).wav` al lado del original sin tocarlo.
El tempo y la duración no cambian, así que sigue alineado con el click.

### Separar instrumentos

Cada uno pide su instrumento y recibe dos archivos: **el instrumento solo** y **el resto del tema sin ese instrumento**.

```bash
song-wizard separate --stem vocals "tema.opus"    # cantante
song-wizard separate --stem drums  "tema.opus"    # batería
song-wizard separate --stem bass   "tema.opus"    # bajo
song-wizard separate --stem guitar "tema.opus"    # guitarra
```

Genera, por ejemplo, `Título (drums).wav` y `Título (no drums).wav` al lado del original.
Se pueden pedir varios a la vez y procesar una carpeta entera:

```bash
song-wizard separate --stem drums --stem bass "Música/Show"
```

Para tener **todos los stems** (por ejemplo, para mezclar en REAPER):

```bash
song-wizard separate --stem all "tema.opus"
```

Genera `Título (vocals).wav`, `(drums)`, `(bass)`, `(guitar)` y `(other)`, donde "other" es todo
lo demás: teclados, sintes, coros, efectos. Los cinco suman exactamente el tema original: con todos
los faders a 0 dB suena igual que la grabación. No genera los "no X", porque se arman silenciando
una pista. Como los stems salen de modelos distintos, "other" puede tener algún resto de los otros
instrumentos.

- Cada instrumento se separa con el modelo que mejor lo hace: Mel-Band Roformer para la voz,
  Demucs `htdemucs_ft` para batería y bajo, Demucs `htdemucs_6s` para la guitarra.
- Instrumento + resto suman **exactamente** el tema original, y todo queda alineado.
- La primera vez descarga los modelos (unos 1.3 GB en total si usás todos).
- La guitarra es la separación menos precisa: suele mezclarse algo de teclados o de otras guitarras.

#### ¿Dónde corre la separación?

Separar es lo único pesado. song-wizard elige solo dónde correrlo, y anda en cualquier
computadora; lo que cambia es cuánto tarda:

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

Los archivos son WAV de 32 bits float a 44.1 kHz: no se recortan los picos y REAPER, Ableton,
Logic o cualquier DAW los abre directo.

## Anexo: pruebas

Probado el 31/10/2026 con song-wizard 0.1.0, en este equipo:

- Windows con WSL2 (Ubuntu 24.04.5)
- AMD Ryzen 5 8500G (6 núcleos, 12 hilos), 11 GB de RAM disponibles en WSL
- NVIDIA GeForce RTX 4060 de 8 GB, driver 610.88
- Python 3.12.3, PyTorch 2.15.0 (CUDA 13.2), audio-separator 0.48.0, Essentia 2.1b6.dev1389,
  yt-dlp 2026.10.26, Rubber Band 3.3.0, ffmpeg 6.1.1

| Prueba | Tipo | Resultado |
|---|---|---|
| Instalar desde GitHub con `uv tool install` | Real | ✅ `setup` en verde |
| `download` de una playlist de 11 temas, y volver a correrla | Real | ✅ La segunda vez reconoce los 11 y no baja nada |
| `download` de un video suelto y con `SONG_WIZARD_DIR` | Real (sin descargar) | ✅ Rutas correctas |
| `key` sobre los 11 temas | Real | ✅ 9 con 4/4; los 2 dudosos marcan la alternativa (en ambos, la relativa o una quinta) |
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
