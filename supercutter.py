#!/usr/bin/env python3

import argparse
from collections import namedtuple, Counter
import datetime
# import itertools as it
import json
import pickle
import os
import subprocess
import sys
from typing import Any, Dict, Iterator, List, TextIO, Tuple
import webvtt


# a format string to tell youtube-dl how to save files.
YOUTUBE_DL_FILE_FMT = "%(id)s=%(title)s.%(ext)s"


# represents an occurence of a keyword in a video.
# word: string
# start, end: time in float seconds
Keyword = namedtuple("Keyword", "word start end")


# represents one video and all the occurrences of keywords within.
# id: youtube integer id
# vttpath: location of .vtt format subtitle file
# vidpath: location of video file
# fps: video fps
# hits: list of Keyword objects
Video = namedtuple("Video", "id vttpath vidpath fps hits")


# url should be youtube channel, playlist, etc.
# anything youtube-dl understands should work.
# downloads subtitles file for every video.
# TODO: user can input limit on number of files.
# TODO: detect when both auto-gen and real subtitles exist, and prefer real.
def download_subtitles(url: str, path: str, number: int) -> None:
	os.makedirs(path, exist_ok=True)
	args = [
		"--skip-download",
		"--write-sub",
		"--write-auto-sub",
		"--restrict-filename", # generate ascii filenames with no spaces
		"-o", os.path.join(path, YOUTUBE_DL_FILE_FMT),
	]
	if number > 0:
		print(f"limiting to {number} videos")
		args += ["--max-downloads", str(number)]
	subprocess.run(["youtube-dl"] + args + [url])


# searches a single subtitle file for keywords.
def find_keywords(vttfile: str, keywords: List[str]) -> Iterator[Keyword]:
	prevline = ""
	for caption in webvtt.read(vttfile):
		lines = caption.text.strip().lower().split("\n")
		for line in lines:
			# when a second line is appended to the subtitle,
			# it's encoded as a second caption containing the first line repeated
			if line == prevline:
				continue
			prevline = line
			for word in keywords:
				if word in line:
					# TODO analyze audio to get tighter bound on this word
					yield Keyword(word=word, start=caption._start, end=caption._end)


# searches all the videos in the result directory for keywords.
def find_all_keywords(directory: str, keywords: List[str]) -> List[Video]:
	result = []
	for entry in os.scandir(directory):
		video_id = entry.name.split("=")[0]
		hits = list(find_keywords(entry.path, keywords))
		if hits:
			vidpath = ""
			fps = 0.0
			result.append(Video(video_id, entry.path, vidpath, fps, hits))
	return result


# downloads only those videos in which keywords were found in the subtitle file.
# returns updated Videos with vidpath set.
def download_keyword_videos(result: List[Video], directory: str) -> List[Video]:
	args = [
		"-o", os.path.join(directory, YOUTUBE_DL_FILE_FMT),
		"--restrict-filename",
		"--print-json",
		"--sleep-interval", "10",  # avoid suspicion
		"--max-sleep-interval", "100",
		"-f", "best[height<=720][fps<=?30]",  # reduce bandwidth
	]
	# we could spawn a bunch of threads, but let's not be too obvious
	updated = []
	for video in result:
		print("downloading:", video.vttpath)
		p = subprocess.run(["youtube-dl"] + args + [video.id],
			capture_output=True
		)
		info = json.loads(p.stdout)
		path = info["_filename"]
		new_video = video._replace(vidpath=path)
		updated.append(new_video)
		print("complete.")
	return updated


# shells out to ffprobe utility (from ffmpeg) to read video FPS from file.
def read_fps(vidpath: str) -> float:
	# based on: https://askubuntu.com/a/723362
	out = subprocess.check_output(["ffprobe", vidpath,
		"-v", "0", "-select_streams", "v",
		"-print_format", "flat", "-show_entries","stream=r_frame_rate"],
		encoding="utf8")
	rate = out.split('"')[1].split("/")
	if len(rate) == 1:
		return float(rate[0])
	if len(rate) == 2:
		return float(rate[0]) / float(rate[1])
	return -1.0


# read the FPS of all the downloaded videos, return updated result.
def read_result_fps(result: List[Video]) -> List[Video]:
	updated = []
	for video in result:
		fps = read_fps(video.vidpath)
		assert fps > 20
		updated.append(video._replace(fps=fps))
	return updated


# convert floating point number of seconds into H:M:S:frame timecode
def timecode(secs: float, fps: float) -> str:
	hms = datetime.timedelta(seconds=int(secs))
	frame = int((secs % 1) * fps)
	return f"{hms}:{frame:02}"


# write the edit list for the supercut based on the keyword times.
# the .edl format can be consumed by Premiere, etc.
def write_edl(result: List[Video], title: str, f: TextIO) -> None:
	# header
	f.write(f"TITLE: {title}\n")
	f.write("FCM: DROP FRAME\n")
	f.write("\n")

	counter = 1
	edit_time = 0.0
	for video in result:
		_, path = os.path.split(video.vidpath)
		for hit in video.hits:
			assert counter < 1000, "EDL format only supports 999 edits"
			dt = hit.end - hit.start
			codes = " ".join(timecode(t, video.fps) for t in
				(hit.start, hit.end, edit_time, edit_time + dt))
			lines = (
				f"{counter:03}  AX       AA/V  C        {codes}\n"
				f"* FROM CLIP NAME: {path}\n")
			f.write(lines)
			edit_time += dt
			counter += 1


def url2dir(url: str) -> str:
	domains = ["youtube.com", "youtu.be"]
	for d in domains:
		if d in url:
			_, after = url.split(d + "/")
			return after.replace("/", "_")
	domains_str = ", ".join(domains)
	raise ValueError(f"url domain not in [{domains_str}]")


def main():
	parser = argparse.ArgumentParser(
		description='tool for automatic construction of "supercut" videos')
	parser.add_argument("url", type=str,
		help="url of a youtube channel, playlist, single video, etc.")
	parser.add_argument("keywords", type=str, nargs="+",
		help="keywords to include in the supercut")
	parser.add_argument("--output", type=str, default="./",
		help="directory to store results in")
	parser.add_argument("--number", type=int, default=0,
		help="limit the number of videos scraped")
	args = parser.parse_args()
	keywords = list(set(kw.lower() for kw in args.keywords))

	result_dir = os.path.join(args.output, url2dir(args.url))
	pickle_path = os.path.join(result_dir, "keyword_scan.pickle")
	edl_path = os.path.join(result_dir, "supercut.edl")
	subtitle_dir = os.path.join(result_dir, "subtitles")
	video_dir = os.path.join(result_dir, "videos")

	print(f"downloading subtitle files from {args.url}...")
	download_subtitles(args.url, subtitle_dir, args.number)

	print("searching subtitle files for the keywords:")
	print(", ".join(keywords))
	result = find_all_keywords(subtitle_dir, keywords)
	with open(pickle_path, "wb") as f:
		pickle.dump(result, f)
	print("subtitle scan complete.")

	print("downloading videos with keyword hits.")
	with open(pickle_path, "rb") as f:
		result = pickle.load(f)
	result = download_keyword_videos(result, video_dir)
	result = read_result_fps(result)
	with open(pickle_path, "wb") as f:
		pickle.dump(result, f)

	print("generating edit description list (.edl) file.")
	with open(pickle_path, "rb") as f:
		result = pickle.load(f)
	with open(edl_path, "w") as f:
		write_edl(result, "Supercut", f)
	fps_count = Counter(vid.fps for vid in result)
	for fps, count in fps_count.most_common():
		print(f"{fps:.2f} frames per second: {count} videos")


if __name__ == "__main__":
	main()
