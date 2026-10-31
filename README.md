# Luv(sic) Pt. 3 Dissected

An interactive, beat-by-beat look at the piano loop in Nujabes' "Luv(sic) Part 3" (instrumental) and why it sounds nostalgic.

Open `index.html` in a browser, or serve this directory with any static web server. There is no build step. Keep the `audio/` directory alongside `index.html` when publishing.

For timeline seeking over HTTP, use a host that supports byte-range requests for media files.

## What's on the page

- **A loop player.** A 16-beat diagram shows the chords, the held D♭ in the upper voice, and the bass line, with a playhead that moves in time.
  - **Synth mode** plays the chord changes with simple generated voicings. You can switch the sus4 chords, the Gø7 walk-down, and a muffle filter on and off to hear what each one does.
  - **Instrumental mode:** press **Play instrumental** to listen to the bundled 6:14 recording while the diagram follows the measured beat grid. Click a brightness bar to jump to that pass. Playback uses the browser's native audio player; no upload or browser storage setup is needed.
- **The write-up:**
  - The loop structure
  - The appoggiatura (a D♭ held for ten beats that resolves to C for one beat)
  - The vi–ii–V–I harmony and the half-diminished chord
  - The filter that muffles and clears the piano
  - The "old record" tone: detuning, darkness and narrow stereo
  - The swing
  - Where the sample comes from

## Measuring it yourself

`analysis/analyze_loop.py` produces the numbers the page uses: the beat grid, the per-pass filter levels, tuning, key, tone, stereo width, loudness range and swing.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # ffmpeg is also needed to decode webm/mp3
python analysis/analyze_loop.py path/to/your/track.webm
```

The script writes `data/analysis.json`. The page has those values built in as `T0`, `IBI` and `LD`, so the measurements do not need to be fetched at runtime.

| Measure | Result |
| --- | --- |
| Tempo | 95.0 BPM, steady |
| Loop | 16 beats (10.11 s), 37 passes |
| Tuning | −17 cents from A440 |
| Key | A♭ major / F minor |
| Bass line | F F F F · B♭ B♭ B♭ B♭ · E♭ E♭ E♭ E♭ · A♭ A♭ A♭ G |
| Piano layer | 95% of energy below 2.2 kHz |
| Spectral tilt | −3.3 dB/octave vs pink noise |
| Stereo | L/R correlation 0.89 |
| Loudness range | 2.6 dB |
| Swing | off-beat sixteenths at ~69% of the eighth |

Chord and pitch readings from mixed audio are estimates. They match published transcriptions (Hooktheory, Chordify).

## Bundled audio

The supplied instrumental is included at `audio/luvsic-pt3-instrumental.webm`. The page loads its metadata and starts playback when a visitor presses play. Use a browser that supports WebM audio, such as Chrome. The recording belongs to its rights holders. The [official upload is also on YouTube](https://www.youtube.com/watch?v=NhG4cQATy6c).

Other audio exports remain ignored by Git; `.gitignore` explicitly includes this bundled file.

## Sources

- [Luv(sic) Hexalogy, Wikipedia](https://en.wikipedia.org/wiki/Luv(Sic)_Hexalogy)
- [Luv sic pt 3 chord analysis, Hooktheory](https://www.hooktheory.com/theorytab/view/nujabes/luv-sic-pt-3)
- [The ballad of the tearful: why some songs make you cry, NPR](https://www.npr.org/2012/02/13/146818461/the-ballad-of-the-tearful-why-some-songs-make-you-cry)
- [When the pulse of the song goes on: fade-out in popular music, *Psychology of Music*](https://metatoc.com/papers/27043-when-the-pulse-of-the-song-goes-on-fade-out-in-popular-music-and-the-pulse-continuity-phenomenon)
- [Your beat plus my melody: Shing02 honors Nujabes, KEXP](https://kexp.org/read/2018/3/7/your-beat-plus-my-melody-shing02-honors-legendary-producer-and-friend-nujabes-tribute-performances)

An independent listening analysis made with Claude. Not affiliated with Nujabes, Shing02 or Hydeout Productions.
