# song-wizard

<p align="center"><img src="img/logo.png" width="160" alt="song-wizard"></p>

[![CI](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml/badge.svg)](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml)

Herramienta de terminal para preparar temas para ensayar con la banda. Es un proyecto personal, hecho por hobby y sin fines comerciales.

- **download**: baja el audio de un link (un tema o una playlist) en la mejor calidad disponible, sin recomprimir.
- **key**: detecta la tonalidad.
- **bpm**: detecta el tempo y avisa si varía a lo largo del tema.
- **click**: genera una pista de click fija, con el tempo, el compás y la duración que quieras.
- **transpose**: sube o baja el tono sin cambiar el tempo.
- **speed**: hace un tema más lento (o más rápido) sin cambiar el tono, para sacarlo de a poco.
- **separate**: separa tu instrumento del resto del tema (voz, batería, bajo o guitarra).
- **convert**: convierte a MP3 (o M4A) para compartir, por ejemplo por WhatsApp.
- **rename**: cambia el nombre de un tema y de todo lo que se generó a partir de él.
- **delete**: manda a la papelera un tema (con todo lo que se generó a partir de él) o archivos sueltos.
- **list**: muestra los temas de tu carpeta de música (y de donde hayas bajado), con lo que se detectó de cada uno.
- **report**: si algo falla, arma un reporte para pedir ayuda.
- **ui**: todo lo anterior desde una página en el navegador, sin usar la terminal.

Todo menos `download` funciona con cualquier archivo de audio que tengas: grabaciones de ensayo, temas comprados, maquetas propias, etc.

Funciona en **Mac con chip M** (M1 a M5, con macOS 15 o más nuevo), **Linux** y **Windows con WSL**. No funciona en Mac con procesador Intel.

## Requerimientos

song-wizard está escrito en Python, pero usa algunos programas externos que hay que instalar aparte. Los comandos de [Instalación](#instalación) instalan todos; acá se explica para qué sirve cada uno. Todos son programas libres y de código abierto, y se instalan desde sus fuentes oficiales.

| Programa | Por qué hace falta | Cómo lo usa song-wizard |
|---|---|---|
| [**uv**](https://docs.astral.sh/uv/) | Instala song-wizard y sus librerías de Python en un entorno aislado, sin tocar el Python del sistema. Si hace falta, también baja Python 3.12. | `uv tool install` deja disponible el comando `song-wizard`, y `song-wizard upgrade` lo actualiza. |
| [**ffmpeg**](https://ffmpeg.org) | Lee y convierte cualquier formato de audio (Opus, MP3, M4A, WAV…). | Decodifica los temas antes de detectar la tonalidad, transponer o separar. En `download`, yt-dlp lo usa para extraer el audio (y para generar los `.wav` con `--wav`). |
| [**deno**](https://deno.com) | Algunos sitios exigen resolver un desafío en JavaScript antes de dejar descargar, y deno es el programa que ejecuta ese JavaScript. Node v20 o más nuevo también sirve. | yt-dlp, el motor de descarga, lo detecta y lo usa solo en `download`. |
| [**rubberband**](https://breakfastquay.com/rubberband/) | Cambia el tono sin cambiar el tempo, o el tempo sin cambiar el tono, con muy buena calidad. | `transpose` le pasa los semitonos y genera `Título (+2).wav`; `speed` le pasa la velocidad y genera `Título (80%).wav`. |

En Linux y WSL además se instalan `curl` (para bajar los instaladores oficiales de uv y deno) y `build-essential` + `python3-dev`, para compilar una librería de Python que no viene precompilada. En Mac no hace falta, porque el compilador ya lo instala Homebrew.

Las librerías de Python que hacen el trabajo pesado las instala uv automáticamente: [yt-dlp](https://github.com/yt-dlp/yt-dlp) para las descargas, [Essentia](https://essentia.upf.edu) para la tonalidad, y [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) y [PyTorch](https://pytorch.org) para separar instrumentos.

Todo se procesa en tu computadora: song-wizard no manda tus archivos a ningún servidor. Solo se conecta a internet para bajar los temas que le pidas, bajar los modelos de separación la primera vez y actualizarse.

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

Conviene hacerlo seguido: los sitios cambian a menudo y las descargas pueden dejar de andar hasta actualizar.

### Qué se guarda en tu computadora

| Qué | Dónde | Tamaño |
|---|---|---|
| song-wizard y sus librerías | `~/.local/share/uv/tools/song-wizard` | ~6 GB en Linux/WSL (incluye las librerías de NVIDIA para usar la placa de video); bastante menos en Mac |
| Modelos de separación | Linux/WSL: `~/.local/share/song-wizard/models`<br>Mac: `~/Library/Application Support/song-wizard/models` | ~1.3 GB si usás los cuatro instrumentos; se bajan la primera vez que se usa cada uno |
| Registro de temas ya bajados | Linux/WSL: `~/.local/share/song-wizard/archives`<br>Mac: `~/Library/Application Support/song-wizard/archives` | unos pocos KB |
| Log (qué comandos corrieron y los errores, para resolver problemas) | Linux/WSL: `~/.local/share/song-wizard/logs`<br>Mac: `~/Library/Application Support/song-wizard/logs` | 2 MB como máximo: lo más viejo se borra solo |
| Reportes de `song-wizard report` | Linux/WSL: `~/.local/share/song-wizard/reports`<br>Mac: `~/Library/Application Support/song-wizard/reports` | unos pocos KB cada uno; se pueden borrar |
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

- **Biblioteca**: las carpetas de tu carpeta de música con sus temas, la tonalidad y el tempo de cada uno si ya los detectaste, y los archivos generados de cada tema (stems, versiones transpuestas o con otra velocidad, MP3), cada uno con su casilla para usarlo en las acciones (con Shift, la casilla elige o saca todo lo que hay entre la última que tocaste y esa). Los archivos de cada tema arrancan plegados ("▸ 5 archivos") para que la lista no se haga larga; "desplegar todo" y "plegar todo" los abren y cierran de una vez, y el navegador recuerda cuáles dejaste abiertos. Con ▶ se escucha cualquiera y con ✎ se renombra un tema. Tocando la tonalidad o el tempo se corrige a mano lo que detectó el sistema (ver [Corregir la tonalidad o el tempo](#corregir-la-tonalidad-o-el-tempo-a-mano)). "setlist" abre la lista de la carpeta lista para imprimir (ver [Setlist](#setlist)). "abrir" muestra la carpeta en el Explorador de archivos (o el Finder en Mac). Si cambiás archivos por fuera (los copiás, renombrás o borrás), la biblioteca se actualiza sola al volver a la página, o con "↻ actualizar".
- **Practicar**: el botón "practicar" de cada tema abre un reproductor con una pista por instrumento separado (con volumen, silencio y solo para cada una), un click que acompaña al tema con cuenta antes de entrar, la velocidad en vivo sin cambiar el tono (de 50 % a 150 %), el tono en vivo sin cambiar la velocidad (6 semitonos para cada lado) y la repetición de un tramo entre dos marcas A y B. Ver [Practicar](#practicar).
- **Bajar**: pegás el link de un tema o de una playlist arriba de todo. "en Música" elige otra carpeta para las playlists nuevas (escribiendo la ruta o con "elegir…", que abre el selector de carpetas del sistema).
- **Borrar**: "borrar archivos seleccionados", al lado de lo elegido, muestra exactamente qué archivos se van y los manda a la papelera del sistema. Ver [Borrar](#borrar).
- **Pista de click**: con un tema elegido se completan su tempo (si ya lo detectaste), su duración y los compases que la cubren; para un compás más, le sumás 1.
- **Acciones** sobre los temas elegidos, o sobre un archivo suelto (por ejemplo, para cambiar la velocidad solo de la batería separada o medir el tempo sobre ella): tonalidad, tempo, separar instrumentos, transponer, cambiar la velocidad, convertir y generar un click.
- **Reproductor de abajo**: el ▶ de cualquier archivo lo escucha ahí, con su forma de onda; tocando el dibujo se salta a esa parte.
- **Trabajos**: lo que está corriendo, con una barra de avance y el tiempo que lleva; se puede cancelar. Corren de a uno.
- **Playlists bajadas**: las mismas de `song-wizard archives`, con la opción de buscar temas nuevos, moverlas a otra carpeta (van enteras y se siguen viendo en la biblioteca, con su ubicación) o olvidarlas. Las carpetas que son una playlist también tienen "buscar temas nuevos": baja solo lo que se agregó a la playlist desde la última vez.

La interfaz queda corriendo de fondo y la terminal queda libre para otra cosa (o para cerrarla). Volver a escribir `song-wizard ui` abre la misma interfaz, sin arrancar otra. Para cerrarla: "apagar" (abajo, en Trabajos) o `song-wizard ui --stop`; si hay algo corriendo, pregunta antes. Con `--foreground` queda en la terminal como antes, y Ctrl+C la cierra.

En WSL, Linux se apaga solo un rato después de cerrar todas sus terminales, y la interfaz con él: si la usás con todas las ventanas de Ubuntu cerradas y deja de responder, volvé a abrirla con `song-wizard ui`.

Funciona solo en tu computadora: el servidor no acepta conexiones de afuera, y cada vez que se abre usa una clave nueva en el link, así que ni otras páginas abiertas en el navegador pueden usarla. Si el navegador no se abre solo, abrí el link que muestra la terminal.

#### Practicar

Con "Todos" separado, el reproductor tiene las cinco pistas (voz, batería, bajo, guitarra y otros); si separaste un instrumento solo, ese instrumento y el resto del tema (y si separaste varios por separado, elegís cuál arriba); sin stems, el tema original, que igual sirve para practicar más lento o repetir un tramo.

- Cada pista tiene su volumen, **M** para silenciarla y **S** para escuchar solo esa (se pueden sumar varias en solo). Arriba de todas, **Maestro** sube o baja todo junto (el navegador lo recuerda).
- La velocidad cambia mientras suena y el tono no cambia. Para guardar una versión más lenta como archivo, está [Cambiar la velocidad](#cambiar-la-velocidad).
- **Tono**: sube o baja el tema hasta 6 semitonos sin cambiar la velocidad, por ejemplo para probar otra tonalidad para el que canta; si el tema tiene tonalidad detectada, muestra a cuál queda (Am → Gm). El click no cambia y sigue a tiempo. Al cambiarlo hay un instante de silencio. Es calidad de ensayo: para una versión prolija como archivo (por ejemplo para compartir), está [Cambiar el tono](#cambiar-el-tono), que suena mejor.
- Para repetir un tramo: **A** donde empieza y **B** donde termina; al marcar B empieza a repetir. "repetir" lo prende y apaga, y la marca se ve sobre la barra.
- La barra muestra la forma de onda del tema: tocándola se salta a esa parte.
- Con el teclado: espacio reproduce y pausa, `[` y `]` marcan A y B, `L` repite, las flechas saltan 5 segundos, `-` y `+` cambian la velocidad, `1` a `5` silencian una pista y `C` el click. `D` muestra cuánto se separan las pistas entre sí (deberían quedar en unos pocos milisegundos).

**El click.** La última pista del reproductor es un click que sigue al tema: cae en cada tiempo aunque saltes a cualquier parte, repitas un tramo o cambies la velocidad, y como lo genera el navegador en el momento, suena nítido también a velocidades bajas. Para que coincida con el tema hace falta su tempo exacto y dónde cae el primer golpe; se ajustan en "Ajustar el click":

- "detectar" los busca en el tema (lo mismo que `song-wizard align`, ver abajo). Si el tempo quedó a la mitad o al doble del real, ÷2 y ×2 lo corrigen.
- La vista ampliada muestra el principio del tema con las líneas del click encima (la marcada es el primer tiempo de cada compás): arrastrando sobre el dibujo se mueven hasta que caigan sobre los golpes. Para el ajuste fino, −10 ms y +10 ms; si el primer tiempo quedó en otro tiempo del compás, −1 tiempo y +1 tiempo. "escuchar el principio" lo reproduce con el click para comprobarlo de oído.
- Se guarda solo, en `click.txt` en la carpeta del tema (como `key.txt` y `bpm.txt`), y `rename` lo renombra con el tema.

**La cuenta.** Con el click encendido, al dar play desde el principio suena la cuenta (uno o dos compases, o ninguna) y la música entra en su tiempo: si el tema empieza con un silencio, parte de la cuenta cae sobre ese silencio, así que la música entra justo donde corresponde. Con "también al seguir desde una pausa", la cuenta suena también al retomar desde cualquier punto, para practicar una parte.

Medido en Edge: el click cae a ~1 ms del tema, también después de saltar y a 125 %; la cuenta y la entrada de la música, a 3 ms. Por debajo de 100 % el navegador demora un poco el tema al estirarlo y song-wizard lo compensa en Brave, Chrome y Edge (en Firefox y Safari, todavía no); a esas velocidades el tema estirado igual "baila" unos ±15 ms de golpe a golpe, por cómo lo estira el navegador.

Las pistas se escuchan desde la carpeta de música a medida que suenan, sin cargarlas enteras en memoria.

#### La interfaz y la terminal

Todo lo que hace la interfaz se puede hacer también desde la terminal; casi siempre es el mismo comando que la interfaz usa por detrás:

| En la interfaz | En la terminal |
|---|---|
| Biblioteca | `song-wizard list` (`list TEXTO` filtra, `--files` muestra los stems y versiones de cada tema) |
| Bajar (y "en Música" para elegir la carpeta) | `song-wizard download URL` (`--wav`, `--to CARPETA`) |
| "buscar temas nuevos" | `song-wizard archives --update N` (o `all`) |
| Playlists bajadas: mover, olvidar | `song-wizard archives` (`--move N CARPETA`, `--delete N`) |
| "abrir" | `song-wizard open` (la carpeta de música, o la que digas) |
| Tonalidad, Tempo | `song-wizard key`, `song-wizard bpm` |
| Tocar la tonalidad o el tempo para corregirlos | `song-wizard key --set Am TEMA`, `song-wizard bpm --set 120 TEMA` |
| Separar instrumentos | `song-wizard separate --stem ...` |
| Cambiar el tono, Cambiar la velocidad | `song-wizard transpose`, `song-wizard speed` |
| Convertir para compartir | `song-wizard convert` |
| Pista de click | `song-wizard click` (`--for TEMA` le pone el nombre del tema) |
| Ajustar el click (detectar, tempo, primer golpe) | `song-wizard align` (`--bpm`, `--first`, `--meter`) |
| ✎ renombrar | `song-wizard rename` |
| Borrar archivos seleccionados | `song-wizard delete` |
| Reportar un problema | `song-wizard report` |
| "apagar" | `song-wizard ui --stop` |
| "setlist" | `song-wizard setlist CARPETA` |
| Practicar | Es un reproductor, así que vive en el navegador: `song-wizard ui --practice TEMA` lo abre directo en ese tema |

### Bajar temas

```bash
song-wizard download "https://.../playlist?list=..."   # una playlist
song-wizard download "https://.../watch?v=..."         # un tema suelto
```

- Las playlists se guardan en `Música/<nombre de la playlist>/001 - Título.opus`, numeradas en orden. Los temas sueltos van a `Música/Singles/`. En WSL, "Música" es la carpeta Música de Windows.
- Si volvés a correr la misma playlist, solo baja los temas nuevos, numerados según su lugar en la playlist (y con `.wav` si la primera vez usaste `--wav`, en la interfaz). En la interfaz es el botón "buscar temas nuevos" de la carpeta de la playlist. Los temas que se sacaron de la playlist no se borran de tu carpeta.
- `--wav` además genera un `.wav` de cada tema (misma calidad, ocupa 10 veces más).
- Para playlists privadas: agregá `--cookies-from-browser chrome` (o `firefox`, `safari`) al final.
- Para guardar una playlist nueva en otra carpeta (por ejemplo, una que se sincroniza con la nube): `--to "G:\Mi unidad\Ensayos"` (en WSL sirven las rutas de Windows). Adentro se crea la carpeta de la playlist.
- En WSL, la unidad de Google Drive para Windows (por ejemplo `H:`) aparece después de que arranca WSL y no se conecta sola: si song-wizard dice que no ve la unidad, conectala con `sudo mkdir -p /mnt/h && sudo mount -t drvfs H: /mnt/h` (cambiando `h` por su letra). Hay que repetirlo cada vez que se reinicia WSL; para que se conecte sola, agregá la línea `H: /mnt/h drvfs defaults,nofail 0 0` a `/etc/fstab` (con `nofail`, si Drive todavía no arrancó, WSL sigue igual).
- Una playlist que ya bajaste sigue bajándose en su carpeta, esté donde esté, aunque la hayas movido con `archives --move` (ver abajo).
- Para cambiar la carpeta de música de todo: `music_dir` en `song-wizard config`, o `SONG_WIZARD_DIR=~/Ensayos`.
- Para volver a bajar temas que ya están en el registro: agregá `--no-download-archive` al final. Si los archivos siguen en la carpeta, sumá también `--force-overwrites`, porque si no se saltean igual.

Para ver qué playlists bajaste y cuántos temas de cada una:

```bash
song-wizard archives
```

```
   #  Playlist                 Songs  Last download
   1  Ensayo diciembre            11  2026-10-31 18:44
   2  Singles (single links)       1  2026-10-31 18:44
```

Para llevar una playlist a otra carpeta sin perder nada (temas, stems, resultados y su registro): `song-wizard archives --move 1 "G:\Mi unidad\Ensayos"`. Queda en `G:\Mi unidad\Ensayos\<nombre de la playlist>`, la interfaz la sigue mostrando y los temas nuevos se bajan ahí. Si ya la moviste a mano, el mismo comando solo anota dónde está ahora.

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

### Corregir la tonalidad o el tempo a mano

Si la detección se equivocó (o ya sabés cómo es el tema), lo escribís vos y queda en lugar de lo detectado. En la interfaz, tocando la tonalidad o el tempo del tema (si todavía no se analizó, aparecen "tono?" y "BPM?" al pasar el mouse); en la terminal:

```bash
song-wizard key --set Am "tema.opus"
song-wizard key --set "Sib mayor" "tema.opus"   # también en español: La menor, Fa#m, Do
song-wizard bpm --set 98.5 "tema.opus"
```

Queda marcado "set by hand" en `key.txt` / `bpm.txt` (✍ en la interfaz), y volver a analizar la carpeta no lo pisa. Para detectarlo de nuevo desde el audio: `--force`, o "detectar" en la interfaz. Si el tema tiene el click de práctica ajustado a otro tempo, avisa para que lo corrijas en [Practicar](#practicar).

### Pista de click

Genera un click fijo, con el primer tiempo de cada compás acentuado:

```bash
song-wizard click 120                            # 120 BPM, 4/4, 1 minuto
song-wizard click 96 --meter 3/4 --bars 32       # 32 compases de 3/4
song-wizard click 123 --duration 4:30            # 4 minutos y medio
song-wizard click 105.6 --like "tema.opus"       # tan largo como un tema, y con su nombre
song-wizard click 92 --bars 8 --for "tema.opus"  # con el nombre del tema, pero de 8 compases
song-wizard click 90 --subdivide 2               # con corcheas
```

- Genera `Click 120 BPM 4-4.wav` en la carpeta donde lo corrés; `-o` elige otro archivo o carpeta.
- Con `--like` o `--for`, el click lleva el nombre del tema y queda a su lado: `tema (click 105.6 BPM 4-4).wav`. Así la interfaz lo muestra con los archivos del tema, y `rename` lo renombra junto con el resto. En la interfaz pasa lo mismo cuando hay un solo tema (o un archivo de un tema) elegido.
- Acepta tempos con decimales, así podés usar el número exacto que da `song-wizard bpm`.
- La duración se redondea hacia arriba a compases completos. Sin `--duration`, `--bars` ni `--like`, dura un minuto.
- `--subdivide` agrega clicks más suaves entre tiempo y tiempo: `2` = corcheas, `3` = tresillos, `4` = semicorcheas.
- El compás: el número de arriba es la cantidad de clicks por compás (`4/4` = 4, `3/4` = 3, `6/8` = 6).
- Es un click de tempo fijo: sirve para ensayar sin la grabación o a otro tempo. Si el tema original se grabó sin click (`bpm` dice `varies`), un click fijo se va a ir desfasando de la grabación.
- Para mandarlo por WhatsApp: `song-wizard convert "Click 120 BPM 4-4.wav"`.

### Tempo y primer golpe para el click

```bash
song-wizard align "tema.opus"                        # lo detecta
song-wizard align --bpm 103.06 --first 1.554 "tema.opus"   # a mano
song-wizard align "Música/Show"                     # todos los temas de la carpeta
```

Busca el tempo exacto (con decimales) y dónde cae el primer golpe, y lo guarda en `click.txt`, que el click del reproductor de práctica usa para acompañar al tema. `--meter` cambia el compás (4/4 si no se dice). Como cualquier detector de tempo, puede dar la mitad o el doble del real: se corrige con `--bpm` o con ÷2 y ×2 en la interfaz. Si el tempo del tema varía (grabado sin click), lo avisa: un click fijo se va a ir desfasando.

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

### Renombrar un tema

```bash
song-wizard rename "001 - Tema (Official Video).opus" "Tema"
```

Cambia el nombre del tema y de todo lo que se generó a partir de él: el `.wav` o el `.mp3`, los stems, las versiones transpuestas o con otra velocidad, y sus líneas en `key.txt` y `bpm.txt`. Queda `001 - Tema.opus`, `001 - Tema (drums).wav`, etc. Se puede pasar cualquier archivo del tema, no solo el original.

La numeración (`001 - `) se mantiene, salvo que el nombre nuevo traiga la suya (`"005 - Tema"`). Si alguno de los nombres nuevos ya existe, no renombra nada. Tampoco acepta los caracteres que Windows no permite en nombres de archivo (`\ / : * ? " < > |`).

Bajar de nuevo la playlist no vuelve a bajar el tema renombrado: el registro de descargas guarda qué link se bajó, no el nombre del archivo.

### Borrar

```bash
song-wizard delete "001 - Tema.opus"              # el tema con todo lo suyo
song-wizard delete "001 - Tema (drums).wav"       # solo ese stem
song-wizard delete --file "001 - Tema.mp3"        # solo esa copia
```

Todo va a la papelera del sistema (en WSL, a la Papelera de reciclaje de Windows si el archivo está en un disco de Windows), así que se puede recuperar. Si algo no se puede mandar a la papelera, se detiene y no borra nada más.

- Un tema se va con todo lo que se generó a partir de él (sus otros formatos, stems, versiones y clicks) y con sus líneas en `key.txt`, `bpm.txt` y `click.txt`.
- Si era de una playlist, sale también de su registro: "buscar temas nuevos" (o volver a correr `download`) lo vuelve a bajar.
- Un stem, una versión o un click se van solos; `--file` borra solo ese archivo aunque sea una copia del tema, como el `.mp3`.
- Pide confirmación antes de borrar; `--yes` no pregunta.

### Setlist

```bash
song-wizard setlist "Música/Show"
```

```
Show

  1. Tema uno     Am   106   5:08  (Artista)
  2. Tema dos     F#m? 178   4:11  (Otro artista)
  ...
23 songs, 1:40:00
```

La lista de la carpeta en el orden de sus archivos (`001 - …`), con la tonalidad, el tempo y la duración de cada tema, y el total. Guarda `Setlist.txt` y `Setlist.html` en la carpeta; el `.html` se abre en el navegador y se imprime en una hoja A4, con la letra lo más grande que entre. En la interfaz, el botón "setlist" de cada carpeta abre la misma hoja.

- La tonalidad y el tempo salen de lo que ya detectaste con `key` y `bpm` (o pusiste a mano); los que falten quedan en blanco. Un `?` marca una tonalidad dudosa.
- El nombre se limpia: sin el número, y sin agregados como "(Official Video)" o "[HD]". Si el archivo se llama "Artista - Tema", el artista va más chico al lado. Si quedó al revés, se arregla con ✎ / `rename`.
- `--title` cambia el título de arriba (por defecto, el nombre de la playlist o de la carpeta).

### Si algo falla

```bash
song-wizard report
```

Arma un archivo de texto con el estado de tu computadora (lo mismo que muestra `song-wizard setup`) y lo último que hizo song-wizard, incluido el error completo. Te muestra dónde quedó, y si querés abre la carpeta y el formulario para reportar el problema en GitHub, ya completado: ahí contás qué pasó y arrastrás el archivo. ¿Sin cuenta de GitHub? Mandale el archivo por WhatsApp o mail a quien te ayude con song-wizard.

En la interfaz es el botón "reportar un problema", arriba de los trabajos; los que fallan tienen también su botón "reportar".

El reporte no incluye audio. Tu carpeta personal aparece como `~` (por ejemplo `~/Music/...` en vez de `/home/tu-usuario/Music/...`), pero los nombres de temas y carpetas quedan: si no querés que se vean, revisá el archivo antes de mandarlo. Sale de un log que song-wizard guarda siempre (ver [Qué se guarda en tu computadora](#qué-se-guarda-en-tu-computadora)) y que nunca se manda solo a ningún lado.

## Aviso legal

song-wizard es un proyecto personal, hecho por hobby para preparar ensayos, **sin fines comerciales**: no se vende, no se cobra y no se monetiza de ninguna forma. Esto no es asesoramiento legal.

- **Sos responsable de lo que bajás y procesás.** Usalo solo con audio sobre el que tengas derechos o permiso de uso, y respetá los derechos de autor y los términos de servicio de cada sitio, que en general no permiten descargar contenido salvo con sus propias funciones. No compartas ni publiques los temas, stems o pistas que generes a partir de material ajeno.
- **No apto para uso comercial.** Aunque el código de song-wizard es libre (ver [Licencia](#licencia)), algunas piezas que usa no lo permiten o no tienen una licencia clara: [diffq](https://github.com/facebookresearch/diffq) (una dependencia de audio-separator) tiene licencia CC BY-NC 4.0, que prohíbe el uso comercial; y los modelos de separación (Demucs, el Mel-Band Roformer de voz y los modelos de UVR) no indican la licencia de sus pesos entrenados. Cualquier uso comercial requiere revisar esas licencias por separado.
- **Sin afiliación.** song-wizard no está afiliado ni respaldado por ninguna plataforma de audio o video ni por los proyectos que usa. Todas las marcas pertenecen a sus dueños.
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
- `key.txt` y `bpm.txt` (también la tonalidad y el tempo puestos a mano, en inglés o en español, que volver a analizar no pisa), la configuración, la carpeta de música y los registros de `archives`.
- `setlist`: orden, nombres limpios, tonalidad dudosa marcada, total, nombres con HTML mostrados como texto, y la hoja desde la interfaz (solo con la clave).
- El tono en vivo del reproductor (corriendo el procesador con Node): afinación exacta, nada agregado y el mismo retardo para cada tono.
- `ui`: la seguridad (clave, dominio, rutas fuera de la carpeta de música, acciones inválidas), que corra de fondo (arranca una vez, se reusa, se apaga con `--stop` o desde la página, y solo con la clave), la biblioteca agrupada por tema, la reproducción por partes y un trabajo de click de punta a punta.

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
| `download` de un tema suelto y con `SONG_WIZARD_DIR` | Real (sin descargar) | ✅ Rutas correctas |
| `key` sobre 11 temas | Real | ✅ 9 con 4/4; los 2 dudosos marcan la alternativa (en ambos, la relativa o una quinta) |
| `bpm` sobre 11 temas | Real | ✅ 8 estables, 2 con tempo variable (121-125 y 144-147) y 1 dudoso que sugiere la mitad |
| `key` y `bpm` guardan `key.txt` / `bpm.txt`; volver a analizar un tema solo cambia su línea | Real | ✅ |
| `download --no-download-archive` | Real (sin descargar) | ✅ Ignora el registro y no lo modifica |
| `download` + `archives` (2 temas de una playlist y un tema suelto) | Real | ✅ Guarda el nombre de la playlist; la lista muestra la playlist con 2 temas y los sueltos con 1 |
| `archives` con un registro anterior, sin nombre guardado | Real | ✅ Busca el nombre de la playlist una vez y lo guarda |
| `archives --delete` con número inexistente, texto inválido o sin confirmar | Real | ✅ No borra nada y explica por qué |
| `archives --delete all --yes` | Real | ✅ Borra los registros; los temas bajados quedan intactos |
| `click` a 120 BPM 4/4, 96 BPM 3/4, 105.6 BPM durante 10 minutos, con tresillos y `--like` | Real | ✅ Cada golpe a 0.03 ms de su posición teórica (redondeo a la muestra), también a los 10 minutos; cantidad de golpes, acentos y subdivisiones correctos; `--like` cubre todo el tema |
| `ui`: seguridad | Real | ✅ Sin clave, con clave incorrecta o con otro dominio responde 403; rutas fuera de la carpeta de música, rechazadas; acciones que no existen, rechazadas |
| `ui`: todos los trabajos desde la API (tonalidad, tempo, transponer, separar, convertir, click, bajar, olvidar registros) | Real | ✅ Todos terminan bien; el avance de la separación se ve en vivo; cancelar a mitad de una separación la detiene |
| `ui`: elegir un archivo suelto (un stem o una versión con otra velocidad) | Real | ✅ Las acciones corren solo sobre ese archivo y el resultado queda agrupado bajo su tema; el click toma el tempo de lo elegido (al 80 %, el del tema × 0.8); los stems muestran su propia tonalidad y tempo si se analizaron |
| `ui`: acciones que no corresponden a lo elegido | Real | ✅ Separar solo se habilita con temas originales; cambiar el tono o la velocidad, con temas y stems pero no con versiones ya transpuestas o con otra velocidad; debajo de la acción se explica por qué |
| `ui`: "abrir" una carpeta | Real (WSL) | ✅ Abre el Explorador de Windows en la carpeta, tanto en `C:` como en una carpeta de Linux (`\\wsl.localhost\...`); rechaza carpetas fuera de la de música. En Mac (`open`) y Linux (`xdg-open`) **no probado** a mano |
| `ui`: barra de avance | Real | ✅ `speed` sobre 2 temas de 4:33 avanza de 0 a 100 % repartido entre los dos ("58% (2/2) other.opus"); la separación y las descargas muestran el porcentaje de cada paso; tonalidad y tempo, una barra animada sin porcentaje; el tiempo transcurrido se ve mientras corre y queda la duración al terminar |
| `rename` en una carpeta de `C:` (disco de Windows) | Real | ✅ Renombra el tema y su versión al 80 % y actualiza `key.txt`; mantiene el `001 - `; un cambio solo de mayúsculas (`song` → `Song`) funciona; rechaza `:` y no toca nada |
| `rename`: nombre ocupado o falla a mitad de camino | Simulada | ✅ No renombra nada, o deshace lo que ya había renombrado |
| `ui`: renombrar con ✎ | Real | ✅ Enter guarda y Escape cancela; lo escrito no se pierde si la biblioteca se actualiza mientras tanto; el tema y su stem quedan con el nombre nuevo |
| Log: cada comando, cómo terminó y sus errores | Real | ✅ Un trabajo de la interfaz que falla deja su comando, el error y el código de salida; un error inesperado deja el detalle completo, con lo que dijo el programa externo (ffmpeg, Rubber Band) |
| `report` | Real (WSL) | ✅ Guarda el archivo con `setup` y el final del log; la carpeta personal (`/home/…`, `/mnt/c/Users/…`, `C:\Users\…`) aparece como `~`; el link al formulario de GitHub entra en 2000 caracteres con las últimas líneas del log |
| `report`: abrir el formulario en el navegador desde la terminal | **No probado** | En WSL se abre con `cmd.exe start` escapando los `&` (verificado que `cmd` recibe el link entero); falta ver que el navegador lo abra |
| `ui`: "reportar un problema" | Real | ✅ Muestra el reporte entero antes de mandarlo, con el link a GitHub y el botón para mostrar el archivo |
| `ui`: practicar con 5 pistas de 5:41 (Edge, sin sonido) | Real | ✅ Las pistas no se separan más de 3 ms al arrancar, al saltar al minuto 2 y al 75 % (el tiempo avanza a 0.749, tono preservado); el tramo A-B se repite sin pasarse de B; silencio y solo dan los volúmenes correctos; detecta "Todos", un instrumento con su resto, o el tema solo |
| `ui`: practicar escuchando, en el navegador de todos los días | **Falta** | Lo anterior se midió con el sonido apagado; falta escucharlo con stems reales |
| `ui`: practicar en Mac (Safari) | **No probado** | Safari tiene `preservesPitch`; falta ver que reproduzca los WAV de 32 bits float de los stems |
| "buscar temas nuevos" de una playlist | Real (sobre una copia, sin tocar la carpeta real) | ✅ Con el registro de una playlist de 18 temas que tenía 10, bajó solo los 8 que faltaban, numerados 011 a 018; guarda la carpeta en el registro; los registros anteriores se reconocen por el nombre de la carpeta |
| Click con el nombre del tema (`--like`, `--for` y desde la interfaz con un tema elegido) | Real | ✅ `001 - Tema (80%) (click 96 BPM 4-4).wav` queda al lado del tema y la biblioteca lo agrupa con sus archivos; `-o` sigue eligiendo dónde |
| `align` sobre baterías sintéticas (90 a 137 BPM, con y sin silencio al principio) | Real | ✅ Tempo a ±0.02 BPM y primer golpe a ±1 ms; a 160 BPM da 80 (la mitad), que se corrige con ÷2/×2 o `--bpm` |
| `align` sobre un tema real de 4:33 | Real | ✅ 103.06 BPM (`bpm` dice 103.1) y el primer golpe donde arranca el sonido en la forma de onda |
| Click del reproductor contra el tema (Edge, sin sonido, grabando lo que sale) | Real | ✅ ~1 ms a 100 %, después de saltar y a 125 %; la cuenta de un compás, a 3 ms de su lugar, con la música entrando en su tiempo, también al retomar desde una pausa; al 75 %, −3 ms en promedio (±15 ms del tema estirado) |
| Click del reproductor escuchándolo | **Falta** | Medido con el sonido apagado; falta escucharlo en el navegador de todos los días |
| Forma de onda | Real | ✅ Un tema de 4:33 tarda ~2 s la primera vez (después queda guardada); el principio ampliado, 0.1 s |
| `delete` de un tema en una carpeta de `C:` | Real | ✅ El tema, su stem y su versión llegan a la Papelera de Windows (nombres con `ñ` y `⧸` incluidos); el otro tema queda; `key.txt` pierde su línea; el tema sale del registro de la playlist por el link que guarda el archivo |
| `delete`: un stem solo, una copia con `--file`, sin confirmar, papelera que falla | Simulada | ✅ Solo ese archivo; sin `--yes` y sin terminal no borra; si la papelera falla no toca nada más |
| `ui`: "borrar archivos seleccionados" | Real | ✅ La ventana lista exactamente qué se va (un tema con todos sus archivos, un stem solo) y arranca con "cancelar" elegido |
| `archives --move` con una ruta de Windows, de una carpeta de Linux a `C:` | Real | ✅ La playlist va entera (tema, stem y `key.txt`); un registro anterior, sin carpeta guardada, se encuentra por nombre; volver a moverla al mismo lugar avisa que ya está ahí |
| `download --to` y playlists ya bajadas que siguen en su carpeta | Simulada (sin descargar) | ✅ Las nuevas van a la carpeta pedida; las conocidas, a la suya; un `%` en la ruta no rompe la plantilla de yt-dlp |
| `ui`: playlist fuera de la carpeta de música | Real | ✅ Aparece en la biblioteca con su ubicación (en formato Windows en WSL), se escucha y se procesa; rutas para salir de su carpeta, rechazadas |
| `ui`: "elegir…" (selector de carpetas del sistema) | **No probado** | Abre el selector de Windows, del Finder o de zenity; falta probarlo a mano |
| `list`, `archives` (con la columna de carpeta) sobre la biblioteca real | Real (solo lectura) | ✅ Cada tema con su tonalidad, tempo y cantidad de archivos; `--files` los lista; las playlists dicen dónde están (Música y Drive) |
| `archives --update`, `open` | Simulada | ✅ Busca temas nuevos en las playlists elegidas (o `all`) con su `--wav`; los temas sueltos no tienen playlist y lo avisa; `open` abre la carpeta del archivo dado |
| Tonalidad y tempo a mano (`--set`, y tocando el badge en la interfaz) | Real (datos de prueba) | ✅ En Edge: tocar el tempo, escribir 100 y Enter lo guarda en `bpm.txt` marcado a mano y lo muestra con ✍; los temas sin analizar muestran "tono?" / "BPM?" al pasar el mouse; volver a correr `key`/`bpm` lo mantiene y `--force` lo reemplaza |
| `ui` de fondo: arrancar, reusar y apagar | Real (datos de prueba) | ✅ La terminal queda libre al instante; el servidor sigue después de cerrar la terminal que lo abrió; otro `ui` reusa el mismo; `--stop` lo cierra (pregunta si hay un trabajo corriendo); "apagar" en Edge lo cierra y la página avisa que está apagada; el archivo con la clave queda legible solo por el usuario. **Falta probar** cerrar todas las terminales de WSL |
| Tono en vivo en el reproductor (de -6 a +6 semitonos) | Real (audio sintético) | ✅ Tonos puros de 98 y 440 Hz llegan a la frecuencia pedida con un error menor a 3 cents; lo demás queda por debajo de -73 dB y el nivel se mantiene. El retardo es el mismo para todos los tonos (±1.5 ms). En Edge, grabando dentro del navegador, la música y el click quedan a 1 ms (tono 0), 4 ms (-3) y 2 ms (+3). **Falta escucharlo con temas reales** y comparar con `transpose` |
| `setlist` sobre la playlist real | Real (solo lectura, sin guardar en la carpeta) | ✅ Los 23 temas en orden con tonalidad, tempo y duración, total 1:40:00; impreso a PDF desde Edge entra en una A4 |
| `ui --practice` con un stem | Real | ✅ Abre la interfaz directo en el reproductor de su tema; con un archivo fuera de la biblioteca avisa y no arranca |
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
