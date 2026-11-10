"""The interface's server, on a real local port."""

import http.client
import json
import threading
import time

import numpy as np
import pytest
import soundfile as sf

import synth

from song_wizard import config, system, ui

TOKEN = "test-token"


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "music"
    root.mkdir()
    runner = ui.Runner()
    httpd = ui.Server(("127.0.0.1", 0), ui.make_handler(TOKEN, root, runner, 0))
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = ui.make_handler(TOKEN, root, runner, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield port, root
    httpd.shutdown()
    httpd.server_close()


def request(port, method, path, body=None, token=TOKEN, host=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    all_headers = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    if token is not None:
        all_headers["X-Token"] = token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        all_headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=all_headers)
    response = conn.getresponse()
    content = response.read()
    conn.close()
    return response, content


def get_json(port, path):
    response, content = request(port, "GET", path)
    assert response.status == 200
    return json.loads(content)


def test_page_with_token(server):
    port, _ = server
    response, content = request(port, "GET", f"/?t={TOKEN}", token=None)
    assert response.status == 200
    assert b"<html" in content.lower()


@pytest.mark.parametrize("token, host", [(None, None), ("wrong", None), (TOKEN, "evil.example:80")])
def test_forbidden(server, token, host):
    port, _ = server
    assert request(port, "GET", "/api/library", token=token, host=host)[0].status == 403
    assert request(port, "POST", "/api/jobs", {"action": "key", "paths": [""]}, token=token, host=host)[0].status == 403


# What a browser sends, by where the request comes from.
OWN_PAGE = {"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors"}
TYPED_IN = {"Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate"}
OTHER_SITE = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors", "Origin": "https://evil.example"}
# Another server on this computer, on another port: same site, but not the same origin.
OTHER_PORT = {"Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "no-cors", "Origin": "http://127.0.0.1:3000"}


def test_without_token_only_its_own_page(server):
    port, _ = server
    # Acting on a song that isn't there: 404 if the request is let in, 403 if not.
    job = {"path": "nothing.opus"}
    # The page itself, and what it asks for.
    assert request(port, "GET", "/", token=None, headers=TYPED_IN)[0].status == 200
    assert request(port, "GET", "/api/library", token=None, headers=OWN_PAGE)[0].status == 200
    assert request(port, "POST", "/api/reaper", job, token=None, headers=OWN_PAGE)[0].status == 404
    # Any other page in the browser can't do anything, nor read anything...
    for headers in (OTHER_SITE, OTHER_PORT):
        assert request(port, "POST", "/api/reaper", job, token=None, headers=headers)[0].status == 403
        assert request(port, "POST", "/api/shutdown", {}, token=None, headers=headers)[0].status == 403
        assert request(port, "GET", "/api/audio?path=x.wav", token=None, headers=headers)[0].status == 403
        # ...not even with a link that opens it as a page, except for the page itself.
        link = {**headers, "Sec-Fetch-Mode": "navigate"}
        assert request(port, "GET", "/api/library", token=None, headers=link)[0].status == 403
        assert request(port, "GET", "/", token=None, headers=link)[0].status == 200
    # A typed-in address can only look, never act.
    assert request(port, "POST", "/api/reaper", job, token=None, headers=TYPED_IN)[0].status == 403
    # Browsers from before Sec-Fetch-Site: by Origin.
    assert request(port, "POST", "/api/reaper", job, token=None, headers={"Origin": f"http://127.0.0.1:{port}"})[0].status == 404
    assert request(port, "POST", "/api/reaper", job, token=None, headers={"Origin": f"http://localhost:{port}"})[0].status == 404
    assert request(port, "POST", "/api/reaper", job, token=None, headers={"Origin": "http://127.0.0.1:3000"})[0].status == 403
    # Nothing says where it comes from (not a browser, or a very old one): refused.
    assert request(port, "POST", "/api/reaper", job, token=None)[0].status == 403
    # Its own page, but under another name (DNS rebinding): refused.
    assert request(port, "GET", "/api/library", token=None, host="evil.example:80",
                   headers={**OWN_PAGE, "Origin": "http://evil.example"})[0].status == 403


def test_links_from_before_still_work(server):
    port, _ = server
    assert request(port, "GET", f"/api/library?t={TOKEN}", token=None)[0].status == 200
    assert request(port, "GET", "/api/library?t=wrong", token=None, headers=OWN_PAGE)[0].status == 403


def test_localhost_host_allowed(server):
    port, _ = server
    assert request(port, "GET", "/api/library", host=f"localhost:{port}")[0].status == 200


def test_paths_outside_the_music_folder(server, tmp_path):
    port, _ = server
    (tmp_path / "secret.wav").write_bytes(b"secret")
    assert request(port, "GET", "/api/audio?path=../secret.wav")[0].status == 403
    assert request(port, "GET", f"/api/audio?path={tmp_path / 'secret.wav'}")[0].status == 403
    response, _ = request(port, "POST", "/api/jobs", {"action": "key", "paths": ["../secret.wav"]})
    assert response.status == 403
    response, _ = request(port, "POST", "/api/jobs", {"action": "click", "bpm": 120, "folder": "../.."})
    assert response.status == 403


@pytest.mark.parametrize("body", [
    {"action": "rm"}, {"paths": []}, {"action": "key", "paths": []},
    {"action": "download", "url": "file:///etc/passwd"}, {"action": "convert", "paths": [""], "format": "exe"},
    {"action": "separate", "paths": [""], "stems": ["kazoo"]}, {"action": "transpose", "paths": [""], "semitones": "x"},
    {"action": "speed", "paths": [""]}, {"action": "speed", "paths": [""], "percent": "fast"},
])
def test_bad_requests(server, body):
    port, _ = server
    assert request(port, "POST", "/api/jobs", body)[0].status == 400


def test_library_groups_files_under_their_song(server):
    port, root = server
    here = root / "Show" / "001 - Song"
    here.mkdir(parents=True)
    names = ["001 - Song.opus", "001 - Song.wav", "001 - Song.mp3", "drums.wav", "no drums.wav", "+2.wav",
             "drums 80%.wav", "record 2026-11-01 19-05-12.wav", "lyrics.json", "001 - Song.rpp"]
    for name in names:
        (here / name).write_bytes(b"x")
    (here / "key.txt").write_text("G    G major\n")
    (here / "tempo.txt").write_text("120.25 BPM 4/4, first beat 0.512 s  set by hand\n")
    (root / "Show" / "002 - Other (Live)").mkdir()
    (root / "Show" / "002 - Other (Live)" / "002 - Other (Live).opus").write_bytes(b"x")
    (root / "Show" / "Click 120 BPM 4-4.wav").write_bytes(b"x")
    (root / "Show" / "notes.txt").write_bytes(b"x")
    (root / "Loose").mkdir()
    (root / "Loose" / "Loose.mp3").write_bytes(b"x")
    library = get_json(port, "/api/library")
    assert library["root"] == str(root)
    main, folder = library["folders"]
    assert main["name"] == "(carpeta principal)" and [s["name"] for s in main["songs"]] == ["Loose.mp3"]
    assert main["songs"][0]["path"] == "Loose/Loose.mp3"
    assert folder["name"] == "Show" and folder["path"] == "Show"
    song, other = folder["songs"]
    assert song["name"] == "001 - Song.opus" and song["path"] == "Show/001 - Song/001 - Song.opus"
    assert song["key"] == "G    G major" and song["bpm"] == "120.25 BPM 4/4, first beat 0.512 s  set by hand"
    assert song["click"] == {"bpm": 120.25, "meter": "4/4", "first": 0.512}
    assert song["lyrics"] and song["reaper"]
    kinds = {f["name"]: (f["kind"], f["part"]) for f in song["files"]}
    assert kinds == {"001 - Song.wav": ("copy", None), "001 - Song.mp3": ("copy", None), "drums.wav": ("stem", "drums"),
                     "no drums.wav": ("stem", "no drums"), "+2.wav": ("version", None), "drums 80%.wav": ("version", None),
                     "record 2026-11-01 19-05-12.wav": ("take", None)}
    assert next(f for f in song["files"] if f["name"] == "drums 80%.wav")["speed"] == pytest.approx(0.8)
    assert other["name"] == "002 - Other (Live).opus" and other["files"] == []
    assert [e["name"] for e in folder["extras"]] == ["Click 120 BPM 4-4.wav"]


def test_library_shows_folders_from_before_closed(server):
    """Songs loose in their folder, as before 0.42.0: shown only as needing tidy."""
    port, root = server
    (root / "Show").mkdir()
    for name in ["001 - Song.opus", "001 - Song (drums).wav", "002 - Other.opus"]:
        (root / "Show" / name).write_bytes(b"x")
    (folder,) = get_json(port, "/api/library")["folders"]
    assert folder["name"] == "Show" and folder["songs"] == [] and folder["old"] == 2
    job = json.loads(request(port, "POST", "/api/jobs", {"action": "tidy", "folder": "Show"})[1])
    assert job["title"] == "Acomodar en carpetas: Show"
    status, lines = wait_for(port, job["id"])
    assert status == "done", lines
    (folder,) = get_json(port, "/api/library")["folders"]
    assert [s["path"] for s in folder["songs"]] == ["Show/001 - Song/001 - Song.opus", "Show/002 - Other/002 - Other.opus"]
    assert [f["name"] for f in folder["songs"][0]["files"]] == ["drums.wav"]


def test_audio_ranges(server):
    port, root = server
    data = bytes(range(256)) * 4
    (root / "a.opus").write_bytes(data)
    response, content = request(port, "GET", "/api/audio?path=a.opus")
    assert response.status == 200 and content == data
    assert response.getheader("Content-Type") == "audio/ogg"
    response, content = request(port, "GET", "/api/audio?path=a.opus", headers={"Range": "bytes=100-199"})
    assert response.status == 206 and content == data[100:200]
    assert response.getheader("Content-Range") == f"bytes 100-199/{len(data)}"
    response, content = request(port, "GET", "/api/audio?path=a.opus", headers={"Range": "bytes=1000-"})
    assert response.status == 206 and content == data[1000:]
    response, content = request(port, "GET", "/api/audio?path=a.opus", headers={"Range": "bytes=-24"})
    assert response.status == 206 and content == data[-24:]
    assert request(port, "GET", "/api/audio?path=missing.opus")[0].status == 404


def wait_for(port, job_id, seconds=60):
    deadline = time.time() + seconds
    lines = []
    while time.time() < deadline:
        jobs = get_json(port, f"/api/jobs?job={job_id}&since={len(lines)}")
        job = next(j for j in jobs if j["id"] == job_id)
        lines += job["lines"]
        if job["status"] not in ("queued", "running"):
            return job["status"], lines
        time.sleep(0.2)
    pytest.fail(f"job still running after {seconds} s: {lines}")


def test_click_job(server):
    port, root = server
    response, content = request(port, "POST", "/api/jobs",
                                {"action": "click", "bpm": 90, "meter": "3/4", "bars": 2, "folder": ""})
    assert response.status == 200
    job = json.loads(content)
    assert job["title"] == "Click 90 BPM 3/4"
    status, lines = wait_for(port, job["id"])
    assert status == "done", lines
    track, sr = sf.read(root / "Click 90 BPM 3-4.wav")
    assert len(track) / sr == pytest.approx(2 * 3 * 60 / 90, abs=0.05)


def test_speed_job(server):
    port, root = server
    synth.song(root, "tone.wav", synth.sine(440, 2))
    response, content = request(port, "POST", "/api/jobs",
                                {"action": "speed", "percent": 80, "semitones": -2, "paths": ["tone/tone.wav"]})
    job = json.loads(content)
    assert job["title"] == "Velocidad 80% y tono -2: tone.wav"
    status, lines = wait_for(port, job["id"])
    assert status == "done", lines
    song = get_json(port, "/api/library")["folders"][0]["songs"][0]
    assert song["name"] == "tone.wav"
    assert [f["name"] for f in song["files"]] == ["80%, -2.opus"]


def test_job_on_a_single_stem(server):
    port, root = server
    synth.song(root, "tone.wav", synth.sine(440, 2))
    synth.write(root / "tone" / "drums.wav", synth.sine(220, 2))
    response, content = request(port, "POST", "/api/jobs", {"action": "speed", "percent": 50, "paths": ["tone/drums.wav"]})
    status, lines = wait_for(port, json.loads(content)["id"])
    assert status == "done", lines
    (song,) = get_json(port, "/api/library")["folders"][0]["songs"]
    assert sorted(f["name"] for f in song["files"]) == ["drums 50%.opus", "drums.wav"]
    assert sf.info(root / "tone" / "drums 50%.opus").duration == pytest.approx(4, abs=0.05)  # Opus: lossy, 48 kHz


def test_rename_job(server):
    port, root = server
    (root / "Song (HQ)").mkdir()
    for name in ["Song (HQ).opus", "drums.wav"]:
        (root / "Song (HQ)" / name).write_bytes(b"x")
    response, content = request(port, "POST", "/api/jobs", {"action": "rename", "paths": ["Song (HQ)/Song (HQ).opus"], "name": "Song"})
    job = json.loads(content)
    assert job["title"] == "Renombrar Song (HQ).opus → Song"
    status, lines = wait_for(port, job["id"])
    assert status == "done", lines
    (song,) = get_json(port, "/api/library")["folders"][0]["songs"]
    assert song["path"] == "Song/Song.opus" and [f["name"] for f in song["files"]] == ["drums.wav"]
    two = {"action": "rename", "paths": ["Song/Song.opus", "Song/drums.wav"], "name": "X"}
    assert request(port, "POST", "/api/jobs", two)[0].status == 400


def test_playlist_update(server, monkeypatch):
    from song_wizard import archives
    port, root = server
    ran = []
    monkeypatch.setattr(ui.Runner, "run", lambda self, job: ran.append(job.args) or setattr(job, "status", "done"))
    (root / "Show").mkdir()
    (root / "Show" / "001 - A.opus").write_bytes(b"x")
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "PLx.txt").write_text("youtube a\n")
    url = "https://www.youtube.com/playlist?list=PLx"
    archives.remember("PLx", url, "Show", folder=str(root / "Show"), wav=True)
    folder = get_json(port, "/api/library")["folders"][-1]
    assert folder["playlist"] == {"id": "PLx", "title": "Show", "url": url, "wav": True}
    (row,) = get_json(port, "/api/archives")
    assert row["url"] == url and row["wav"] is True
    response, content = request(port, "POST", "/api/jobs", {"action": "download", "url": url, "wav": True, "title": "Show"})
    job = json.loads(content)
    assert job["title"] == "Buscar temas nuevos: Show"
    wait_for(port, job["id"])
    assert ran == [["download", "--wav", url]]


def test_click_for_one_song(server):
    port, root = server
    synth.song(root / "Show", "001 - Song.wav", synth.sine(440, 2))
    path = "Show/001 - Song/001 - Song.wav"
    body = {"action": "click", "bpm": 120, "like": path, "for": path, "folder": "Show"}
    status, lines = wait_for(port, json.loads(request(port, "POST", "/api/jobs", body)[1])["id"])
    assert status == "done", lines
    (song,) = get_json(port, "/api/library")["folders"][-1]["songs"]
    assert [(f["name"], f["kind"]) for f in song["files"]] == [("click 120 BPM 4-4.wav", "click")]
    assert request(port, "POST", "/api/jobs", {**body, "for": "../x.wav"})[0].status == 403


def test_peaks(server):
    port, root = server
    synth.write(root / "tone.wav", synth.sine(440, 4, peak=0.5) * np.r_[np.ones(2 * synth.SR), np.zeros(2 * synth.SR)])
    whole = get_json(port, "/api/peaks?path=tone.wav&n=100")
    assert whole["from"] == 0 and whole["seconds"] == pytest.approx(4, abs=0.01) and len(whole["peaks"]) == 100
    assert whole["peaks"][10] > 0.4 and whole["peaks"][90] == 0  # loud first half, silent second
    part = get_json(port, "/api/peaks?path=tone.wav&n=50&from=1&to=3")
    assert part["from"] == 1 and part["seconds"] == pytest.approx(2, abs=0.01)
    assert part["peaks"][10] > 0.4 and part["peaks"][40] == 0
    assert request(port, "GET", "/api/peaks?path=../x.wav")[0].status == 403
    assert request(port, "GET", "/api/peaks?path=missing.wav")[0].status == 404
    assert request(port, "GET", "/api/peaks?path=tone.wav&n=lots")[0].status == 400


def test_peaks_streamed(server):
    """stream=1 sends the outline in parts as it's read (40 s: 15 s at a time) and ends with the
    same outline as without it; a file that can't be read ends with an error line."""
    port, root = server
    synth.write(root / "long.wav", synth.sine(440, 40, peak=0.5))
    ui.PEAKS.clear()
    lines = [json.loads(line) for line in request(port, "GET", "/api/peaks?path=long.wav&n=80&stream=1")[1].splitlines()]
    parts, last = lines[:-1], lines[-1]
    assert len(parts) >= 2 and all(p["of"] == 80 and p["seconds"] == pytest.approx(40, abs=0.01) for p in parts)
    assert [len(p["peaks"]) for p in parts] == sorted(len(p["peaks"]) for p in parts) and len(parts[0]["peaks"]) < 80
    assert all(v > 0.4 for v in parts[0]["peaks"])
    ui.PEAKS.clear()
    assert last == get_json(port, "/api/peaks?path=long.wav&n=80")
    # Remembered: only the outline itself.
    assert [json.loads(x) for x in request(port, "GET", "/api/peaks?path=long.wav&n=80&stream=1")[1].splitlines()] == [last]
    (root / "bad.wav").write_bytes(b"not audio")
    (line,) = request(port, "GET", "/api/peaks?path=bad.wav&stream=1")[1].splitlines()
    assert "error" in json.loads(line)


def test_click_settings(server, monkeypatch):
    port, root = server
    (root / "001 - Song").mkdir()
    (root / "001 - Song" / "001 - Song.opus").write_bytes(b"x")
    path = "001 - Song/001 - Song.opus"
    body = {"path": path, "bpm": 97.3, "meter": "3/4", "first": 1.25}
    response, content = request(port, "POST", "/api/click-settings", body)
    assert response.status == 200 and json.loads(content) == {"bpm": 97.3, "meter": "3/4", "first": 1.25}
    (song,) = get_json(port, "/api/library")["folders"][0]["songs"]
    # Set in the practice player: the song's tempo, by hand (detecting again keeps it).
    assert song["click"] == {"bpm": 97.3, "meter": "3/4", "first": 1.25}
    assert song["bpm"] == "97.30 BPM 3/4, first beat 1.250 s  set by hand"
    for bad in [{**body, "bpm": 5}, {**body, "meter": "fast"}, {**body, "first": "x"}, {"path": path}]:
        assert request(port, "POST", "/api/click-settings", bad)[0].status == 400
    assert request(port, "POST", "/api/click-settings", {**body, "path": "../x"})[0].status == 403
    ran = []
    monkeypatch.setattr(ui.Runner, "run", lambda self, job: ran.append(job.args) or setattr(job, "status", "done"))
    job = json.loads(request(port, "POST", "/api/jobs", {"action": "align", "paths": [path], "force": True})[1])
    assert job["title"] == "Tempo y primer golpe: 001 - Song.opus"
    wait_for(port, job["id"])
    assert ran == [["align", "--force", str((root / path).resolve())]]


def test_failed_job(server):
    port, root = server
    (root / "broken.wav").write_bytes(b"not audio")
    response, content = request(port, "POST", "/api/jobs",
                                {"action": "click", "bpm": 120, "like": "broken.wav", "folder": ""})
    status, _ = wait_for(port, json.loads(content)["id"])
    assert status == "failed"


@pytest.fixture
def launched(monkeypatch):
    calls = []
    monkeypatch.setattr(system, "launch", calls.append)
    monkeypatch.setattr(system, "folder_command", lambda path: ["open", str(path)])
    return calls


def test_open_folder(server, launched):
    port, root = server
    (root / "Show").mkdir()
    response, content = request(port, "POST", "/api/open", {"path": "Show"})
    assert response.status == 200
    assert launched == [["open", str((root / "Show").resolve())]]
    assert request(port, "POST", "/api/open", {"path": ""})[0].status == 200
    assert launched[-1] == ["open", str(root.resolve())]


def test_open_folder_refuses(server, launched):
    port, root = server
    (root / "song.opus").write_bytes(b"x")
    assert request(port, "POST", "/api/open", {"path": ".."})[0].status == 403
    assert request(port, "POST", "/api/open", {"path": "missing"})[0].status == 404
    assert request(port, "POST", "/api/open", {"path": "song.opus"})[0].status == 404
    assert request(port, "POST", "/api/open", {"path": "Show"}, token="wrong")[0].status == 403
    assert launched == []


def test_report(server, monkeypatch, launched):
    from song_wizard import report
    port, _ = server
    monkeypatch.setattr(report, "setup_output", lambda: "Everything is ready.")
    response, content = request(port, "POST", "/api/report", {})
    assert response.status == 200
    data = json.loads(content)
    assert data["name"].startswith("song-wizard-report-") and "Everything is ready." in data["text"]
    assert data["url"].startswith(report.ISSUES)
    assert request(port, "POST", "/api/report/open", {})[0].status == 200
    assert launched == [["open", str(report.REPORTS_DIR)]]
    assert request(port, "POST", "/api/report", {}, token="wrong")[0].status == 403


def test_info(server):
    port, root = server
    synth.write(root / "tone.wav", synth.sine(440, 2.5))
    (root / "broken.wav").write_bytes(b"not audio")
    assert get_json(port, "/api/info?path=tone.wav") == {"duration": 2.5}
    assert get_json(port, "/api/info?path=broken.wav") == {"duration": None}
    assert request(port, "GET", "/api/info?path=../x")[0].status == 403
    assert request(port, "GET", "/api/info?path=missing.wav")[0].status == 404


def test_delete_job(server, monkeypatch):
    port, root = server
    ran = []
    monkeypatch.setattr(ui.Runner, "run", lambda self, job: ran.append(job.args) or setattr(job, "status", "done"))
    for name in ["Song.opus", "Song (drums).wav"]:
        (root / name).write_bytes(b"x")
    body = {"action": "delete", "songs": ["Song.opus"], "files": ["Song (drums).wav"]}
    job = json.loads(request(port, "POST", "/api/jobs", body)[1])
    assert job["title"] == "Borrar: Song.opus, Song (drums).wav"
    wait_for(port, job["id"])
    r = root.resolve()
    assert ran == [["delete", "--yes", str(r / "Song.opus"), "--file", str(r / "Song (drums).wav")]]
    assert request(port, "POST", "/api/jobs", {"action": "delete"})[0].status == 400
    assert request(port, "POST", "/api/jobs", {"action": "delete", "files": ["../x"]})[0].status == 403


def test_playlist_outside_the_music_folder(server, monkeypatch, tmp_path):
    from song_wizard import archives
    port, root = server
    drive = tmp_path / "drive" / "Show"
    synth.song(drive, "001 - A.wav", synth.sine(440, 1))
    (tmp_path / "secret.wav").write_bytes(b"s")
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "PLx.txt").write_text("site a\n")
    archives.remember("PLx", "https://example.com/playlist?list=PLx", "Show", folder=str(drive))
    (key,) = ui.outside(root)
    (folder,) = get_json(port, "/api/library")["folders"]
    assert folder["path"] == f"{key}/Show" and folder["location"] == str(drive.parent)
    assert folder["songs"][0]["path"] == f"{key}/Show/001 - A/001 - A.wav" and folder["playlist"]["id"] == "PLx"
    quoted = key.replace("@", "%40")
    assert request(port, "GET", f"/api/audio?path={quoted}/Show/001%20-%20A/001%20-%20A.wav")[0].status == 200
    assert request(port, "GET", f"/api/audio?path={quoted}/../../secret.wav")[0].status == 403
    assert request(port, "GET", "/api/audio?path=%40deadbeef/x.wav")[0].status == 403
    ran = []
    monkeypatch.setattr(ui.Runner, "run", lambda self, job: ran.append(job.args) or setattr(job, "status", "done"))
    job = json.loads(request(port, "POST", "/api/jobs", {"action": "key", "paths": [f"{key}/Show/001 - A/001 - A.wav"]})[1])
    wait_for(port, job["id"])
    assert ran[-1] == ["key", str((drive / "001 - A" / "001 - A.wav").resolve())]
    other = tmp_path / "elsewhere"
    other.mkdir()
    job = json.loads(request(port, "POST", "/api/jobs", {"action": "archives-move", "id": "PLx", "title": "Show", "to": str(other)})[1])
    wait_for(port, job["id"])
    assert ran[-1] == ["archives", "--move", "PLx", str(other)]
    job = json.loads(request(port, "POST", "/api/jobs", {"action": "download", "url": "https://example.com/x", "to": str(other)})[1])
    wait_for(port, job["id"])
    assert ran[-1] == ["download", "--to", str(other), "https://example.com/x"]
    job = json.loads(request(port, "POST", "/api/jobs", {"action": "order", "folder": f"{key}/Show", "songs": [f"{key}/Show/001 - A/001 - A.wav"]})[1])
    wait_for(port, job["id"])
    assert ran[-1] == ["order", str(drive.resolve()), str((drive / "001 - A" / "001 - A.wav").resolve())]
    job = json.loads(request(port, "POST", "/api/jobs", {"action": "archives-add", "to": str(other)})[1])
    wait_for(port, job["id"])
    assert ran[-1] == ["archives", "--add", str(other)]
    for bad in [{"action": "archives-move", "id": "PLx", "to": str(tmp_path / "nope")}, {"action": "archives-move", "id": "../x", "to": str(other)},
                {"action": "archives-add", "to": str(tmp_path / "nope")}, {"action": "archives-add"},
                {"action": "order", "folder": f"{key}/Show", "songs": []}, {"action": "order", "folder": f"{key}/Show", "songs": ["x.wav"]},
                {"action": "download", "url": "https://example.com/x", "to": "relative/dir"}]:
        assert request(port, "POST", "/api/jobs", bad)[0].status == 400
    monkeypatch.setattr(system, "pick_folder", lambda: "/picked")
    assert json.loads(request(port, "POST", "/api/pick-folder", {})[1]) == {"path": "/picked"}


def test_icon_and_logo_need_no_token(server):
    port, _ = server
    response, content = request(port, "GET", "/favicon.ico", token=None)
    assert response.status == 200 and response.getheader("Content-Type") == "image/x-icon" and content[:4] == b"\0\0\1\0"
    response, content = request(port, "GET", "/static/logo.png", token=None)
    assert response.status == 200 and content[:8] == b"\x89PNG\r\n\x1a\n"
    assert request(port, "GET", "/static/other.png", token=None)[0].status == 403
    assert request(port, "GET", "/favicon.ico", token=None, host="evil.example:80")[0].status == 403


def test_folder_on_an_unmounted_drive(server, monkeypatch):
    port, _ = server
    monkeypatch.setattr(system, "is_wsl", lambda: True)
    monkeypatch.setattr(system.shutil, "which", lambda name: None)
    monkeypatch.setattr(system.os.path, "ismount", lambda p: False)
    response, content = request(port, "POST", "/api/jobs", {"action": "download", "url": "https://example.com/x", "to": "H:\\Mi unidad"})
    data = json.loads(content)
    assert response.status == 400 and data["command"] == f"sudo mkdir -p /mnt/h && sudo mount -t drvfs H: /mnt/h -o {system.mount_options()}"


def test_singles_in_two_places(server, tmp_path):
    from song_wizard import archives
    port, root = server
    (root / "Singles" / "Here").mkdir(parents=True)
    (root / "Singles" / "Here" / "Here.opus").write_bytes(b"x")
    drive = tmp_path / "drive"
    (drive / "Singles" / "There").mkdir(parents=True)
    (drive / "Singles" / "There" / "There.opus").write_bytes(b"x")
    (drive / "empty").mkdir()  # no audio: not listed
    archives.ARCHIVE_DIR.mkdir(parents=True)
    (archives.ARCHIVE_DIR / "singles.txt").write_text("site a\nsite b\n")
    archives.remember(archives.SINGLES, None, None, folder=str(drive / "Singles"))
    archives.remember(archives.SINGLES, None, None, folder=str(root / "Singles"))  # the latest single went here
    folders = get_json(port, "/api/library")["folders"]
    assert [(f["name"], f["location"], f["songs"][0]["name"]) for f in folders] == [
        ("Singles", None, "Here.opus"), ("Singles", str(drive), "There.opus")]


def test_audio_in_stretches(server):
    """A player's "from here on" gets a stretch, not the whole file: holding a connection per
    track until the end stalled the practice player past 6 tracks (browsers open 6 per server)."""
    port, root = server
    data = bytes(range(256)) * ((ui.AUDIO_CHUNK * 2 + 1000) // 256)
    (root / "big.wav").write_bytes(data)
    response, content = request(port, "GET", "/api/audio?path=big.wav", headers={"Range": "bytes=0-"})
    assert response.status == 206 and content == data[:ui.AUDIO_CHUNK]
    assert response.getheader("Content-Range") == f"bytes 0-{ui.AUDIO_CHUNK - 1}/{len(data)}"
    # The last stretch ends with the file; an explicit range is given whole.
    start = len(data) - 500
    response, content = request(port, "GET", "/api/audio?path=big.wav", headers={"Range": f"bytes={start}-"})
    assert content == data[start:]
    response, content = request(port, "GET", "/api/audio?path=big.wav", headers={"Range": f"bytes=10-{ui.AUDIO_CHUNK * 2}"})
    assert content == data[10:ui.AUDIO_CHUNK * 2 + 1]


def test_settings_file_from_the_page(server):
    port, root = server
    data = get_json(port, "/api/config")
    assert "[download]" in data["text"] and data["text"] == config.CONFIG_PATH.read_text()  # made on first look
    assert data["values"]["audio"]["stems"] == "opus" and "[audio]" in data["template"]
    response, content = request(port, "POST", "/api/config", {"text": '[audio]\nstems = "wav"\n'})
    assert response.status == 200 and json.loads(content)["values"]["audio"]["stems"] == "wav"
    assert config.CONFIG_PATH.read_text() == '[audio]\nstems = "wav"\n'
    response, content = request(port, "POST", "/api/config", {"text": "[audio\nstems = 1"})
    assert response.status == 400 and "TOML" in json.loads(content)["error"]
    assert config.CONFIG_PATH.read_text() == '[audio]\nstems = "wav"\n'  # left as it was
