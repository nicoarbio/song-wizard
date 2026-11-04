# song-wizard

<p align="center"><img src="img/logo.png" width="160" alt="song-wizard"></p>

[![CI](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml/badge.svg)](https://github.com/nicoarbio/song-wizard/actions/workflows/ci.yml)

**English** · [Español](README.es.md)

A terminal tool to get songs ready for rehearsing with your band. It's a personal project, made as a hobby and not for profit.

- **download**: downloads the audio of a link (a song or a playlist) in the best quality available, without re-encoding.
- **key**: detects the key.
- **bpm**: detects the tempo and tells you if it drifts along the song.
- **click**: makes a steady click track, with the tempo, meter and length you want.
- **transpose**: raises or lowers the pitch without changing the tempo.
- **speed**: makes a song slower (or faster) without changing the pitch, to learn it bit by bit.
- **separate**: splits your instrument from the rest of the song (vocals, drums, bass or guitar).
- **convert**: converts to MP3 (or M4A) to share, over WhatsApp for example.
- **tag**: shows or changes a song's data (title, artist, album, year, genre…), in the song and everything made from it.
- **rename**: renames a song and everything made from it.
- **delete**: sends a song (with everything made from it) or single files to the trash.
- **list**: shows the songs in your music folder (and wherever you downloaded to), with what was detected for each.
- **report**: if something fails, puts together a report to ask for help.
- **ui**: all of the above from a page in the browser, without the terminal.

Everything but `download` works with any audio file you have: rehearsal recordings, songs you bought, your own demos, and so on.

It runs on **Macs with an M chip** (M1 to M5, with macOS 15 or newer), **Linux** and **Windows with WSL**. It doesn't run on Intel Macs.

## Requirements

song-wizard is written in Python, but it uses a few outside programs that are installed separately. The commands in [Installation](#installation) install them all; this is what each one is for. They're all free and open source, installed from their official sources.

| Program | Why it's needed | How song-wizard uses it |
|---|---|---|
| [**uv**](https://docs.astral.sh/uv/) | Installs song-wizard and its Python libraries in an isolated environment, without touching the system's Python. If needed, it also gets Python 3.12. | `uv tool install` makes the `song-wizard` command available, and `song-wizard upgrade` updates it. |
| [**ffmpeg**](https://ffmpeg.org) | Reads and converts any audio format (Opus, MP3, M4A, WAV…). | Decodes songs before detecting the key, transposing or separating. In `download`, yt-dlp uses it to extract the audio (and to make the `.wav` files with `--wav`). |
| [**deno**](https://deno.com) | Some sites require solving a JavaScript challenge before letting you download, and deno is the program that runs that JavaScript. Node v20 or newer works too. | yt-dlp, the download engine, finds it and uses it only in `download`. |
| [**rubberband**](https://breakfastquay.com/rubberband/) | Changes the pitch without changing the tempo, or the tempo without changing the pitch, with very good quality. | `transpose` gives it the semitones and makes `Title (+2).wav`; `speed` gives it the speed and makes `Title (80%).wav`. |

On Linux and WSL, `curl` is also installed (to get the official uv and deno installers), and `build-essential` + `python3-dev`, to compile a Python library that doesn't come precompiled. On a Mac they're not needed, because Homebrew already installs the compiler.

The Python libraries that do the heavy lifting are installed by uv automatically: [yt-dlp](https://github.com/yt-dlp/yt-dlp) for downloads, [Essentia](https://essentia.upf.edu) for the key, and [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) and [PyTorch](https://pytorch.org) to separate instruments.

Everything is processed on your computer: song-wizard doesn't send your files to any server. It only goes online to download the songs you ask for, to download the separation models the first time, and to update itself.

`song-wizard setup` checks that they're all installed.

## Installation

### Mac

1. If you don't have Homebrew, install it following the instructions at [brew.sh](https://brew.sh).
2. Open the Terminal and run:

   ```bash
   brew install ffmpeg deno rubberband uv
   uv tool install --exclude-newer "7 days" \
     --exclude-newer-package "yt-dlp=2 days" --exclude-newer-package "yt-dlp-ejs=2 days" \
     git+https://github.com/nicoarbio/song-wizard
   ```

### Linux or WSL (Ubuntu)

On Windows, if you don't have WSL: open PowerShell as administrator, run `wsl --install`, restart and open "Ubuntu" from the Start menu. Then, in that terminal:

```bash
sudo apt update && sudo apt install -y ffmpeg rubberband-cli curl build-essential python3-dev
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://deno.land/install.sh | sh
```

Close and open the terminal again, and then:

```bash
uv tool install --exclude-newer "7 days" \
  --exclude-newer-package "yt-dlp=2 days" --exclude-newer-package "yt-dlp-ejs=2 days" \
  git+https://github.com/nicoarbio/song-wizard
```

### Check that everything works

```bash
song-wizard setup
```

Everything should be green. It also tells you whether separation will use the graphics card (much faster) or only the processor.

### Settings

```bash
song-wizard config
```

Shows where the settings file is and which values are in use. The file is created on its own, with everything commented out, the first time you run any command. For now it holds the download folder. Whatever you pass to a command always wins over the file.

- Linux/WSL: `~/.config/song-wizard/config.toml`
- Mac: `~/Library/Application Support/song-wizard/config.toml`

```toml
[download]
music_dir = "~/Rehearsals"
```

### Upgrading

```bash
song-wizard upgrade              # installs the newest version
song-wizard upgrade --check      # only tells you if there's a new version
song-wizard upgrade --list       # the published versions
song-wizard upgrade --to 0.12.0  # installs another version, newer or older
```

Every published version is a `vX.Y.Z` tag on GitHub. `upgrade` installs the newest one if you have an older one; if you already have the newest, it updates what song-wizard uses (yt-dlp, mostly). A version with a serious problem can be **retired**: it's listed in `retired.txt` (in this repository) with the reason, and then `upgrade` and the interface don't offer it, `--list` doesn't show it (`--list --all` does, with the reason), `--to` doesn't install it unless with `--force`, and whoever has it is told so and `upgrade` moves them to the newest one that isn't retired, even if it's older. The tag isn't deleted.

**A week's wait, for safety.** Installing and `upgrade` take only versions of the libraries song-wizard uses that were published at least 7 days ago (2 for yt-dlp, which sites break often): if one came out with malicious code (it has happened to popular libraries, through a stolen account), it's usually found and pulled within hours or days, before it reaches you. song-wizard itself comes from its tag in this repository. On GitHub, each change to the dependencies and every Monday they're checked against the lists of known vulnerabilities and malicious packages. If `uv` doesn't understand `"7 days"`, it's old: `uv self update` (or `brew upgrade uv`).

Versions before 0.15 don't know how to move between tags: if you go back to one with `--to`, to return to the newest run `uv tool install --force git+https://github.com/nicoarbio/song-wizard`.

In the interface, the version shows at the top, next to the name (click it to check again). If there's a new one, "update to …" shows up: it updates, restarts the interface, and the same page reloads on its own when it's ready. It checks for new versions at most every 6 hours.

It's worth doing often: sites change a lot, and downloads can stop working until you update.

### What's stored on your computer

| What | Where | Size |
|---|---|---|
| song-wizard and its libraries | `~/.local/share/uv/tools/song-wizard` | ~6 GB on Linux/WSL (it includes NVIDIA's libraries to use the graphics card); much less on a Mac |
| Separation models | Linux/WSL: `~/.local/share/song-wizard/models`<br>Mac: `~/Library/Application Support/song-wizard/models` | ~2 GB if you use all four instruments (piano comes from the same model as the guitar), and 0.4 GB more for the drum kit; each is downloaded the first time it's used |
| Chord model | Linux/WSL: `~/.local/share/song-wizard/models`<br>Mac: `~/Library/Application Support/song-wizard/models` | 12 MB, downloaded the first time chords are detected |
| Record of songs already downloaded | Linux/WSL: `~/.local/share/song-wizard/archives`<br>Mac: `~/Library/Application Support/song-wizard/archives` | a few KB |
| Log (which commands ran and the errors, to solve problems) | Linux/WSL: `~/.local/share/song-wizard/logs`<br>Mac: `~/Library/Application Support/song-wizard/logs` | 2 MB at most: the oldest is deleted on its own |
| Reports from `song-wizard report` | Linux/WSL: `~/.local/share/song-wizard/reports`<br>Mac: `~/Library/Application Support/song-wizard/reports` | a few KB each; they can be deleted |
| What song-wizard changed in REAPER (to show it and put it back) | Linux/WSL: `~/.local/share/song-wizard/reaper.json`<br>Mac: `~/Library/Application Support/song-wizard/reaper.json` | under 1 KB |
| A copy of REAPER's preferences from before changing them | Next to REAPER's: `reaper.ini.before-song-wizard` (on Windows, in `%APPDATA%\REAPER`) | as big as REAPER's |
| Your songs | The Music folder (or the one you choose) | whatever you download |

The models are downloaded from public sources: Demucs's from the servers of Meta (who made it), and the others from the public GitHub repositories of the [UVR](https://github.com/Anjok07/ultimatevocalremovergui) project and of audio-separator.

### Uninstalling

```bash
song-wizard uninstall
```

It first shows what it removes and how much each thing takes (the separation models, the record of downloaded playlists, the logs, the settings and song-wizard itself, with its own Python and everything it uses), and asks. If song-wizard changed REAPER's preference for takes (see [REAPER](#reaper)), it offers to put it back as it was. `--keep-data` removes only the program and keeps the rest, to install it again later.

Your songs aren't touched. Nor are ffmpeg, deno, rubberband or uv, which other programs may use: if you don't use them for anything else, uninstall them yourself with `brew uninstall` (Mac) or `sudo apt remove` (Linux). uv keeps a download cache shared with everything you install with it; `uv cache clean` empties it (nothing breaks: it's downloaded again if needed).

## Usage

### Browser interface

```bash
song-wizard ui
```

Opens a page in the browser (on WSL, the Windows browser) with everything song-wizard does, without typing commands:

- **Library**: the folders in your music folder with their songs, each one's key and tempo if you already detected them, and the files made from each song (stems, versions transposed or at another speed, MP3s), each with its checkbox to use it in the actions (with Shift, the checkbox picks or drops everything between the last one you clicked and this one). Each song's files start folded ("▸ 5 files") so the list doesn't get long; "expand all" and "collapse all" open and close them at once, and the browser remembers which ones you left open. ▶ plays any of them. Each song shows its file name without the extension ("001 - Artist - Title"; the full name on hover), and next to it, in gray, its album, year and genre if it has them. "more" opens the song's other actions: its data, lyrics, trimming and the REAPER project (the dot on "more" means the song already has lyrics or a project). "more › Song data…" shows and changes the title, artist, album and everything the file keeps, and correcting the artist or title renames it (see [Song data](#song-data)). The filter at the top looks for loose words, in any order and regardless of accents and case, in each song's name, folder and data: "rock ultimo" finds the rock songs of the album "Último show". Clicking the key or tempo corrects by hand what was detected (see [Fixing the key or tempo by hand](#fixing-the-key-or-tempo-by-hand)). "more › Lyrics" shows the song's lyrics to mark them with colors and notes (see [Lyrics](#lyrics)), and "more › Create REAPER project" or "Open in REAPER" takes it to REAPER (see [REAPER](#reaper)). "setlist" makes the folder's list to print, and "setlist of the picked songs" (below, next to the selection) makes it with the songs you picked, from any folder (see [Setlist](#setlist)). "open" shows the folder in the File Explorer (or the Finder on a Mac). If you change files outside (copy, rename or delete them), the library updates on its own when you come back to the page, or with "↻ refresh".
- **Practice**: each song's "practice" button opens, in the whole window, a player with each track's waveform and the lyrics on the side, with a track per separated instrument (with volume, mute and solo for each), a click that follows the song with a count-in, the speed live without changing the pitch (from 50 % to 150 %), the pitch live without changing the speed (6 semitones each way) looping a section between two marks, A and B, and a monitor to hear a mic (the room, the band) in your headphones, and the song's chords bar by bar, to correct by hand. See [Practice](#practice).
- **Download**: paste the link of a song or a playlist at the very top. "in Music" picks another folder for new playlists (typing the path or with "choose…", which opens the system's folder picker).
- **Delete**: "delete selected files", next to the selection, shows exactly which files go and sends them to the system's trash. See [Deleting](#deleting).
- **Click track**: with a song picked, its tempo (if you already detected it), its length and the bars that cover it are filled in; for one more bar, add 1.
- **Actions** on the picked songs, or on a single file (to change the speed of just the separated drums, say, or measure the tempo on them): key, tempo, separate instruments, transpose, change the speed, convert and make a click.
- **Bottom player**: any file's ▶ plays it there, with its waveform; clicking the picture jumps to that part.
- **Jobs**: what's running, with a progress bar and the time it's taken; it can be cancelled. They run one at a time.
- **Keyboard shortcuts**: almost everything can be done with the keyboard, and the keys can be changed. "⌨ shortcuts" at the top (or `?`) shows them all. See [Keyboard shortcuts](#keyboard-shortcuts).
- **Language**: "es · en · pt" at the top right switches the interface between Spanish, English and Portuguese (the first time, it takes the browser's language). The browser remembers it, and the pages to print (setlist, lyrics) and the server's messages follow it.
- **Colors**: at the top right, "auto" follows the system (light or dark, as you have it on Windows or the Mac), and "light" or "dark" keep it fixed. The browser remembers it. The pages to print (setlist, lyrics) are always light.
- **Downloaded playlists**: the same as `song-wizard archives`, with the option to check for new songs, move them to another folder (they go whole and still show in the library, with their location) or forget them. "add folder…" brings in a folder copied from another computer or kept in Drive (see [Playlists on another computer](#playlists-on-another-computer)). Folders that are a playlist also have "check for new songs": it downloads only what was added to the playlist since last time.

The interface keeps running in the background and the terminal is free for something else (or to close it). Typing `song-wizard ui` again opens the same interface, without starting another. To close it: "shut down" (below, in Jobs) or `song-wizard ui --stop`; if something is running, it asks first. `song-wizard ui --restart` closes it and opens it again (after `upgrade`, say, which tells you if the interface is still on the old version). With `--foreground` it stays in the terminal as before, and Ctrl+C closes it.

On WSL, Linux shuts down on its own a while after all its terminals are closed, and the interface with it: if you use it with every Ubuntu window closed and it stops responding, open it again with `song-wizard ui`.

It only works on your computer: the server doesn't take outside connections, and only serves its own page, so other pages open in the browser can't use it (the browser tells it where each request comes from). The link is always `http://127.0.0.1:8765` (or the port the terminal shows, if that one is taken), so it can be bookmarked. If the browser doesn't open on its own, open the link the terminal shows.

#### Practice

With "All" separated, the player has the five tracks (vocals, drums, bass, guitar and other); if you separated a single instrument, that instrument and the rest of the song (and if you separated several one by one, you pick which at the top); with no stems, the original song, which is still good for practicing slower or looping a section.

The player fills the whole window. The controls are at the top: play, speed, pitch, the A-B section and the master volume. Below, a row per track with its waveform, all on the same timeline, and on the right, the lyrics. "⛶ full screen" (or `F`) also hides the browser's bars; Esc goes back, and the player stays open.

- Each track has its row: the name, **M** to mute it, **S** to hear only that one (several can be soloed together), its volume and its waveform. A track that isn't sounding is dimmed. Above them all is the whole song's waveform. Clicking any waveform jumps to that moment, and the position and the A-B section show on all of them. **Master**, at the top, turns everything up or down together (the browser remembers it).
- **Zoom**: the mouse wheel on any waveform zooms all the tracks in and out together, around the mouse (with Shift it moves sideways); there are also − and +, "all" and "section", which zooms into the A-B section. Above the tracks there's a bar with the whole song and a box over what's in view: drag it to move, a click jumps elsewhere and the wheel on the bar moves sideways. Up close, each waveform is drawn in more detail. While playing, the view turns the page when the position reaches its edge (if you just moved it by hand, it waits a few seconds), and if you jump to another moment, it goes there.
- The click's row shows its beats (if they don't fit, only the bars), with the first of each bar marked.
- The speed changes while playing and the pitch doesn't change. To save a slower version as a file, there's [Changing the speed](#changing-the-speed).
- **Pitch**: raises or lowers the song up to 6 semitones without changing the speed, to try another key for the singer, say; if the song's key was detected, it shows where it ends up (Am → Gm). The click doesn't change and stays in time. Changing it brings a moment of silence. It's rehearsal quality: for a clean version as a file (to share, say), there's [Changing the key](#changing-the-key), which sounds better.
- To loop a section: **A** where it starts and **B** where it ends; marking B starts the loop. "loop" turns it on and off, and the section shows over the waveforms.
- **Lyrics**: the right column has the song's lyrics (on narrow screens, below the tracks). "lyrics ▸" (or `Y`) folds it so the waveforms get wider, and the browser remembers it. It comes with its colors and notes, and can be marked right there with the mouse. If the lyrics have times, the line being sung is highlighted and the lyrics scroll on their own (if you scrolled them with the wheel, it waits a few seconds before going on), and double-clicking a line jumps the song to that moment. If the song has no lyrics, they can be looked up from there.
- **Lyrics times**: "times" opens a column on the left with the moment each line starts. While the song plays, you click a line's time right when it starts being sung, or press T and the next line is marked: that way pasted lyrics get synced by listening to the song once. × clears a time, and −0.5 s / +0.5 s move them all together (if your version has a different intro than the lyrics database's, where the times come from when there are any). Ctrl+Z undoes this too.
- With the keyboard: Space plays and pauses, the arrows jump 5 seconds and with Shift one bar (by the click), `Home` goes back to the start (or to A), `[` and `]` mark A and B, `L` loops, `-` and `+` change the speed, `,` and `.` the pitch, `R` puts everything back to normal, `Z` and `X` zoom in and out, `F` goes full screen and `Y` shows or hides the lyrics. For the tracks: `↑` and `↓` pick one (it's marked), `M` mutes it, `S` solos it and Shift+`↑`/`↓` change its volume; also `1` to `9` and `0` (the tenth) mute a track directly, Shift+number solos it, and `C` turns the click on or off. `I` turns the monitor on or off. `D` shows how far apart the tracks are from each other (they should stay within a few milliseconds). Below the tracks is the short list; all of them, and how to change them, in [Keyboard shortcuts](#keyboard-shortcuts).

**The click.** The player's last track is a click that follows the song: it falls on every beat even if you jump anywhere, loop a section or change the speed, and since the browser makes it on the spot, it sounds crisp at low speeds too. To line up with the song it needs its exact tempo and where the first beat falls; they're set in "Adjust the click":

- "detect" finds them in the song (the same as `song-wizard align`, see below). If the tempo came out half or double the real one, ÷2 and ×2 fix it.
- The zoomed view shows the start of the song with the click's lines on top (the marked one is the first beat of each bar): dragging over the picture moves them until they fall on the hits. For fine-tuning, −10 ms and +10 ms; if the first beat landed on another beat of the bar, −1 beat and +1 beat. "listen to the start" plays it with the click to check by ear.
- It's saved on its own, in `click.txt` in the song's folder (like `key.txt` and `bpm.txt`), and `rename` renames it with the song.

**The count-in.** With the click on, pressing play from the start plays the count-in (one or two bars, or none) and the music comes in on time: if the song starts with silence, part of the count falls over that silence, so the music comes in exactly where it should. With "also when resuming", the count-in also plays when resuming from any point, to practice a part.

Measured in Edge: the click falls within ~1 ms of the song, also after jumping and at 125 %; the count-in and the music coming in, within 3 ms. Below 100 % the browser delays the song a bit while stretching it, and song-wizard makes up for it in Brave, Chrome and Edge (not yet in Firefox and Safari); at those speeds the stretched song still "wobbles" about ±15 ms from hit to hit, because of how the browser stretches it.

The tracks are streamed from the music folder as they play, without loading them whole into memory.

**The chords.** Below the song's waveform there's a row of chords, on the same timeline as the tracks: a block per chord, placed on the click's beats, with the one playing now lit. Next to the play button, in big letters, the chord playing now and the next one, to read while you play. "detect" finds them (see [Chords](#chords)); it needs the song's click adjusted first, since the chords go on its beats, so if the song has none it opens "Adjust the click".

- They follow the pitch: raise the song 2 semitones and Am reads Bm, to try the song in another key for the singer.
- "simplify" shows only major and minor (A7 → A, Am7 → Am), for whoever wants the easy version; the browser remembers it.
- To correct one, click it: change its name, split it at the beat you clicked, join it with the next one or delete it. What you correct is marked ✍ and detecting again doesn't overwrite it. A name song-wizard doesn't read as a chord ("riff", "see tab") is saved anyway, with a warning: it just isn't transposed or simplified.
- Zoom in with the wheel to read them: with the whole song in view, chords too short to fit show their name only when you hover over them.

**The monitor.** "🎤 monitor" opens a bar to hear a microphone (the room, the band) in your headphones, mixed with the tracks: to practice with in-ears on without taking one out. "turn on" asks the browser for the mic (the first time it asks for permission) and turns it on; it starts off and low every time. It has:

- **Input**: which mic. The browser remembers it; if it isn't plugged in, it uses the default one.
- **The level** reaching the mic (the monitor's volume doesn't change it). If it says "overloading", it will sound broken however low you set it: move the mic away or lower its level in Windows' sound settings (and turn off Windows' "audio enhancements", if the mic has them).
- **Volume**, apart from the master: the middle is the mic as it comes (0 dB), and it goes from silence to +12 dB. "mute" silences it without turning it off.
- **Low cut**: takes out what's below 120 Hz. The kick reaches you through your body anyway, and it's what most overloads a laptop mic. On by default.
- **Limiter**: it only holds back single peaks over −6 dB (a cymbal right next to the mic, a knock on the mic), to look after your ears; below that, the volume doesn't change at all. "limiting" lights up while it's holding a peak. It's on by default and can be turned off (it says so, and the browser remembers it). It adds about 6 ms of delay.
- **Delay**: the browser's estimate of how late the mic reaches your ears.

Heads-up, honestly: in the browser the mic arrives some tens of milliseconds late. With an acoustic drum kit you hear your hit directly and, a moment later, through the mic: it can sound doubled. It works best low, to hear the band and the room more than your own drums. It only works with the page open on the same PC (`localhost`): browsers don't allow the mic over the local network without https. Closing Practice turns it off.

#### Keyboard shortcuts

"⌨ shortcuts" (top right), `?` or "all shortcuts" in Practice open the list of every shortcut, grouped by where they work: the library, Practice and the lyrics window. While you're typing in a text field they do nothing.

- **In the library**: `↑` and `↓` go through the songs (the current one is marked; clicking a song makes it current too), and on that song `Enter` plays it, `P` opens it in Practice, `L` opens its lyrics, `.` its "more" menu, `E` its data, `X` adds it to the selection (or drops it), `→` and `←` show or hide its stems and versions. `/` goes to the filter. Space pauses or resumes the bottom player, and Shift+`←`/`→` move it 5 seconds.
- **In the song's data**: Enter saves, Esc closes without saving, and Ctrl+Enter ("save and next") saves and opens the data of the next song in the list, to correct a whole playlist in one go.
- **Changing a key**: in the list, click the key and press the new one. "+" adds another key for the same thing and × removes it. If the new key already does something else in the same place, it asks: changing a key swaps the two, and adding it takes it from the other action. Changed ones carry ✍ and "reset all" goes back to the factory keys. They're saved in the browser (like the colors). Buttons show their shortcut on hover, with the keys you have.
- **Pedals**: a page-turner pedal (the ones for sheet music, Bluetooth or USB) sends keys like any keyboard: assign it whatever you like, play and pause for example, to practice without taking your hands off the instrument.
- **MIDI**: with "use a MIDI device" (the browser asks for permission once), hitting a pad, playing a key or pressing a pedal on a connected MIDI device also works when assigning a shortcut: it shows as "MIDI note 36" or "MIDI control 64". It works in Chrome and Edge; Firefox asks to install a separate permission, and Safari has no MIDI.

#### The interface and the terminal

Everything the interface does can also be done from the terminal; it's almost always the same command the interface uses behind the scenes:

| In the interface | In the terminal |
|---|---|
| Library | `song-wizard list` (`list TEXT` filters, `--files` shows each song's stems and versions) |
| Download (and "in Music" to pick the folder) | `song-wizard download URL` (`--wav`, `--to FOLDER`) |
| "check for new songs" | `song-wizard archives --update N` (or `all`) |
| Downloaded playlists: move, forget, add folder | `song-wizard archives` (`--move N FOLDER`, `--delete N`, `--add FOLDER`) |
| "open" | `song-wizard open` (the music folder, or the one you name) |
| Key, Tempo | `song-wizard key`, `song-wizard bpm` |
| Clicking the key or tempo to correct them | `song-wizard key --set Am SONG`, `song-wizard bpm --set 120 SONG` |
| Separate instruments | `song-wizard separate --stem ...` |
| Change the key, Change the speed | `song-wizard transpose`, `song-wizard speed` |
| Convert to share | `song-wizard convert` |
| Click track | `song-wizard click` (`--for SONG` names it after the song) |
| Adjust the click (detect, tempo, first beat) | `song-wizard align` (`--bpm`, `--first`, `--meter`) |
| "more › Song data…", and "data" on a stem or version | `song-wizard tag SONG` (`--set FIELD=VALUE`, `--unset FIELD`, `--only`) |
| Correcting the artist or title in "Song data…" | `song-wizard tag`, or `song-wizard rename` to give it any name |
| "more › Trim…" | `song-wizard trim SONG --start T --end T` (`--pad-start S`, `--pad-end S`) |
| Delete selected files | `song-wizard delete` |
| Report a problem | `song-wizard report` |
| "shut down" | `song-wizard ui --stop` (`--restart` closes it and opens it again) |
| The version, at the top, and "update to …" | `song-wizard upgrade` (`--check` only tells you if there's a new one; `--list` (`--all` includes the retired ones) and `--to VERSION`, only in the terminal) |
| "save the order in the folder" (a folder's setlist) | `song-wizard order FOLDER SONG SONG...` |
| A folder's "setlist", or "setlist of the picked songs" | `song-wizard setlist FOLDER`, or `song-wizard setlist SONG SONG...` (`--lyrics`, `--out FILE.html`) |
| "more › Lyrics": find, write or paste, print | `song-wizard lyrics SONG` (`--from FILE`, `--export`); colors and notes are marked in the browser |
| "more › Create REAPER project", "Open in REAPER", "Redo" | `song-wizard reaper SONG` (`--redo`, `--no-open`) |
| REAPER box: the takes preference, putting it back | `song-wizard reaper --setting show` (`restore`, `apply`) |
| Chords in Practice: "detect" | `song-wizard chords SONG` (`--force`); correcting them is done in the browser |
| Practice | It's a player, so it lives in the browser: `song-wizard ui --practice SONG` opens it straight on that song |

### Downloading songs

```bash
song-wizard download "https://.../playlist?list=..."   # a playlist
song-wizard download "https://.../watch?v=..."         # a single song
```

- Playlists are saved in `Music/<playlist name>/001 - Artist - Title.opus`, numbered in order, with the artist and title the song comes with. For videos that aren't from a label or YouTube Music, the "artist" is often whoever uploaded the video and the title carries extras like "(HQ)": it shows that way from the start so you can correct it in [Song data](#song-data). Single songs go to `Music/Singles/`. On WSL, "Music" is the Windows Music folder.
- If you run the same playlist again, it only downloads the new songs, numbered by their place in the playlist (and with `.wav` if you used `--wav` the first time, in the interface). In the interface it's the "check for new songs" button on the playlist's folder. Songs taken off the playlist aren't deleted from your folder.
- `--wav` also makes a `.wav` of each song (same quality, 10 times the size).
- For private playlists: add `--cookies-from-browser chrome` (or `firefox`, `safari`) at the end.
- To save a new playlist in another folder (one synced to the cloud, say): `--to "G:\My Drive\Rehearsals"` (on WSL, Windows paths work). The playlist's folder is created inside.
- On WSL, the Google Drive for Windows drive (`H:`, say) shows up after WSL starts and doesn't connect on its own: if song-wizard says it doesn't see the drive, connect it with `sudo mkdir -p /mnt/h && sudo mount -t drvfs H: /mnt/h` (changing `h` for its letter). It has to be repeated every time WSL restarts; to have it connect on its own, add the line `H: /mnt/h drvfs defaults,nofail 0 0` to `/etc/fstab` (with `nofail`, if Drive hasn't started yet, WSL goes on all the same).
- A playlist you already downloaded keeps downloading into its folder, wherever it is, even if you moved it with `archives --move` (see below).
- New songs of a playlist you already have are numbered after the last one in its folder (not by their place in the site's playlist), so they don't clash with an order of your own or with songs you added by hand (see [Songs added by hand and the folder's order](#songs-added-by-hand-and-the-folders-order)).
- To change the music folder for everything: `music_dir` in `song-wizard config`, or `SONG_WIZARD_DIR=~/Rehearsals`.
- To download again songs that are already in the record: add `--no-download-archive` at the end. If the files are still in the folder, also add `--force-overwrites`, or they're skipped anyway.

To see which playlists you downloaded and how many songs each has:

```bash
song-wizard archives
```

```
   #  Playlist                 Songs  Last download
   1  December rehearsal          11  2026-10-31 18:44
   2  Singles (single links)       1  2026-10-31 18:44
```

To take a playlist to another folder without losing anything (songs, stems, results and its record): `song-wizard archives --move 1 "G:\My Drive\Rehearsals"`. It ends up in `G:\My Drive\Rehearsals\<playlist name>`, the interface keeps showing it and new songs are downloaded there. If you already moved it by hand, the same command just notes where it is now.

#### Playlists on another computer

Each playlist keeps its record (where it came from and which songs were already downloaded) in its own folder, in a hidden file `.song-wizard.json`. So the folder carries it: copy it to another computer, or keep it in a synced folder like Google Drive, and there the playlist shows up in "Downloaded playlists" with "check for new songs" working, downloading only what isn't in the folder yet. If another computer downloads songs into the same synced folder, this one knows it too.

- Inside the music folder (or where your downloads already go), it's picked up on its own when the library opens.
- Anywhere else: `song-wizard archives --add "G:\My Drive\Rehearsals"` (or "add folder…" in the interface). It can be the playlist's folder or the one that holds several; its songs show in the library from then on.
- Playlists downloaded before 0.28.0 get their record the first time the library opens with 0.28.0 or newer on the computer that downloaded them.

#### Songs added by hand and the folder's order

A song you already have as a file (sent over WhatsApp, from a CD, a rehearsal recording) is used where it is: put it in the playlist's folder and, when the library opens, it takes the number after the last one, is named by its data ("004 - Artist - Title"; without data, it keeps its name) and gets its `.wav` if the playlist keeps them. From then on it's one more song. Songs downloaded afterwards go on from that number. A file that changed less than 30 seconds ago (still copying in) waits for the next time. Outside playlists (Singles, folders of your own) nothing is renumbered on its own.

To change the folder's order: in its "setlist" window, put the songs in order and click "save the order in the folder"; or `song-wizard order "Music/Show" "004 - Artist - Title.mp3" "001 - Other.opus"` (the songs not given go after, in the order they had). Each song's stems, versions, results, lyrics and REAPER project go with it. "Check for new songs" isn't affected: the record knows each song by its video, not by its name or number.

To forget a playlist, so it's downloaded whole again next time: `song-wizard archives --delete 1` (or several numbers, or `all` for all of them). It asks for confirmation and never deletes the songs already downloaded.

### Detecting the key

```bash
song-wizard key "Music/Show"          # every song in the folder
song-wizard key "song.opus"
```

```
  A    A major   relative F#m   4/4  01 - Song one.opus
  Em   E minor   relative G     2/4  02 - Song two.opus  uncertain, also: G
```

The results are also kept in `key.txt`, in the songs' folder; if you later analyze a single song, only its line is updated. In a folder only the original songs are analyzed, not the stems or the versions made from them.

`4/4` means the four detection methods agree. With fewer, it's worth confirming by ear: the most common mix-up is a key with its relative (Em and G use the same notes), which is why it's always shown. It detects the main key; if the song modulates, it doesn't say.

### Detecting the tempo

```bash
song-wizard bpm "Music/Show"
song-wizard bpm "song.opus"
```

```
   103.1 BPM  01 - Song one.opus  steady
   123.1 BPM  02 - Song two.opus  varies 121-125, probably played without a click
   178.2 BPM  03 - Song three.opus  uncertain, check by ear (could be 89.1)
```

The results are also kept in `bpm.txt`, in the songs' folder, as with `key`.

- `steady`: the tempo stays fixed, as when recorded with a click.
- `varies`: the tempo changes along the song (many songs from the 80s and 90s were recorded without a click). The range it moves in is shown; a steady click will drift away from it.
- `uncertain`: the detection isn't reliable. Most often the detector gives double or half the real tempo, which is why the alternative is suggested.

### Fixing the key or tempo by hand

If the detection got it wrong (or you already know the song), you type it in and it's used instead of what was detected. In the interface, by clicking the song's key or tempo (if it wasn't analyzed yet, "key?" and "BPM?" show on hover); in the terminal:

```bash
song-wizard key --set Am "song.opus"
song-wizard key --set "Sib mayor" "song.opus"   # Spanish works too: La menor, Fa#m, Do
song-wizard bpm --set 98.5 "song.opus"
```

It's marked "set by hand" in `key.txt` / `bpm.txt` (✍ in the interface), and analyzing the folder again doesn't overwrite it. To detect it again from the audio: `--force`, or "detect" in the interface. If the song has its practice click set to another tempo, it tells you so you can fix it in [Practice](#practice).

### Click track

Makes a steady click, with the first beat of each bar accented:

```bash
song-wizard click 120                            # 120 BPM, 4/4, 1 minute
song-wizard click 96 --meter 3/4 --bars 32       # 32 bars of 3/4
song-wizard click 123 --duration 4:30            # four and a half minutes
song-wizard click 105.6 --like "song.opus"       # as long as a song, and named after it
song-wizard click 92 --bars 8 --for "song.opus"  # named after the song, but 8 bars long
song-wizard click 90 --subdivide 2               # with eighth notes
```

- It makes `Click 120 BPM 4-4.wav` in the folder you run it from; `-o` picks another file or folder.
- With `--like` or `--for`, the click carries the song's name and sits next to it: `song (click 105.6 BPM 4-4).wav`. That way the interface shows it with the song's files, and `rename` renames it along with the rest. The interface does the same when a single song (or a file of one song) is picked.
- It takes tempos with decimals, so you can use the exact number `song-wizard bpm` gives.
- The length is rounded up to whole bars. Without `--duration`, `--bars` or `--like`, it lasts a minute.
- `--subdivide` adds softer clicks between beats: `2` = eighth notes, `3` = triplets, `4` = sixteenth notes.
- The meter: the top number is how many clicks per bar (`4/4` = 4, `3/4` = 3, `6/8` = 6).
- It's a steady-tempo click: it's for rehearsing without the recording or at another tempo. If the original song was recorded without a click (`bpm` says `varies`), a steady click will drift away from the recording.
- To send it over WhatsApp: `song-wizard convert "Click 120 BPM 4-4.wav"`.

### Tempo and first beat for the click

```bash
song-wizard align "song.opus"                              # detects them
song-wizard align --bpm 103.06 --first 1.554 "song.opus"   # by hand
song-wizard align "Music/Show"                             # every song in the folder
```

Finds the exact tempo (with decimals) and where the first beat falls, and saves them in `click.txt`, which the practice player's click uses to follow the song. `--meter` changes the meter (4/4 if not given). Like any tempo detector, it can give half or double the real one: fix it with `--bpm` or with ÷2 and ×2 in the interface. If the song's tempo varies (recorded without a click), it says so: a steady click will drift away.

### Chords

```bash
song-wizard chords "song.opus"
song-wizard chords "Music/Show"         # every song in the folder
song-wizard chords --force "song.opus"  # detect again also what was corrected by hand
```

Detects the song's chords and saves them next to it as `<song>.chords.json`, which the practice player shows and lets you correct (see [Practice](#practice)). The changes are moved onto the song's beats, from its click (`click.txt`, see [Tempo and first beat for the click](#tempo-and-first-beat-for-the-click)); a song without one gets it first. Chords corrected by hand are kept, unless `--force`. Renaming, trimming and deleting the song take its chords along.

It's a guide to correct by ear, not a transcription: on rock and pop songs, in our tests, it got the chord's root right about 95 % of the time (checked against what the bass plays), and major or minor almost always. It names richer chords too (7, maj7, m7, sus...) when it hears them; "simplify" in the player hides them.

The detection is [BTC](https://github.com/jayg996/BTC-ISMIR19) (a model trained to recognize chords, from a 2019 research paper). Its code is copied into song-wizard (`third_party/btc`, with its MIT license), not installed as a library that updates on its own. Its model (12 MB) is downloaded the first time from a fixed address and used only if its fingerprint (SHA-256) matches, and it's opened as numbers only, so a tampered file can't run anything.

### Changing the key

```bash
song-wizard transpose +2 "song.opus"      # a whole step up
song-wizard transpose -1 "song.opus"      # a half step down
song-wizard transpose -1 "Music/Show"     # every song in the folder
```

The number is in semitones: `+1` = a half step, `+2` = a whole step. It takes decimals (`-0.5`) in case a song is out of tune with A 440. It makes `Title (+2).wav` next to the original without touching it. The tempo and length don't change, so it stays lined up with the click.

### Changing the speed

```bash
song-wizard speed 80 "song.opus"                   # at 80 %: slower, same pitch
song-wizard speed 70 "song (no guitar).wav"        # the song without your instrument, slower
song-wizard speed 90 --semitones -2 "song.opus"    # slower and a whole step down, in one go
```

The number is the percentage of the original speed, from 25 to 200: under 100 is slower, over 100 faster. The pitch doesn't change, unless you add `--semitones` (as in `transpose`). It makes `Title (80%).wav` (or `Title (90%, -2).wav`) next to the original without touching it.

It's for learning a song bit by bit: practice it at 70 %, then at 85 % and finally at full speed. To practice with a click, make the click at the new tempo: if the song is at 120 BPM, at 80 % it's 96. The slower, the more you hear that the audio is stretched, especially the drums.

### Separating instruments

Each person asks for their instrument and gets two files: **the instrument alone** and **the rest of the song without that instrument**.

```bash
song-wizard separate --stem vocals "song.opus"    # singer
song-wizard separate --stem drums  "song.opus"    # drums
song-wizard separate --stem bass   "song.opus"    # bass
song-wizard separate --stem guitar "song.opus"    # guitar
song-wizard separate --stem piano  "song.opus"    # piano
song-wizard separate --stem drumkit "song.opus"   # the drum kit in pieces
```

It makes, for example, `Title (drums).wav` and `Title (no drums).wav` next to the original. Several can be asked for at once, and a whole folder processed:

```bash
song-wizard separate --stem drums --stem bass "Music/Show"
```

To get **every stem** (to mix in REAPER, say):

```bash
song-wizard separate --stem all "song.opus"
```

It makes `Title (vocals).wav`, `(drums)`, `(bass)`, `(guitar)` and `(other)`, where "other" is everything else: keyboards, synths, backing vocals, effects. The five add up exactly to the original song: with every fader at 0 dB it sounds the same as the recording. It doesn't make the "no X" files, because they're made by muting a track. Since the stems come from different models, "other" may hold some leftovers of the other instruments.

- Each instrument is separated with the model that does it best: Mel-Band Roformer for vocals, Demucs `htdemucs_ft` for drums and bass, and BS-Roformer SW (6 instruments) for guitar and piano, which come out together from a single pass if both are asked for.
- Instrument + rest add up **exactly** to the original song, and everything stays lined up.
- **Piano** is for songs with a real piano (acoustic or electric): synths stay in the rest, and in some songs it takes something else (horns, for example). That's why it isn't in "All": it's asked for separately (`--stem all --stem piano` gives both).
- The first time it downloads the models: about 2 GB for the four instruments (the vocals one is 870 MB and the guitar and piano one, 670 MB; piano adds nothing), and 420 MB more for the drum kit.
- Guitar is the least precise separation: some keyboards or other guitars may get mixed in. Up to 0.11 it was separated with Demucs `htdemucs_6s`, which also took horns and piano; songs separated back then keep that guitar until they're separated again.
- **The drum kit** (`--stem drumkit`, or "Drum kit" in the interface) splits the drums into kick, snare, toms, hi-hat, ride and crash, with MDX23C DrumSep: `Title (kick).wav`, `(snare)`, `(toms)`, `(hihat)`, `(ride)`, `(crash)`, plus `(drums rest)`, what's left of the drums, so everything adds up to the exact drums. It works on the drums already separated, so if the song doesn't have them, it separates them first. In "practice" it shows as "Drum kit": each piece with its volume, along with the other instruments (or with the song without drums). The model is 438 MB and takes about a minute per song.
- An open horns model (UVR `17_HP-Wind_Inst`) and piano on songs without piano were tried too: they separate, but not as well as the rest, so they're not in for now.

#### Where does separation run?

Separating is the only heavy part. song-wizard picks where to run it on its own, and it works on any computer; what changes is how long it takes:

| Your computer | Where it runs | A 5-minute song, per instrument |
|---|---|---|
| NVIDIA GTX 16 series, RTX 20 or newer | Graphics card | under 1 minute (measured with an RTX 4060) |
| Mac with an M chip | Apple's graphics | fast; it depends on the Mac model |
| NVIDIA GTX 10 or older, AMD, Intel or no card | Processor | about 10 minutes (measured with a 6-core Ryzen 5) |

- If the card doesn't have enough memory, song-wizard says so and goes on with the processor.
- If the card is NVIDIA but isn't used, updating the NVIDIA driver is usually enough.
- `--cpu` forces the processor, in case the card gives trouble.
- `song-wizard setup` shows where it will run on your computer.
- Asking for drums and bass together costs the same as asking for one: they come from the same model.

The files are 32-bit float WAVs at 44.1 kHz: peaks aren't clipped and REAPER, Ableton, Logic or any DAW opens them directly.

### Converting to share (WhatsApp, email…)

The 32-bit WAVs song-wizard makes are ideal to work with, but they're big (about 20 MB a minute). To send them over WhatsApp:

```bash
song-wizard convert "song (no drums).wav"         # one file
song-wizard convert "Music/Show"                  # every WAV in the folder
song-wizard convert --format m4a "song.wav"       # M4A (AAC) instead of MP3
```

- It makes `Title.mp3` next to the original: MP3 at ~190 kbps, which any phone plays. A 5-minute song ends up at about 7 MB. M4A takes the same space and sounds slightly better; MP3 is the most compatible.
- On a folder it only converts lossless files (WAV, FLAC, AIFF), so as not to re-encode the downloaded `.opus` files. If you name a file, it converts any format.
- If the file has peaks over 0 dB (stems do), it turns the volume down just enough so they don't clip, and tells you how much.
- It doesn't overwrite existing files; `--overwrite` replaces them.
- To work in a DAW keep using the WAVs: MP3 loses some quality and adds a few milliseconds of silence at the start, so it doesn't stay perfectly lined up with the click or the other stems.

### Song data

```bash
song-wizard tag "001 - Band - Song.opus"                                  # shows all its data
song-wizard tag "001 - Band - Song.opus" --set "artist=Band" --set "album=Live" --unset genre
song-wizard tag "001 - Band - Song (80%).mp3" --set "comment=the show's one" --only
```

The data is what the file keeps and music players show (your phone, WhatsApp, REAPER): title, artist, album, year, genre and any other, under whatever name you like. It's changed in the song and everything made from it (the `.wav` or `.mp3`, the stems, the versions), all of them or none; takes recorded in REAPER are left as they are. The audio isn't touched. With `--only`, only that file changes: a note on one version, say.

If the artist or title changes, the song and all of its files become `001 - Artist - Title` (like `rename`, with the lyrics, the REAPER project and the results). Characters Windows doesn't allow in a file name are replaced by look-alikes (`:` by `：`); in the data they stay as you typed them.

In the interface, "more › Song data…" (or `E`) shows everything the file has, including what the download brought (the video's description, the date it was uploaded), without filtering anything. Changed fields are marked, × removes a field and "add a field" adds a known one (composer, comment, track number…) or another with any name you like. At the bottom it tells you if the song is going to be renamed. "save and next" (Ctrl+Enter) goes on to the next song. On a stem or a version, "data" changes only that file.

- A field with your own name, in an `.opus` (or `.ogg`, `.flac`), can't have accents or other special letters in its name (its value can): `Ano` instead of `Año`.
- What song-wizard makes later (stems, versions at another key or speed, the song's click, MP3s) comes out with the song's data, so a loose file (on a USB stick, in WhatsApp) still tells where it comes from.
- Every file song-wizard downloads, makes, converts or trims carries its mark in `encoded_by` ("Made with"): `song-wizard 0.23.0`, the version that made it. Saving the data doesn't change it (a file without one gets it); it isn't edited.
- The download's link (`purl`) is shown but not changed: `delete` uses it to know which download the song came from.
- In `.wav` files, the data goes in the WAV's own list (title, artist, album, year, genre, comment) and all of it, your own fields too, in an ID3 part inside the file, which ffmpeg and most players read. Windows' File Explorer shows no data for any WAV (it does for `.opus`).
- The setlist, the lyrics search and the library take the title and artist from the data; a song without data, from its file name.

### Renaming a song

```bash
song-wizard rename "001 - Song (Official Video).opus" "Song"
```

Renames the song and everything made from it: the `.wav` or `.mp3`, the stems, the versions transposed or at another speed, the takes recorded in REAPER, the lyrics, the REAPER project (and the file names inside it, so it keeps opening), and its lines in `key.txt` and `bpm.txt`. It ends up `001 - Song.opus`, `001 - Song (drums).wav`, etc. Any file of the song can be given, not only the original.

The numbering (`001 - `) is kept, unless the new name brings its own (`"005 - Song"`). If any of the new names already exists, nothing is renamed. It doesn't take the characters Windows doesn't allow in file names (`\ / : * ? " < > |`) either.

Downloading the playlist again doesn't download the renamed song again: the download record keeps which link was downloaded, not the file name.

The interface has no "rename": the name follows the artist and title, which are corrected in [Song data](#song-data). `rename` stays in the terminal to give a song any other name.

### Trimming a song

```bash
song-wizard trim "001 - Song.opus" --start 0:12.5 --end 3:58   # keeps 0:12.5 to 3:58
song-wizard trim "001 - Song.opus" --start 8                    # cuts the first 8 seconds
song-wizard trim "001 - Song.opus" --pad-start 2 --pad-end 1    # adds 2 s of silence before and 1 s after
```

Cuts the start or end of the song (a video's intro or credits), or adds silence before or after it. Times go in seconds (`12.5`) or in minutes and seconds (`0:12.5`); the silence, in seconds, with decimals.

It's done on the song and everything made from it at once, so they stay lined up: its other formats, the stems, the transposed versions and the clicks, with the same cut; and the versions at another speed, with the cut in proportion (at 80 %, 10 s of the song are 12.5 s). The practice click's first beat and the lyrics' times move the same, so "practice" stays in sync. Takes recorded in REAPER are left as they are, because they're lined up to the REAPER project; that project is now out of step, so it's best to redo it (`reaper --redo`).

The cut is sample-exact, so the song and its stems stay lined up; compressed files (like the `.opus`) are encoded again at a high quality, because cutting them without doing so rounds to about 20 ms. It first writes all the new files and only if they all come out right does it replace the old ones, which go to the trash. It asks first, unless with `--yes`.

In the interface, "more › Trim…" shows the song's waveform with two handles to drag, and what stays marked. The mouse wheel zooms in and out (with Shift it moves sideways), and below there's a bar with the whole song, where what stays is marked and a box shows the stretch in view above: drag it to move, a click jumps elsewhere and the wheel on the bar moves sideways. "show the start" and "show the end" zoom around each handle, and "▶ from here" and "▶ up to here" play 5 seconds from the chosen start or up to the end, to adjust by ear. The exact times and the silence can also be typed.

### Deleting

```bash
song-wizard delete "001 - Song.opus"              # the song with everything that's its
song-wizard delete "001 - Song (drums).wav"       # only that stem
song-wizard delete --file "001 - Song.mp3"        # only that copy
```

Everything goes to the system's trash (on WSL, to the Windows Recycle Bin if the file is on a Windows drive), so it can be recovered. If something can't be sent to the trash, it stops and deletes nothing else.

- A song goes with everything made from it (its other formats, stems, versions and clicks) and with its lines in `key.txt`, `bpm.txt` and `click.txt`.
- If it was from a playlist, it also leaves its record: "check for new songs" (or running `download` again) downloads it again.
- A stem, a version or a click goes alone; `--file` deletes only that file even if it's a copy of the song, like the `.mp3`.
- It asks for confirmation before deleting; `--yes` doesn't ask.

### Lyrics

```bash
song-wizard lyrics "Music/Show"                    # finds each song's lyrics
song-wizard lyrics --from lyrics.txt "song.opus"   # or takes them from a file
song-wizard lyrics --export "song.opus"            # saves them ready to print
```

Looks up each song's lyrics in an open lyrics database, by its artist and title (from [its data](#song-data), or if it has none, from the file name "Artist - Song") and its length, and saves them next to the song as `Song.lyrics.json`. If they're not found, they can be typed or pasted by hand. They go with the song: `rename` renames them and `delete` deletes them with it.

In the interface, "more › Lyrics" ("Lyrics ✓" if the song already has them) shows them to work on:

- **Markers**: like a PDF highlighter. You pick a color (or the keys 1 to 5, which can be changed in [Keyboard shortcuts](#keyboard-shortcuts)) and the cursor becomes a marker of that color: drag over the lyrics and they're painted when you let go, or click a word. It takes whole words. Next to each color you write what it means (who sings each part, or the backing vocals, say), and that shows as a legend.
- **Eraser** (G): dragging removes the color, and a click removes the whole mark you touch.
- **Note** (N): click a line to write it a comment ("drums come in", "break", "repeat twice"). Clicking the note changes it, and leaving it empty deletes it.
- Esc lets go of the tool and Ctrl+Z (or "undo") goes back.
- **Write or paste**: to correct the lyrics or enter them by hand. The lines you don't change keep their colors and notes.
- **Print**: opens the lyrics with their colors, notes and legend in another tab, to print them or save them as PDF; if they're long, they go in two columns. `lyrics --export` saves the same page as `Song.lyrics.html`.

Everything is saved on its own. Looking up the lyrics again replaces them and the colors and notes are lost (the legend stays), which is why it asks first.

### REAPER

```bash
song-wizard reaper "001 - Song.opus"          # opens it in REAPER, and creates it first if it doesn't exist
song-wizard reaper --redo "001 - Song.opus"   # makes a new one (the old one goes to the trash)
song-wizard reaper --setting show             # what song-wizard changed in REAPER (restore puts it back)
```

Opens the song's REAPER project, `Song.rpp`, which sits next to the song. If it doesn't exist, it first makes it with whatever is there at that moment:

- **A track per stem**, with the instrument's name: the same ones the practice player starts with (every instrument, or the separated instrument and the rest). The other stems and the original song are there as muted tracks, to switch between them. If the song isn't separated, the song goes alone. All at 0 dB.
- **The tempo and meter** of the click adjusted in "practice" (or `align`), with decimals, and the audio shifted so the song's first beat falls right on a bar, with one bar of count-in before. If the click isn't adjusted, it uses the tempo from `bpm.txt` without lining it up (or 120 BPM if there's none), and says so. If it doesn't fall exactly, fix it in REAPER.
- **A "Click" track** with REAPER's click, which follows the project's tempo: if you fix the tempo in REAPER, the click follows it.
- **A "Recording" track** ready to record (with Ctrl+R) from inputs 1 and 2, with monitoring (hearing what comes in) off; turn it on in the track if you want it.
- The files go by name, without copying them: the project keeps working if you move the folder, on Drive too.

An existing project is never overwritten, because it may have changes made in REAPER. `--redo` (or "more › Redo REAPER project") sends the old one to the trash and makes a new one, after separating more instruments, say. If REAPER isn't installed, the project is created all the same, but not opened ("Open in REAPER" is disabled).

**Takes.** For what you record in REAPER to show up with its song in the library, the takes have to be named `Song (record 2026-11-01 19-05-12).wav`. That's a REAPER preference that applies to all your projects (Options › Preferences › Recording › "Recorded filenames"), so song-wizard changes it the first time you create or open a project, with REAPER closed (REAPER saves its preferences when closing and would overwrite the change). It tells you when it does, with the old value and the new one, and keeps a copy of REAPER's preferences as `reaper.ini.before-song-wizard`.

In the interface, the **REAPER** box (below Jobs) always shows what changed, when and how it was before, with a button to put it back. In the terminal: `song-wizard reaper --setting show`, and `--setting restore` to go back. Restoring puts only that preference back as it was, without touching anything else in REAPER, and song-wizard doesn't change it again until you ask (`--setting apply`, or "set it again"). By hand: in that REAPER preference, put the old value.

Takes follow the song: `rename` renames them and `delete` deletes them with it, like the project.

### Setlist

```bash
song-wizard setlist "Music/Show"
```

```
Show

  1. Song one     Am   106   5:08  (Artist)
  2. Song two     F#m? 178   4:11  (Another artist)
  ...
23 songs, 1:40:00
```

The folder's list in the order of its files (`001 - …`), with each song's key, tempo and length, and the total. It saves `Setlist.txt` and `Setlist.html` in the folder; the `.html` opens in the browser and prints on one A4 page, with the text as big as fits.

**With songs from any folder**, in the order you want: name the songs instead of the folder.

```bash
song-wizard setlist "Music/Show/003 - Song.opus" "Music/Other/001 - Another song.opus" --title "Saturday's show" --out show.html
```

Shows the list in that order and saves nothing in the folders (the folders stay tied to their playlists); `--out` saves the page wherever you say. A stem or a version counts as its song.

**In the interface**, each folder's "setlist" button opens the list of its songs; to make one with loose songs, pick them with their checkboxes (in the order you pick them) and click "setlist of the picked songs", below. Either way a window opens where you change the title, put the songs in order by dragging them (or with ↑ ↓), drop the ones that don't go with ×, and "open to print" opens the page in another tab. Nothing is saved from the interface: to have it as a file, print it as PDF. Opened from a folder, "save the order in the folder" renumbers its files in the order of the list (see [Songs added by hand and the folder's order](#songs-added-by-hand-and-the-folders-order)).

- `--lyrics` (or "with lyrics" in the window) adds, after the list, the lyrics of each song that has them, with their colors and notes, one per page and with its setlist number. Songs without lyrics are skipped.
- The key and tempo come from what you already detected with `key` and `bpm` (or set by hand); missing ones are left blank. A `?` marks a doubtful key.
- The title and artist come from the [song's data](#song-data) (if it has none, from the file name, "Artist - Song"), without extras like "(Official Video)" or "[HD]". The artist goes smaller next to it. If something came out wrong, fix it in the song's data.
- `--title` changes the title at the top (by default, the playlist's or folder's name; with loose songs, "Setlist").
- With a folder, `--out` saves the page there instead of in the folder.

### If something fails

```bash
song-wizard report
```

Puts together a text file with the state of your computer (the same as `song-wizard setup` shows) and the last things song-wizard did, including the full error. It shows you where it is, and if you like it opens the folder and the form to report the problem on GitHub, already filled in: there you tell what happened and drag the file in. No GitHub account? Send the file over WhatsApp or email to whoever helps you with song-wizard.

In the interface it's the "report a problem" button, above the jobs; jobs that fail also have their own "report" button.

The report includes no audio. Your home folder shows as `~` (`~/Music/...` instead of `/home/your-user/Music/...`, say), but song and folder names stay: if you don't want them seen, look over the file before sending it. It comes from a log song-wizard always keeps (see [What's stored on your computer](#whats-stored-on-your-computer)) and that's never sent anywhere on its own.

## Legal notice

song-wizard is a personal project, made as a hobby to prepare rehearsals, **not for profit**: it isn't sold, charged for or monetized in any way. This isn't legal advice.

- **You're responsible for what you download and process.** Use it only with audio you have rights to or permission to use, and respect copyright and each site's terms of service, which generally don't allow downloading content except through their own features. Don't share or publish the songs, stems or tracks you make from someone else's material.
- **Not for commercial use.** Although song-wizard's code is free (see [License](#license)), some pieces it uses don't allow it or have no clear license: [diffq](https://github.com/facebookresearch/diffq) (a dependency of audio-separator) is licensed CC BY-NC 4.0, which forbids commercial use; and the separation models (Demucs, the vocals Mel-Band Roformer, the guitar and piano BS-Roformer SW, and the drum kit's MDX23C DrumSep) don't state the license of their trained weights; for BS-Roformer SW, its own page marks it as unknown. song-wizard includes no model: it downloads them the first time they're used, from the public repositories where their authors or the UVR project published them. Any commercial use requires checking those licenses separately.
- **No affiliation.** song-wizard isn't affiliated with or endorsed by any audio or video platform or by the projects it uses. All trademarks belong to their owners.
- **No warranty.** It's offered as is, without warranty of any kind, as its license states.

## License

song-wizard's code is distributed under the [GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later): you can use, study, modify and share it, as long as what you share keeps the same license and its source code. It's the right license because song-wizard uses [Essentia](https://essentia.upf.edu), which is distributed under AGPL-3.0.

## Credits

song-wizard is a thin layer over the work of other free projects:

- [Ultimate Vocal Remover (UVR)](https://github.com/Anjok07/ultimatevocalremovergui), by Anjok07 and aufr33, and its collection of separation models.
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator), which lets UVR's models be used from Python.
- [Demucs](https://github.com/facebookresearch/demucs), by Meta: the `htdemucs_ft` model, for drums and bass.
- [Mel-Band Roformer Vocal Model](https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model), by KimberleyJensen, for vocals, trained with [ZFTurbo](https://github.com/ZFTurbo/Music-Source-Separation-Training)'s code.
- BS-Roformer SW, by jarredou: the 6-instrument model that gives guitar and piano.
- MDX23C DrumSep, by aufr33 and jarredou (with the MDX23C architecture, by ZFTurbo): the drum kit.
- [Essentia](https://essentia.upf.edu), by the Music Technology Group of Universitat Pompeu Fabra: key, tempo and beats.
- [BTC](https://github.com/jayg996/BTC-ISMIR19), by Jonggwon Park, Kyoyun Choi, Sungwook Jeon, Dokyun Kim and Jonghun Park (ISMIR 2019): chords. Its code is in `src/song_wizard/third_party/btc`, under its MIT license.
- [LRCLIB](https://lrclib.net): an open, community lyrics database.
- [Rubber Band](https://breakfastquay.com/rubberband/), by Breakfast Quay: pitch and speed changes.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): downloads.
- [ffmpeg](https://ffmpeg.org): reading and converting audio.
- [mutagen](https://github.com/quodlibet/mutagen): writing a song's data in its files.
- [PyTorch](https://pytorch.org) and [uv](https://docs.astral.sh/uv/).

## Appendix: tests

### Automated tests

Every change pushed to GitHub runs the automated tests, on Linux (Ubuntu) and on a Mac with an M chip (macOS 15): the result shows in the badge at the very top. Besides the tests, they install song-wizard the same way as in [Installation](#installation), to check it installs well on both systems.

They use synthetic audio made in the test itself (tones, chords and a simple drum beat), never real songs, and they don't go online. They cover:

- That every terminal command reaches what it has to do.
- `key`: a chord progression in G major, A minor, E-flat major and F-sharp minor gives the right key with 4/4.
- `bpm`: a drum beat at 90, 120 and 137 BPM gives the exact tempo (±0.5) and "steady".
- `click`: every hit within 0.1 ms of its theoretical position over 10 minutes, also with tempos with decimals; accents and subdivisions in place; the length rounds to whole bars.
- `transpose`: the pitch changes by what was asked (an A 440 goes up to 880 with +12), the length doesn't change and peaks over 0 dB are kept intact; with 0 semitones it gives back the original.
- `speed`: from 25 % to 200 %, the length changes exactly as asked, the pitch stays the same (and changes as asked with `--semitones`) and peaks over 0 dB are kept intact; a click's hits fall in place at the new tempo.
- `convert`: turns down only what goes over 0 dB; in a folder it skips compressed files; it doesn't overwrite files without `--overwrite`.
- `key.txt` and `bpm.txt` (also the key and tempo set by hand, in English or Spanish, which analyzing again doesn't overwrite), the settings, the music folder and the `archives` records (also the one each playlist keeps in its folder: taken by another computer, updated by downloading and deleting, removed when forgetting, a copy that doesn't take over, and a damaged or odd record ignored).
- `lyrics`: picks the version with the closest length, lyrics with times, no internet or no results, pasting from a file (keeping the marks if the text didn't change), checking what the page saves, the page to print (with names as text, never HTML), and that they follow the song when renaming and deleting it (the lyrics database isn't queried in the tests).
- `separate`: the drum kit in the terminal, which instruments go in "All" (not piano, unless asked), and that guitar and piano use the same model (a single pass).
- `chords`: BTC's names written as on a chord sheet (Am7, C#m7b5, N.C.), the changes moved onto the click's beats (flickers under half a beat dropped), what was corrected by hand kept when detecting again, any name saved with its quotes escaped (and shapes that don't fit refused), the chords following a rename and a trim, the page reading and saving them, and the model used only if its SHA-256 matches (and not downloaded again). Detecting with the real model needs to download it (12 MB): `uv run pytest -m network` checks that a synthetic I-IV-V-I in G gives G, C and D.
- `trim`: the same cut in the song and its stems, sample-exact (a pulse at 3 s stays where it should), the `.opus` encoded again lined up with the stems (under half a millisecond), versions at another speed in proportion, the silence added, REAPER takes untouched, 32-bit float WAVs that stay float, the download's link kept, the click and lyrics moving along, and that if one file fails nothing changes.
- `reaper`: which tracks go in (every stem, an instrument with the rest or the song alone, and the rest muted), the first beat on a bar line with tempos with decimals, names with quotes, that an existing project isn't overwritten (and `--redo`), the takes preference (with REAPER open it isn't touched; restoring puts back only that line, without touching what changed afterwards, and song-wizard doesn't change it again), Windows line endings intact, and that the project, the file names inside it and the takes follow the song when renaming and deleting it. REAPER isn't opened or touched in the tests.
- `tag`: data read and written in `.opus`, `.wav` and `.mp3` (also with line breaks and your own field names), in the song and its stems and versions but not in the takes, the audio intact, a WAV that stays a WAV (and one damaged by 0.22.0–0.22.3 mended), renaming when the artist or title changes (with the characters Windows doesn't allow), `--only`, the download's link that isn't removed, what's made later carrying the song's data and song-wizard's mark, the name of what's downloaded, the filter by words without accents, the settings file created by any command, and the interface's window.
- Numbering: a song added by hand to a playlist's folder takes the next number, named by its data, with its `.wav` if the playlist keeps them (and not while it's still copying in, nor outside playlists); downloads go on after the last number, while a new playlist keeps the site's order; `order` renumbers a folder (also swapping numbers) with each song's files and results, and refuses songs from elsewhere.
- `setlist`: order, clean names, doubtful key marked, total, names with HTML shown as text, and the page from the interface (only from its own page). With loose songs: from several folders in the order asked, a stem counts as its song, nothing is saved in the folders, a song that isn't there gives an error, and paths outside the music folder refused; the lyrics with their marks after the list, only of the songs that have them.
- The player's live pitch (running the processor with Node): exact tuning, nothing added and the same delay for every pitch.
- Upgrading: retired versions (not offered or listed, `--to` asks for `--force`, whoever has a retired one is told and moved to the newest that isn't, and if the list can't be read nothing stops), comparing versions, reading the published versions from the tags (and not failing without internet), `upgrade --list` and `--to`, that `upgrade` installs the newest tag (or only updates what it uses if it's already on the latest, or reinstalls from the folder if it was installed that way), `upgrade --check`, the check from the interface (remembered for a few hours, unless asked again), and that a restart asked from the page brings up a new interface on the same port, without opening the browser.
- Languages: the interface's texts are keys with a file per language (`static/i18n/es.json`, `en.json`, `pt.json`); the three have the same keys, every key the page or the server uses is there and none is left over, no language asks for a value the Spanish doesn't have, and the server answers in the page's language.
- `ui`: security (it only serves its own page: another page, even from another server on this computer, can't act or read anything; the domain; paths outside the music folder; invalid actions), that it runs in the background (it starts once, is reused, shuts down with `--stop`, with its internal key, or from the page), the library grouped by song, playing by parts and a click job end to end.

`separate` doesn't run in the automated tests because it needs to download the models (1.3 GB); it can be tested by hand with `uv run pytest -m slow`, which checks that instrument + rest add up to the original. To run the tests on your computer, from the project's folder: `uv run pytest`.

### Manual tests

The record of what was tested by hand and how (with real songs, programs and browsers, or simulating cases like an old graphics card), to repeat it when that part is touched, is in [CHECKLIST.md](CHECKLIST.md).
