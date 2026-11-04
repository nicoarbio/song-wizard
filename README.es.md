# song-wizard

<p align="center"><img src="img/logo.png" width="160" alt="song-wizard"></p>

[![CI](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml/badge.svg)](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml)

[English](README.md) · **Español**

Herramienta de terminal para preparar temas para ensayar con la banda. Es un proyecto personal, hecho por hobby y sin fines comerciales.

- **download**: baja el audio de un link (un tema o una playlist) en la mejor calidad disponible, sin recomprimir.
- **key**: detecta la tonalidad.
- **bpm**: detecta el tempo y avisa si varía a lo largo del tema.
- **click**: genera una pista de click fija, con el tempo, el compás y la duración que quieras.
- **transpose**: sube o baja el tono sin cambiar el tempo.
- **speed**: hace un tema más lento (o más rápido) sin cambiar el tono, para sacarlo de a poco.
- **separate**: separa tu instrumento del resto del tema (voz, batería, bajo o guitarra).
- **convert**: convierte a MP3 (o M4A) para compartir, por ejemplo por WhatsApp.
- **tag**: muestra o cambia los datos de un tema (título, artista, álbum, año, género…), en el tema y en todo lo que se generó a partir de él.
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
   uv tool install --exclude-newer "7 days" \
     --exclude-newer-package "yt-dlp=2 days" --exclude-newer-package "yt-dlp-ejs=2 days" \
     git+https://github.com/nicoarbio/song-wizard
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
uv tool install --exclude-newer "7 days" \
  --exclude-newer-package "yt-dlp=2 days" --exclude-newer-package "yt-dlp-ejs=2 days" \
  git+https://github.com/nicoarbio/song-wizard
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

Muestra dónde está el archivo de configuración y qué valores se están usando. El archivo se crea solo, con todo comentado, la primera vez que corrés cualquier comando. Por ahora guarda la carpeta de descargas. Lo que pases en cada comando siempre gana sobre el archivo.

- Linux/WSL: `~/.config/song-wizard/config.toml`
- Mac: `~/Library/Application Support/song-wizard/config.toml`

```toml
[download]
music_dir = "~/Ensayos"
```

### Actualizar

```bash
song-wizard upgrade              # instala la versión más nueva
song-wizard upgrade --check      # solo dice si hay una versión nueva
song-wizard upgrade --list       # las versiones publicadas
song-wizard upgrade --to 0.12.0  # instala otra versión, más nueva o más vieja
```

Cada versión publicada es un tag `vX.Y.Z` en GitHub. `upgrade` instala el más nuevo si tenés uno anterior; si ya tenés el más nuevo, actualiza lo que usa song-wizard (yt-dlp, sobre todo). Una versión con un problema grave se puede **retirar**: queda en `retired.txt` (en este repositorio) con el motivo, y entonces `upgrade` y la interfaz no la ofrecen, `--list` no la muestra (`--list --all` sí, con el motivo), `--to` no la instala salvo con `--force`, y a quien la tenga se le avisa y `upgrade` lo pasa a la más nueva que no esté retirada, aunque sea anterior. El tag no se borra.

**Una semana de espera, por seguridad.** Instalar y `upgrade` toman solo versiones de las librerías que usa song-wizard publicadas hace al menos 7 días (2 para yt-dlp, que los sitios rompen seguido): si alguna salió con código malicioso (les pasó a librerías populares, por una cuenta robada), en general se descubre y se retira en horas o días, antes de llegarte. song-wizard mismo viene de su tag en este repositorio. En GitHub, con cada cambio de dependencias y todos los lunes, se revisan contra las listas de vulnerabilidades y paquetes maliciosos conocidos. Si `uv` no entiende `"7 days"`, está viejo: `uv self update` (o `brew upgrade uv`).

Las versiones anteriores a la 0.15 no saben moverse por tags: si volvés a una de ellas con `--to`, para volver a la más nueva corré `uv tool install --force git+https://github.com/nicoarbio/song-wizard`.

En la interfaz, la versión aparece arriba, al lado del nombre (tocándola, busca de nuevo). Si hay una nueva, aparece "actualizar a …": actualiza, reinicia la interfaz y la misma página se recarga sola cuando está lista. Busca versiones nuevas a lo sumo cada 6 horas.

Conviene hacerlo seguido: los sitios cambian a menudo y las descargas pueden dejar de andar hasta actualizar.

### Qué se guarda en tu computadora

| Qué | Dónde | Tamaño |
|---|---|---|
| song-wizard y sus librerías | `~/.local/share/uv/tools/song-wizard` | ~6 GB en Linux/WSL (incluye las librerías de NVIDIA para usar la placa de video); bastante menos en Mac |
| Modelos de separación | Linux/WSL: `~/.local/share/song-wizard/models`<br>Mac: `~/Library/Application Support/song-wizard/models` | ~2 GB si usás los cuatro instrumentos (el piano sale del mismo modelo que la guitarra), y 0.4 GB más para la batería en partes; se bajan la primera vez que se usa cada uno |
| Modelos de acordes y de voz | Linux/WSL: `~/.local/share/song-wizard/models`<br>Mac: `~/Library/Application Support/song-wizard/models` | 12 MB (acordes) y 89 MB (las notas de la voz), cada uno se baja la primera vez que se usa |
| Registro de temas ya bajados | Linux/WSL: `~/.local/share/song-wizard/archives`<br>Mac: `~/Library/Application Support/song-wizard/archives` | unos pocos KB |
| Log (qué comandos corrieron y los errores, para resolver problemas) | Linux/WSL: `~/.local/share/song-wizard/logs`<br>Mac: `~/Library/Application Support/song-wizard/logs` | 2 MB como máximo: lo más viejo se borra solo |
| Reportes de `song-wizard report` | Linux/WSL: `~/.local/share/song-wizard/reports`<br>Mac: `~/Library/Application Support/song-wizard/reports` | unos pocos KB cada uno; se pueden borrar |
| Qué cambió song-wizard en Reaper (para mostrarlo y restaurarlo) | Linux/WSL: `~/.local/share/song-wizard/reaper.json`<br>Mac: `~/Library/Application Support/song-wizard/reaper.json` | menos de 1 KB |
| Copia de las preferencias de Reaper de antes de cambiarlas | Al lado de las de Reaper: `reaper.ini.before-song-wizard` (en Windows, en `%APPDATA%\REAPER`) | lo que pesen las de Reaper |
| Tus temas | La carpeta Música (o la que elijas) | lo que bajes |

Los modelos se bajan de fuentes públicas: los de Demucs, de los servidores de Meta (que lo creó), y los demás, de los repositorios públicos en GitHub del proyecto [UVR](https://github.com/Anjok07/ultimatevocalremovergui) y de audio-separator.

### Desinstalar

```bash
song-wizard uninstall
```

Primero muestra qué borra y cuánto ocupa cada cosa (los modelos de separación, el registro de playlists bajadas, los logs, la configuración y song-wizard mismo, con su propio Python y todo lo que usa), y pregunta. Si song-wizard cambió la preferencia de Reaper para las tomas (ver [Reaper](#reaper)), ofrece dejarla como estaba. `--keep-data` borra solo el programa y deja el resto, para instalarlo de nuevo más adelante.

Tus temas no se tocan. Tampoco ffmpeg, deno, rubberband ni uv, que pueden usar otros programas: si no los usás para otra cosa, desinstalalos vos con `brew uninstall` (Mac) o `sudo apt remove` (Linux). uv guarda un caché de descargas compartido con todo lo que instalás con él; `uv cache clean` lo vacía (no se rompe nada: se vuelve a bajar si hace falta).

## Uso

### Interfaz en el navegador

```bash
song-wizard ui
```

Abre una página en el navegador (en WSL, el navegador de Windows) con todo lo que hace song-wizard, sin escribir comandos:

- **Biblioteca**: las carpetas de tu carpeta de música con sus temas, la tonalidad y el tempo de cada uno si ya los detectaste, y los archivos generados de cada tema (stems, versiones transpuestas o con otra velocidad, MP3), cada uno con su casilla para usarlo en las acciones (con Shift, la casilla elige o saca todo lo que hay entre la última que tocaste y esa). Los archivos de cada tema arrancan plegados ("▸ 5 archivos") para que la lista no se haga larga; "desplegar todo" y "plegar todo" los abren y cierran de una vez, y el navegador recuerda cuáles dejaste abiertos. Con ▶ se escucha cualquiera. Cada tema se ve con su número, su título y, abajo, más chico, su artista, tomados del nombre del archivo ("001 - Artista - Título"; el nombre completo, al pasar el mouse). Su álbum, año y género no se muestran, pero el filtro los encuentra. "más" abre las otras acciones del tema: sus datos, la letra, los acordes, recortar y el proyecto de Reaper (el puntito en "más" indica que el tema ya tiene letra, acordes o proyecto). "más › Datos del tema…" muestra y cambia el título, el artista, el álbum y todo lo que guarda el archivo, y corregir el artista o el título le cambia el nombre (ver [Datos del tema](#datos-del-tema)). El filtro de arriba busca palabras sueltas, en cualquier orden y sin importar tildes ni mayúsculas, en el nombre, la carpeta y los datos de cada tema: "rock ultimo" encuentra los temas de género rock del álbum "Último show". Tocando la tonalidad o el tempo se corrige a mano lo que detectó el sistema (ver [Corregir la tonalidad o el tempo](#corregir-la-tonalidad-o-el-tempo-a-mano)). "más › Letra" muestra la letra del tema para marcarla con colores y notas (ver [Letras](#letras)), y "más › Crear proyecto de Reaper" o "Abrir en Reaper" lo lleva a Reaper (ver [Reaper](#reaper)). "setlist" arma la lista de la carpeta para imprimir, y "setlist con lo elegido" (abajo, junto a la selección) la arma con los temas que elegiste, de cualquier carpeta (ver [Setlist](#setlist)). "abrir" muestra la carpeta en el Explorador de archivos (o el Finder en Mac). Si cambiás archivos por fuera (los copiás, renombrás o borrás), la biblioteca se actualiza sola al volver a la página, o con "↻ actualizar".
- **Practicar**: el botón "practicar" de cada tema abre, en toda la ventana, un reproductor con la forma de onda de cada pista y la letra al costado, con una pista por instrumento separado (con volumen, silencio y solo para cada una), un click que acompaña al tema con cuenta antes de entrar, la velocidad en vivo sin cambiar el tono (de 50 % a 150 %), el tono en vivo sin cambiar la velocidad (6 semitonos para cada lado) la repetición de un tramo entre dos marcas A y B, y un monitor para escuchar un micrófono (la sala, la banda) en los auriculares, y los acordes del tema compás por compás, para corregir a mano. Ver [Practicar](#practicar).
- **Bajar**: pegás el link de un tema o de una playlist arriba de todo. "en Música" elige otra carpeta para las playlists nuevas (escribiendo la ruta o con "elegir…", que abre el selector de carpetas del sistema).
- **Borrar**: "borrar archivos seleccionados", al lado de lo elegido, muestra exactamente qué archivos se van y los manda a la papelera del sistema. Ver [Borrar](#borrar).
- **Pista de click**: con un tema elegido se completan su tempo (si ya lo detectaste), su duración y los compases que la cubren; para un compás más, le sumás 1.
- **Acciones** sobre los temas elegidos, o sobre un archivo suelto (por ejemplo, para cambiar la velocidad solo de la batería separada o medir el tempo sobre ella): tonalidad, tempo, separar instrumentos, transponer, cambiar la velocidad, convertir y generar un click.
- **Reproductor de abajo**: el ▶ de cualquier archivo lo escucha ahí, con su forma de onda; tocando el dibujo se salta a esa parte.
- **Trabajos**: lo que está corriendo, con una barra de avance y el tiempo que lleva; se puede cancelar. Corren de a uno.
- **Atajos de teclado**: casi todo se puede hacer con el teclado, y las teclas se pueden cambiar. "⌨ atajos" arriba (o `?`) los muestra todos. Ver [Atajos de teclado](#atajos-de-teclado).
- **Idioma**: "es · en · pt", arriba a la derecha, cambia la interfaz entre español, inglés y portugués (la primera vez toma el idioma del navegador). El navegador lo recuerda, y las hojas para imprimir (setlist, letra) y los mensajes del servidor lo siguen.
- **Colores**: arriba a la derecha, "automático" sigue al sistema (claro u oscuro, como lo tengas en Windows o en el Mac), y "claro" u "oscuro" lo dejan fijo. El navegador lo recuerda. Las hojas para imprimir (setlist, letra) son siempre claras.
- **Playlists bajadas**: las mismas de `song-wizard archives`, con la opción de buscar temas nuevos, moverlas a otra carpeta (van enteras y se siguen viendo en la biblioteca, con su ubicación) o olvidarlas. "agregar carpeta…" suma una carpeta copiada de otra compu o en Drive (ver [Playlists en otra compu](#playlists-en-otra-compu)). Las carpetas que son una playlist también tienen "buscar temas nuevos": baja solo lo que se agregó a la playlist desde la última vez.

La interfaz queda corriendo de fondo y la terminal queda libre para otra cosa (o para cerrarla). Volver a escribir `song-wizard ui` abre la misma interfaz, sin arrancar otra. Para cerrarla: "apagar" (abajo, en Trabajos) o `song-wizard ui --stop`; si hay algo corriendo, pregunta antes. `song-wizard ui --restart` la cierra y la vuelve a abrir (por ejemplo después de `upgrade`, que avisa si la interfaz sigue con la versión anterior). Con `--foreground` queda en la terminal como antes, y Ctrl+C la cierra.

En WSL, Linux se apaga solo un rato después de cerrar todas sus terminales, y la interfaz con él: si la usás con todas las ventanas de Ubuntu cerradas y deja de responder, volvé a abrirla con `song-wizard ui`.

Funciona solo en tu computadora: el servidor no acepta conexiones de afuera, y solo atiende a su propia página, así que otras páginas abiertas en el navegador no pueden usarla (el navegador le dice de dónde viene cada pedido). El link es siempre `http://127.0.0.1:8765` (o el puerto que muestre la terminal, si ese está ocupado), así que se puede guardar en favoritos. Si el navegador no se abre solo, abrí el link que muestra la terminal.

#### Practicar

Con "Todos" separado, el reproductor tiene las cinco pistas (voz, batería, bajo, guitarra y otros); si separaste un instrumento solo, ese instrumento y el resto del tema (y si separaste varios por separado, elegís cuál arriba); sin stems, el tema original, que igual sirve para practicar más lento o repetir un tramo.

El reproductor ocupa toda la ventana. Arriba están los controles: reproducir, velocidad, tono, el tramo A-B y el volumen maestro. Abajo, una fila por pista con su forma de onda, todas sobre el mismo eje de tiempo, y a la derecha, la letra. "⛶ pantalla completa" (o `F`) saca además las barras del navegador; Esc vuelve, y el reproductor sigue abierto.

- Cada pista tiene su fila: el nombre, **M** para silenciarla, **S** para escuchar solo esa (se pueden sumar varias en solo), su volumen y su forma de onda. Una pista que no suena se ve atenuada. Arriba de todas está la onda del tema entero. Tocando cualquier onda se salta a ese momento, y la posición y el tramo A-B se ven sobre todas. **Maestro**, arriba, sube o baja todo junto (el navegador lo recuerda).
- **Acercar**: la rueda del mouse sobre cualquier onda acerca y aleja todas las pistas juntas, alrededor del mouse (con Shift se mueve a los costados); también están − y +, "todo" y "tramo", que acerca al tramo A-B. Arriba de las pistas hay una barra con el tema entero y un recuadro sobre lo que se ve: se arrastra para moverse, un clic salta a otra parte y la rueda sobre la barra mueve a los costados. De cerca, cada onda se dibuja con más detalle. Mientras suena, la vista pasa de página cuando la posición llega al borde (si la acabás de mover a mano, espera unos segundos), y si saltás a otro momento, va ahí.
- La fila del click muestra sus golpes (si no entran, solo los compases), con el primero de cada compás marcado.
- La velocidad cambia mientras suena y el tono no cambia. Para guardar una versión más lenta como archivo, está [Cambiar la velocidad](#cambiar-la-velocidad).
- **Tono**: sube o baja el tema hasta 6 semitonos sin cambiar la velocidad, por ejemplo para probar otra tonalidad para el que canta; si el tema tiene tonalidad detectada, muestra a cuál queda (Am → Gm). El click no cambia y sigue a tiempo. Al cambiarlo hay un instante de silencio. Es calidad de ensayo: para una versión prolija como archivo (por ejemplo para compartir), está [Cambiar el tono](#cambiar-el-tono), que suena mejor.
- Para repetir un tramo: **A** donde empieza y **B** donde termina; al marcar B empieza a repetir. "repetir" lo prende y apaga, y el tramo se ve sobre las ondas.
- **Letra**: en la columna de la derecha está la letra del tema (en pantallas angostas, debajo de las pistas). "letra ▸" (o `Y`) la pliega para que las ondas ganen ancho, y el navegador lo recuerda. Viene con sus colores y notas, y se puede marcar ahí mismo con el mouse. Si la letra tiene tiempos, la línea que suena se resalta y la letra avanza sola (si la moviste con la rueda, espera unos segundos antes de seguir), y con doble clic en una línea el tema salta a ese momento. Si el tema no tiene letra, se puede buscar desde ahí.
- **Tiempos de la letra**: "tiempos" abre una columna a la izquierda con el momento en que empieza cada línea. Mientras suena el tema, tocás el tiempo de una línea justo cuando empieza a cantarse, o apretás T y se marca la línea siguiente: así una letra pegada queda sincronizada escuchando el tema una vez. La × borra un tiempo, y −0.5 s / +0.5 s corren todos juntos (por ejemplo, si tu versión tiene otra intro que la de la base de letras, de donde vienen los tiempos cuando los hay). Ctrl+Z deshace también esto.
- Con el teclado: espacio reproduce y pausa, las flechas saltan 5 segundos y con Shift un compás (según el click), `Inicio` vuelve al principio (o a A), `[` y `]` marcan A y B, `L` repite, `-` y `+` cambian la velocidad, `,` y `.` el tono, `R` vuelve todo a lo normal, `Z` y `X` acercan y alejan, `F` pasa a pantalla completa y `Y` muestra u oculta la letra. Para las pistas: `↑` y `↓` eligen una (se marca), `M` la silencia, `S` la pone en solo y Shift+`↑`/`↓` le cambian el volumen; además `1` a `9` y `0` (la décima) silencian una pista directo, Shift+número la pone en solo, y `C` prende o apaga el click. `I` prende o apaga el monitor. `D` muestra cuánto se separan las pistas entre sí (deberían quedar en unos pocos milisegundos). Debajo de las pistas está la lista corta; todas, y para cambiarlas, en [Atajos de teclado](#atajos-de-teclado).

**El click.** La última pista del reproductor es un click que sigue al tema: cae en cada tiempo aunque saltes a cualquier parte, repitas un tramo o cambies la velocidad, y como lo genera el navegador en el momento, suena nítido también a velocidades bajas. Para que coincida con el tema hace falta su tempo exacto y dónde cae el primer golpe; se ajustan en "Ajustar el click":

- "detectar" los busca en el tema (lo mismo que `song-wizard align`, ver abajo). Si el tempo quedó a la mitad o al doble del real, ÷2 y ×2 lo corrigen.
- La vista ampliada muestra el principio del tema con las líneas del click encima (la marcada es el primer tiempo de cada compás): arrastrando sobre el dibujo se mueven hasta que caigan sobre los golpes. Para el ajuste fino, −10 ms y +10 ms; si el primer tiempo quedó en otro tiempo del compás, −1 tiempo y +1 tiempo. "escuchar el principio" lo reproduce con el click para comprobarlo de oído. Si el principio no sirve para calibrar (un tema que arranca sin golpes marcados), dejalo sonar hasta donde entra el ritmo y tocá "ver donde suena": la vista va a ese punto, y como las líneas son una sola grilla para todo el tema, ajustarlas ahí las ajusta en todo el tema. "ver el principio" vuelve.
- Se guarda solo, en `click.txt` en la carpeta del tema (como `key.txt` y `bpm.txt`), y `rename` lo renombra con el tema.

**La cuenta.** Con el click encendido, al dar play desde el principio suena la cuenta (uno o dos compases, o ninguna) y la música entra en su tiempo: si el tema empieza con un silencio, parte de la cuenta cae sobre ese silencio, así que la música entra justo donde corresponde. Con "también al seguir desde una pausa", la cuenta suena también al retomar desde cualquier punto, para practicar una parte.

Medido en Edge: el click cae a ~1 ms del tema, también después de saltar y a 125 %; la cuenta y la entrada de la música, a 3 ms. Por debajo de 100 % el navegador demora un poco el tema al estirarlo y song-wizard lo compensa en Brave, Chrome y Edge (en Firefox y Safari, todavía no); a esas velocidades el tema estirado igual "baila" unos ±15 ms de golpe a golpe, por cómo lo estira el navegador.

Las pistas se escuchan desde la carpeta de música a medida que suenan, sin cargarlas enteras en memoria.

**Los acordes.** Debajo de la onda del tema hay una fila de acordes, en la misma línea de tiempo que las pistas: un bloque por acorde, ubicado sobre los tiempos del click, con el que suena resaltado. Al lado del botón de reproducir, en grande, el acorde que suena y el que sigue, para leerlo mientras tocás. "detectar" los encuentra (ver [Acordes](#acordes)); necesita primero el click ajustado, porque los acordes van sobre sus tiempos, así que si el tema no lo tiene abre "Ajustar el click".

- Siguen al tono: si subís el tema 2 semitonos, Am se lee Bm, para probar el tema en otro tono para la cantante.
- "simplificar" muestra solo mayor y menor (A7 → A, Am7 → Am), para el que quiere la versión fácil; el navegador lo recuerda.
- Si un cambio no cae donde lo escuchás, arrastrá el borde entre los dos acordes: se engancha a los tiempos del click (con Alt apretado, se mueve libre).
- Para corregir uno, tocalo: cambiale el nombre, partilo en el tiempo que tocaste, unilo con el siguiente o borralo. Lo corregido queda marcado con ✍ y volver a detectar no lo pisa. Un nombre que song-wizard no lee como acorde ("riff", "ver tab") se guarda igual, con un aviso: solo que no se transporta ni se simplifica.
- "ocultar acordes" (o `A`) oculta la fila y el "ahora → sigue", para el que no los necesita (el baterista, por ejemplo); el navegador lo recuerda.
- Acercá con la rueda para leerlos: con el tema entero a la vista, los acordes muy cortos muestran su nombre solo al pasar el mouse.

**Las notas.** En las filas del bajo y de la voz (con esos instrumentos separados), sus notas, a la altura de su tono, así también se ve el dibujo de la línea, con sus nombres cuando entran (acercá para leerlos; la octava aparece al pasar el mouse). "detectar notas", al lado del nombre de la pista, las encuentra (ver [Notas](#notas)); también "detectar" en la fila de acordes, que detecta acordes y notas juntos, y "más › Detectar las notas" en la biblioteca. Cada parte necesita solo su pista: con "Bajo y el resto", las notas del bajo. "escuchar", al lado del nombre de la pista, las hace sonar con un tono suave, siguiendo la velocidad y el tono: para aprender la melodía o la línea de bajo, más lento si hace falta. Para corregir una, tocala y escribí la nota (E, Eb, F#2: sin el número mantiene su octava), o borrala; lo corregido se mantiene al volver a detectar. "ocultar notas", también al lado del nombre, oculta las notas de esa pista ("ver notas" las vuelve a mostrar); el navegador lo recuerda. Siguen al tono como los acordes.

**Los trabajos, sin salir.** Lo que mandás a hacer (detectar acordes o notas, el click…) sigue mientras practicás: "trabajos", arriba, dice cuántos hay en curso para este tema y abre su lista ("de todos los temas" muestra todos), y la fila que se está detectando muestra su avance en lugar del botón "detectar". Al terminar, los acordes o las notas aparecen solos.

**El monitor.** "🎤 monitor" abre una barra para escuchar un micrófono (la sala, la banda) en los auriculares, mezclado con las pistas: para ensayar con in-ears puestos sin sacarte uno. "prender" le pide el micrófono al navegador (la primera vez pide permiso) y lo prende; arranca apagado y bajo cada vez. Tiene:

- **Entrada**: qué micrófono. El navegador lo recuerda; si no está enchufado, usa el predeterminado.
- **El nivel** que llega al micrófono (el volumen del monitor no lo cambia). Si dice "satura", va a sonar roto por más bajo que lo pongas: alejá el micrófono o bajale el nivel en la configuración de sonido de Windows (y apagá las "mejoras de audio" de Windows, si el micrófono las tiene).
- **Volumen**, aparte del maestro: la mitad es el micrófono tal cual llega (0 dB), y va de silencio a +12 dB. "silenciar" lo calla sin apagarlo.
- **Cortar graves**: saca lo que está debajo de 120 Hz. El bombo ya te llega por el cuerpo, y es lo que más satura un micrófono de laptop. Viene prendido.
- **Limitador**: solo frena los picos sueltos que pasan de −6 dB (un platillo pegado al micrófono, un golpe al micrófono), para cuidarte los oídos; por debajo de eso, el volumen no cambia nada. "limitando" se prende mientras está frenando un pico. Viene prendido y se puede apagar (lo avisa, y el navegador lo recuerda). Suma unos 6 ms de demora.
- **Demora**: lo que el navegador estima que tarda el micrófono en llegarte a los oídos.

Ojo, honestamente: en el navegador el micrófono llega unas decenas de milisegundos tarde. Con una batería acústica oís tu golpe directo y, un momento después, por el micrófono: puede sonar doble. Anda mejor bajo, para oír a la banda y la sala más que tu propia batería. Solo anda con la página abierta en la misma PC (`localhost`): los navegadores no dejan usar el micrófono por la red local sin https. Al cerrar Practicar se apaga.

#### Atajos de teclado

"⌨ atajos" (arriba a la derecha), `?` o "todos los atajos" en Practicar abren la lista de todos los atajos, separados por dónde valen: la biblioteca, Practicar y la ventana de la letra. Mientras escribís en un campo de texto no hacen nada.

- **En la biblioteca**: `↑` y `↓` recorren los temas (el elegido se marca; también se elige tocándolo), y sobre ese tema `Enter` lo escucha, `P` lo abre en Practicar, `L` abre su letra, `.` su menú "más", `E` sus datos, `X` lo suma a lo elegido (o lo saca), `→` y `←` muestran u ocultan sus stems y versiones. `/` va al filtro. Espacio pausa o sigue el reproductor de abajo, y Shift+`←`/`→` lo mueven 5 segundos.
- **En los datos del tema**: Enter guarda, Esc cierra sin guardar, y Ctrl+Enter ("guardar y seguir") guarda y abre los datos del tema siguiente de la lista, para corregir una playlist entera de corrido.
- **Cambiar una tecla**: en la lista, tocás la tecla y apretás la nueva. "+" agrega otra tecla para lo mismo y × la saca. Si la tecla nueva ya hace otra cosa en el mismo lugar, pregunta: al cambiar una tecla se intercambian, y al agregarla, la otra acción se queda sin ella. Las cambiadas llevan ✍ y "restablecer todo" vuelve a las de fábrica. Se guardan en el navegador (como los colores). Los botones muestran su atajo al pasar el mouse, con las teclas que tengas.
- **Pedales**: un pedal para pasar páginas (los de partituras, por Bluetooth o USB) manda teclas como cualquier teclado: se le asigna lo que quieras, por ejemplo reproducir y pausar, para practicar sin sacar las manos del instrumento.
- **MIDI**: con "usar un aparato MIDI" (el navegador pide permiso una vez) también vale pegarle a un pad, tocar una tecla o pisar un pedal de un aparato MIDI conectado al asignar un atajo: queda como "MIDI nota 36" o "MIDI control 64". Anda en Chrome y Edge; Firefox pide instalar un permiso aparte, y Safari no tiene MIDI.

#### La interfaz y la terminal

Todo lo que hace la interfaz se puede hacer también desde la terminal; casi siempre es el mismo comando que la interfaz usa por detrás:

| En la interfaz | En la terminal |
|---|---|
| Biblioteca | `song-wizard list` (`list TEXTO` filtra, `--files` muestra los stems y versiones de cada tema) |
| Bajar (y "en Música" para elegir la carpeta) | `song-wizard download URL` (`--wav`, `--to CARPETA`) |
| "buscar temas nuevos" | `song-wizard archives --update N` (o `all`) |
| Playlists bajadas: mover, olvidar, agregar carpeta | `song-wizard archives` (`--move N CARPETA`, `--delete N`, `--add CARPETA`) |
| "abrir" | `song-wizard open` (la carpeta de música, o la que digas) |
| Tonalidad, Tempo | `song-wizard key`, `song-wizard bpm` |
| Tocar la tonalidad o el tempo para corregirlos | `song-wizard key --set Am TEMA`, `song-wizard bpm --set 120 TEMA` |
| Separar instrumentos | `song-wizard separate --stem ...` |
| Cambiar el tono, Cambiar la velocidad | `song-wizard transpose`, `song-wizard speed` |
| Convertir para compartir | `song-wizard convert` |
| Pista de click | `song-wizard click` (`--for TEMA` le pone el nombre del tema) |
| Ajustar el click (detectar, tempo, primer golpe) | `song-wizard align` (`--bpm`, `--first`, `--meter`) |
| "más › Datos del tema…", y "datos" en un stem o una versión | `song-wizard tag TEMA` (`--set CAMPO=VALOR`, `--unset CAMPO`, `--only`) |
| Corregir el artista o el título en "Datos del tema…" | `song-wizard tag`, o `song-wizard rename` para ponerle cualquier nombre |
| "más › Recortar…" | `song-wizard trim TEMA --start T --end T` (`--pad-start S`, `--pad-end S`) |
| Borrar archivos seleccionados | `song-wizard delete` |
| Reportar un problema | `song-wizard report` |
| "apagar" | `song-wizard ui --stop` (`--restart` la cierra y la vuelve a abrir) |
| La versión, arriba, y "actualizar a …" | `song-wizard upgrade` (`--check` solo dice si hay una nueva; `--list` (`--all` incluye las retiradas) y `--to VERSIÓN`, solo en la terminal) |
| "guardar el orden en la carpeta" (setlist de una carpeta) | `song-wizard order CARPETA TEMA TEMA...` |
| "setlist" de una carpeta, o "setlist con lo elegido" | `song-wizard setlist CARPETA`, o `song-wizard setlist TEMA TEMA...` (`--lyrics`, `--out ARCHIVO.html`) |
| "más › Letra": buscar, escribir o pegar, imprimir | `song-wizard lyrics TEMA` (`--from ARCHIVO`, `--export`); los colores y las notas se marcan en el navegador |
| "más › Crear proyecto de Reaper", "Abrir en Reaper", "Rehacer" | `song-wizard reaper TEMA` (`--redo`, `--no-open`) |
| Apartado Reaper: la preferencia de las tomas, restaurarla | `song-wizard reaper --setting show` (`restore`, `apply`) |
| Acordes: "más › Detectar los acordes", "Acordes" en Analizar (los temas elegidos), "detectar" en Practicar | `song-wizard chords TEMA` (`--force`); corregirlos se hace en el navegador |
| Notas: "detectar notas" al lado del nombre de la pista, "detectar" en la fila de acordes (acordes y notas), "más › Detectar las notas" | `song-wizard notes TEMA` (`--part`, `--force`); corregirlas se hace en el navegador |
| Practicar | Es un reproductor, así que vive en el navegador: `song-wizard ui --practice TEMA` lo abre directo en ese tema |

### Bajar temas

```bash
song-wizard download "https://.../playlist?list=..."   # una playlist
song-wizard download "https://.../watch?v=..."         # un tema suelto
```

- Las playlists se guardan en `Música/<nombre de la playlist>/001 - Artista - Título.opus`, numeradas en orden, con el artista y el título que trae el tema. En los videos que no son de un sello o de YouTube Music, el "artista" suele ser quien subió el video y el título trae agregados como "(HQ)": se ve así de entrada para corregirlo en [Datos del tema](#datos-del-tema). Los temas sueltos van a `Música/Singles/`. En WSL, "Música" es la carpeta Música de Windows.
- Si volvés a correr la misma playlist, solo baja los temas nuevos, numerados según su lugar en la playlist (y con `.wav` si la primera vez usaste `--wav`, en la interfaz). En la interfaz es el botón "buscar temas nuevos" de la carpeta de la playlist. Los temas que se sacaron de la playlist no se borran de tu carpeta.
- `--wav` además genera un `.wav` de cada tema (misma calidad, ocupa 10 veces más).
- Para playlists privadas: agregá `--cookies-from-browser chrome` (o `firefox`, `safari`) al final.
- Para guardar una playlist nueva en otra carpeta (por ejemplo, una que se sincroniza con la nube): `--to "G:\Mi unidad\Ensayos"` (en WSL sirven las rutas de Windows). Adentro se crea la carpeta de la playlist.
- En WSL, la unidad de Google Drive para Windows (por ejemplo `H:`) aparece después de que arranca WSL y no se conecta sola: si song-wizard dice que no ve la unidad, conectala con `sudo mkdir -p /mnt/h && sudo mount -t drvfs H: /mnt/h` (cambiando `h` por su letra). Hay que repetirlo cada vez que se reinicia WSL; para que se conecte sola, agregá la línea `H: /mnt/h drvfs defaults,nofail 0 0` a `/etc/fstab` (con `nofail`, si Drive todavía no arrancó, WSL sigue igual).
- Una playlist que ya bajaste sigue bajándose en su carpeta, esté donde esté, aunque la hayas movido con `archives --move` (ver abajo).
- Los temas nuevos de una playlist que ya tenés se numeran después del último de su carpeta (no por su lugar en la playlist del sitio), así no chocan con un orden tuyo ni con temas que agregaste a mano (ver [Temas agregados a mano y el orden de la carpeta](#temas-agregados-a-mano-y-el-orden-de-la-carpeta)).
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

#### Playlists en otra compu

Cada playlist guarda su registro (de dónde salió y qué temas ya se bajaron) en su propia carpeta, en un archivo oculto `.song-wizard.json`. Así la carpeta lo lleva consigo: copiala a otra compu, o tenela en una carpeta sincronizada como Google Drive, y ahí la playlist aparece en "Playlists bajadas" con "buscar temas nuevos" andando, bajando solo lo que todavía no está en la carpeta. Si otra compu baja temas en la misma carpeta sincronizada, esta también se entera.

- Dentro de la carpeta de música (o donde ya van tus descargas), se toma sola al abrir la biblioteca.
- En cualquier otro lado: `song-wizard archives --add "G:\Mi unidad\Ensayos"` (o "agregar carpeta…" en la interfaz). Puede ser la carpeta de la playlist o la que tiene varias; desde entonces sus temas se ven en la biblioteca.
- Las playlists bajadas antes de la 0.28.0 reciben su registro la primera vez que se abre la biblioteca con la 0.28.0 o más nueva en la compu que las bajó.

#### Temas agregados a mano y el orden de la carpeta

Un tema que ya tenés como archivo (te lo pasaron por WhatsApp, de un CD, una grabación del ensayo) se usa donde está: ponelo en la carpeta de la playlist y, al abrir la biblioteca, toma el número siguiente al último, se nombra por sus datos ("004 - Artista - Título"; sin datos, conserva su nombre) y recibe su `.wav` si la playlist los usa. Desde ahí es un tema más. Los que se bajen después siguen desde ese número. Un archivo que cambió hace menos de 30 segundos (se está copiando) espera a la próxima vez. Fuera de las playlists (Singles, carpetas tuyas) no se renumera nada solo.

Para cambiar el orden de la carpeta: en su ventana de "setlist", ordená los temas y tocá "guardar el orden en la carpeta"; o `song-wizard order "Música/Show" "004 - Artista - Título.mp3" "001 - Otro.opus"` (los temas que no nombrás van después, en el orden que tenían). Los stems, versiones, resultados, letra y proyecto de Reaper de cada tema van con él. "Buscar temas nuevos" no se ve afectado: el registro conoce cada tema por su video, no por su nombre ni su número.

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

### Acordes

```bash
song-wizard chords "tema.opus"
song-wizard chords "Música/Show"        # todos los temas de la carpeta
song-wizard chords --force "tema.opus"  # volver a detectar también lo corregido a mano
```

Detecta los acordes del tema y los guarda al lado, como `<tema>.chords.json`, que el reproductor de práctica muestra y deja corregir (ver [Practicar](#practicar)). Los cambios se ubican sobre los tiempos del tema, según su click (`click.txt`, ver [Tempo y primer golpe para el click](#tempo-y-primer-golpe-para-el-click)); un tema sin click lo recibe primero. Los acordes corregidos a mano se mantienen, salvo con `--force`. Renombrar, recortar y borrar el tema llevan sus acordes con él.

Es una guía para corregir de oído, no una transcripción: en temas de rock y pop, en nuestras pruebas, acertó la nota base del acorde cerca del 95 % de las veces (comparando con lo que toca el bajo), y mayor o menor casi siempre. También nombra acordes más ricos (7, maj7, m7, sus...) cuando los escucha; "simplificar" en el reproductor los oculta.

La detección es [BTC](https://github.com/jayg996/BTC-ISMIR19) (un modelo entrenado para reconocer acordes, de un trabajo de investigación de 2019). Su código está copiado dentro de song-wizard (`third_party/btc`, con su licencia MIT), no instalado como una librería que se actualiza sola. Su modelo (12 MB) se baja la primera vez de una dirección fija y se usa solo si su huella digital (SHA-256) coincide, y se abre solo como números, así que un archivo alterado no puede ejecutar nada.

### Notas

```bash
song-wizard notes "tema.opus"                 # las del bajo y las de la voz
song-wizard notes --part vocals "tema.opus"   # solo una
song-wizard notes --force "tema.opus"         # volver a detectar también lo corregido a mano
```

Sigue las notas del bajo y de la voz separados (separalos antes con `song-wizard separate --stem bass` / `--stem vocals`) y las guarda al lado del tema, como `<tema>.notes.json`, que el reproductor de práctica muestra, hace sonar y deja corregir (ver [Practicar](#practicar)). Renombrar, recortar y borrar el tema las llevan con él.

Las del bajo salen sólidas. Las de la voz andan bien con una voz clara y al frente; una voz rasposa o coros cantando encima la confunden: sigue una sola línea a la vez. El bajo se sigue con pYIN (de librosa), y la voz con [CREPE](https://github.com/maxrmorrison/torchcrepe), un modelo hecho para seguir la altura de una voz, copiado dentro de song-wizard (`third_party/crepe`, con su licencia MIT) como el modelo de acordes; su modelo (89 MB) se baja la primera vez de una dirección fija, se usa solo si su SHA-256 coincide y se abre solo como números.

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
song-wizard separate --stem piano  "tema.opus"    # piano
song-wizard separate --stem drumkit "tema.opus"   # la batería en partes
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

- Cada instrumento se separa con el modelo que mejor lo hace: Mel-Band Roformer para la voz, Demucs `htdemucs_ft` para batería y bajo, y BS-Roformer SW (de 6 instrumentos) para la guitarra y el piano, que salen juntos de una sola pasada si se piden los dos.
- Instrumento + resto suman **exactamente** el tema original, y todo queda alineado.
- **El piano** es para temas con piano de verdad (acústico o eléctrico): los sintetizadores quedan en el resto, y en algunos temas se lleva otra cosa (por ejemplo, vientos). Por eso no entra en "Todos": se pide aparte (`--stem all --stem piano` da los dos).
- La primera vez descarga los modelos: unos 2 GB para los cuatro instrumentos (el de voz pesa 870 MB y el de guitarra y piano, 670 MB; el piano no suma nada), y 420 MB más para la batería en partes.
- La guitarra es la separación menos precisa: puede mezclarse algo de teclados o de otras guitarras. Hasta la 0.11 se separaba con Demucs `htdemucs_6s`, que además tomaba vientos y piano; los temas separados antes conservan esa guitarra hasta que se vuelva a separar.
- **La batería en partes** (`--stem drumkit`, o "Batería en partes" en la interfaz) separa la batería en bombo, redoblante, toms, hi-hat, ride y crash, con MDX23C DrumSep: `Título (kick).wav`, `(snare)`, `(toms)`, `(hihat)`, `(ride)`, `(crash)`, más `(drums rest)`, lo que queda de la batería, para que todo sume la batería exacta. Trabaja sobre la batería ya separada, así que si el tema no la tiene, la separa primero. En "practicar" aparece como "Batería en partes": cada pieza con su volumen, junto con los otros instrumentos (o con el tema sin batería). El modelo pesa 438 MB y tarda alrededor de un minuto por tema.
- Se probaron también un modelo abierto de vientos (UVR `17_HP-Wind_Inst`) y el piano en temas sin piano: separan, pero no tan bien como el resto, así que por ahora no están.

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

### Datos del tema

```bash
song-wizard tag "001 - Banda - Tema.opus"                                  # muestra todos sus datos
song-wizard tag "001 - Banda - Tema.opus" --set "artist=Banda" --set "album=En vivo" --unset genre
song-wizard tag "001 - Banda - Tema (80%).mp3" --set "comment=la del show" --only
```

Los datos son los que guarda el archivo y muestran los reproductores (el celular, WhatsApp, Reaper): título, artista, álbum, año, género y cualquier otro, con el nombre que quieras. Se cambian en el tema y en todo lo que se generó a partir de él (el `.wav` o `.mp3`, los stems, las versiones), todos o ninguno; las tomas grabadas en Reaper quedan como están. El audio no se toca. Con `--only`, cambia solo ese archivo: por ejemplo, una nota sobre una versión.

Si cambia el artista o el título, el tema y todo lo suyo pasan a llamarse `001 - Artista - Título` (como `rename`, con la letra, el proyecto de Reaper y los resultados). Los caracteres que Windows no acepta en un nombre de archivo se reemplazan por otros parecidos (`:` por `：`); en los datos quedan como los escribiste.

En la interfaz, "más › Datos del tema…" (o `E`) muestra todo lo que tiene el archivo, también lo que trajo la descarga (la descripción del video, la fecha en que se subió), sin filtrar nada. Los cambiados se marcan, × saca un dato y "agregar un dato" suma uno conocido (compositor, comentario, número de pista…) u otro con el nombre que quieras. Abajo avisa si el tema va a cambiar de nombre. "guardar y seguir" (Ctrl+Enter) pasa al tema siguiente. En un stem o una versión, "datos" cambia solo ese archivo.

- Un dato con nombre propio, en un `.opus` (o `.ogg`, `.flac`), no puede llevar tildes ni eñes en el nombre (el valor sí): `Ano` en vez de `Año`.
- Lo que song-wizard genera después (stems, versiones con otro tono o velocidad, el click del tema, los MP3) sale con los datos del tema, así que un archivo suelto (en un pendrive, en WhatsApp) sigue diciendo de dónde viene.
- Cada archivo que song-wizard baja, genera, convierte o recorta lleva su marca en `encoded_by` ("Hecho con"): `song-wizard 0.23.0`, la versión que lo hizo. Guardar los datos no la cambia (un archivo que no tenía, la recibe); no se edita.
- El link de la descarga (`purl`) se muestra pero no se cambia: `delete` lo usa para saber de qué descarga vino el tema.
- En los `.wav`, los datos van en la lista propia del WAV (título, artista, álbum, año, género, comentario) y todos, también los propios, en una parte ID3 adentro del archivo, que leen ffmpeg y la mayoría de los reproductores. El Explorador de Windows no muestra datos de ningún WAV (los `.opus` sí).
- El setlist, la búsqueda de la letra y la biblioteca toman el título y el artista de los datos; un tema sin datos, del nombre del archivo.

### Renombrar un tema

```bash
song-wizard rename "001 - Tema (Official Video).opus" "Tema"
```

Cambia el nombre del tema y de todo lo que se generó a partir de él: el `.wav` o el `.mp3`, los stems, las versiones transpuestas o con otra velocidad, las tomas grabadas en Reaper, la letra, el proyecto de Reaper (y los nombres de archivo que tiene adentro, para que siga abriendo), y sus líneas en `key.txt` y `bpm.txt`. Queda `001 - Tema.opus`, `001 - Tema (drums).wav`, etc. Se puede pasar cualquier archivo del tema, no solo el original.

La numeración (`001 - `) se mantiene, salvo que el nombre nuevo traiga la suya (`"005 - Tema"`). Si alguno de los nombres nuevos ya existe, no renombra nada. Tampoco acepta los caracteres que Windows no permite en nombres de archivo (`\ / : * ? " < > |`).

Bajar de nuevo la playlist no vuelve a bajar el tema renombrado: el registro de descargas guarda qué link se bajó, no el nombre del archivo.

En la interfaz no hay "renombrar": el nombre sigue al artista y al título, que se corrigen en [Datos del tema](#datos-del-tema). `rename` queda en la terminal para ponerle a un tema cualquier otro nombre.

### Recortar un tema

```bash
song-wizard trim "001 - Tema.opus" --start 0:12.5 --end 3:58   # se queda con 0:12.5 a 3:58
song-wizard trim "001 - Tema.opus" --start 8                    # corta los primeros 8 segundos
song-wizard trim "001 - Tema.opus" --pad-start 2 --pad-end 1    # agrega 2 s de silencio adelante y 1 s atrás
```

Corta el principio o el final del tema (la intro o los créditos de un video), o le agrega silencio adelante o atrás. Los tiempos van en segundos (`12.5`) o en minutos y segundos (`0:12.5`); el silencio, en segundos, con decimales.

Se hace sobre el tema y todo lo generado a partir de él a la vez, para que sigan alineados: sus otros formatos, los stems, las versiones transpuestas y los clicks, con el mismo corte; y las versiones a otra velocidad, con el corte en proporción (a 80 %, 10 s del tema son 12.5 s). El primer golpe del click de práctica y los tiempos de la letra se corren lo mismo, así que "practicar" sigue sincronizado. Las tomas grabadas en Reaper quedan como están, porque van alineadas al proyecto de Reaper; ese proyecto queda corrido, así que conviene rehacerlo (`reaper --redo`).

El corte es exacto a la muestra, para que el tema y sus stems sigan alineados; los archivos comprimidos (como el `.opus`) se vuelven a codificar a una calidad alta, porque cortarlos sin hacerlo redondea a unos 20 ms. Primero escribe todos los archivos nuevos y solo si salen todos bien reemplaza los de antes, que van a la papelera. Pregunta antes, salvo con `--yes`.

En la interfaz, "más › Recortar…" muestra la forma de onda del tema con dos manijas para arrastrar, y lo que queda marcado. La rueda del mouse acerca y aleja (con Shift se mueve a los costados), y debajo hay una barra con el tema entero, donde lo que queda está marcado y un recuadro muestra el tramo que se ve arriba: se arrastra para moverse, un clic salta a otra parte y la rueda sobre la barra mueve a los costados. "ver el inicio" y "ver el fin" acercan alrededor de cada manija, y "▶ desde acá" y "▶ hasta acá" escuchan 5 segundos desde el inicio elegido o hasta el fin, para ajustar de oído. También se pueden escribir los tiempos exactos y el silencio.

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

### Letras

```bash
song-wizard lyrics "Música/Show"          # busca la letra de cada tema
song-wizard lyrics --from letra.txt "tema.opus"   # o la toma de un archivo
song-wizard lyrics --export "tema.opus"   # la guarda lista para imprimir
```

Busca la letra de cada tema en una base de letras abierta, por su artista y título (de [sus datos](#datos-del-tema), o si no tiene, del nombre del archivo "Artista - Tema") y su duración, y la guarda al lado del tema como `Tema.lyrics.json`. Si no la encuentra, se escribe o se pega a mano. Va con el tema: `rename` la renombra y `delete` la borra con él.

En la interfaz, el botón "letra" de cada tema (dice "letra ✓" si ya la tiene) la muestra para trabajarla:

- **Marcadores**: como un resaltador de PDF. Elegís un color (o las teclas 1 a 5, que se pueden cambiar en [Atajos de teclado](#atajos-de-teclado)) y el cursor pasa a ser un marcador de ese color: arrastrás sobre la letra y queda pintada al soltar, o hacés clic en una palabra. Toma palabras enteras. Al lado de cada color escribís qué significa (por ejemplo, quién canta cada parte, o los coros), y eso aparece como leyenda.
- **Goma** (G): arrastrando saca el color, y con un clic borra toda la marca que tocás.
- **Nota** (N): clic en una línea para escribirle un comentario ("entra la batería", "corte", "repetir 2 veces"). Tocando la nota se cambia, y si la dejás vacía se borra.
- Esc suelta la herramienta y Ctrl+Z (o "deshacer") vuelve atrás.
- **Escribir o pegar**: para corregir la letra o cargarla a mano. Las líneas que no cambies conservan sus colores y notas.
- **Imprimir**: abre la letra con sus colores, notas y leyenda en otra pestaña, para imprimirla o guardarla como PDF; si es larga, va en dos columnas. `lyrics --export` guarda la misma hoja como `Tema.lyrics.html`.

Todo se guarda solo. Buscar la letra de nuevo la reemplaza y se pierden los colores y las notas (la leyenda queda), por eso pregunta antes.

### Reaper

```bash
song-wizard reaper "001 - Tema.opus"          # lo abre en Reaper, y si no existe lo crea antes
song-wizard reaper --redo "001 - Tema.opus"   # arma uno nuevo (el anterior va a la papelera)
song-wizard reaper --setting show             # qué cambió song-wizard en Reaper (restore lo vuelve atrás)
```

Abre el proyecto de Reaper del tema, `Tema.rpp`, que queda al lado del tema. Si no existe, primero lo arma con lo que haya en ese momento:

- **Una pista por stem**, con el nombre del instrumento: los mismos con los que arranca el reproductor de práctica (todos los instrumentos, o el instrumento separado y el resto). Los demás stems y el tema original quedan como pistas silenciadas, para cambiar de una a otra. Si el tema no está separado, va el tema solo. Todas a 0 dB.
- **El tempo y el compás** del click ajustado en "practicar" (o `align`), con decimales, y el audio corrido para que el primer golpe del tema caiga justo en un compás, con un compás de cuenta antes. Si el click no está ajustado, usa el tempo de `bpm.txt` sin alinear (o 120 BPM si no hay), y lo avisa. Si no cae exacto, se corrige en Reaper.
- **Pista "Click"** con el click de Reaper, que sigue el tempo del proyecto: si corregís el tempo en Reaper, el click lo sigue.
- **Pista "Grabación"** lista para grabar (con Ctrl+R) desde las entradas 1 y 2, con el monitoreo (escuchar lo que entra) apagado; se prende en la pista si lo querés.
- Los archivos van con su nombre, sin copiarlos: el proyecto sigue andando si movés la carpeta, también en Drive.

Un proyecto que ya existe nunca se pisa, porque puede tener cambios hechos en Reaper. `--redo` (o "más › Rehacer proyecto de Reaper") manda el anterior a la papelera y arma uno nuevo, por ejemplo después de separar más instrumentos. Si Reaper no está instalado, el proyecto se crea igual, pero no se abre ("Abrir en Reaper" queda deshabilitado).

**Las tomas.** Para que lo que grabes en Reaper aparezca con su tema en la biblioteca, las tomas tienen que llamarse `Tema (record 2026-11-01 19-05-12).wav`. Eso es una preferencia de Reaper que vale para todos tus proyectos (Options › Preferences › Recording › "Recorded filenames"), así que song-wizard la cambia la primera vez que creás o abrís un proyecto, con Reaper cerrado (Reaper guarda sus preferencias al cerrarse y pisaría el cambio). Te avisa cuando lo hace, con el valor de antes y el nuevo, y guarda una copia de las preferencias de Reaper como `reaper.ini.before-song-wizard`.

En la interfaz, el apartado **Reaper** (debajo de Trabajos) muestra siempre qué cambió, cuándo y cómo era antes, con un botón para restaurarlo. En la terminal: `song-wizard reaper --setting show`, y `--setting restore` para volver atrás. Restaurar vuelve solo esa preferencia a como estaba, sin tocar nada más de Reaper, y song-wizard no la vuelve a cambiar hasta que se lo pidas (`--setting apply`, o "volver a ajustarlo"). A mano: en esa preferencia de Reaper, poné el valor de antes.

Las tomas siguen al tema: `rename` las renombra y `delete` las borra con él, igual que el proyecto.

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

La lista de la carpeta en el orden de sus archivos (`001 - …`), con la tonalidad, el tempo y la duración de cada tema, y el total. Guarda `Setlist.txt` y `Setlist.html` en la carpeta; el `.html` se abre en el navegador y se imprime en una hoja A4, con la letra lo más grande que entre.

**Con temas de cualquier carpeta**, en el orden que quieras: nombrá los temas en vez de la carpeta.

```bash
song-wizard setlist "Música/Show/003 - Tema.opus" "Música/Otra/001 - Otro tema.opus" --title "Show del sábado" --out show.html
```

Muestra la lista en ese orden y no guarda nada en las carpetas (las carpetas siguen atadas a sus playlists); `--out` guarda la hoja donde digas. Un stem o una versión cuenta como su tema.

**En la interfaz**, el botón "setlist" de cada carpeta abre la lista de sus temas; para armar una con temas sueltos, elegilos con sus casillas (en el orden en que los vas eligiendo) y tocá "setlist con lo elegido", abajo. En los dos casos se abre una ventana donde cambiás el título, ordenás los temas arrastrándolos (o con ↑ ↓), sacás los que no van con ×, y "abrir para imprimir" abre la hoja en otra pestaña. Desde la interfaz no se guarda nada: para tenerla en un archivo, imprimila como PDF. Abierta desde una carpeta, "guardar el orden en la carpeta" renumera sus archivos en el orden de la lista (ver [Temas agregados a mano y el orden de la carpeta](#temas-agregados-a-mano-y-el-orden-de-la-carpeta)).

- `--lyrics` (o "con las letras" en la ventana) suma, después de la lista, la letra de cada tema que la tenga, con sus colores y notas, una por página y con su número del setlist. Los temas sin letra se saltean.
- La tonalidad y el tempo salen de lo que ya detectaste con `key` y `bpm` (o pusiste a mano); los que falten quedan en blanco. Un `?` marca una tonalidad dudosa.
- El título y el artista salen de los [datos del tema](#datos-del-tema) (si no tiene, del nombre del archivo, "Artista - Tema"), sin agregados como "(Official Video)" o "[HD]". El artista va más chico al lado. Si algo quedó mal, se corrige en los datos del tema.
- `--title` cambia el título de arriba (por defecto, el nombre de la playlist o de la carpeta; con temas sueltos, "Setlist").
- Con una carpeta, `--out` guarda la hoja ahí en vez de en la carpeta.

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
- **No apto para uso comercial.** Aunque el código de song-wizard es libre (ver [Licencia](#licencia)), algunas piezas que usa no lo permiten o no tienen una licencia clara: [diffq](https://github.com/facebookresearch/diffq) (una dependencia de audio-separator) tiene licencia CC BY-NC 4.0, que prohíbe el uso comercial; y los modelos de separación (Demucs, el Mel-Band Roformer de voz, el BS-Roformer SW de guitarra y piano, y el MDX23C DrumSep de la batería en partes) no indican la licencia de sus pesos entrenados; en el caso del BS-Roformer SW, su propia página la marca como desconocida. song-wizard no incluye ningún modelo: los baja la primera vez que se usan, de los repositorios públicos donde los publicaron sus autores o el proyecto UVR. Cualquier uso comercial requiere revisar esas licencias por separado.
- **Sin afiliación.** song-wizard no está afiliado ni respaldado por ninguna plataforma de audio o video ni por los proyectos que usa. Todas las marcas pertenecen a sus dueños.
- **Sin garantías.** Se ofrece tal cual, sin garantía de ningún tipo, como establece su licencia.

## Licencia

El código de song-wizard se distribuye bajo la [GNU Affero General Public License v3.0 o posterior](LICENSE) (AGPL-3.0-or-later): podés usarlo, estudiarlo, modificarlo y compartirlo, siempre que lo que compartas mantenga la misma licencia y su código fuente. Es la licencia que corresponde porque song-wizard usa [Essentia](https://essentia.upf.edu), que se distribuye bajo AGPL-3.0.

## Créditos

song-wizard es una capa fina sobre el trabajo de otros proyectos libres:

- [Ultimate Vocal Remover (UVR)](https://github.com/Anjok07/ultimatevocalremovergui), de Anjok07 y aufr33, y su colección de modelos de separación.
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator), que permite usar los modelos de UVR desde Python.
- [Demucs](https://github.com/facebookresearch/demucs), de Meta: el modelo `htdemucs_ft`, para batería y bajo.
- [Mel-Band Roformer Vocal Model](https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model), de KimberleyJensen, para la voz, entrenado con el código de [ZFTurbo](https://github.com/ZFTurbo/Music-Source-Separation-Training).
- BS-Roformer SW, de jarredou: el modelo de 6 instrumentos que da la guitarra y el piano.
- MDX23C DrumSep, de aufr33 y jarredou (con la arquitectura MDX23C, de ZFTurbo): la batería en partes.
- [Essentia](https://essentia.upf.edu), del Music Technology Group de la Universitat Pompeu Fabra: tonalidad, tempo y pulsos.
- [BTC](https://github.com/jayg996/BTC-ISMIR19), de Jonggwon Park, Kyoyun Choi, Sungwook Jeon, Dokyun Kim y Jonghun Park (ISMIR 2019): los acordes. Su código está en `src/song_wizard/third_party/btc`, con su licencia MIT.
- [CREPE](https://github.com/marl/crepe), de Jong Wook Kim, Justin Salamon, Peter Li y Juan Pablo Bello (ICASSP 2018), en su versión para PyTorch [torchcrepe](https://github.com/maxrmorrison/torchcrepe), de Max Morrison: las notas de la voz. Su código está en `src/song_wizard/third_party/crepe`, con su licencia MIT.
- [librosa](https://librosa.org): los datos de audio de los acordes, y pYIN para las notas del bajo.
- [LRCLIB](https://lrclib.net): base de letras abierta y comunitaria.
- [Rubber Band](https://breakfastquay.com/rubberband/), de Breakfast Quay: cambio de tono y de velocidad.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): descargas.
- [ffmpeg](https://ffmpeg.org): lectura y conversión de audio.
- [mutagen](https://github.com/quodlibet/mutagen): escribir los datos de un tema en sus archivos.
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
- `key.txt` y `bpm.txt` (también la tonalidad y el tempo puestos a mano, en inglés o en español, que volver a analizar no pisa), la configuración, la carpeta de música y los registros de `archives` (también el que cada playlist guarda en su carpeta: lo toma otra compu, se actualiza al bajar y al borrar, se quita al olvidarla, una copia no se adueña, y uno dañado o raro se ignora).
- `lyrics`: elige la versión de duración más cercana, letra con tiempos, sin internet o sin resultados, pegar desde un archivo (conserva las marcas si el texto no cambió), validación de lo que guarda la página, la hoja para imprimir (con nombres como texto, nunca HTML), y que siga al tema al renombrarlo y borrarlo (la base de letras no se consulta en las pruebas).
- `separate`: la batería en partes en la terminal, qué instrumentos entran en "Todos" (el piano no, salvo que se pida), y que guitarra y piano usen el mismo modelo (una sola pasada).
- `chords`: los nombres de BTC escritos como en una hoja de acordes (Am7, C#m7b5, N.C.), los cambios ubicados sobre los tiempos del click (los parpadeos de menos de medio tiempo se descartan), lo corregido a mano se mantiene al volver a detectar, cualquier nombre se guarda con sus comillas escapadas (y lo que no tiene la forma esperada se rechaza), los acordes siguen al renombrar y al recortar, la página los lee y los guarda, y el modelo se usa solo si su SHA-256 coincide (y no se vuelve a bajar). Detectar con el modelo real necesita bajarlo (12 MB): `uv run pytest -m network` comprueba que un I-IV-V-I sintético en G da G, C y D.
- `notes`: una línea de bajo sintética seguida con pYIN da sus notas exactas a tiempo (±50 ms), y la misma nota cortada por un hueco mínimo queda unida; lo corregido a mano se mantiene al volver a detectar (y no con `--force`); un tema sin stems lo avisa; lo que no tiene la forma esperada se rechaza; las notas siguen al recortar y al renombrar; la página las lee, las guarda y pide una sola parte. Con el modelo de voz (`-m network`): una melodía cantada sintética con vibrato da sus notas a menos de 40 ms.
- `trim`: el mismo corte en el tema y sus stems, exacto a la muestra (un pulso a los 3 s queda donde tiene que quedar), el `.opus` vuelto a codificar alineado con los stems (menos de medio milisegundo), las versiones a otra velocidad en proporción, el silencio agregado, las tomas de Reaper sin tocar, los WAV de 32 bits float que siguen siendo float, el link de la descarga que se conserva, el click y la letra que se corren, y que si un archivo falla no cambie nada.
- `reaper`: qué pistas entran (todos los stems, un instrumento con el resto o el tema solo, y el resto silenciado), el primer golpe en la raya de un compás con tempos con decimales, nombres con comillas, que un proyecto existente no se pise (y `--redo`), la preferencia de las tomas (con Reaper abierto no la toca; restaurarla vuelve solo esa línea, sin tocar lo que cambió después, y song-wizard no la vuelve a cambiar), los fines de línea de Windows intactos, y que el proyecto, sus nombres de archivo adentro y las tomas sigan al tema al renombrarlo y borrarlo. Reaper no se abre ni se toca en las pruebas.
- `tag`: los datos leídos y escritos en `.opus`, `.wav` y `.mp3` (también con saltos de línea y nombres propios), en el tema y sus stems y versiones pero no en las tomas, el audio intacto, el renombrado al cambiar artista o título (con los caracteres que Windows no acepta), `--only`, el link de la descarga que no se borra, el nombre de lo que se baja, el filtro por palabras sin tildes, el archivo de configuración creado por cualquier comando, y la ventana de la interfaz.
- Numeración: un tema agregado a mano a la carpeta de una playlist toma el número siguiente, se nombra por sus datos y recibe su `.wav` si la playlist los usa (y no mientras se está copiando, ni fuera de las playlists); lo que se baja sigue después del último número, y una playlist nueva conserva el orden del sitio; `order` renumera una carpeta (también intercambiando números) con los archivos y resultados de cada tema, y rechaza temas de otro lado.
- `setlist`: orden, nombres limpios, tonalidad dudosa marcada, total, nombres con HTML mostrados como texto, y la hoja desde la interfaz (solo desde su propia página). Con temas sueltos: de varias carpetas en el orden pedido, un stem cuenta como su tema, no se guarda nada en las carpetas, un tema que no está da error, y rutas fuera de la carpeta de música rechazadas; las letras con sus marcas después de la lista, solo de los temas que la tienen.
- El tono en vivo del reproductor (corriendo el procesador con Node): afinación exacta, nada agregado y el mismo retardo para cada tono.
- Actualizar: las versiones retiradas (no se ofrecen ni se listan, `--to` pide `--force`, quien tiene una retirada es avisado y pasado a la más nueva que no lo esté, y si la lista no se puede leer no frena nada), comparar versiones, leer las versiones publicadas de los tags (y no fallar sin internet), `upgrade --list` y `--to`, que `upgrade` instale el tag más nuevo (o solo actualice lo que usa si ya está en el último, o reinstale desde la carpeta si se instaló así), `upgrade --check`, la consulta desde la interfaz (que se recuerda unas horas, salvo que se pida de nuevo), y que el reinicio pedido desde la página levante una interfaz nueva en el mismo puerto, sin abrir el navegador.
- Idiomas: los textos de la interfaz son claves con un archivo por idioma (`static/i18n/es.json`, `en.json`, `pt.json`); los tres tienen las mismas claves, toda clave que usan la página o el servidor está y no sobra ninguna, ningún idioma pide un valor que el español no tenga, y el servidor contesta en el idioma de la página.
- `ui`: la seguridad (solo atiende a su propia página: otra página, aunque sea de otro servidor en esta computadora, no puede actuar ni leer nada; el dominio; rutas fuera de la carpeta de música; acciones inválidas), que corra de fondo (arranca una vez, se reusa, se apaga con `--stop`, con su clave interna, o desde la página), la biblioteca agrupada por tema, la reproducción por partes y un trabajo de click de punta a punta.

`separate` no corre en las pruebas automáticas porque necesita bajar los modelos (1.3 GB); se puede probar a mano con `uv run pytest -m slow`, que verifica que instrumento + resto sumen el original. Para correr las pruebas en tu computadora, desde la carpeta del proyecto: `uv run pytest`.

### Pruebas a mano

El registro de lo que se probó a mano y cómo (con temas, programas y navegadores reales, o simulando casos como una placa de video vieja), para repetirlo cuando se toca esa parte, está en [CHECKLIST.md](CHECKLIST.md) (en inglés).
