"""The interface's server, on a real local port."""

import http.client
import json
import threading
import time
from http.server import ThreadingHTTPServer

import pytest
import soundfile as sf

import synth

from song_wizard import ui

TOKEN = "test-token"


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "music"
    root.mkdir()
    runner = ui.Runner()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ui.make_handler(TOKEN, root, runner, 0))
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
    show = root / "Show"
    show.mkdir()
    names = ["001 - Song.opus", "001 - Song.wav", "001 - Song.mp3", "001 - Song (drums).wav",
             "001 - Song (no drums).wav", "001 - Song (+2).wav", "002 - Other (Live).opus",
             "Click 120 BPM 4-4.wav", "notes.txt"]
    for name in names:
        (show / name).write_bytes(b"x")
    (show / "key.txt").write_text("# header\n001 - Song.opus\tG    G major\n")
    (show / "bpm.txt").write_text("# header\n001 - Song (drums).wav\t120.0 BPM  steady\n")
    (root / "Loose.mp3").write_bytes(b"x")
    library = get_json(port, "/api/library")
    assert library["root"] == str(root)
    main, folder = library["folders"]
    assert main["name"] == "(carpeta principal)" and [s["name"] for s in main["songs"]] == ["Loose.mp3"]
    assert folder["name"] == "Show" and folder["path"] == "Show"
    song, other = folder["songs"]
    assert song["name"] == "001 - Song.opus" and song["key"] == "G    G major" and song["bpm"] is None
    assert sorted(f["name"] for f in song["files"]) == sorted(
        ["001 - Song.wav", "001 - Song.mp3", "001 - Song (drums).wav", "001 - Song (no drums).wav", "001 - Song (+2).wav"])
    drums = next(f for f in song["files"] if f["name"] == "001 - Song (drums).wav")
    assert drums["bpm"] == "120.0 BPM  steady" and drums["key"] is None
    assert other["name"] == "002 - Other (Live).opus" and other["files"] == []
    assert [e["name"] for e in folder["extras"]] == ["Click 120 BPM 4-4.wav"]


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
    synth.write(root / "tone.wav", synth.sine(440, 2))
    response, content = request(port, "POST", "/api/jobs",
                                {"action": "speed", "percent": 80, "semitones": -2, "paths": ["tone.wav"]})
    job = json.loads(content)
    assert job["title"] == "Velocidad 80% y tono -2: tone.wav"
    status, lines = wait_for(port, job["id"])
    assert status == "done", lines
    song = get_json(port, "/api/library")["folders"][0]["songs"][0]
    assert song["name"] == "tone.wav"
    assert [f["name"] for f in song["files"]] == ["tone (80%, -2).wav"]


def test_job_on_a_single_stem(server):
    port, root = server
    synth.write(root / "tone.wav", synth.sine(440, 2))
    synth.write(root / "tone (drums).wav", synth.sine(220, 2))
    response, content = request(port, "POST", "/api/jobs", {"action": "speed", "percent": 50, "paths": ["tone (drums).wav"]})
    status, lines = wait_for(port, json.loads(content)["id"])
    assert status == "done", lines
    (song,) = get_json(port, "/api/library")["folders"][0]["songs"]
    assert sorted(f["name"] for f in song["files"]) == ["tone (drums) (50%).wav", "tone (drums).wav"]
    assert sf.info(root / "tone (drums) (50%).wav").duration == pytest.approx(4)


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
    monkeypatch.setattr(ui.subprocess, "Popen", lambda cmd, **kwargs: calls.append(cmd))
    return calls


def test_open_folder(server, launched, monkeypatch):
    port, root = server
    (root / "Show").mkdir()
    monkeypatch.setattr(ui, "folder_command", lambda path: ["open", str(path)])
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


def test_folder_command(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "is_wsl", lambda: False)
    monkeypatch.setattr(ui.sys, "platform", "darwin")
    assert ui.folder_command(tmp_path) == ["open", str(tmp_path)]
    monkeypatch.setattr(ui.sys, "platform", "linux")
    monkeypatch.setattr(ui.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert ui.folder_command(tmp_path) == ["xdg-open", str(tmp_path)]
    monkeypatch.setattr(ui.shutil, "which", lambda name: None)
    assert ui.folder_command(tmp_path) is None


def test_folder_command_wsl(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "is_wsl", lambda: True)
    monkeypatch.setattr(ui.shutil, "which", lambda name: f"/usr/bin/{name}")

    class Done:
        stdout = "C:\\Users\\me\\Music\\Show\n"

    monkeypatch.setattr(ui.subprocess, "run", lambda cmd, **kwargs: Done() if cmd[:2] == ["wslpath", "-w"] else None)
    assert ui.folder_command(tmp_path) == ["explorer.exe", "C:\\Users\\me\\Music\\Show"]
