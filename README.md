# supercutter
Tool to construct "supercut" video edits (e.g. every time [Tabasko Sweet](https://www.youtube.com/playlist?list=PLi_iu5SegOb2kvX550TRTkJopEFE1eBs4) says "family") by scraping Youtube.

1. You specify a channel, playlist, etc., and a list of keywords.
2. `supercutter` splices together every time a keyword appears in your videos.
3. The output is an .EDL file that can be imported in your preferred video editor for fine-tuning.

Rather than analyzing audio, `supercutter` downloads subtitle files from Youtube.
When videos do not have manually written subtitles, Youtube auto-generates them with speech-to-text algorithms.
These subtitles usually do a good job recognizing words, but they are not precisely localized in time.
However, this is not a big deal, because you will want to manually fine-tune the results anyway for perfect humorous timing.

`supercutter` generates an .EDL file: a simple, old, text format that should be importable by almost any video editor.

`supercutter` depends heavily on [`youtube-dl`](https://rg3.github.io/youtube-dl/) to parse Youtube's web pages and extract the video and subtitle files.
Thanks to the `youtube-dl` developers for their awesome work!

`supercutter` requires at least Python 3.6.

## Installing dependencies

* [Install `youtube-dl`.](https://github.com/rg3/youtube-dl/blob/master/README.md#installation)
* [Install `ffmpeg`](https://ffmpeg.org/download.html) to get the `ffprobe` utility used to read frames-per-second values from video files.
* [Install `webvtt-py`](https://webvtt-py.readthedocs.io/en/latest/quickstart.html#installation) for parsing subtitle files.

## Running the script

    usage: supercutter.py [-h] [--output OUTPUT] [--number NUMBER]
                          url keywords [keywords ...]

    positional arguments:
      url              url of a youtube channel, playlist, single video, etc.
      keywords         keywords to include in the supercut

    optional arguments:
      -h, --help       show this help message and exit
      --output OUTPUT  directory to store results in
      --number NUMBER  limit the number of videos scraped

## Loading the EDL output in Adobe Premiere

*note: these steps are only tested in Premiere Pro CC 10.4.*

* Create a new project.
* File > Import `supercut.edl`.
* Premiere will ask "What video standard does this EDL use"? `supercutter` has printed the frames-per-second of the videos you downloaded. Make your choice based on this list.
* Premiere asks you to pick a Sequence Preset. Currently, `supercutter` limits download resolution to 720p, so choose 720p resolution.
* The loaded `.edl` will appear as a folder called "supercut" in your project, but all the links to the video files will be broken.
* Double-click on the "supercut" folder. Shift-select **all** of the missing clips.
* Right-click on one selected clip and choose "Link Media..."
* Make sure the "Relink others automatically" box is checked.
* Click the "Locate" button.
* Find the location of that clip inside the `/videos` subdirectory of the `supercutter` output directory.
* All the other clips should be found automatically.
* You should now be able to drop the Supercut sequence into the timeline and see your results.
* Since `supercutter` only makes edits based on the subtitle file (instead of actually analyzing the audio), the supercut will need a lot of fine-tuning.
* The Ripple Edit tool is particularly useful.
* **If anyone knows how to fix the EDL so the links aren't broken upon import, please open an issue or pull request!**
