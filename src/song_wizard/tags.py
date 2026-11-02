"""A song's data (title, artist, album, year, genre, or any other) as the audio file keeps it, the
way music players read it. Read with ffprobe, whatever the format. Written with ffmpeg, which
keeps the audio as it is; in a WAV with mutagen, as an ID3 chunk (the WAV's own list holds only a
few fields), which ffprobe, ffmpeg and most players read.

A song's data goes to the song and everything made from it (other formats, stems, versions), all
or none; REAPER takes are left alone. Changing the artist or the title renames the song to
"NNN - Artist - Title", like a download is named."""

import os
import re
import shutil
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from .audio import AUDIO_EXTS, base_of, die

# The fields shown first, in this order, and the ones the library and the filter use.
MAIN = ("title", "artist", "album", "date", "genre")
# Kept by a download for "song-wizard delete" to find where it came from: never removed.
KEEP = ("purl", "encoded_by")
# Each file's own: "song-wizard 0.22.6", the version that made it (downloaded, separated, ...).
MARK = "encoded_by"
# Fields with their own ID3 frame in a WAV (others go as TXXX, by name).
FRAMES = {"encoded_by": "TENC", "title": "TIT2", "artist": "TPE1", "album": "TALB", "genre": "TCON", "composer": "TCOM",
          "album_artist": "TPE2", "track": "TRCK", "disc": "TPOS", "publisher": "TPUB", "copyright": "TCOP"}
# A take recorded in REAPER: "Title (record 2026-01-03 2015).wav".
TAKE = re.compile(r"^ \(record [^)]*\)(-\d+)?$")
# Not allowed in Windows file names: the look-alikes yt-dlp also uses.
LOOKALIKE = str.maketrans({"\\": "⧹", "/": "⧸", ":": "：", "*": "＊", "?": "？", '"': "＂", "<": "＜", ">": "＞", "|": "｜"})

_cache = {}


def _id3_in_front(path):
    """How many bytes of ID3 a WAV has in front of it (0.22.0 to 0.22.3 left it so), or 0."""
    try:
        with open(path, "rb") as f:
            head = f.read(10)
    except OSError:
        return 0
    if len(head) < 10 or head[:3] != b"ID3" or not os.fspath(path).lower().endswith(".wav"):
        return 0
    size = (head[6] & 0x7F) << 21 | (head[7] & 0x7F) << 14 | (head[8] & 0x7F) << 7 | (head[9] & 0x7F)
    return 10 + size + (10 if head[5] & 0x10 else 0)


def _without_front(path, skip, to):
    """The WAV at path, without the ID3 in front of it, written to `to`."""
    with open(path, "rb") as src, open(to, "wb") as dst:
        src.seek(skip)
        shutil.copyfileobj(src, dst, 1 << 20)


def read(path):
    """{field: value} of the file; {} if it has none or can't be read."""
    path = os.fspath(path)
    try:
        st = os.stat(path)
    except OSError:
        return {}
    # A file replaced has another inode: its time and size alone can match the old one's (on the
    # Mac, data rewritten in the room kept for it leaves the size as it was).
    key = (path, st.st_ino, st.st_mtime_ns, st.st_ctime_ns, st.st_size)
    if key not in _cache and _id3_in_front(path):
        # ffmpeg 8 doesn't open such a WAV at all: its data is that ID3 (mutagen reads it).
        try:
            from mutagen.id3 import ID3
            frames = ID3(path)
            _cache[key] = {**{k: str(frames[f]) for k, f in FRAMES.items() if f in frames},
                           **{t.desc: str(t) for t in frames.getall("TXXX")},
                           **({"date": str(frames["TDRC"])} if "TDRC" in frames else {}),
                           **({"comment": str(frames.getall("COMM")[0])} if frames.getall("COMM") else {})}
        except Exception:
            _cache[key] = {}
    if key not in _cache:
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-of", "json", "-show_entries",
                                  "format_tags:stream_tags", "-select_streams", "a:0", path],
                                 capture_output=True, text=True, check=True, timeout=30).stdout
            import json
            data = json.loads(out or "{}")
            tags = dict(data.get("format", {}).get("tags", {}))
            for stream in data.get("streams", []):
                tags.update(stream.get("tags", {}))  # an Ogg file (.opus) keeps them in its stream
        except (subprocess.SubprocessError, OSError, ValueError):
            tags = {}
        if len(_cache) > 5000:
            _cache.clear()
        _cache[key] = {k.lower() if k.upper() == k else k: v for k, v in tags.items()}
    return dict(_cache[key])


def read_many(paths):
    """read() of many files at once (the library's first load)."""
    paths = list(paths)
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(paths, pool.map(read, paths)))


def title_artist(path, tags=None):
    """(title, artist) of a song: from its data, else from its file name
    ("003 - Artist - Song (Official Video).opus")."""
    from .setlist import NOISE, title_of
    tags = read(path) if tags is None else tags
    title, artist = (tags.get("title") or "").strip(), (tags.get("artist") or "").strip()
    if not title:
        return title_of(os.path.basename(path))
    return NOISE.sub("", title).strip() or title, artist


def name_for(tags):
    """"Artist - Title" for a file name (the "001 - " stays), or None without a title."""
    title, artist = (tags.get("title") or "").strip(), (tags.get("artist") or "").strip()
    if not title:
        return None
    name = f"{artist} - {title}" if artist else title
    name = re.sub(r"\s+", " ", name.translate(LOOKALIKE)).strip().rstrip(".").strip()
    return name or None


def plain(text):
    """Lowercase, without accents: "Canción" and "cancion" are the same to the filter."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def matches(words, *texts):
    """Every word of the filter is somewhere in these texts (any order, accents and case aside)."""
    hay = plain(" ".join(t for t in texts if t))
    return all(plain(w) in hay for w in words.split())


def song_files(path):
    """The song's audio files (it, its other formats, stems and versions), without REAPER takes."""
    folder, name = os.path.split(os.path.abspath(path))
    base = base_of(name)
    return [os.path.join(folder, n) for n in sorted(os.listdir(folder))
            if os.path.splitext(n)[1].lower() in AUDIO_EXTS and base_of(n) == base
            and not TAKE.match(os.path.splitext(n)[0][len(base):])
            and os.path.isfile(os.path.join(folder, n))]


def _id3(tags):
    from mutagen import id3
    frames = id3.ID3()
    for k, v in tags.items():
        if k == "comment":
            frames.add(id3.COMM(encoding=3, lang="eng", desc="", text=v))
        elif k == "date" and re.fullmatch(r"\d{4}(-\d\d(-\d\d)?)?", v):
            frames.add(id3.TDRC(encoding=3, text=v))
        elif k in FRAMES:
            frames.add(getattr(id3, FRAMES[k])(encoding=3, text=v))
        else:
            frames.add(id3.TXXX(encoding=3, desc=k, text=v))
    return frames


# Formats whose data mutagen writes the same everywhere (ffmpeg's stream copy keeps or drops
# them depending on its version: ffmpeg 8, on the Mac, kept an .opus's old data).
VORBIS = (".opus", ".ogg", ".oga", ".flac")


def _write_copy(path, tags, temp):
    """The file with exactly these fields, at temp (the audio copied as it is)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in VORBIS or ext == ".mp3":
        shutil.copyfile(path, temp)
        import mutagen
        if ext == ".mp3":
            from mutagen.mp3 import MP3
            audio = MP3(temp)
            audio.tags = _id3(tags)
        else:
            audio = mutagen.File(temp)
            if audio is None:
                raise ValueError("not a file it knows")
            if audio.tags is None:
                audio.add_tags()
            audio.tags.clear()
            for k, v in tags.items():
                audio.tags[k] = v
        audio.save()
        return
    source, front = path, _id3_in_front(path)
    if front:  # a WAV with its data in front of it: from the WAV alone (ffmpeg 8 won't open it)
        source = temp + ".src.wav"
        _without_front(path, front, source)
    try:
        _ffmpeg_copy(source, ext, tags, temp)
    finally:
        if source != path and os.path.exists(source):
            os.remove(source)
    if ext == ".wav" and tags:
        # Inside the WAV, as its "id3 " chunk. (Setting wave.tags to a plain ID3 would put it in
        # front of the file, as in an MP3: ffmpeg 6 reads that, ffmpeg 8 and Windows don't take
        # it for a WAV anymore. 0.22.0 to 0.22.3 did so; writing the data again mends it.)
        from mutagen.wave import WAVE
        wave = WAVE(temp)
        if wave.tags is None:
            wave.add_tags()
        wave.tags.clear()
        for frame in _id3(tags).values():
            wave.tags.add(frame)
        wave.save()


def _ffmpeg_copy(source, ext, tags, temp):
    """The audio copied as it is to temp, with these fields (in a WAV, only its own list's)."""
    command = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", source, "-map", "0", "-c", "copy",
               "-map_metadata", "-1", "-map_metadata:s:a", "-1"]
    if ext == ".wav":
        # The WAV's own list takes a few fields (some programs read only those); all of them go in
        # its ID3 chunk. Bitexact: without ffmpeg's name in the list.
        command += ["-fflags", "+bitexact"]
        for k in ("title", "artist", "album", "date", "genre", "comment", "copyright"):
            if tags.get(k):
                command += ["-metadata", f"{k}={tags[k]}"]
    else:
        for k, v in tags.items():
            command += ["-metadata", f"{k}={v}", "-metadata:s:a:0", f"{k}={v}"]
        if ext in (".m4a", ".mp4", ".m4b"):
            command += ["-movflags", "use_metadata_tags"]  # else only the fields MP4 knows
    command.append(temp)  # the format goes by the extension, the same as the file's
    subprocess.run(command, check=True, capture_output=True)


def mark():
    from . import __version__
    return f"song-wizard {__version__}"


def stamp(new, source=None):
    """On a file song-wizard just made: the data of the file it came from (its song, say) and
    song-wizard's mark. A failure here only warns: the file itself is fine."""
    try:
        data = {k: v for k, v in (read(source) if source else {}).items() if k not in (MARK, "encoder")}
        write([new], {**data, MARK: mark()})
    except (SystemExit, Exception) as e:
        print(f"  (couldn't write the data of {os.path.basename(new)}: {e})")


def write(paths, tags, own=None):
    """These fields, and only these, on every file: all of them or none. own(path) adds that
    file's own fields (its mark)."""
    temps = []
    try:
        for path in paths:
            folder, name = os.path.split(path)
            temp = os.path.join(folder, f".{name}.song-wizard-tags{os.path.splitext(name)[1]}")
            temps.append((temp, path))
            _write_copy(path, {**tags, **(own(path) if own else {})}, temp)
    except Exception as e:  # ffmpeg, the disk, or mutagen (a field name an Ogg file can't take)
        for temp, _ in temps:
            if os.path.exists(temp):
                os.remove(temp)
        detail = e.stderr.decode(errors="replace").strip() if getattr(e, "stderr", None) else str(e) or type(e).__name__
        die(f"Nothing changed: couldn't write {os.path.basename(temps[-1][1])}: {detail}")
    for temp, path in temps:
        shutil.copymode(path, temp)
        os.replace(temp, path)
    forget(paths)


def forget(paths):
    """Drop what was read of these files (they were just written)."""
    gone = {os.fspath(p) for p in paths}
    for key in [k for k in _cache if k[0] in gone]:
        del _cache[key]


def show(path):
    tags = read(path)
    print(os.path.basename(path))
    if not tags:
        print("  (no data)")
    for k in [*[k for k in MAIN if k in tags], *sorted(k for k in tags if k not in MAIN)]:
        value = tags[k].replace("\n", "\n" + " " * (len(k) + 4))
        print(f"  {k}: {value}")


def run(path, set_=(), unset=(), only=False):
    """Change the data of a song (and everything made from it), or of this file only."""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        die(f"{path}: not found")
    if not set_ and not unset:
        return show(path)
    old = read(path)
    tags = dict(old)
    for item in set_:
        k, sep, v = item.partition("=")
        k = k.strip()
        if not sep or not k:
            die(f'"{item}": write it as field=value (for example artist=Someone).')
        tags[k] = v
    for k in unset:
        if k in KEEP:
            die(f"{k} stays: it's where the download came from (song-wizard delete uses it).")
        tags.pop(k, None)
    tags = {k: v for k, v in tags.items() if v != "" or k in KEEP}
    tags.pop("encoder", None)  # ffmpeg writes its own
    tags.pop(MARK, None)  # each file keeps its own mark (or gets this version's)
    files = [path] if only else song_files(path)
    # Ogg and FLAC files take field names of plain letters only.
    odd = [k for k in tags if not re.fullmatch(r"[\x20-\x3c\x3e-\x7d]+", k)]
    if odd and any(os.path.splitext(f)[1].lower() in VORBIS for f in files):
        die(f"Nothing changed: {', '.join(odd)}: a field name in an .opus, .ogg or .flac file can't have accents "
            "or other special letters (Ano instead of Año, say).")
    write(files, tags, own=lambda f: {MARK: read(f).get(MARK) or mark()})
    for f in files:
        print(f"  {os.path.basename(f)}")
    print(f"Saved the data in {len(files)} file{'s' if len(files) != 1 else ''}.")
    # A new artist or title renames the song (and all that goes with it), like a download.
    if not only and any((tags.get(k) or "") != (old.get(k) or "") for k in ("artist", "title")):
        new = name_for(tags)
        current = base_of(os.path.basename(path))
        number = re.match(r"^\d+ - ", current)
        if new and (number.group(0) if number else "") + new != current:
            from . import rename
            try:
                rename.run(path, new)
            except SystemExit as e:
                print(f"Not renamed: {e.code}")
