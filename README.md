# rekordbox-track-id for OBS
Because of a lack of any API from rekordbox, this project reads the track info from rekordbox using 
computer vision assuming that rekordbox is using the default theme and the 2 deck horizontal layout in 
performance mode.

It writes this info into text files that can be easily read by OBS Studio these files should be located
in the rekordbox-track-id folder located in same folder as the executable.

## Running
This requires you to pip install pytesseract, win32gui, win32ui, OpenCV, and pillow (gonna clean these up eventually)

This also only works on Windows due to using win32gui to get the screenshots, not sure if this is possible on macOS nor do I have a mac to test

After installing those packages, it's as simple as
``python3 main.py``

I will also try to make a standalone executable that can just be run without installing all of this.

## Debugging
If you want to submit a bug to me make sure to include the files prefixed with "debug" in your rekordbox-track-id folder.

I can't guarantee any amount of support for this, I will make this work for me and a friend for what we need and for how long we need it.