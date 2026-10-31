# song-wizard

Herramienta de terminal para preparar temas para ensayar con la banda:

- **download**: baja temas o playlists de YouTube en la mejor calidad disponible (Opus original, sin recomprimir).
- **key**: detecta la tonalidad.
- **transpose**: sube o baja el tono sin cambiar el tempo.
- **separate**: separa tu instrumento del resto del tema (voz, batería, bajo o guitarra).

Funciona en **Mac con chip M** (M1 a M5, con macOS 15 o más nuevo), **Linux** y **Windows con WSL**.
No funciona en Mac con procesador Intel.

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

- Cada instrumento se separa con el modelo que mejor lo hace: Mel-Band Roformer para la voz,
  Demucs `htdemucs_ft` para batería y bajo, Demucs `htdemucs_6s` para la guitarra.
- Instrumento + resto suman **exactamente** el tema original, y todo queda alineado.
- La primera vez descarga los modelos (unos 1.3 GB en total si usás todos).
- Con placa de video (NVIDIA o Mac con chip M) un tema tarda alrededor de un minuto por modelo;
  solo con el procesador, bastante más.
- La guitarra es la separación menos precisa: suele mezclarse algo de teclados o de otras guitarras.

Los archivos son WAV de 32 bits float a 44.1 kHz: no se recortan los picos y REAPER, Ableton,
Logic o cualquier DAW los abre directo.
