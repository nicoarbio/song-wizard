# Pruebas a mano

Registro de lo que se probó a mano y cómo, además de las [pruebas automáticas](README.md#pruebas-automáticas) que corren en cada cambio: sirve para repetirlas cuando se toca esa parte. "Real" es con temas, programas o navegadores reales; "Simulada", forzando el caso (por ejemplo, una placa de video vieja) sin tenerlo.

## Equipo

Las pruebas reales se hicieron en:

- Windows con WSL2 (Ubuntu 24.04.5)
- AMD Ryzen 5 8500G (6 núcleos, 12 hilos), 11 GB de RAM disponibles en WSL
- NVIDIA GeForce RTX 4060 de 8 GB, driver 610.88
- Python 3.12.3, PyTorch 2.15.0 (CUDA 13.2), audio-separator 0.48.0, Essentia 2.1b6.dev1389, yt-dlp 2026.10.26, Rubber Band 3.3.0, ffmpeg 6.1.1

## Resultados

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
| `ui`: seguridad | Real (Edge, con un script) | ✅ Sin la clave en el link, la página carga, reproduce y actúa; un link viejo con `?t=` sigue andando y la clave desaparece de la barra de direcciones. Una página servida desde otro puerto de la misma computadora no puede leer la biblioteca (el navegador lo bloquea) ni apagar la interfaz, ni con un pedido ni con un formulario (403). Con otro dominio, 403; rutas fuera de la carpeta de música y acciones que no existen, rechazadas |
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
| `report`: abrir el formulario en el navegador desde la terminal | Real (por el usuario) | ✅ En WSL se abre con `cmd.exe start` escapando los `&`; el navegador abre el formulario con el link entero |
| `ui`: "reportar un problema" | Real | ✅ Muestra el reporte entero antes de mandarlo, con el link a GitHub y el botón para mostrar el archivo |
| `ui`: practicar con 5 pistas de 5:41 (Edge, sin sonido) | Real | ✅ Las pistas no se separan más de 3 ms al arrancar, al saltar al minuto 2 y al 75 % (el tiempo avanza a 0.749, tono preservado); el tramo A-B se repite sin pasarse de B; silencio y solo dan los volúmenes correctos; detecta "Todos", un instrumento con su resto, o el tema solo |
| `ui`: practicar con sonido | Real (por el usuario, con stems reales) | ✅ Los stems suenan juntos, a la velocidad y con el loop elegidos |
| "buscar temas nuevos" de una playlist | Real (sobre una copia, sin tocar la carpeta real) | ✅ Con el registro de una playlist de 18 temas que tenía 10, bajó solo los 8 que faltaban, numerados 011 a 018; guarda la carpeta en el registro; los registros anteriores se reconocen por el nombre de la carpeta |
| Click con el nombre del tema (`--like`, `--for` y desde la interfaz con un tema elegido) | Real | ✅ `001 - Tema (80%) (click 96 BPM 4-4).wav` queda al lado del tema y la biblioteca lo agrupa con sus archivos; `-o` sigue eligiendo dónde |
| `align` sobre baterías sintéticas (90 a 137 BPM, con y sin silencio al principio) | Real | ✅ Tempo a ±0.02 BPM y primer golpe a ±1 ms; a 160 BPM da 80 (la mitad), que se corrige con ÷2/×2 o `--bpm` |
| `align` sobre un tema real de 4:33 | Real | ✅ 103.06 BPM (`bpm` dice 103.1) y el primer golpe donde arranca el sonido en la forma de onda |
| Click del reproductor contra el tema (Edge, sin sonido, grabando lo que sale) | Real | ✅ ~1 ms a 100 %, después de saltar y a 125 %; la cuenta de un compás, a 3 ms de su lugar, con la música entrando en su tiempo, también al retomar desde una pausa; al 75 %, −3 ms en promedio (±15 ms del tema estirado) |
| Click del reproductor con sonido | Real (por el usuario) | ✅ Se escucha bien, sobre el tema |
| Forma de onda | Real | ✅ Un tema de 4:33 tarda ~2 s la primera vez (después queda guardada); el principio ampliado, 0.1 s |
| `delete` de un tema en una carpeta de `C:` | Real | ✅ El tema, su stem y su versión llegan a la Papelera de Windows (nombres con `ñ` y `⧸` incluidos); el otro tema queda; `key.txt` pierde su línea; el tema sale del registro de la playlist por el link que guarda el archivo |
| `delete`: un stem solo, una copia con `--file`, sin confirmar, papelera que falla | Simulada | ✅ Solo ese archivo; sin `--yes` y sin terminal no borra; si la papelera falla no toca nada más |
| `ui`: "borrar archivos seleccionados" | Real | ✅ La ventana lista exactamente qué se va (un tema con todos sus archivos, un stem solo) y arranca con "cancelar" elegido |
| `archives --move` con una ruta de Windows, de una carpeta de Linux a `C:` | Real | ✅ La playlist va entera (tema, stem y `key.txt`); un registro anterior, sin carpeta guardada, se encuentra por nombre; volver a moverla al mismo lugar avisa que ya está ahí |
| `download --to` y playlists ya bajadas que siguen en su carpeta | Simulada (sin descargar) | ✅ Las nuevas van a la carpeta pedida; las conocidas, a la suya; un `%` en la ruta no rompe la plantilla de yt-dlp |
| `ui`: playlist fuera de la carpeta de música | Real | ✅ Aparece en la biblioteca con su ubicación (en formato Windows en WSL), se escucha y se procesa; rutas para salir de su carpeta, rechazadas |
| `ui`: "elegir…" (selector de carpetas del sistema) | Real (por el usuario, en Windows) | ✅ Abre el selector de carpetas de Windows y la carpeta elegida queda como destino |
| `list`, `archives` (con la columna de carpeta) sobre la biblioteca real | Real (solo lectura) | ✅ Cada tema con su tonalidad, tempo y cantidad de archivos; `--files` los lista; las playlists dicen dónde están (Música y Drive) |
| `archives --update`, `open` | Simulada | ✅ Busca temas nuevos en las playlists elegidas (o `all`) con su `--wav`; los temas sueltos no tienen playlist y lo avisa; `open` abre la carpeta del archivo dado |
| Tonalidad y tempo a mano (`--set`, y tocando el badge en la interfaz) | Real (datos de prueba) | ✅ En Edge: tocar el tempo, escribir 100 y Enter lo guarda en `bpm.txt` marcado a mano y lo muestra con ✍; los temas sin analizar muestran "tono?" / "BPM?" al pasar el mouse; volver a correr `key`/`bpm` lo mantiene y `--force` lo reemplaza |
| `ui` de fondo: arrancar, reusar y apagar | Real (datos de prueba) | ✅ La terminal queda libre al instante; el servidor sigue después de cerrar la terminal que lo abrió; otro `ui` reusa el mismo; `--stop` lo cierra (pregunta si hay un trabajo corriendo); "apagar" en Edge lo cierra y la página avisa que está apagada; el archivo con la clave queda legible solo por el usuario. Probado por el usuario: después de cerrar todas las ventanas de Ubuntu, la interfaz sigue respondiendo |
| Tono en vivo en el reproductor (de -6 a +6 semitonos) | Real (audio sintético) | ✅ Tonos puros de 98 y 440 Hz llegan a la frecuencia pedida con un error menor a 3 cents; lo demás queda por debajo de -73 dB y el nivel se mantiene. El retardo es el mismo para todos los tonos (±1.5 ms). En Edge, grabando dentro del navegador, la música y el click quedan a 1 ms (tono 0), 4 ms (-3) y 2 ms (+3). Probado por el usuario con temas reales: suena bien |
| `lyrics` contra la base de letras real (con archivos de prueba con nombre y duración de un tema conocido, y uno inventado) | Real | ✅ Encuentra la del tema conocido con la duración más cercana (275 s contra 276 s) y con tiempos; la del inventado no aparece y lo dice; si la base no responde (503) reintenta una vez y sigue con el resto |
| Letra en la interfaz: marcadores, goma, nota, deshacer, leyenda e imprimir | Real (Edge, con un script) | ✅ Arrastrar a mitad de palabra toma la palabra entera (sin espacios en los bordes); dos líneas de una vez; clic en una palabra la pinta; clic con la goma borra esa marca; Ctrl+Z deshace; la nota y la leyenda se guardan; la hoja para imprimir muestra todo con sus colores |
| Tiempos de la letra (columna, tecla T, corrimiento, deshacer, doble clic) | Real (Edge, con un script, letra pegada sin tiempos) | ✅ Con T en 10, 14 y 20 s quedan marcadas las líneas 1, 2 y 4 (salteando la vacía) y se guardan; +0.5 s las corre y deshacer las vuelve; doble clic en una línea lleva el tema a medio segundo antes de su tiempo; la línea que suena se resalta |
| Letra en el reproductor de práctica | Real (Edge, con un script) | ✅ Aparece debajo del click con sus marcas y se puede marcar ahí; con la letra con tiempos, a los 75 s queda resaltada la línea que suena en ese momento |
| `reaper`: Reaper abre el proyecto armado | Real (Reaper 7.84, tema sintético con golpes a 123.4 BPM y el primero a 0.737 s) | ✅ Reaper lo carga y lo exporta a audio desde la terminal (`reaper.exe -renderproject`). En el audio exportado, el primer golpe del tema cae en la raya del compás 2 y el click de Reaper cae sobre los 40 golpes del tema, todos con la misma diferencia (2.8 ms, la de los filtros de la medición): sin deriva con un tempo con decimales |
| `reaper`: los formatos de audio | Real (Reaper 7.84, un tono de 2 s en cada formato) | ✅ Exportado con Reaper, suenan .wav, .aiff, .flac, .mp3, .opus, .ogg, .m4a, .webm, .aac, .mp4 y .mkv. La 0.9.0 sin publicar ponía el .opus original como si fuera .wav y quedaba en silencio; lo encontró el usuario y quedó corregido |
| `reaper`: la preferencia de las tomas | Real (Reaper de esta PC) | ✅ Con Reaper cerrado se agrega la línea en `reaper.ini` (el resto del archivo queda igual, con sus fines de línea de Windows) y se guarda la copia; Reaper la mantiene después de abrirse y cerrarse. Grabada una toma en Reaper (por el usuario), aparece con su tema en la biblioteca |
| `trim` desde la terminal (tema `.opus` con su link de descarga, un stem float, una versión al 80 %, una toma de Reaper, click y letra) | Real (audio sintético) | ✅ Cortando 2 s adelante, hasta 8.5 s, con 1 s de silencio antes y 0.5 s después: el tema y el stem quedan en 8.00 s y la versión al 80 % en 10.00 s; la toma no se toca; el link de la descarga sigue en el `.opus` y el stem sigue siendo float; el primer golpe del click, que quedaba cortado, pasa al golpe siguiente; la letra se corre 1 s |
| Recortar en la interfaz | Real (Edge, con un script, tema sintético de 30 s) | ✅ "más › Recortar…" abre la onda con las dos manijas; arrastrar la del inicio la mueve; la rueda acerca (con la onda de ese tramo en detalle); los tiempos y el silencio escritos a mano se aplican; "▶ desde acá" reproduce desde el inicio elegido; "recortar" deja los tres archivos en 24.05 s, lo esperado |
| Recortar: barra para moverse con zoom | Real (Edge, con un script) | ✅ Muestra el tema entero con lo que queda marcado y un recuadro en el tramo visible; arrastrar el recuadro mueve la vista (de 3 a 13 s, la vista pasa de 1–5 s a 11–15 s); un clic en otra parte centra la vista ahí; la rueda sobre la barra la mueve a los costados |
| Biblioteca con una carpeta de descargas que no está (la unidad de Google Drive sin conectar en WSL) | Real (esta PC, con los temas sueltos en `H:` sin montar; y en Edge, con una unidad de prueba) | ✅ Antes sus temas desaparecían sin aviso; ahora la carpeta aparece como "no disponible", con su ruta de Windows y "cómo conectarla" con el comando para copiar; `list` dice lo mismo. Si la carpeta se movió, lo dice sin comando |
| Confirmaciones propias (apagar, rehacer el proyecto de Reaper, buscar la letra de nuevo, olvidar una playlist) | Real (Edge, con un script) | ✅ Salen en un cartel con el diseño de la interfaz en vez del del navegador; cancelar y Esc no hacen nada; en lo que no se deshace, el botón es rojo y el foco arranca en "cancelar"; encima del diálogo de la letra se superpone y al cancelar la letra sigue abierta |
| Menú "más", apartado Reaper y aviso del cambio | Real (Edge, con un script) | ✅ "más" abre la letra, renombrar y el proyecto de Reaper (crear, o abrir y rehacer si ya existe); Esc o un clic afuera lo cierran; sin Reaper instalado, "Abrir en Reaper" queda deshabilitado y dice por qué; el apartado Reaper y el aviso muestran la preferencia, el valor de antes, el nuevo, el archivo y la copia |
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
| Mac con chip M | Real (pruebas automáticas, macOS 15) | ✅ Se instala y pasan todas las pruebas automáticas |
| Linux sin WSL | Real (pruebas automáticas, Ubuntu) | ✅ Se instala y pasan todas las pruebas automáticas |
