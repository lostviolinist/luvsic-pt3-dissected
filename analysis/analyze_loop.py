#!/usr/bin/env python3
"""Measure the loop in Nujabes' "Luv(sic) Part 3" instrumental.

Usage:
    python analyze_loop.py path/to/track.(webm|mp3|wav) [--out ../data/analysis.json]

The script does not ship with audio. Point it at your own copy of the
6:14 instrumental from Luv(sic) Hexalogy. It prints a summary and writes the
numbers the web page uses (beat grid and per-pass filter levels) to JSON.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import librosa
import scipy.signal as ss

PC = ['C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B']
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
LOOP_BEATS = 16


def load_stereo(path, sr):
    """Decode any format ffmpeg understands to a float stereo array."""
    try:
        y, _ = librosa.load(path, sr=sr, mono=False)
    except Exception:
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "track.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "2", "-ar", str(sr), str(wav)], check=True)
            y, _ = librosa.load(wav, sr=sr, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    return y


def pitch_class_chroma(y, sr, hop, fmin_note, n_oct, tuning):
    """Pitch-class energy from a CQT limited to one register (bass or upper)."""
    C = np.abs(librosa.cqt(y, sr=sr, hop_length=hop, fmin=librosa.note_to_hz(fmin_note),
                           n_bins=12 * n_oct, bins_per_octave=12, tuning=tuning))
    base = librosa.note_to_midi(fmin_note) % 12
    ch = np.zeros((12, C.shape[1]))
    for i in range(C.shape[0]):
        ch[(base + i) % 12] += C[i]
    return ch


def band_db(S, f, lo, hi):
    return 10 * np.log10(S[(f >= lo) & (f < hi)].sum() + 1e-12)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "analysis.json"))
    args = ap.parse_args()

    sr = 44100
    st = load_stereo(args.audio, sr)
    y = st.mean(0)
    dur = len(y) / sr
    y_h, y_p = librosa.effects.hpss(y, margin=2)

    # ---- Beat grid: track beats, fit a straight line (the tempo is steady), then
    # shift the phase so grid beats sit on the drum hits.
    sr22 = 22050
    y22 = librosa.resample(y, orig_sr=sr, target_sr=sr22)
    _, beats = librosa.beat.beat_track(y=y22, sr=sr22, units="time")
    keep = beats < dur - 30                      # ignore the fade-out
    n = np.arange(len(beats))
    ibi, t0 = np.polyfit(n[keep], beats[keep], 1)
    p22 = librosa.effects.percussive(y22, margin=2)
    env = librosa.onset.onset_strength(y=p22, sr=sr22, hop_length=64)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr22, hop_length=64, units="time")
    on = on[(on > 5) & (on < dur - 30)]
    ph = ((on - t0) / ibi) % 1
    ph = np.where(ph > 0.5, ph - 1, ph)
    t0 += np.median(ph[np.abs(ph) < 0.15]) * ibi
    t0 -= np.floor(t0 / ibi) * ibi               # earliest grid beat at or after 0 s
    grid = np.arange(t0, dur, ibi)

    # ---- Tuning and key
    tuning = librosa.estimate_tuning(y=librosa.resample(y_h, orig_sr=sr, target_sr=sr22), sr=sr22, resolution=0.01)
    chroma = librosa.feature.chroma_cqt(y=y_h, sr=sr, tuning=tuning)
    prof = chroma.mean(1)
    keys = []
    for k in range(12):
        keys.append((float(np.corrcoef(prof, np.roll(KK_MAJOR, k))[0, 1]), f"{PC[k]} major"))
        keys.append((float(np.corrcoef(prof, np.roll(KK_MINOR, k))[0, 1]), f"{PC[k]} minor"))
    keys.sort(reverse=True)

    # ---- Beat-synchronous bass and upper-register chroma
    hop = 512
    frames = librosa.time_to_frames(grid, sr=sr, hop_length=hop)
    bass = pitch_class_chroma(y_h, sr, hop, 'C1', 3, tuning)
    upper = pitch_class_chroma(y_h, sr, hop, 'C4', 3, tuning)

    def per_beat(ch):
        cols = [ch[:, a:b].mean(1) if b > a else ch[:, a] for a, b in zip(frames[:-1], frames[1:])]
        return np.array(cols).T                   # 12 x beats

    B, U = per_beat(bass), per_beat(upper)

    # Bar phase: chord changes (bass root changes) should land on bar lines.
    roots = B.argmax(0)
    changes = np.r_[False, roots[1:] != roots[:-1]]
    bar_phase = int(np.argmax([changes[p::4].mean() for p in range(4)]))
    start = bar_phase                             # loop starts on the first bar line
    loop_start = float(grid[start])
    loop_len = LOOP_BEATS * ibi
    n_loops = int((dur - loop_start) // loop_len)

    # Loop repetition: similarity of each pass to the average pass (upper + bass chroma)
    feats = np.vstack([B, U])
    feats = feats / (np.linalg.norm(feats, axis=0, keepdims=True) + 1e-9)
    passes = np.stack([feats[:, start + k * 16: start + (k + 1) * 16] for k in range(n_loops)
                       if start + (k + 1) * 16 <= feats.shape[1]])
    mean_pass = passes.mean(0)
    sim = [float(np.mean(np.sum(p * mean_pass, 0) / (np.linalg.norm(mean_pass, axis=0) + 1e-9))) for p in passes]

    # Average loop: bass root and strongest upper pitch class on each of the 16 beats
    Bl = np.stack([B[:, start + k * 16: start + (k + 1) * 16] for k in range(len(passes))]).mean(0)
    Ul = np.stack([U[:, start + k * 16: start + (k + 1) * 16] for k in range(len(passes))]).mean(0)
    bass_line = [PC[i] for i in Bl.argmax(0)]
    upper_top = [PC[i] for i in Ul.argmax(0)]

    # ---- Per-pass filter levels (harmonic layer) and loudness
    f = librosa.fft_frequencies(sr=sr, n_fft=4096)
    rows = []
    for k in range(n_loops):
        a, b = int((loop_start + k * loop_len) * sr), min(int((loop_start + (k + 1) * loop_len) * sr), len(y))
        S = (np.abs(librosa.stft(y_h[a:b], n_fft=4096)) ** 2).mean(1)
        rows.append([band_db(S, f, 1500, 4000), band_db(S, f, 40, 150), 10 * np.log10(np.mean(y[a:b] ** 2) + 1e-12)])
    rows = np.array(rows)
    rows -= np.median(rows[: max(1, n_loops - 3)], axis=0)

    # ---- Tone: rolloff of the piano layer, spectral tilt vs pink noise, stereo width
    roll95 = float(np.median(librosa.feature.spectral_rolloff(y=y_h, sr=sr, roll_percent=0.95)))
    fw, P = ss.welch(y, fs=sr, nperseg=8192)
    centers = 100 * 2 ** np.arange(0, 8)
    oct_db = [10 * np.log10(P[(fw >= c / np.sqrt(2)) & (fw < c * np.sqrt(2))].sum()) for c in centers]
    tilt = float(np.polyfit(np.log2(centers), oct_db, 1)[0])  # 0 = pink noise
    lr_corr = float(np.corrcoef(st[0], st[1])[0, 1])

    # ---- Dynamics: spread of 3-second loudness across the track
    w = 3 * sr
    st_db = 20 * np.log10(np.array([np.sqrt(np.mean(y[i:i + w] ** 2)) for i in range(0, len(y) - w, w)]) + 1e-9)
    loud_range = float(np.percentile(st_db, 95) - np.percentile(st_db, 10))

    # ---- Swing: where the off-beat sixteenths land inside their eighth note
    ph = ((on - t0) / ibi) % 1
    a16 = ph[(ph > 0.6) & (ph < 0.95)]
    swing = float((np.median(a16) - 0.5) / 0.5) if len(a16) else float("nan")

    out = {
        "duration_s": round(dur, 2),
        "tempo_bpm": round(60 / ibi, 2),
        "beat_s": round(float(ibi), 7),
        "loop_start_s": round(loop_start, 4),
        "loop_beats": LOOP_BEATS,
        "loop_s": round(float(loop_len), 3),
        "passes": n_loops,
        "tuning_cents": round(float(tuning) * 100, 1),
        "key_candidates": [{"key": k, "r": round(r, 3)} for r, k in keys[:3]],
        "pass_similarity_min": round(min(sim), 3),
        "bass_line": bass_line,
        "upper_top": upper_top,
        "piano_rolloff95_hz": int(roll95),
        "tilt_db_per_octave_vs_pink": round(tilt, 2),
        "lr_correlation": round(lr_corr, 3),
        "loudness_range_db": round(loud_range, 1),
        "swing_percent_of_eighth": round(swing * 100, 1),
        "per_pass": [{"start_s": round(loop_start + k * loop_len, 2),
                      "bright_1500_4000_db": round(float(r[0]), 1),
                      "low_40_150_db": round(float(r[1]), 1),
                      "total_db": round(float(r[2]), 1)} for k, r in enumerate(rows)],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))

    print(f"Tempo          {out['tempo_bpm']} BPM (beat = {ibi * 1000:.1f} ms)")
    print(f"Loop           {LOOP_BEATS} beats = {loop_len:.2f} s, starts at {loop_start:.3f} s, {n_loops} passes")
    print(f"Pass match     every pass ≥ {min(sim) * 100:.0f}% similar to the average pass")
    print(f"Tuning         {out['tuning_cents']:+.0f} cents from A440")
    print(f"Key            " + ", ".join(f"{k['key']} ({k['r']})" for k in out['key_candidates']))
    print(f"Bass line      {' '.join(bass_line)}")
    print(f"Upper voice    {' '.join(upper_top)}")
    print(f"Piano layer    95% of energy below {roll95 / 1000:.1f} kHz")
    print(f"Tilt           {tilt:+.1f} dB/octave relative to pink noise")
    print(f"Stereo         L/R correlation {lr_corr:.2f}")
    print(f"Loudness range {loud_range:.1f} dB (3 s windows, 10th–95th percentile)")
    print(f"Swing          off-beat 16ths at {swing * 100:.0f}% of the eighth (50 straight, 66.7 triplet)")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
